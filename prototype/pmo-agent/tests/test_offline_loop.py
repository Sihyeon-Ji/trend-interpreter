"""Seed plus whole-loop integration test — it runs with no API key and no Jira account.

Note → extraction (a fake Gemini) → validation → schedule impact → approval → written to the
local board, all in one pass. Once this passes, the only unknown left is whether a real Gemini
reads the note properly.

The memo never names a ticket key. Real notes do not carry them, and working out which task a
line means is the agent's job — so the test resolves the key the same way the agent does.

Run: python -m pytest tests/test_offline_loop.py -q
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile
import unittest

from test_ingest import caller_returning  # noqa: E402

from pmo_agent import approve, ingest, schedule, tools  # noqa: E402
from pmo_agent.adapters.memory import MemoryBoard  # noqa: E402
from pmo_agent.seeds import board as seed  # noqa: E402

TODAY = dt.date(2026, 9, 21)


class TestSeed(unittest.TestCase):
    def test_forty_tasks_and_four_owners(self):
        issues = seed.build(TODAY)
        self.assertEqual(len(issues), 40)
        tasks = schedule.from_jira_issues(issues)
        self.assertEqual(len({t.assignee for t in tasks.values()}), 4)

    def test_the_same_seed_builds_the_same_board(self):
        self.assertEqual(seed.build(TODAY), seed.build(TODAY))

    def test_the_dependencies_have_no_cycle(self):
        schedule.topo_order(schedule.from_jira_issues(seed.build(TODAY)))  # no exception = pass

    def test_there_is_finished_work_and_work_in_flight(self):
        tasks = schedule.from_jira_issues(seed.build(TODAY))
        statuses = {t.status for t in tasks.values()}
        self.assertIn("Done", statuses)
        self.assertIn("In Progress", statuses)

    def test_some_tasks_really_are_at_risk(self):
        tasks = schedule.from_jira_issues(seed.build(TODAY))
        self.assertTrue(schedule.risks(tasks, TODAY))

    def test_every_task_has_points_and_a_due_date(self):
        tasks = schedule.from_jira_issues(seed.build(TODAY))
        self.assertTrue(all(t.points and t.duedate for t in tasks.values()))

    def test_no_real_names_crept_in(self):
        names = {t.assignee for t in schedule.from_jira_issues(seed.build(TODAY)).values()}
        self.assertEqual(names, set(seed.PEOPLE))

    def test_it_writes_to_a_file(self):
        d = tempfile.mkdtemp()
        try:
            r = seed.write(os.path.join(d, "b.json"), TODAY)
            self.assertEqual(r["count"], 40)
            self.assertEqual(len(MemoryBoard(r["path"]).search(limit=100)), 40)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestOfflineLoop(unittest.TestCase):
    """The whole loop, with no keys."""

    MEMO_TASK = "Data migration"  # what the note calls it — no ticket key anywhere
    NEW_DUE = "2026-10-05"

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        path = os.path.join(self.dir, "board.json")
        seed.write(path, TODAY)
        self.board = MemoryBoard(path)
        tools._j = self.board
        self.keep_log, approve.LOG = approve.LOG, os.path.join(self.dir, "approvals.jsonl")

    def tearDown(self):
        tools._j = None
        approve.LOG = self.keep_log
        shutil.rmtree(self.dir, ignore_errors=True)

    def _key(self) -> str:
        """Which task the memo meant — resolved, not written down."""
        key, why = ingest.resolve(self.MEMO_TASK, tools._fetch())
        self.assertIsNotNone(key, why)
        return str(key)

    def test_it_reads_the_board_and_analyses_the_schedule(self):
        r = tools.analyze_schedule(today=TODAY.isoformat())
        self.assertEqual(r["total"], 40)
        self.assertTrue(r["critical_path"])
        self.assertTrue(r["risks"])

    def test_the_delay_simulation_runs(self):
        key = tools.analyze_schedule(today=TODAY.isoformat())["critical_path"][0]
        r = tools.simulate_delay(key, 3, today=TODAY.isoformat())
        self.assertTrue(r["affected"])

    def test_a_note_gets_as_far_as_a_proposal(self):
        r = self._ingest_memo()
        self.assertTrue(r["resolved"])
        self.assertTrue(r["proposals"])
        self.assertFalse(r["applied"])

    def test_the_title_in_the_note_resolves_to_a_task(self):
        # The point of the whole thing: the note says "Data migration", not a key.
        r = self._ingest_memo()
        self.assertEqual([u["key"] for u in r["resolved"]], [self._key()])

    def test_the_board_changes_only_after_approval(self):
        key = self._key()
        r = self._ingest_memo()
        before = self.board.issue(key)["fields"]["duedate"]
        approve.apply(r["proposals"], [], source="test")  # nothing chosen
        self.assertEqual(MemoryBoard(self.board.path).issue(key)["fields"]["duedate"], before)
        approve.apply(r["proposals"], [0], source="test")  # approve the first proposal only
        self.assertEqual(MemoryBoard(self.board.path).issue(key)["fields"]["duedate"], self.NEW_DUE)

    def test_the_approval_is_recorded(self):
        key = self._key()
        r = self._ingest_memo()
        approve.apply(r["proposals"], [0], source="memo")
        with open(approve.LOG, encoding="utf-8") as f:
            self.assertIn(key, f.read())

    def test_the_schedule_is_recomputed_after_it_is_applied(self):
        r = self._ingest_memo()
        before = tools.analyze_schedule(today=TODAY.isoformat())["predicted_finish"]
        approve.apply(r["proposals"], [0], source="test")
        tools._j = MemoryBoard(self.board.path)  # read the board again
        self.assertIsInstance(
            tools.analyze_schedule(today=TODAY.isoformat())["predicted_finish"], str
        )
        self.assertIsInstance(before, str)

    def _ingest_memo(self):
        """A note that pushes one task's due date out, naming it the way a person would."""
        tasks = tools._fetch()
        caller = caller_returning(
            {
                "updates": [
                    {
                        "task": self.MEMO_TASK,
                        "duedate": self.NEW_DUE,
                        "note": "held up by an external API spec change",
                        "confidence": 0.9,
                    }
                ],
                "notes": ["team sync cancelled next week"],
                "questions": [],
            }
        )
        return ingest.ingest("meeting note", tasks=tasks, today=TODAY, caller=caller)


class TestBackendSelection(unittest.TestCase):
    def test_an_environment_variable_selects_the_local_board(self):
        keep, tools._j = os.environ.get("PMO_BACKEND"), None
        os.environ["PMO_BACKEND"] = "memory"
        try:
            self.assertIsInstance(tools.jira(), MemoryBoard)
        finally:
            tools._j = None
            os.environ.pop("PMO_BACKEND", None)
            if keep:
                os.environ["PMO_BACKEND"] = keep


if __name__ == "__main__":
    unittest.main(verbosity=2)
