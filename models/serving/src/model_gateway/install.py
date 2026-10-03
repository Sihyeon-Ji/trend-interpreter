"""Install a hash-pinned approved release on a prepared GPU boot image."""

import base64
import fcntl
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from model_gateway.engine import chat_request

MODEL_ROOT = Path("/var/lib/trend/models")
RUNTIME = Path("/run/trend-gateway")
DEVICE = "/dev/disk/by-id/google-trend-models"
MAX_METADATA = 1024 * 1024
OLLAMA = "http://127.0.0.1:11434"
# Loading the weights from the model disk onto the GPU takes longer than the gateway's request
# deadline, and the first prompt of realistic length pays a further one-time cost. Both happen
# here, before the gateway starts.
WARM_DEADLINE = 600
WARM_PROMPTS = (
    ("Reply with OK.", 1),
    (
        "You check a slang dictionary entry against its evidence. "
        + "Entry: a short internet expression, its meaning, origin and nuance. " * 40
        + 'Answer only with JSON {"verdict": "ok"} or {"verdict": "fix"}.',
        8,
    ),
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused")


def request(url, headers, data=None, timeout=30):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    return opener.open(Request(url, data=data, headers=headers), timeout=timeout)


def metadata(path):
    with request(
        "http://metadata.google.internal/computeMetadata/v1/" + path, {"Metadata-Flavor": "Google"}
    ) as response:
        if response.headers.get("Metadata-Flavor") != "Google":
            raise ValueError("Invalid metadata response")
        raw = response.read(MAX_METADATA + 1)
        if len(raw) > MAX_METADATA:
            raise ValueError("Metadata limit")
        return json.loads(raw)


def object_url(uri, generation, bucket, prefix):
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "gs"
        or parsed.netloc != bucket
        or parsed.query
        or parsed.fragment
        or not parsed.path.removeprefix("/").startswith(prefix)
        or not re.fullmatch(r"[1-9][0-9]*", str(generation))
    ):
        raise ValueError("Object is outside approved scope")
    name = quote(parsed.path.removeprefix("/"), safe="")
    return f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{name}?alt=media&generation={generation}"


def validate_release(release, bucket, prefix):
    if (
        release.get("schema_version") != 1
        or release.get("approved") is not True
        or not release.get("approved_by")
        or not release.get("approved_at")
        or datetime.fromisoformat(release["approved_at"]).tzinfo is None
        or not re.fullmatch(r"[a-f0-9]{64}", release.get("evaluation_sha256", ""))
    ):
        raise ValueError("Independent release approval required")
    for key in ("ollama_image", "gateway_image"):
        if not re.fullmatch(r"[a-z0-9./_-]+@sha256:[a-f0-9]{64}", release.get(key, "")):
            raise ValueError("Pin container image digest")
    if (
        not re.fullmatch(r"[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+", release.get("model", ""))
        or not re.fullmatch(r"[a-f0-9]{64}", release.get("model_digest", ""))
        or set(release.get("files", {})) != {"model.gguf", "Modelfile"}
    ):
        raise ValueError("Invalid model release")
    for name, item in release["files"].items():
        object_url(item["uri"], item["generation"], bucket, prefix)
        maximum = 100 * 1024**3 if name == "model.gguf" else 64 * 1024
        if (
            type(item.get("size")) is not int
            or not 0 < item["size"] <= maximum
            or not re.fullmatch(r"[a-f0-9]{64}", item.get("sha256", ""))
        ):
            raise ValueError("Invalid model artifact")
    return release


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def download(item, destination, token, bucket, prefix, fetch=request):
    url = object_url(item["uri"], item["generation"], bucket, prefix)
    if destination.exists():
        if destination.stat().st_size != item["size"] or digest(destination) != item["sha256"]:
            raise ValueError("Existing artifact checksum mismatch")
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as target:
            temporary = Path(target.name)
            size = 0
            sha = hashlib.sha256()
            with fetch(url, {"Authorization": "Bearer " + token}) as response:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > item["size"]:
                        raise ValueError("Download limit")
                    sha.update(chunk)
                    target.write(chunk)
            if size != item["size"] or sha.hexdigest() != item["sha256"]:
                raise ValueError("Download checksum mismatch")
            os.fsync(target.fileno())
        temporary.chmod(0o644)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def command(args, *, input=None, capture=False):
    result = subprocess.run(
        args,
        input=input,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=1800,
    )
    if result.returncode:
        raise RuntimeError("Runtime command failed")
    return result.stdout.decode().strip() if capture else None


