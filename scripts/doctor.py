"""Read-only development probes. No DB writes, model loading or dependency startup."""

import hashlib
import os
import platform
import subprocess
import tomllib
from pathlib import Path

import httpx

PROBE_TIMEOUT_SECONDS = 3
LOCAL_MODEL = "gemma4:e4b"
OLLAMA_URL = "http://host.docker.internal:11434"


def get_json(client: httpx.Client, url: str) -> tuple[int | None, object]:
    try:
        response = client.get(url)
        return response.status_code, response.json()
    except (httpx.RequestError, ValueError):
        return None, None


def check_services(client: httpx.Client) -> bool:
    ready = True
    for name, url in (
        ("API", "http://api:8000/api/health"),
        ("Web and API proxy", "http://web:5173/api/health"),
    ):
        status, data = get_json(client, url)
        ok = status == 200 and isinstance(data, dict) and data.get("status") == "ok"
        ok = ok and data.get("provider") == "mock"
        ready = ready and ok
        print(
            f"{'PASS' if ok else 'FAIL'} {name}: {'Mock reachable' if ok else 'not ready as Mock'}"
        )
    status, data = get_json(client, "http://api:8000/api/lab/runs?limit=1")
    db_ok = status == 200 and isinstance(data, list)
    print(f"{'PASS' if db_ok else 'FAIL'} DB history read: {'ready' if db_ok else 'unavailable'}")
    if not ready or not db_ok:
        print("Next: docker compose up -d --wait; docker compose ps -a; inspect db-init/API logs")
    return ready and db_ok


def check_ollama(client: httpx.Client) -> None:
    status, version = get_json(client, f"{OLLAMA_URL}/api/version")
    if (
        status != 200
        or not isinstance(version, dict)
        or not isinstance(version.get("version"), str)
    ):
        print(
            "OPTIONAL Ollama server: unreachable or invalid response; "
            "Mock development is unaffected"
        )
        print("Next on Mac: command -v ollama; see docs/개발환경/개발-명령어.md")
        return
    print("PASS Optional Ollama server: reachable from Docker")
    status, data = get_json(client, f"{OLLAMA_URL}/api/tags")
    if status != 200 or not isinstance(data, dict) or not isinstance(data.get("models"), list):
        print("OPTIONAL Ollama model inventory: unavailable or invalid response")
        return
    installed = any(
        isinstance(model, dict) and model.get("name") == LOCAL_MODEL for model in data["models"]
    )
    print(
        f"{'PASS' if installed else 'OPTIONAL'} Local model {LOCAL_MODEL}: "
        f"{'installed' if installed else 'not installed'}"
    )
    if not installed:
        print(f"Next for optional inference: ollama pull {LOCAL_MODEL}")
    print("NOT TESTED Inference and answer quality; explicitly run ollama-check when wanted")


def main() -> int:
    root = Path("/checkout")
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text())["project"]["name"]
        digest = hashlib.sha256((root / "compose.yaml").read_bytes()).hexdigest()[:12]
    except (OSError, ValueError, KeyError):
        print("FAIL Checkout files: run from repo root; see docs/개발환경/macOS-설치-진단.md")
        return 1
    if project != "builder-cup":
        print("FAIL Checkout: unexpected Python project")
        return 1
    print(f"Project: {os.environ.get('COMPOSE_PROJECT_NAME', 'unknown')}; Compose SHA256: {digest}")
    print("Host path/branch/ports: see docs/개발환경/macOS-설치-진단.md")
    node = subprocess.run(
        ["node", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    python = platform.python_version()
    tools_ok = node == "v24.21.0" and python.startswith("3.12.")
    print(f"{'PASS' if tools_ok else 'FAIL'} Container toolchain: Node {node}, Python {python}")
    with httpx.Client(timeout=PROBE_TIMEOUT_SECONDS, trust_env=False) as client:
        ready = check_services(client)
        check_ollama(client)
    print(
        "Read-only probes finished. "
        "No service startup, DB writes, model pull or inference requested."
    )
    return 0 if ready and tools_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
