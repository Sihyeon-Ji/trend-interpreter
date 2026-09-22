"""Run one synthetic Gemma 4 workflow and link its report to PostgreSQL history."""

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from builder_cup import history
from builder_cup.config import Settings
from builder_cup.database import DatabaseUnavailable
from builder_cup.model_evaluation import dump_json, load_suite
from builder_cup.providers import OllamaProvider, Provider, ProviderFailure


class SimulatedFailureProvider:
    def __init__(self, model: str, code: str):
        self.model = model
        self.code = code

    async def generate(self, text: str):
        raise ProviderFailure(self.code)

    async def close(self) -> None:
        pass


async def execute(
    case_id: str,
    failure: str | None,
    settings: Settings,
    provider: Provider,
    output_dir: Path,
) -> tuple[int, Path]:
    suite_path = Path("evaluation-cases/ollama-lab.json")
    suite, suite_sha256 = load_suite(suite_path)
    case = next((item for item in suite.cases if item.id == case_id), None)
    if case is None:
        raise ValueError(f"Unknown evaluation case: {case_id}")
    run_id = uuid4()
    started = datetime.now(UTC)
    report = {
        "report_schema_version": 1,
        "report_id": str(uuid4()),
        "run_id": str(run_id),
        "started_at": started.isoformat(),
        "source": {
            "commit": os.environ.get("SOURCE_COMMIT", "unknown"),
            "dirty": os.environ.get("SOURCE_DIRTY", "unknown").lower(),
        },
        "suite": {"version": suite.suite_version, "sha256": suite_sha256},
        "case": case.model_dump(mode="json"),
        "provider": "ollama",
        "model": provider.model,
        "simulation": failure,
        "status": "running",
        "result": None,
        "error_code": None,
        "history": None,
    }
    exit_code = 0
    try:
        result = await history.run_with_history(
            case.text,
            str(run_id),
            provider,
            settings,
        )
        report["status"] = "completed"
        report["result"] = result.model_dump(mode="json")
    except ProviderFailure as exc:
        exit_code = 1
        report["status"] = "failed"
        report["error_code"] = exc.code
    except DatabaseUnavailable:
        exit_code = 1
        report["status"] = "failed"
        report["error_code"] = "database_unavailable"
    finally:
        try:
            stored = await asyncio.to_thread(history.read_run, settings, UUID(str(run_id)))
        except DatabaseUnavailable:
            stored = None
            exit_code = 1
            report["status"] = "failed"
            report["error_code"] = "database_unavailable"
        if stored is not None:
            report["history"] = stored.model_dump(mode="json")
            if case.text in stored.model_dump_json():
                raise RuntimeError("Workflow history unexpectedly contains source text")
        report["finished_at"] = datetime.now(UTC).isoformat()
        output_dir.mkdir(exist_ok=True)
        path = output_dir / f"ollama-history-{started.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        dump_json(path, report)
    if report["history"] is None and report["error_code"] != "database_unavailable":
        raise RuntimeError("Workflow run was not persisted")
    if report["history"] is not None:
        stored = report["history"]
        if stored["id"] != str(run_id) or stored["provider"] != "ollama":
            raise RuntimeError("Report and workflow history metadata do not match")
    return exit_code, path


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", nargs="?", default="meeting")
    parser.add_argument("--failure", choices=["model_unavailable", "model_timeout"])
    args = parser.parse_args()
    settings = Settings(_env_file=None)
    provider: Provider
    if args.failure:
        provider = SimulatedFailureProvider(settings.ollama_model, args.failure)
    else:
        provider = OllamaProvider(settings)
        await provider.verify_local_model()
    try:
        exit_code, path = await execute(
            args.case_id,
            args.failure,
            settings,
            provider,
            Path("artifacts"),
        )
    finally:
        await provider.close()
    data = json.loads(path.read_text())
    print(f"Run ID: {data['run_id']}")
    print(f"Status: {data['status']}; error: {data['error_code']}")
    print(f"History API: http://localhost:8000/api/lab/runs/{data['run_id']}")
    print(f"Report: {path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