def mount_models(allow_format=False):
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    if subprocess.run(["mountpoint", "-q", str(MODEL_ROOT)], check=False).returncode == 0:
        source = command(
            ["findmnt", "-n", "-o", "SOURCE", "--target", str(MODEL_ROOT)], capture=True
        )
        if Path(source).resolve() != Path(DEVICE).resolve():
            raise ValueError("Unexpected model mount")
        return
    result = subprocess.run(
        ["blkid", "-s", "TYPE", "-o", "value", DEVICE],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode == 2:
        if allow_format is not True:
            raise ValueError("Explicit empty-disk initialization required")
        signatures = json.loads(command(["wipefs", "--no-act", "--json", DEVICE], capture=True))
        if signatures.get("signatures"):
            raise ValueError("Refuse to format existing disk signatures")
        command(["mkfs.ext4", "-L", "trend-models", DEVICE])
    elif result.returncode != 0 or result.stdout.strip() != b"ext4":
        raise ValueError("Unsupported model filesystem")
    command(["mount", "-o", "nodev,nosuid", DEVICE, str(MODEL_ROOT)])


def secret(version, token):
    if not re.fullmatch(
        r"projects/[a-z0-9-]+/secrets/[A-Za-z0-9_-]+/versions/[1-9][0-9]*", version
    ):
        raise ValueError("Pin a numeric secret version")
    with request(
        "https://secretmanager.googleapis.com/v1/" + version + ":access",
        {"Authorization": "Bearer " + token},
    ) as response:
        raw = response.read(MAX_METADATA + 1)
        if len(raw) > MAX_METADATA:
            raise ValueError("Secret limit")
        data = json.loads(raw)["payload"]["data"]
        return base64.b64decode(data, validate=True)


def runtime_commands(release, assets):
    return [
        [
            "docker",
            "run",
            "-d",
            "--name",
            "trend-ollama",
            "--pull=never",
            "--network=host",
            "--gpus=all",
            "--log-driver=none",
            "-e",
            "OLLAMA_HOST=127.0.0.1:11434",
            "-e",
            "OLLAMA_NO_CLOUD=1",
            "-e",
            "OLLAMA_NUM_PARALLEL=1",
            "-e",
            "OLLAMA_MAX_LOADED_MODELS=1",
            "--mount",
            f"type=bind,src={assets},dst=/models,readonly",
            "--mount",
            f"type=bind,src={MODEL_ROOT / 'ollama'},dst=/root/.ollama",
            release["ollama_image"],
        ],
        [
            "docker",
            "exec",
            "trend-ollama",
            "ollama",
            "create",
            release["model"],
            "-f",
            "/models/Modelfile",
        ],
        [
            "docker",
            "run",
            "-d",
            "--name",
            "trend-gateway",
            "--pull=never",
            "--network=host",
            "--log-driver=none",
            "--env-file",
            str(RUNTIME / "gateway.env"),
            "--mount",
            f"type=bind,src={RUNTIME / 'locks'},dst=/run/trend-gateway",
            "--mount",
            f"type=bind,src={RUNTIME / 'tls'},dst=/run/tls,readonly",
            release["gateway_image"],
        ],
    ]


def wait_ollama():
    end = time.monotonic() + 30
    while time.monotonic() < end:
        try:
            with request(OLLAMA + "/api/version", {}) as response:
                if json.loads(response.read(4096)).get("version"):
                    return
        except (OSError, ValueError):
            time.sleep(0.2)
    raise RuntimeError("Ollama startup deadline")


def warm_model(model):
    for prompt, tokens in WARM_PROMPTS:
        body = json.dumps(chat_request(model, prompt, tokens)).encode()
        with request(
            OLLAMA + "/api/chat",
            {"Content-Type": "application/json"},
            data=body,
            timeout=WARM_DEADLINE,
        ) as response:
            result = json.loads(response.read(MAX_METADATA))
        if result.get("model") != model or result.get("done") is not True:
            raise RuntimeError("Model warm-up failed")


def start_runtime(release, assets):
    """Start Ollama, import and warm the model, then start the gateway; remove both on failure."""
    try:
        for index, args in enumerate(runtime_commands(release, assets)):
            command(args)
            if index == 0:
                wait_ollama()
            elif index == 1:
                warm_model(release["model"])
    except Exception:
        for name in ("trend-gateway", "trend-ollama"):
            subprocess.run(
                ["docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        raise RuntimeError("Runtime installation failed") from None


def install():
    config = metadata("instance/attributes/trend-runtime")
    token = metadata("instance/service-accounts/default/token")["access_token"]
    url = object_url(
        config["release_uri"],
        config["release_generation"],
        config["models_bucket"],
        config["models_prefix"],
    )
    with request(url, {"Authorization": "Bearer " + token}) as response:
        raw = response.read(MAX_METADATA + 1)
    if len(raw) > MAX_METADATA or hashlib.sha256(raw).hexdigest() != config["release_sha256"]:
        raise ValueError("Release checksum mismatch")
    release = validate_release(json.loads(raw), config["models_bucket"], config["models_prefix"])
    RUNTIME.mkdir(parents=True, exist_ok=True)
    RUNTIME.chmod(0o755)
    with (RUNTIME / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for name in ("trend-gateway", "trend-ollama"):
            existing = command(["docker", "ps", "-aq", "--filter", f"name=^/{name}$"], capture=True)
            if existing:
                state = command(
                    ["docker", "inspect", "--format", "{{.State.Running}}", name], capture=True
                )
                if state != "false":
                    raise ValueError("Drain running runtime before reinstalling")
                command(["docker", "rm", name])
        for key in ("ollama_image", "gateway_image"):
            command(["docker", "image", "inspect", release[key]])
        mount_models(config.get("format_model_disk") is True)
        assets = MODEL_ROOT / config["release_sha256"]
        assets.mkdir(exist_ok=True)
        required = sum(item["size"] for item in release["files"].values()) * 2 + 10 * 1024**3
        if shutil.disk_usage(MODEL_ROOT).free < required:
            raise ValueError("Insufficient model storage")
        for name, item in release["files"].items():
            download(item, assets / name, token, config["models_bucket"], config["models_prefix"])
        with (assets / "model.gguf").open("rb") as source:
            if source.read(4) != b"GGUF":
                raise ValueError("Invalid GGUF header")
        modelfile = (assets / "Modelfile").read_text()
        if not modelfile.startswith("FROM /models/model.gguf\n") or re.search(
            r"(?im)^\s*(FROM|ADAPTER)\s", modelfile.split("\n", 1)[1]
        ):
            raise ValueError("Only the pinned local GGUF may be imported")
        bearer = secret(config["token_secret_version"], token).decode()
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", bearer):
            raise ValueError("Invalid gateway credential")
        tls = json.loads(secret(config["tls_secret_version"], token))
        tls_dir = RUNTIME / "tls"
        tls_dir.mkdir(exist_ok=True)
        for name, value in (("cert.pem", tls["cert_pem"]), ("key.pem", tls["key_pem"])):
            path = tls_dir / name
            path.write_text(value)
            path.chmod(0o400)
            os.chown(path, 10001, 10001)
        ssl.create_default_context().load_cert_chain(
            str(tls_dir / "cert.pem"), str(tls_dir / "key.pem")
        )
        locks = RUNTIME / "locks"
        locks.mkdir(exist_ok=True)
        locks.chmod(0o755)
        os.chown(locks, 10001, 10001)
        env = RUNTIME / "gateway.env"
        env.touch(mode=0o600, exist_ok=True)
        env.chmod(0o600)
        env.write_text(
            f"GATEWAY_TOKEN={bearer}\nGATEWAY_MODEL={release['model']}\nGATEWAY_MODEL_DIGEST={release['model_digest']}\n"
        )
        (MODEL_ROOT / "ollama").mkdir(exist_ok=True)
        start_runtime(release, assets)


if __name__ == "__main__":
    try:
        install()
        print(json.dumps({"installed": True, "gpu_readiness": "not-verified"}))
    except Exception as error:
        print(json.dumps({"installed": False, "error_code": type(error).__name__}))
        raise SystemExit(1) from None
