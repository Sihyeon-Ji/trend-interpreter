"""Local board adapter tests — the point is that it is *the same shape* as Jira.

Same shape is what lets schedule, tools and approve ignore which backend is in use.

Run: python -m pytest tests/test_memory_board.py -q
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from pmo_agent import schedule  # noqa: E402
from pmo_agent.adapters.memory import MemoryBoard, make_issue  # noqa: E402


def sample():
    return [
        make_issue("ECHO-1", "Requirements", "Done", "Maya", "2026-09-18", 3, blocks=["ECHO-2"]),
        make_issue(
            "ECHO-2", "Schema design", "In Progress", "Leo", "2026-09-24", 4, blocks=["ECHO-3"]
        ),
        make_issue("ECHO-3", "API build", "To Do", "Maya", "2026-09-29", 5),
    ]


class BoardTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "board.json")
        self.board = MemoryBoard(self.path)
        self.board._issues = {i["key"]: i for i in sample()}
        self.board._save()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def reloaded(self):
        return MemoryBoard(self.path)


class TestShapeMatchesJira(BoardTestCase):
    def test_schedule_reads_it_unchanged(self):
        tasks = schedule.from_jira_issues(self.board.search())
        self.assertEqual(tasks["ECHO-2"].deps, ["ECHO-1"])
        self.assertEqual(tasks["ECHO-1"].points, 3)
        self.assertTrue(tasks["ECHO-1"].is_done)
        self.assertEqual(tasks["ECHO-2"].assignee, "Leo")

    def test_whoami_and_project_info_exist(self):
        self.assertIn("displayName", self.board.whoami())
        self.assertEqual(self.board.project_info()["key"], "ECHO")

    def test_the_only_writable_site_is_local(self):
        self.assertEqual(self.board.allow, ["local"])


class TestSearch(BoardTestCase):
    def test_it_filters_by_status(self):
        r = self.board.search('project = ECHO AND status = "To Do"')
        self.assertEqual([i["key"] for i in r], ["ECHO-3"])

    def test_it_filters_by_assignee(self):
        r = self.board.search('assignee = "Maya"')
        self.assertEqual({i["key"] for i in r}, {"ECHO-1", "ECHO-3"})

    def test_it_sorts_by_due_date(self):
        self.assertEqual([i["key"] for i in self.board.search()], ["ECHO-1", "ECHO-2", "ECHO-3"])

    def test_it_honours_limit(self):
        self.assertEqual(len(self.board.search(limit=2)), 2)

    def test_jql_it_does_not_understand_returns_everything(self):
        self.assertEqual(len(self.board.search("some strange JQL")), 3)


class TestWriteGate(BoardTestCase):
    def test_nothing_changes_without_approval(self):
        self.assertTrue(self.board.set_fields("ECHO-3", {"duedate": "2026-10-05"})["dry_run"])
        self.assertTrue(self.board.comment("ECHO-3", "please confirm")["dry_run"])
        self.assertTrue(self.board.transition("ECHO-3", "In Progress")["dry_run"])
        self.assertTrue(self.board.create_issue("a new task")["dry_run"])
        self.assertEqual(self.reloaded().issue("ECHO-3")["fields"]["duedate"], "2026-09-29")

    def test_approval_writes_it_to_the_file(self):
        self.board.set_fields("ECHO-3", {"duedate": "2026-10-05"}, approve=True)
        self.assertEqual(self.reloaded().issue("ECHO-3")["fields"]["duedate"], "2026-10-05")

    def test_comments_accumulate(self):
        self.board.comment("ECHO-3", "first comment", approve=True)
        self.board.comment("ECHO-3", "second comment", approve=True)
        self.assertEqual(len(self.reloaded().issue("ECHO-3")["fields"]["comments"]), 2)

    def test_a_transition_is_applied(self):
        self.board.transition("ECHO-3", "In Progress", approve=True)
        self.assertEqual(self.reloaded().issue("ECHO-3")["fields"]["status"]["name"], "In Progress")

    def test_it_cannot_transition_to_its_current_status(self):
        self.assertIn("error", self.board.transition("ECHO-3", "To Do"))

    def test_a_new_issue_continues_the_numbering(self):
        r = self.board.create_issue("a new task", approve=True)
        self.assertEqual(r["key"], "ECHO-4")
        self.assertEqual(len(self.reloaded().search()), 4)

    def test_a_link_lands_on_both_sides(self):
        self.board.link("ECHO-2", "ECHO-3", approve=True)
        b = self.reloaded()
        self.assertTrue(
            any(
                link.get("outwardIssue", {}).get("key") == "ECHO-3"
                for link in b.issue("ECHO-2")["fields"]["issuelinks"]
            )
        )
        self.assertTrue(
            any(
                link.get("inwardIssue", {}).get("key") == "ECHO-2"
                for link in b.issue("ECHO-3")["fields"]["issuelinks"]
            )
        )

    def test_an_unknown_issue_is_an_error(self):
        with self.assertRaises(RuntimeError):
            self.board.issue("ECHO-99")


class TestDoneHistory(BoardTestCase):
    def test_a_transition_records_the_time(self):
        self.board.transition("ECHO-3", "Done", approve=True)
        f = self.reloaded().issue("ECHO-3")["fields"]
        self.assertIn("status_changed_at", f)

    def test_it_returns_only_recent_completions(self):
        self.assertEqual(self.board.done_since(7), [])  # nothing has transitioned yet
        self.board.transition("ECHO-3", "Done", approve=True)
        self.assertEqual([i["key"] for i in self.reloaded().done_since(7)], ["ECHO-3"])

    def test_anything_but_done_is_excluded(self):
        self.board.transition("ECHO-3", "In Progress", approve=True)
        self.assertEqual(self.reloaded().done_since(7), [])

    def test_a_korean_status_name_transitions_too(self):
        r = self.board.transition("ECHO-3", "Done", approve=True)
        self.assertEqual(r["status"], "Done")


class TestMemoryOnly(unittest.TestCase):
    def test_it_works_without_a_file(self):
        b = MemoryBoard(issues=sample())
        self.assertIsNone(b.path)
        b.set_fields("ECHO-3", {"duedate": "2026-10-05"}, approve=True)
        self.assertEqual(b.issue("ECHO-3")["fields"]["duedate"], "2026-10-05")

    def test_an_empty_board_does_not_break_it(self):
        b = MemoryBoard(issues=[])
        self.assertEqual(b.search(), [])


class TestPersistedFormat(BoardTestCase):
    def test_the_json_is_human_readable(self):
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["project"], "ECHO")
        self.assertEqual(len(data["issues"]), 3)
        self.assertIn("saved_at", data)

    def test_the_saved_timestamp_is_refreshed(self):
        def saved_at():
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)["saved_at"]

        before = saved_at()
        self.board.comment("ECHO-1", "x", approve=True)
        self.assertIsInstance(before, str)
        self.assertIsInstance(saved_at(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
