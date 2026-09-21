"""Weekly report tests — do the numbers agree with schedule.py, and does the prose match the data.

Run: python -m pytest tests/test_report.py -q
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import unittest

from pmo_agent import report, schedule  # noqa: E402
from pmo_agent.seeds import board as seed  # noqa: E402

TODAY = dt.date(2026, 9, 21)  # a Monday


def tasks():
    return schedule.to_tasks(
        [
            {
                "key": "ECHO-1",
                "summary": "Requirements",
                "status": "Done",
                "assignee": "Maya Okonkwo",
                "points": 3,
            },
            {
                "key": "ECHO-2",
                "summary": "Schema design",
                "status": "In Progress",
                "assignee": "Leo Fischer",
                "points": 4,
                "deps": ["ECHO-1"],
                "duedate": "2026-09-23",
            },
            {
                "key": "ECHO-3",
                "summary": "API build",
                "status": "To Do",
                "assignee": "Maya Okonkwo",
                "points": 5,
                "deps": ["ECHO-2"],
                "duedate": "2026-09-18",
            },  # already past
            {
                "key": "ECHO-4",
                "summary": "Documentation",
                "status": "To Do",
                "assignee": "Leo Fischer",
                "points": 1,
                "duedate": "2026-10-30",
            },
        ]
    )


class TestPieces(unittest.TestCase):
    def test_groups_remaining_work_by_owner(self):
        w = {r["assignee"]: r for r in report.workload(tasks())}
        self.assertNotIn("Maya Okonkwo", [r for r in w if w[r]["count"] == 0])
        self.assertEqual(w["Leo Fischer"]["count"], 2)  # ECHO-2, ECHO-4
        self.assertEqual(w["Maya Okonkwo"]["count"], 1)  # ECHO-1 is done, so it drops out

    def test_finished_tasks_leave_the_load(self):
        self.assertEqual(sum(r["count"] for r in report.workload(tasks())), 3)

    def test_picks_only_what_is_due_this_week(self):
        keys = [t.key for t in report.due_soon(tasks(), TODAY)]
        self.assertIn("ECHO-2", keys)  # 9/23
        self.assertNotIn("ECHO-4", keys)  # 10/30 is a long way off
        self.assertNotIn("ECHO-3", keys)  # already past — that belongs under Past due

    def test_committed_finish_is_the_latest_due_date(self):
        self.assertEqual(report.committed_finish(tasks()), dt.date(2026, 10, 30))

    def test_no_due_dates_means_no_committed_finish(self):
        self.assertIsNone(report.committed_finish(schedule.to_tasks([{"key": "A"}])))

    def test_collects_what_is_past_due(self):
        self.assertEqual([t.key for t in report.overdue(tasks(), TODAY)], ["ECHO-3"])

    def test_the_question_names_the_owner_and_the_key(self):
        r = schedule.risks(tasks(), TODAY)[0]
        q = report.question_for(r)
        self.assertIn(r["key"], q)
        self.assertIn(r["assignee"], q)
        self.assertTrue(q.endswith("?"))

    def test_blocking_relationships_go_into_the_question(self):
        r = next(x for x in schedule.risks(tasks(), TODAY) if x["key"] == "ECHO-2")
        self.assertIn("ECHO-3", report.question_for(r))


class TestApprovalLog(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "approvals.jsonl")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, rows):
        with open(self.path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def test_counts_only_successes_inside_the_window(self):
        self.write(
            [
                {
                    "at": "2026-09-19T10:00:00",
                    "ok": True,
                    "tool": "propose_comment",
                    "args": {"key": "A"},
                },
                {
                    "at": "2026-09-01T10:00:00",
                    "ok": True,
                    "tool": "propose_comment",
                    "args": {"key": "B"},
                },
                {
                    "at": "2026-09-19T11:00:00",
                    "ok": False,
                    "tool": "propose_comment",
                    "args": {"key": "C"},
                },
            ]
        )
        keys = [r["args"]["key"] for r in report.recent_approvals(dt.date(2026, 9, 14), self.path)]
        self.assertEqual(keys, ["A"])

    def test_survives_a_missing_log(self):
        self.assertEqual(report.recent_approvals(TODAY, os.path.join(self.dir, "nope.jsonl")), [])

    def test_skips_broken_lines(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not json at all}\n")
            f.write(
                json.dumps({"at": "2026-09-19T10:00:00", "ok": True, "tool": "x", "args": {}})
                + "\n"
            )
        self.assertEqual(len(report.recent_approvals(dt.date(2026, 9, 14), self.path)), 1)


class TestWeekly(unittest.TestCase):
    def setUp(self):
        self.md = report.weekly(tasks(), TODAY)

    def test_every_section_is_present(self):
        for h in (
            "# ECHO weekly report",
            "## At a glance",
            "## At risk of slipping",
            "## Critical path",
            "## Due this week",
            "## Work left per owner",
            "## Needs checking",
            "## Applied recently",
        ):
            self.assertIn(h, self.md)

    def test_shows_committed_and_forecast_side_by_side(self):
        self.assertIn("| committed finish | 2026-10-30 |", self.md)
        self.assertIn(schedule.forecast(tasks(), TODAY)["project_finish"].isoformat(), self.md)

    def test_the_numbers_match_schedule(self):
        t = tasks()
        f = schedule.forecast(t, TODAY)
        self.assertIn(f["project_finish"].isoformat(), self.md)
        self.assertIn(f"| at risk of slipping | {len(schedule.risks(t, TODAY))} |", self.md)

    def test_counts_progress(self):
        self.assertIn("1/4 done (25%)", self.md)

    def test_the_past_due_section_appears_only_when_it_applies(self):
        self.assertIn("## Past due", self.md)
        clean = schedule.to_tasks([{"key": "A", "status": "Done", "points": 1}])
        self.assertNotIn("## Past due", report.weekly(clean, TODAY))

    def test_says_nothing_when_there_is_no_risk(self):
        clean = schedule.to_tasks([{"key": "A", "status": "Done", "points": 1}])
        md = report.weekly(clean, TODAY)
        self.assertIn("## At risk of slipping\n\nNothing.", md)

    def test_states_where_the_numbers_came_from_and_the_limits(self):
        self.assertIn("schedule.py", self.md)
        self.assertIn("business days", self.md)
        self.assertIn("capacity.py", self.md)
        self.assertIn("one concurrent task per person", self.md)

    def test_a_completed_list_adds_the_section(self):
        t = tasks()
        md = report.weekly(t, TODAY, done_recent=[t["ECHO-1"]])
        self.assertIn("## Finished this week", md)
        self.assertIn("ECHO-1", md.split("## Finished this week")[1].split("##")[0])

    def test_an_empty_completed_list_says_nothing(self):
        md = report.weekly(tasks(), TODAY, done_recent=[])
        self.assertIn("## Finished this week\n\nNothing.", md)

    def test_no_completed_list_drops_the_section(self):
        self.assertNotIn("## Finished this week", report.weekly(tasks(), TODAY))

    def test_the_project_name_can_change(self):
        self.assertIn("# DEMO weekly report", report.weekly(tasks(), TODAY, project="DEMO"))

    def test_an_empty_board_still_produces_a_report(self):
        md = report.weekly({}, TODAY)
        self.assertIn("0/0 done", md)
        self.assertIn("## At a glance", md)


class TestSeedReport(unittest.TestCase):
    def test_the_seeded_40_produce_a_report(self):
        t = schedule.from_jira_issues(seed.build(TODAY))
        md = report.weekly(t, TODAY)
        self.assertIn("40 done", md)
        self.assertGreater(len(md.splitlines()), 40)

    def test_the_risk_table_carries_only_the_top_n(self):
        t = schedule.from_jira_issues(seed.build(TODAY))
        rows = [line for line in report.weekly(t, TODAY).splitlines() if line.startswith("| ECHO-")]
        self.assertLessEqual(len([r for r in rows if "d |" in r]), 40)


class TestSave(unittest.TestCase):
    def test_the_date_goes_into_the_filename(self):
        d = tempfile.mkdtemp()
        try:
            p = report.save("# test", TODAY, d)
            self.assertTrue(p.endswith("weekly-2026-09-21.md"))
            with open(p, encoding="utf-8") as f:
                self.assertEqual(f.read(), "# test")
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
