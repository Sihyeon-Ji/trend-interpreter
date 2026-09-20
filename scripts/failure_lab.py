"""Reproduce local Mock failures and verify their persisted node states."""

import argparse
import json
from pathlib import Path

import httpx
from builder_cup.history import RunDetail

CASES = {
    "timeout": (504, "model_timeout", 2, "failed"),
    "invalid_json": (502, "invalid_model_response", 1, "failed"),
    "branch_failure": (500, "document_check_failed", 1, "cancelled"),
    "transient_error": (200, None, 2, "completed"),
    "normal": (200, None, 1, "completed"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", choices=["all", *CASES], default="all")
    args = parser.parse_args()
    scenarios = CASES if args.scenario == "all" else [args.scenario]
    sample = json.loads(Path("evaluation-cases/workflow-lab.json").read_text())[0]["text"]
    with httpx.Client(base_url="http://api:8000", timeout=15) as client:
        for scenario in scenarios:
            expected_http, error_code, attempts, extract_status = CASES[scenario]
            response = client.post("/api/lab/workflow", json={"text": sample, "scenario": scenario})
            if response.status_code != expected_http:
                raise RuntimeError(f"{scenario}: unexpected HTTP {response.status_code}")
            data = response.json()
            run_id = data["error"]["request_id"] if error_code else data["analysis"]["request_id"]
            detail = client.get(f"/api/lab/runs/{run_id}")
            detail.raise_for_status()
            saved = RunDetail.model_validate(detail.json())
            if (
                saved.scenario != scenario
                or saved.error_code != error_code
                or saved.attempts != attempts
                or saved.status != ("failed" if error_code else "completed")
                or len(saved.nodes) != 5
                or saved.nodes[1].status != extract_status
                or any(
                    n.status != ("skipped" if error_code else "completed") for n in saved.nodes[3:]
                )
            ):
                raise RuntimeError(f"{scenario}: unexpected stored state")
            if (
                scenario == "branch_failure"
                and saved.nodes[2].error_code != "document_check_failed"
            ):
                raise RuntimeError("Inspection failure was not recorded")
            if not error_code and saved.outcome != "accepted":
                raise RuntimeError(f"{scenario}: successful sample was not accepted")
            print(
                f"PASS {scenario}: HTTP {expected_http}, status={saved.status}, "
                f"attempts={saved.attempts}, error={saved.error_code}"
            )
            print(f"Read again: docker compose run --rm history-check {run_id}")
    print("PASS means the expected failure or recovery was reproduced; no real model was called.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(f"FAIL: history API returned HTTP {exc.response.status_code}") from None
    except httpx.RequestError:
        raise SystemExit("FAIL: API connection failed") from None
