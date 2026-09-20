"""Exercise fan-out, join and deterministic routing with synthetic documents."""

import json
from pathlib import Path

import httpx
from builder_cup.graph_lab import GraphResult

API_URL = "http://api:8000"
REQUEST_TIMEOUT_SECONDS = 15
CASES_PATH = Path("evaluation-cases/workflow-lab.json")


def main() -> None:
    cases = json.loads(CASES_PATH.read_text())
    with httpx.Client(base_url=API_URL, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for case in cases:
            response = client.post("/api/lab/workflow", json={"text": case["text"]})
            response.raise_for_status()
            result = GraphResult.model_validate(response.json())
            if (
                result.decision.outcome != case["expected_outcome"]
                or result.decision.reason_codes != case["expected_reason_codes"]
                or result.analysis.provider != "mock"
                or result.analysis.request_id != response.headers["X-Request-ID"]
            ):
                raise RuntimeError(f"Unexpected result for fixture {case['id']}")
            print(f"CASE: {case['id']}")
            print(f"INPUT (synthetic):\n{case['text']}")
            print(f"DECISION: {result.decision.outcome}")
            print(f"REASONS: {', '.join(result.decision.reason_codes) or 'none'}")
            print(f"MOCK SUMMARY: {result.analysis.result.summary}")
            print("EVENTS: " + " -> ".join(f"{e.node}:{e.state}" for e in result.events))
        invalid = client.post("/api/lab/workflow", json={"text": "   "})
        if invalid.status_code != 422:
            raise RuntimeError("Blank input was not rejected")
    print(f"PASS: {len(cases)} workflow fixtures and blank input; no real model called")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(f"FAIL: API returned HTTP {exc.response.status_code}") from None
    except httpx.RequestError:
        raise SystemExit("FAIL: API connection failed") from None
