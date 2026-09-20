"""Verify persisted workflow metadata using the real API and PostgreSQL."""

import argparse
import json
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from builder_cup.history import RunDetail

API_URL = "http://api:8000"
REQUEST_TIMEOUT_SECONDS = 15


def read(client: httpx.Client, run_id: str) -> RunDetail:
    response = client.get(f"/api/lab/runs/{run_id}")
    response.raise_for_status()
    return RunDetail.model_validate(response.json())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_id", nargs="?", type=UUID, help="Read an existing run without executing"
    )
    args = parser.parse_args()
    with httpx.Client(base_url=API_URL, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        if args.run_id:
            print(read(client, str(args.run_id)).model_dump_json(indent=2))
            return
        sample = json.loads(Path("evaluation-cases/workflow-lab.json").read_text())[0]["text"]
        marker = f"private-source-{uuid4()}"
        response = client.post("/api/lab/workflow", json={"text": f"{sample}\n{marker}"})
        response.raise_for_status()
        run_id = response.json()["analysis"]["request_id"]
        saved = read(client, run_id)
        if saved.status != "completed" or saved.outcome != "accepted" or len(saved.nodes) != 5:
            raise RuntimeError("Completed workflow was not stored correctly")
        if marker in saved.model_dump_json() or saved.input_tokens != 0 or saved.attempts != 1:
            raise RuntimeError("Stored metadata failed privacy or usage checks")
        if any(node.status != "completed" or node.duration_ms is None for node in saved.nodes):
            raise RuntimeError("Completed node snapshots are missing")

        invalid = client.post("/api/lab/workflow", json={"text": " "})
        if invalid.status_code != 422:
            raise RuntimeError("Invalid input was not rejected")
        failed_id = invalid.json()["error"]["request_id"]
        failed = read(client, failed_id)
        if (
            failed.status != "failed"
            or failed.error_code != "invalid_input"
            or failed.nodes[0].status != "failed"
            or any(node.status != "skipped" for node in failed.nodes[1:])
        ):
            raise RuntimeError("Failed workflow was not stored correctly")
        listed = client.get("/api/lab/runs?limit=100")
        listed.raise_for_status()
        ids = {item["id"] for item in listed.json()}
        if run_id not in ids or failed_id not in ids:
            raise RuntimeError("History list is missing new runs")
        if client.get(f"/api/lab/runs/{uuid4()}").status_code != 404:
            raise RuntimeError("Missing history must return 404")
        if client.get("/api/lab/runs?limit=0").status_code != 422:
            raise RuntimeError("Invalid history limit must return 422")
        print("PASS: successful and failed runs, node snapshots, metadata privacy, list and detail")
        print(f"Completed run: {run_id}")
        print(f"Failed run: {failed_id}")
        print(f"Read again: docker compose run --rm history-check {run_id}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(f"FAIL: API returned HTTP {exc.response.status_code}") from None
    except httpx.RequestError:
        raise SystemExit("FAIL: API connection failed") from None
