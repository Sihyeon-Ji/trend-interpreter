import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from builder_cup.model_evaluation import (
    ManualReview,
    build_review_template,
    compare_reports,
    dump_json,
    load_suite,
    validate_completed_review,
    validate_review_against_report,
)

FIXTURES = Path("tests/fixtures/model-evaluation")
SUITE = Path("evaluation-cases/ollama-lab.json")


def read(name):
    return json.loads((FIXTURES / name).read_text())


def test_suite_has_versioned_neutral_cases_and_unique_evidence():
    suite, digest = load_suite(SUITE)
    assert suite.suite_version == "2026-09-22.1"
    assert len(suite.cases) == 10
    assert len(digest) == 64
    assert {case.category for case in suite.cases} >= {
        "person_task_deadline_relation",
        "negation_and_blocked_state",
        "instruction_inside_source",
    }
    for case in suite.cases:
        assert case.text.count("## ") >= 2
        assert len({item.id for item in case.required_facts + case.forbidden_claims}) == len(
            case.required_facts + case.forbidden_claims
        )


def test_comparison_exposes_conditions_deltas_and_unknown_usage():
    result = compare_reports(read("base-report.json"), read("current-report.json"))
    assert result["comparable"] is True
    assert result["conditions"]["base"]["prompt_version"] == "extract-v1"
    assert result["conditions"]["current"]["source_commit"] == "2222222"
    run = result["runs"][0]
    assert run["output_changed"] is True
    assert run["duration_delta_ms"] == 25
    assert run["input_tokens_delta"] is None
    assert run["output_tokens_delta"] == 3


def test_suite_change_blocks_direct_comparison():
    base = read("base-report.json")
    current = deepcopy(read("current-report.json"))
    current["suite"]["sha256"] = "changed-suite"
    result = compare_reports(base, current)
    assert result["comparable"] is False
    assert result["reason"] == "suite_changed"
    assert result["runs"] == []


def test_schema_valid_output_can_be_manually_marked_omitted():
    suite, digest = load_suite(SUITE)
    case = next(case for case in suite.cases if case.id == "schedule_change")
    report = read("base-report.json")
    report["suite"]["sha256"] = digest
    report["cases"] = [case.model_dump(mode="json")]
    template = build_review_template(report)
    assert template.evaluator == ""
    assert all(item.status == "not_reviewed" for item in template.assessments[0].criteria)

    review = template.model_copy(deep=True)
    review.evaluator = "reviewer@example"
    review.reviewed_at = datetime.now(UTC)
    for criterion in review.assessments[0].criteria:
        criterion.status = "satisfied"
        criterion.output_evidence = "검토 결과 근거"
    missing_time = next(
        item for item in review.assessments[0].criteria if item.criterion_id == "new_rehearsal_time"
    )
    missing_time.status = "omitted"
    missing_time.output_evidence = "응답에는 10월 12일만 있고 오전 11시가 없다."
    validate_completed_review(review)
    validate_review_against_report(review, report)
    assert missing_time.status == "omitted"


def test_review_must_cover_the_matching_report():
    suite, digest = load_suite(SUITE)
    case = next(case for case in suite.cases if case.id == "schedule_change")
    report = read("base-report.json")
    report["suite"]["sha256"] = digest
    report["cases"] = [case.model_dump(mode="json")]
    review = build_review_template(report)
    review.report_id = "different"
    with pytest.raises(ValueError, match="report_id"):
        validate_review_against_report(review, report)


def test_comparison_includes_manual_status_changes(tmp_path):
    suite, digest = load_suite(SUITE)
    case = next(case for case in suite.cases if case.id == "schedule_change")
    base = read("base-report.json")
    current = read("current-report.json")
    for report in (base, current):
        report["suite"]["sha256"] = digest
        report["cases"] = [case.model_dump(mode="json")]
    base_review = build_review_template(base)
    current_review = build_review_template(current)
    for review in (base_review, current_review):
        review.evaluator = "reviewer"
        review.reviewed_at = datetime.now(UTC)
        for criterion in review.assessments[0].criteria:
            criterion.status = "satisfied"
            criterion.output_evidence = "검토 근거"
    current_review.assessments[0].criteria[0].status = "omitted"
    result = compare_reports(base, current, base_review, current_review)
    assert result["manual_review"]["status_changes"] == [
        {
            "case_id": "schedule_change",
            "criterion_id": "new_rehearsal_time",
            "criterion_type": "required_fact",
            "base_status": "satisfied",
            "current_status": "omitted",
        }
    ]
    path = tmp_path / "comparison.json"
    dump_json(path, result)
    assert json.loads(path.read_text())["manual_review"]["base_reviewed_at"]


@pytest.mark.parametrize("missing", ["evaluator", "reviewed_at", "status", "evidence"])
def test_completed_review_requires_attribution_and_evidence(missing):
    review = ManualReview.model_validate(
        {
            "report_id": "report",
            "suite_sha256": "suite",
            "evaluator": "reviewer",
            "reviewed_at": datetime.now(UTC),
            "assessments": [
                {
                    "case_id": "case",
                    "run_id": "run",
                    "provider": "ollama",
                    "phase": "warm",
                    "criteria": [
                        {
                            "criterion_id": "fact",
                            "criterion_type": "required_fact",
                            "status": "satisfied",
                            "source_evidence": "원문 근거",
                            "output_evidence": "출력 근거",
                        }
                    ],
                }
            ],
        }
    )
    if missing == "evaluator":
        review.evaluator = ""
    elif missing == "reviewed_at":
        review.reviewed_at = None
    elif missing == "status":
        review.assessments[0].criteria[0].status = "not_reviewed"
    else:
        review.assessments[0].criteria[0].output_evidence = ""
    with pytest.raises(ValueError):
        validate_completed_review(review)
