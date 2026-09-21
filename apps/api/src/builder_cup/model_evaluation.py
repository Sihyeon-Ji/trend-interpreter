import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReviewStatus = Literal[
    "not_reviewed",
    "satisfied",
    "omitted",
    "contradicted",
    "unsupported_addition",
    "needs_review",
]


class EvaluationCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field(min_length=1)
    source_evidence: str = Field(min_length=1)


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category: str = Field(min_length=1)
    text: str = Field(min_length=1)
    expected_router: Literal["accepted", "needs_revision"]
    required_facts: list[EvaluationCriterion] = Field(min_length=1)
    forbidden_claims: list[EvaluationCriterion] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_criterion_ids(self):
        ids = [item.id for item in self.required_facts + self.forbidden_claims]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion IDs must be unique within a case")
        return self


class EvaluationSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_version: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}\.[0-9]+$")
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_ids(self):
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case IDs must be unique")
        return self


class CriterionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: str
    criterion_type: Literal["required_fact", "forbidden_claim"]
    status: ReviewStatus = "not_reviewed"
    source_evidence: str = Field(min_length=1)
    output_evidence: str = ""
    notes: str = ""


class RunReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    run_id: str
    provider: str
    phase: str
    notes: str = ""
    criteria: list[CriterionReview]


class ManualReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_schema_version: Literal[1] = 1
    report_id: str
    suite_sha256: str
    evaluator: str = ""
    reviewed_at: datetime | None = None
    assessments: list[RunReview]


def load_suite(path: Path) -> tuple[EvaluationSuite, str]:
    raw = path.read_bytes()
    suite = EvaluationSuite.model_validate_json(raw)
    return suite, hashlib.sha256(raw).hexdigest()


def build_review_template(report: dict[str, Any]) -> ManualReview:
    cases = {case["id"]: EvaluationCase.model_validate(case) for case in report["cases"]}
    assessments = []
    for row in report["runs"]:
        if (
            row.get("status") != "completed"
            or row.get("provider") != "ollama"
            or row.get("phase") != "warm"
        ):
            continue
        case = cases[row["case"]]
        criteria = [
            CriterionReview(
                criterion_id=item.id,
                criterion_type="required_fact",
                source_evidence=item.source_evidence,
            )
            for item in case.required_facts
        ]
        criteria.extend(
            CriterionReview(
                criterion_id=item.id,
                criterion_type="forbidden_claim",
                source_evidence=item.source_evidence,
            )
            for item in case.forbidden_claims
        )
        assessments.append(
            RunReview(
                case_id=case.id,
                run_id=row["run_id"],
                provider=row["provider"],
                phase=row["phase"],
                criteria=criteria,
            )
        )
    return ManualReview(
        report_id=report["report_id"],
        suite_sha256=report["suite"]["sha256"],
        assessments=assessments,
    )


def validate_completed_review(review: ManualReview) -> None:
    if not review.evaluator.strip() or review.reviewed_at is None:
        raise ValueError("completed review requires evaluator and reviewed_at")
    for assessment in review.assessments:
        for criterion in assessment.criteria:
            if criterion.status == "not_reviewed":
                raise ValueError("completed review contains not_reviewed criteria")
            if not criterion.output_evidence.strip():
                raise ValueError("completed review requires output_evidence for every criterion")


def validate_review_against_report(review: ManualReview, report: dict[str, Any]) -> None:
    if review.report_id != report["report_id"]:
        raise ValueError("review report_id does not match report")
    if review.suite_sha256 != report["suite"]["sha256"]:
        raise ValueError("review suite_sha256 does not match report")
    expected = build_review_template(report)
    expected_runs = {
        (item.case_id, item.provider, item.phase): {
            (criterion.criterion_id, criterion.criterion_type) for criterion in item.criteria
        }
        for item in expected.assessments
    }
    actual_runs = {
        (item.case_id, item.provider, item.phase): {
            (criterion.criterion_id, criterion.criterion_type) for criterion in item.criteria
        }
        for item in review.assessments
    }
    if actual_runs != expected_runs:
        raise ValueError("review coverage does not match completed Ollama warm runs")
    validate_completed_review(review)


