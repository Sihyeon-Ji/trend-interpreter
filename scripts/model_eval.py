"""Validate evaluation data, reviews and comparisons without calling a model."""

import argparse
import json
from pathlib import Path

from builder_cup.model_evaluation import (
    ManualReview,
    build_review_template,
    compare_reports,
    dump_json,
    load_suite,
    validate_review_against_report,
)

DEFAULT_SUITE = Path("evaluation-cases/ollama-lab.json")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    suite = commands.add_parser("validate-suite")
    suite.add_argument("path", nargs="?", type=Path, default=DEFAULT_SUITE)

    template = commands.add_parser("review-template")
    template.add_argument("report", type=Path)
    template.add_argument("--output", type=Path)

    review = commands.add_parser("validate-review")
    review.add_argument("review", type=Path)
    review.add_argument("--report", type=Path, required=True)

    compare = commands.add_parser("compare")
    compare.add_argument("base", type=Path)
    compare.add_argument("current", type=Path)
    compare.add_argument("--output", type=Path)
    compare.add_argument("--base-review", type=Path)
    compare.add_argument("--current-review", type=Path)
    args = parser.parse_args()

    if args.command == "validate-suite":
        data, digest = load_suite(args.path)
        print(f"PASS: suite {data.suite_version}, {len(data.cases)} cases, SHA256 {digest}")
        return

    if args.command == "review-template":
        result = build_review_template(load_json(args.report))
        output = args.output or args.report.with_suffix(".review.json")
        dump_json(output, result)
        print(f"PASS: review template with {len(result.assessments)} run assessments")
        print(f"Review: {output}")
        return

    if args.command == "validate-review":
        result = ManualReview.model_validate_json(args.review.read_bytes())
        validate_review_against_report(result, load_json(args.report))
        print(f"PASS: completed review by {result.evaluator}, {len(result.assessments)} runs")
        return

    base_review = (
        ManualReview.model_validate_json(args.base_review.read_bytes())
        if args.base_review
        else None
    )
    current_review = (
        ManualReview.model_validate_json(args.current_review.read_bytes())
        if args.current_review
        else None
    )
    result = compare_reports(
        load_json(args.base), load_json(args.current), base_review, current_review
    )
    output = args.output or args.current.with_suffix(".comparison.json")
    dump_json(output, result)
    print(
        f"PASS: reports are {'directly comparable' if result['comparable'] else 'not comparable'}"
    )
    if result["reason"]:
        print(f"Reason: {result['reason']}")
    print(f"Comparison: {output}")


if __name__ == "__main__":
    main()
