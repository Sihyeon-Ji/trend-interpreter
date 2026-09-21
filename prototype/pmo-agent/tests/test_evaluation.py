"""The evaluation cases also run as tests — so a break shows up before the demo.

Running `tools/evaluate.py` by hand is not enough to catch a regression.
Tied in here, every change to the calculation is checked against the answer key automatically.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import evaluate  # noqa: E402

TODAY = dt.date(2026, 9, 21)  # a Monday


class TestCaseFile:
    def test_there_are_fifteen(self):
        cases = evaluate.load_cases()
        assert len(cases) == 15

    def test_seven_detect_and_eight_restraint(self):
        # The team document asks for 5 successes and 5 failures. There are more restraint cases —
        # not inventing what is not there matters more.
        cases = evaluate.load_cases()
        assert sum(1 for c in cases if c["group"] == "detect") == 7
        assert sum(1 for c in cases if c["group"] == "restraint") == 8

    def test_every_case_has_a_registered_check(self):
        for case in evaluate.load_cases():
            assert case["check"] in evaluate.CHECKS, case["id"]

    def test_the_ids_do_not_collide(self):
        ids = [c["id"] for c in evaluate.load_cases()]
        assert len(ids) == len(set(ids))

    def test_each_one_says_why_it_was_planted(self):
        # A case with no stated reason is one nobody will ever be able to fix
        for case in evaluate.load_cases():
            assert case.get("why"), case["id"]
            assert case.get("ask"), case["id"]

    def test_the_jsonl_reads_one_line_at_a_time(self):
        text = evaluate.CASES.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip():
                json.loads(line)


class TestRun:
    def test_they_all_pass(self):
        rows = evaluate.run(TODAY)
        failed = [f"{r['id']}: {r['detail']}" for r in rows if not r["passed"]]
        assert not failed, "failed: " + " / ".join(failed)

    def test_the_results_carry_their_evidence(self):
        for row in evaluate.run(TODAY):
            assert row["detail"], row["id"]

    def test_it_passes_with_todays_date_too(self):
        # The world is built around today — the answer key and the calculation must agree whenever
        rows = evaluate.run()
        assert all(r["passed"] for r in rows), [r["id"] for r in rows if not r["passed"]]

    def test_it_holds_at_dates_other_than_this_one(self):
        """The suite passed on the day it was written and broke the day after.

        The world rebuilds itself from `today`, so a case that happens to line up this
        week looks exactly like one that holds. Four dates here, because they cost a
        second each; `python tools/evaluate.py --dates 13` is the wider sweep, and it is
        clean from today through four months out.
        """
        for day, rows in evaluate.over_dates(4, step=29):
            failed = [r["id"] for r in rows if not r["passed"]]
            assert not failed, f"{day}: {failed}"

    def test_it_does_not_touch_the_real_audit_log(self):
        from pmo_agent import approve as approve_mod

        before = approve_mod.LOG
        evaluate.run(TODAY)
        assert approve_mod.LOG == before
