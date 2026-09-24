"""Wait for a matching alert relay delivery event after Pub/Sub publication."""

import argparse
import json
import subprocess
import time


def delivered(entries: list[dict], incident_id: str, revision: str) -> bool:
    for entry in entries:
        if entry.get("resource", {}).get("labels", {}).get("revision_name") != revision:
            continue
        line = entry.get("textPayload", "")
        try:
            event = json.loads(line.removeprefix("INFO:     "))
        except (json.JSONDecodeError, AttributeError):
            continue
        if (
            event.get("event") == "discord_delivery_succeeded"
            and event.get("incident_id") == incident_id
            and 200 <= event.get("discord_status", 0) < 300
        ):
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incident_id")
    parser.add_argument("revision")
    parser.add_argument("project")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout
    query = (
        'resource.type="cloud_run_revision" '
        'AND resource.labels.service_name="builder-cup-alert-relay" '
        f'AND resource.labels.revision_name="{args.revision}" '
        'AND textPayload:"discord_delivery_succeeded"'
    )
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "gcloud",
                "logging",
                "read",
                query,
                f"--project={args.project}",
                "--limit=30",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        if delivered(json.loads(result.stdout), args.incident_id, args.revision):
            print(f"Discord delivery confirmed for {args.incident_id} on {args.revision}")
            return
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise SystemExit(
        f"Discord delivery not confirmed for {args.incident_id} within {args.timeout}s"
    )


if __name__ == "__main__":
    main()
