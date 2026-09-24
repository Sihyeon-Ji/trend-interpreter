"""Classify changed files between two release commits."""

import subprocess
import sys

ZERO_SHA = "0" * 40
APP_FILES = {
    "Dockerfile",
    "deployment/model-controls.json",
    "pyproject.toml",
    "uv.lock",
    "scripts/deploy-gcp.sh",
}
RELAY_FILES = {
    "scripts/deploy-alert-relay.sh",
    "scripts/verify_alert_delivery.py",
}
SHARED_FILES = {".dockerignore"}
VALIDATION_FILES = {
    "Dockerfile.dev",
    "compose.yaml",
    ".github/workflows/ci.yml",
    ".github/workflows/release-gcp.yml",
}
RETIRED_WORKFLOWS = {
    ".github/workflows/deploy-gcp.yml",
    ".github/workflows/deploy-alert-relay.yml",
}


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def changed_files(before: str, after: str) -> set[str] | None:
    try:
        if before == ZERO_SHA:
            output = git_bytes("ls-tree", "-r", "--name-only", "-z", after)
        else:
            git_bytes("cat-file", "-e", f"{before}^{{commit}}")
            output = git_bytes("diff", "--name-only", "-z", before, after)
    except subprocess.CalledProcessError:
        return None
    return {path.decode("utf-8", errors="surrogateescape") for path in output.split(b"\0") if path}


def classify(paths: set[str] | None) -> dict[str, bool]:
    if paths is None:
        return {"full": True, "infra": True, "app": True, "relay": True}

    app = relay = full = infra = False
    for path in paths:
        if path in SHARED_FILES:
            app = relay = full = True
        elif path in APP_FILES or path.startswith(("apps/api/", "apps/web/")):
            app = full = True
        elif path in RELAY_FILES or path.startswith("apps/alert-relay/"):
            relay = full = True
        elif path.startswith("infra/gcp/"):
            infra = True
        elif path in VALIDATION_FILES or path.startswith(("tests/", "evaluation-cases/")):
            full = True
        elif path.startswith(("docs/", "prototype/")) or path in {
            "README.md",
            "README.kr.md",
            *RETIRED_WORKFLOWS,
        }:
            continue
        elif path.startswith(("scripts/", ".github/workflows/")):
            full = True
        else:
            full = True
    return {"full": full, "infra": infra and not full, "app": app, "relay": relay}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: release_scope.py BEFORE_SHA AFTER_SHA")
    decision = classify(changed_files(sys.argv[1], sys.argv[2]))
    for key, value in decision.items():
        print(f"{key}={str(value).lower()}")


if __name__ == "__main__":
    main()
