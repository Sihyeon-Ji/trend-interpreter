"""Validate a Cloud Run revision before changing traffic and verify the result."""

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request

PROJECT_ID = "stunning-crane-508614-c1"
REGION = "asia-northeast1"
SECRETS = {
    "builder-cup-alert-relay": ("DISCORD_WEBHOOK_URL", "discord-webhook"),
    "trend-production-api": ("DATABASE_URL", "trend-production-database-url"),
    "trend-production-web": ("SESSION_SECRET", "trend-production-session-secret"),
}


class RecoveryError(Exception):
    pass


def command(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def cloud_json(*args: str) -> dict:
    return json.loads(command("gcloud", *args, "--format=json"))


def service_snapshot(service: str) -> dict:
    return cloud_json(
        "run", "services", "describe", service, f"--project={PROJECT_ID}", f"--region={REGION}"
    )


def serving_revision(snapshot: dict) -> str:
    traffic = [item for item in snapshot["status"].get("traffic", []) if item.get("percent") == 100]
    if len(traffic) != 1 or not traffic[0].get("revisionName"):
        raise RecoveryError("Expected exactly one revision serving 100% traffic")
    return traffic[0]["revisionName"]


def validate_revision(service: str, revision: dict) -> tuple[str, str]:
    if revision["metadata"].get("labels", {}).get("serving.knative.dev/service") != service:
        raise RecoveryError("Revision belongs to another service")
    if not any(
        item.get("type") == "Ready" and item.get("status") == "True"
        for item in revision["status"].get("conditions", [])
    ):
        raise RecoveryError("Revision is not Ready")
    container = revision["spec"]["containers"][0]
    image = container["image"]
    if "@sha256:" not in image:
        raise RecoveryError("Revision image is not pinned to a digest")
    variable, secret = SECRETS[service]
    matching = [entry for entry in container.get("env", []) if entry.get("name") == variable]
    if len(matching) != 1:
        raise RecoveryError("Required secret reference is missing")
    reference = matching[0].get("valueFrom", {}).get("secretKeyRef", {})
    version = reference.get("key", "")
    if reference.get("name") != secret or not isinstance(version, str) or not version.isdecimal():
        raise RecoveryError("Revision must reference a numbered secret version")
    return image, version


def validate_relay_iam(policy: dict) -> None:
    members = {
        member
        for binding in policy.get("bindings", [])
        if binding.get("role") == "roles/run.invoker"
        for member in binding.get("members", [])
    }
    expected = f"serviceAccount:builder-cup-alert-push@{PROJECT_ID}.iam.gserviceaccount.com"
    if {"allUsers", "allAuthenticatedUsers"} & members or expected not in members:
        raise RecoveryError("Relay invoker IAM is not private or Pub/Sub cannot invoke it")


def verify_trend(service: str, url: str) -> None:
    """Trend web serves its first page publicly; the private API needs an ID token and must hold data."""
    if service.endswith("-web"):
        with urllib.request.urlopen(f"{url}/", timeout=30) as response:
            if response.status != 200:
                raise RecoveryError("Web first page did not load")
        return
    token = os.getenv("HEALTH_ID_TOKEN") or command("gcloud", "auth", "print-identity-token")
    request = urllib.request.Request(f"{url}/health", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("ok") is not True or not data.get("terms"):
        raise RecoveryError("API health did not report a loaded dictionary")


def verify_http(service: str, url: str) -> None:
    if service.startswith("trend-"):
        verify_trend(service, url)
        return
    token = os.getenv("HEALTH_ID_TOKEN") or command("gcloud", "auth", "print-identity-token")
    request = urllib.request.Request(f"{url}/health", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    if data.get("status") != "ok":
        raise RecoveryError("Health response did not match the service contract")


def preflight(service: str, revision_name: str) -> tuple[str, str, str]:
    snapshot = service_snapshot(service)
    previous = serving_revision(snapshot)
    revision = cloud_json(
        "run",
        "revisions",
        "describe",
        revision_name,
        f"--project={PROJECT_ID}",
        f"--region={REGION}",
    )
    image, version = validate_revision(service, revision)
    secret = SECRETS[service][1]
    state = command(
        "gcloud",
        "secrets",
        "versions",
        "describe",
        version,
        f"--secret={secret}",
        f"--project={PROJECT_ID}",
        "--format=value(state)",
    )
    if state != "ENABLED":
        raise RecoveryError("Revision secret version is not enabled")
    if service == "builder-cup-alert-relay":
        policy = cloud_json(
            "run",
            "services",
            "get-iam-policy",
            service,
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
        )
        validate_relay_iam(policy)
    return previous, image, version


def recover(service: str, revision: str, apply: bool) -> None:
    previous, image, version = preflight(service, revision)
    print(
        f"Target {service}/{revision}, image {image}, secret version {version}; serving {previous}"
    )
    if not apply:
        if revision == previous:
            verify_http(service, service_snapshot(service)["status"]["url"])
            print("Current traffic and authenticated health verified")
        else:
            print("Target is not serving; HTTP validation requires --apply")
        return
    if revision == previous:
        verify_http(service, service_snapshot(service)["status"]["url"])
        print("Revision already serves 100%; health verified")
        return
    update = (
        "gcloud",
        "run",
        "services",
        "update-traffic",
        service,
        f"--project={PROJECT_ID}",
        f"--region={REGION}",
    )
    command(*update, f"--to-revisions={revision}=100", "--quiet")
    try:
        snapshot = service_snapshot(service)
        if serving_revision(snapshot) != revision:
            raise RecoveryError("Traffic did not move to the requested revision")
        verify_http(service, snapshot["status"]["url"])
    except Exception:
        command(*update, f"--to-revisions={previous}=100", "--quiet")
        raise
    print(f"Rollback verified: {service} now serves {revision}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=SECRETS)
    parser.add_argument("revision")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        recover(args.service, args.revision, args.apply)
    except RecoveryError as exc:
        raise SystemExit(f"Recovery check failed: {exc}") from exc
    except (subprocess.CalledProcessError, urllib.error.URLError, KeyError, ValueError) as exc:
        raise SystemExit(f"Recovery check failed: {type(exc).__name__}") from exc


if __name__ == "__main__":
    main()
