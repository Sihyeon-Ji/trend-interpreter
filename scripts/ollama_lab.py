"""Compare synthetic documents with Mock and a local Ollama model, without changing the API."""

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from builder_cup.config import Settings
from builder_cup.graph_lab import run_graph
from builder_cup.model_evaluation import build_review_template, dump_json, load_suite
from builder_cup.providers import PROMPT_VERSION, MockProvider, OllamaProvider, ProviderFailure


def write_readable_report(path: Path, report: dict) -> None:
    lines = [
        "# Local model comparison",
        "",
        f"Started {report['started_at']} — status {report['status']}",
        "",
        report["quality_note"],
        "",
        f"Report `{report['report_id']}`.",
        f"Suite `{report['suite']['version']}` / `{report['suite']['sha256']}`.",
        f"Source `{report['source']['commit']}` / dirty `{report['source']['dirty']}`.",
        f"Model `{report['model']}`, prompt `{report['prompt_version']}`.",
        "First is the first measured call, not a guarantee of a cold model cache.",
    ]
    for case in report["cases"]:
        lines.extend(["", f"## {case['id']}", "", "### Source", ""])
        lines.extend("    " + line for line in case["text"].splitlines())
        lines.extend(
            ["", "Required facts", ""]
            + [
                f"- `{fact['id']}` {fact['description']} — source: {fact['source_evidence']}"
                for fact in case["required_facts"]
            ]
        )
        lines.extend(
            ["", "Forbidden claims", ""]
            + [
                f"- `{fact['id']}` {fact['description']} — source: {fact['source_evidence']}"
                for fact in case["forbidden_claims"]
            ]
        )
        for row in report["runs"]:
            if row["case"] != case["id"]:
                continue
            lines.extend(["", f"### {row['provider']} / {row['phase']} / {row['status']}", ""])
            if row["status"] == "failed":
                lines.append(row["error_code"])
                continue
            analysis = row["result"]["analysis"]
            lines.append(f"Duration {analysis['duration_ms']} ms; tokens {analysis['usage']}")
            lines.append("")
            output = json.dumps(analysis["result"], ensure_ascii=False, indent=2)
            lines.extend("    " + line for line in output.splitlines())
    lines.extend(
        [
            "",
            "## Manual review",
            "",
            "Schema-valid output is not a factuality result. "
            "Fill and validate the matching `.review.json` file.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


async def main() -> None:
    settings = Settings(_env_file=None)
    if settings.model_provider != "ollama":
        raise SystemExit("Use the Compose ollama-check service")
    suite_path = Path("evaluation-cases/ollama-lab.json")
    suite, suite_sha256 = load_suite(suite_path)
    cases = [case.model_dump(mode="json") for case in suite.cases]
    started = datetime.now(UTC)
    source_commit = os.environ.get("SOURCE_COMMIT", "unknown")
    source_dirty = os.environ.get("SOURCE_DIRTY", "unknown").lower()
    report = {
        "report_schema_version": 2,
        "report_id": str(uuid4()),
        "started_at": started.isoformat(),
        "source": {
            "commit": source_commit,
            "dirty": source_dirty == "true" if source_dirty in {"true", "false"} else None,
        },
        "suite": {
            "path": str(suite_path),
            "version": suite.suite_version,
            "sha256": suite_sha256,
        },
        "prompt_version": PROMPT_VERSION,
        "model": settings.ollama_model,
        "settings": {"temperature": 0, "num_ctx": 4096, "num_predict": 1024, "think": False},
        "quality_note": (
            "Schema validity and routing are not factuality scores. "
            "Review required facts and forbidden claims against generated content."
        ),
        "cases": cases,
        "runs": [],
    }
    rows: list[dict] = []
    provider = OllamaProvider(settings)
    failed = False
    try:
        metadata = await provider.verify_local_model()
        version = await provider.client.get("api/version")
        version.raise_for_status()
        tags = await provider.client.get("api/tags")
        tags.raise_for_status()
        model = next(item for item in tags.json()["models"] if item["name"] == provider.model)
        report["runtime"] = {
            "version": version.json()["version"],
            "digest": model["digest"],
            "size_bytes": model["size"],
            "details": metadata.get("details"),
        }
        for case in cases:
            for mode in ("mock", "ollama"):
                active = MockProvider() if mode == "mock" else provider
                config = settings.model_copy(update={"model_provider": mode})
                # Repeat the first real input to distinguish initial loading from a warm request.
                phases = ("first", "warm") if mode == "ollama" and case == cases[0] else ("warm",)
                for phase in phases:
                    run_id = str(uuid4())
                    row = {
                        "case": case["id"],
                        "provider": mode,
                        "phase": phase,
                        "run_id": run_id,
                    }
                    try:
                        result = await run_graph(case["text"], run_id, active, config)
                        row.update(
                            {
                                "status": "completed",
                                "result": result.model_dump(mode="json"),
                            }
                        )
                        if result.decision.outcome != case["expected_router"]:
                            failed = True
                            row["status"] = "failed"
                            row["error_code"] = "unexpected_router_outcome"
                        if mode == "ollama":
                            row["runtime_timings_ns"] = dict(provider.last_timings)
                        print(
                            f"{case['id']} {mode} {phase}: schema valid, "
                            f"{result.analysis.duration_ms} ms"
                        )
                    except ProviderFailure as exc:
                        failed = True
                        row.update(
                            {
                                "status": "failed",
                                "error_code": exc.code,
                            }
                        )
                        print(f"{case['id']} {mode} {phase}: {exc.code}")
                    rows.append(row)
        running = await provider.client.get("api/ps")
        running.raise_for_status()
        report["loaded_model"] = [
            m for m in running.json()["models"] if m["name"] == provider.model
        ]
    except (ProviderFailure, httpx.HTTPError, KeyError, ValueError, StopIteration) as exc:
        failed = True
        report["error_code"] = (
            exc.code if isinstance(exc, ProviderFailure) else "ollama_check_failed"
        )
        print(
            f"FAIL: {report['error_code']}; "
            "verify Ollama is running and the local model is installed"
        )
    finally:
        await provider.close()
        report["runs"] = rows
        report["status"] = "failed" if failed else "completed"
        directory = Path("artifacts")
        directory.mkdir(exist_ok=True)
        path = directory / f"ollama-comparison-{started.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        write_readable_report(path.with_suffix(".md"), report)
        review_path = path.with_suffix(".review.json")
        dump_json(review_path, build_review_template(report))
        print(f"Report: {path}")
        print(f"Readable report: {path.with_suffix('.md')}")
        print(f"Review template: {review_path}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
