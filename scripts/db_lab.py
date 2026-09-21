"""Initialize the local lab or verify synthetic records through its API."""

import argparse
import os
from uuid import UUID, uuid4

import httpx
from builder_cup.config import Settings
from builder_cup.database import LAB_RECORD_LABEL, DatabaseUnavailable, LabRecord, initialize

LAB_API_URL = "http://api:8000"
REQUEST_TIMEOUT_SECONDS = 10


def read(client: httpx.Client, record_id: UUID) -> LabRecord:
    response = client.get(f"/api/lab/records/{record_id}")
    response.raise_for_status()
    return LabRecord.model_validate(response.json())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create the initial lab schema and restricted role")
    commands.add_parser("check", help="Create a synthetic record and verify it by ID")
    reader = commands.add_parser("read", help="Read an existing ID without inserting a new record")
    reader.add_argument("record_id", type=UUID)
    args = parser.parse_args()

    if args.command == "init":
        initialize(Settings())
        print("PASS: initial lab schema and application role ready")
        return

    with httpx.Client(base_url=LAB_API_URL, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        if args.command == "read":
            record = read(client, args.record_id)
            print(record.model_dump_json())
            print("PASS: existing record found")
            return

        response = client.post("/api/lab/records")
        response.raise_for_status()
        record = LabRecord.model_validate(response.json())
        if record.label != LAB_RECORD_LABEL or read(client, record.id) != record:
            raise RuntimeError("Stored record did not match the inserted record")
        if client.get(f"/api/lab/records/{uuid4()}").status_code != 404:
            raise RuntimeError("Missing record did not return HTTP 404")
        if client.get("/api/lab/records/not-a-uuid").status_code != 422:
            raise RuntimeError("Invalid record ID did not return HTTP 422")
        print(record.model_dump_json())
        print("PASS: insert, read, missing record and invalid ID")
        print(f"Read again: docker compose run --rm db-check read {record.id}")
        port = os.environ.get("DEV_API_PORT", "8000")
        print(f"Open: http://localhost:{port}/api/lab/records/{record.id}")


if __name__ == "__main__":
    try:
        main()
    except DatabaseUnavailable:
        raise SystemExit(
            "FAIL: database_unavailable; check db and db-init service status"
        ) from None
    except httpx.HTTPStatusError as exc:
        raise SystemExit(f"FAIL: API returned HTTP {exc.response.status_code}") from None
    except httpx.RequestError:
        raise SystemExit("FAIL: API connection failed") from None
