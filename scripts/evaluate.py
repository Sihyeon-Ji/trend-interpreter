"""Contract smoke evaluation, not a measure of task quality or factual accuracy."""

import asyncio
import json
from pathlib import Path

from builder_cup.config import Settings
from builder_cup.providers import create_provider
from builder_cup.workflow import analyze


async def main():
    settings = Settings()
    provider = create_provider(settings)
    rows = []
    try:
        for line in Path("evals/cases.jsonl").read_text().splitlines():
            case = json.loads(line)
            try:
                result = await analyze(case["text"], case["id"], provider, settings)
                content = result.result.model_dump_json().lower()
                passed = all(term.lower() in content for term in case["required_terms"])
                rows.append({"id": case["id"], "passed": passed, **result.model_dump()})
            except Exception as exc:
                rows.append({"id": case["id"], "passed": False, "error": type(exc).__name__})
    finally:
        await provider.close()
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/evaluation.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(
        f"{sum(row['passed'] for row in rows)}/{len(rows)} contract checks passed "
        f"({settings.model_provider})"
    )
    if not all(row["passed"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
