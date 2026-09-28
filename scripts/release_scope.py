"""Classify changed files between two release commits."""

import subprocess
import sys

ZERO_SHA = "0" * 40
APP_FILES = {
    "scripts/container-smoke.sh",
}
RELAY_FILES = {
    "scripts/deploy-alert-relay.sh",
    "scripts/verify_alert_delivery.py",
}
SHARED_FILES = {
    ".dockerignore",
    "scripts/release_summary.py",
    "scripts/release_recovery.py",
    "scripts/rollback-gcp.sh",
}
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


REDEPLOY_MESSAGES = {
    "ops: 메인 서비스 재배포": (True, False),
    "ops: 알림 중계기 재배포": (False, True),
    "ops: 전체 서비스 재배포": (True, True),
}


def classify(paths: set[str] | None, subject: str = "") -> dict[str, bool]:
    if paths is None:
        return {"full": True, "infra": True, "app": True, "relay": True}

    app = relay = full = infra = False
    for path in paths:
        if path in SHARED_FILES:
            app = relay = full = True
        elif path in APP_FILES or path.startswith(("apps/trend-api/", "apps/trend-web/")):
            app = full = True
        elif path in RELAY_FILES or path.startswith("apps/alert-relay/"):
            relay = full = True
        elif path.startswith("infra/gcp/"):
            infra = True
        elif path in VALIDATION_FILES or path.startswith("tests/"):
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
    redeploy_app, redeploy_relay = REDEPLOY_MESSAGES.get(subject, (False, False))
    app = app or redeploy_app
    relay = relay or redeploy_relay
    full = full or app or relay
    return {"full": full, "infra": infra and not full, "app": app, "relay": relay}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: release_scope.py BEFORE_SHA AFTER_SHA")
    paths = changed_files(sys.argv[1], sys.argv[2])
    try:
        subject = git_bytes("show", "-s", "--format=%s", sys.argv[2]).decode().strip()
    except subprocess.CalledProcessError:
        paths = None
        subject = ""
    decision = classify(paths, subject)
    for key, value in decision.items():
        print(f"{key}={str(value).lower()}")


if __name__ == "__main__":
    main()
