import copy
import hashlib
import io

import pytest

from model_gateway import install
from model_gateway.engine import CONTEXT_TOKENS


def artifact(name, content):
    return {
        "uri": "gs://approved-models/releases/" + name,
        "generation": "123",
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }


@pytest.fixture
def release():
    return {
        "schema_version": 1,
        "approved": True,
        "approved_by": "synthetic reviewer",
        "approved_at": "2026-10-03T12:00:00+09:00",
        "evaluation_sha256": "c" * 64,
        "model": "audit:approved",
        "model_digest": "a" * 64,
        "ollama_image": "ollama/ollama@sha256:" + "b" * 64,
        "gateway_image": "registry.example/gateway@sha256:" + "d" * 64,
        "files": {
            "model.gguf": artifact("model.gguf", b"GGUF synthetic"),
            "Modelfile": artifact("Modelfile", b"FROM /models/model.gguf\n"),
        },
    }


def test_release_requires_complete_pinned_approval(release):
    assert install.validate_release(release, "approved-models", "releases/") == release
    for field, value in [
        ("approved", False),
        ("approved_by", ""),
        ("evaluation_sha256", "unknown"),
        ("approved_at", "2026-10-03"),
        ("gateway_image", "image:latest"),
    ]:
        bad = copy.deepcopy(release)
        bad[field] = value
        with pytest.raises(ValueError):
            install.validate_release(bad, "approved-models", "releases/")


@pytest.mark.parametrize(
    "uri,generation",
    [
        ("gs://other/releases/file", "123"),
        ("gs://approved-models/private/file", "123"),
        ("gs://approved-models/releases/file#latest", "123"),
        ("gs://approved-models/releases/file", "latest"),
    ],
)
def test_objects_cannot_escape_scope_or_generation(uri, generation):
    with pytest.raises(ValueError):
        install.object_url(uri, generation, "approved-models", "releases/")


def test_generation_hash_and_cache_are_verified_before_install(tmp_path):
    content = b"GGUF synthetic"
    item = artifact("model.gguf", content)
    calls = []

    def fetch(url, headers):
        calls.append(url)
        assert url.endswith("generation=123")
        assert headers == {"Authorization": "Bearer synthetic"}
        return io.BytesIO(content)

    path = tmp_path / "model.gguf"
    install.download(item, path, "synthetic", "approved-models", "releases/", fetch)
    install.download(item, path, "synthetic", "approved-models", "releases/", fetch)
    assert len(calls) == 1
    path.write_bytes(b"changed")
    with pytest.raises(ValueError):
        install.download(item, path, "synthetic", "approved-models", "releases/", fetch)


@pytest.mark.parametrize("content", [b"corrupt", b"x" * 100])
def test_failed_download_leaves_no_importable_partial_file(tmp_path, content):
    item = artifact("model.gguf", b"GGUF synthetic")
    with pytest.raises(ValueError):
        install.download(
            item,
            tmp_path / "model.gguf",
            "synthetic",
            "approved-models",
            "releases/",
            lambda *_: io.BytesIO(content),
        )
    assert list(tmp_path.iterdir()) == []


def test_runtime_never_pulls_cloud_models_or_mounts_credentials_as_writable(release, tmp_path):
    commands = install.runtime_commands(release, tmp_path)
    assert "OLLAMA_NO_CLOUD=1" in commands[0]
    assert "OLLAMA_NUM_PARALLEL=1" in commands[0]
    assert "--pull=never" in commands[0] and "--pull=never" in commands[2]
    assert commands[1][2:5] == ["trend-ollama", "ollama", "create"]
    assert not any("GATEWAY_TOKEN=" in arg for cmd in commands for arg in cmd)
    assert any("tls,dst=/run/tls,readonly" in arg for arg in commands[2])
    assert any("locks,dst=/run/trend-gateway" in arg for arg in commands[2])


def test_unapproved_release_has_no_host_commands(monkeypatch, release):
    import json

    raw = json.dumps({**release, "approved": False}).encode()
    config = {
        "release_uri": "gs://approved-models/releases/release.json",
        "release_generation": "123",
        "release_sha256": hashlib.sha256(raw).hexdigest(),
        "models_bucket": "approved-models",
        "models_prefix": "releases/",
    }
    monkeypatch.setattr(
        install,
        "metadata",
        lambda key: (
            config if key.startswith("instance/attributes") else {"access_token": "synthetic"}
        ),
    )
    monkeypatch.setattr(install, "request", lambda *_: io.BytesIO(raw))
    monkeypatch.setattr(install, "command", lambda *_: pytest.fail("Unapproved host command"))
    with pytest.raises(ValueError):
        install.install()