def compare_reviews(base: ManualReview, current: ManualReview) -> dict[str, Any]:
    def indexed(review: ManualReview):
        return {
            (assessment.case_id, criterion.criterion_id, criterion.criterion_type): criterion.status
            for assessment in review.assessments
            for criterion in assessment.criteria
        }

    base_items = indexed(base)
    current_items = indexed(current)
    changes = []
    for key in sorted(base_items.keys() | current_items.keys()):
        previous = base_items.get(key)
        latest = current_items.get(key)
        if previous != latest:
            changes.append(
                {
                    "case_id": key[0],
                    "criterion_id": key[1],
                    "criterion_type": key[2],
                    "base_status": previous,
                    "current_status": latest,
                }
            )
    return {
        "base_evaluator": base.evaluator,
        "base_reviewed_at": base.reviewed_at.isoformat() if base.reviewed_at else None,
        "current_evaluator": current.evaluator,
        "current_reviewed_at": current.reviewed_at.isoformat() if current.reviewed_at else None,
        "status_changes": changes,
    }


def _usage_delta(base: Any, current: Any) -> int | None:
    if not isinstance(base, int) or not isinstance(current, int):
        return None
    return current - base


def compare_reports(
    base: dict[str, Any],
    current: dict[str, Any],
    base_review: ManualReview | None = None,
    current_review: ManualReview | None = None,
) -> dict[str, Any]:
    same_suite = base["suite"]["sha256"] == current["suite"]["sha256"]
    comparison: dict[str, Any] = {
        "comparison_schema_version": 1,
        "base_report_id": base["report_id"],
        "current_report_id": current["report_id"],
        "comparable": same_suite,
        "reason": None if same_suite else "suite_changed",
        "conditions": {
            "base": {
                "source_commit": base["source"]["commit"],
                "source_dirty": base["source"]["dirty"],
                "model": base["model"],
                "model_digest": base.get("runtime", {}).get("digest"),
                "prompt_version": base["prompt_version"],
                "settings": base["settings"],
            },
            "current": {
                "source_commit": current["source"]["commit"],
                "source_dirty": current["source"]["dirty"],
                "model": current["model"],
                "model_digest": current.get("runtime", {}).get("digest"),
                "prompt_version": current["prompt_version"],
                "settings": current["settings"],
            },
        },
        "runs": [],
    }
    if not same_suite:
        return comparison
    if (base_review is None) != (current_review is None):
        raise ValueError("provide both base and current reviews or neither")
    if base_review is not None and current_review is not None:
        validate_review_against_report(base_review, base)
        validate_review_against_report(current_review, current)
        comparison["manual_review"] = compare_reviews(base_review, current_review)
    base_runs = {(row["case"], row["provider"], row["phase"]): row for row in base["runs"]}
    current_runs = {(row["case"], row["provider"], row["phase"]): row for row in current["runs"]}
    for key in sorted(base_runs.keys() | current_runs.keys()):
        previous = base_runs.get(key)
        latest = current_runs.get(key)
        row: dict[str, Any] = {
            "case": key[0],
            "provider": key[1],
            "phase": key[2],
            "comparable": previous is not None and latest is not None,
        }
        if previous is None or latest is None:
            row["reason"] = "run_added" if previous is None else "run_removed"
            comparison["runs"].append(row)
            continue
        previous_analysis = previous.get("result", {}).get("analysis", {})
        latest_analysis = latest.get("result", {}).get("analysis", {})
        previous_usage = previous_analysis.get("usage", {})
        latest_usage = latest_analysis.get("usage", {})
        row.update(
            {
                "base_run_id": previous["run_id"],
                "current_run_id": latest["run_id"],
                "status_changed": previous["status"] != latest["status"],
                "output_changed": previous_analysis.get("result") != latest_analysis.get("result"),
                "duration_delta_ms": _usage_delta(
                    previous_analysis.get("duration_ms"), latest_analysis.get("duration_ms")
                ),
                "input_tokens_delta": _usage_delta(
                    previous_usage.get("input_tokens"), latest_usage.get("input_tokens")
                ),
                "output_tokens_delta": _usage_delta(
                    previous_usage.get("output_tokens"), latest_usage.get("output_tokens")
                ),
            }
        )
        comparison["runs"].append(row)
    return comparison


def dump_json(path: Path, value: Any) -> None:
    if isinstance(value, BaseModel):
        data = value.model_dump(mode="json")
    else:
        data = value
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