def test_complete_install_keeps_secrets_out_of_commands(monkeypatch, tmp_path, release):
    import json

    model = b"GGUF synthetic"
    modelfile = b"FROM /models/model.gguf\n"
    raw = json.dumps(release).encode()
    config = {
        "release_uri": "gs://approved-models/releases/release.json",
        "release_generation": "123",
        "release_sha256": hashlib.sha256(raw).hexdigest(),
        "models_bucket": "approved-models",
        "models_prefix": "releases/",
        "token_secret_version": "projects/test-project/secrets/token/versions/1",
        "tls_secret_version": "projects/test-project/secrets/tls/versions/1",
    }
    root, runtime = tmp_path / "models", tmp_path / "runtime"
    root.mkdir()
    monkeypatch.setattr(install, "MODEL_ROOT", root)
    monkeypatch.setattr(install, "RUNTIME", runtime)
    monkeypatch.setattr(install, "mount_models", lambda _: None)
    monkeypatch.setattr(install, "wait_ollama", lambda: None)
    monkeypatch.setattr(
        install,
        "metadata",
        lambda key: (
            config if key.startswith("instance/attributes") else {"access_token": "synthetic"}
        ),
    )
    warmed = []

    def request(url, _, **kwargs):
        if url.endswith("/api/chat"):
            warmed.append((len(calls), json.loads(kwargs["data"])))
            return io.BytesIO(json.dumps({"model": release["model"], "done": True}).encode())
        return io.BytesIO(
            raw if "release.json" in url else modelfile if "Modelfile" in url else model
        )

    monkeypatch.setattr(install, "request", request)
    # download's default function was bound at definition time.
    original = install.download
    monkeypatch.setattr(install, "download", lambda *args: original(*args, fetch=install.request))
    token = "synthetic-token-" + "x" * 32
    monkeypatch.setattr(
        install,
        "secret",
        lambda path, _: (
            token.encode()
            if "/token/" in path
            else json.dumps(
                {"cert_pem": "test certificate", "key_pem": "test private key"}
            ).encode()
        ),
    )

    class Context:
        def load_cert_chain(self, cert, key):
            assert install.Path(cert).read_text() == "test certificate"
            assert install.Path(key).read_text() == "test private key"

    monkeypatch.setattr(install.ssl, "create_default_context", lambda: Context())
    monkeypatch.setattr(install.os, "chown", lambda *_: None)
    calls = []

    def command(args, **kwargs):
        calls.append(args)
        return "" if kwargs.get("capture") else None

    monkeypatch.setattr(install, "command", command)
    install.install()
    assert (root / config["release_sha256"] / "model.gguf").read_bytes() == model
    assert (runtime / "gateway.env").stat().st_mode & 0o777 == 0o600
    assert (runtime / "tls/key.pem").stat().st_mode & 0o777 == 0o400
    assert (runtime / "locks").exists()
    assert not any(token in str(args) or "test private key" in str(args) for args in calls)
    assert any(args[:2] == ["docker", "exec"] for args in calls)
    gateway_start = next(
        i for i, args in enumerate(calls) if "trend-gateway" in args and "run" in args
    )
    assert len(warmed) == len(install.WARM_PROMPTS)
    assert all(position <= gateway_start for position, _ in warmed)
    assert {body["options"]["num_ctx"] for _, body in warmed} == {CONTEXT_TOKENS}
    assert all(body["keep_alive"] == -1 and body["model"] == release["model"] for _, body in warmed)


def test_failed_warm_up_never_starts_the_gateway(monkeypatch, tmp_path, release):
    calls, removed = [], []

    def cold(_):
        raise TimeoutError("cold start")

    monkeypatch.setattr(install, "command", lambda args, **_: calls.append(args))
    monkeypatch.setattr(install, "wait_ollama", lambda: None)
    monkeypatch.setattr(install, "warm_model", cold)
    monkeypatch.setattr(install.subprocess, "run", lambda args, **_: removed.append(args))
    with pytest.raises(RuntimeError):
        install.start_runtime(release, tmp_path)
    assert not any("trend-gateway" in args and "run" in args for args in calls)
    assert removed == [
        ["docker", "rm", "-f", "trend-gateway"],
        ["docker", "rm", "-f", "trend-ollama"],
    ]


@pytest.mark.parametrize("approved", [False, True])
def test_mount_never_formats_unapproved_or_existing_signatures(monkeypatch, tmp_path, approved):
    import json
    import subprocess

    monkeypatch.setattr(install, "MODEL_ROOT", tmp_path / "models")

    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 1 if args[0] == "mountpoint" else 2, stdout=b"")

    monkeypatch.setattr(install.subprocess, "run", run)
    calls = []

    def command(args, **kwargs):
        calls.append(args)
        assert args[0] not in {"mkfs.ext4", "mount"}
        return json.dumps({"signatures": [{"type": "unknown-data"}]})

    monkeypatch.setattr(install, "command", command)
    with pytest.raises(ValueError):
        install.mount_models(approved)
    if not approved:
        assert not calls
