"""Board-against-code tests — they run with no network.

The two that matter most:
  1. does it actually catch the divergence (is what the repo seed planted detected)
  2. does it stay quiet without evidence (does it avoid calling "unknown" "nothing")

Run: python -m pytest tests/test_signals.py -q
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import unittest

from pmo_agent import schedule, signals  # noqa: E402
from pmo_agent.adapters.memory_repo import MemoryRepo  # noqa: E402
from pmo_agent.seeds import board as seed  # noqa: E402
from pmo_agent.seeds import repo as seed_repo

TODAY = dt.date(2026, 9, 21)


def tasks():
    return schedule.to_tasks(
        [
            {
                "key": "ECHO-1",
                "summary": "Requirements",
                "status": "Done",
                "assignee": "Ada",
                "points": 2,
            },
            {
                "key": "ECHO-2",
                "summary": "Schema",
                "status": "In Progress",
                "assignee": "Bo",
                "points": 3,
            },
            {"key": "ECHO-3", "summary": "API", "status": "To Do", "assignee": "Ada", "points": 3},
            {
                "key": "ECHO-4",
                "summary": "Docs",
                "status": "In Progress",
                "assignee": "Bo",
                "points": 1,
            },
        ]
    )


def commit(key, days_ago, author="Ada", email=None, login=None, name=None):
    d = TODAY - dt.timedelta(days=days_ago)
    return {
        "sha": "abc1234",
        "date": d.isoformat(),
        "author": author,
        "login": login,
        "name": name or author,
        "email": email or f"{author}@t.test",
        "message": f"{key} work",
        "url": f"https://x/commit/{key}",
    }


def pull(number, key, state="open", updated_days=0, draft=False, reviewers=()):
    return {
        "number": number,
        "title": f"{key} implementation",
        "state": state,
        "draft": draft,
        "author": "Bo",
        "branch": f"feat/{key.lower()}",
        "created": (TODAY - dt.timedelta(days=updated_days + 2)).isoformat(),
        "updated": (TODAY - dt.timedelta(days=updated_days)).isoformat(),
        "merged": False,
        "reviewers": list(reviewers),
        "url": f"https://x/pull/{number}",
    }


class TestKeyExtraction(unittest.TestCase):
    def test_it_pulls_a_key_out_of_a_sentence(self):
        self.assertEqual(signals.keys_in("ECHO-12 schema fix"), {"ECHO-12"})
        self.assertEqual(signals.keys_in("fix ECHO-1 and ECHO-22"), {"ECHO-1", "ECHO-22"})

    def test_it_catches_lower_case_too(self):
        self.assertEqual(signals.keys_in("feat/echo-7 work"), {"ECHO-7"})

    def test_it_ignores_things_that_are_not_keys(self):
        self.assertEqual(signals.keys_in("version 1-2 update"), set())
        self.assertEqual(signals.keys_in(""), set())


class TestLink(unittest.TestCase):
    def test_it_links_by_commit_message(self):
        linked = signals.link(tasks(), [commit("ECHO-2", 1)], [])
        self.assertEqual(len(linked["ECHO-2"]["commits"]), 1)
        self.assertEqual(linked["ECHO-1"]["commits"], [])

    def test_it_links_by_pull_request_title_and_branch(self):
        linked = signals.link(tasks(), [], [pull(1, "ECHO-3")])
        self.assertEqual(len(linked["ECHO-3"]["pulls"]), 1)

    def test_it_drops_keys_that_are_not_on_the_board(self):
        linked = signals.link(tasks(), [commit("ECHO-99", 1)], [])
        self.assertNotIn("ECHO-99", linked)
        self.assertTrue(all(not v["commits"] for v in linked.values()))


class TestMismatches(unittest.TestCase):
    def find(self, ms, kind, key=None):
        return [m for m in ms if m["kind"] == kind and (key is None or m["key"] == key)]

    def test_done_but_the_pull_request_is_open(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [], [pull(1, "ECHO-1")]), TODAY)
        self.assertTrue(self.find(ms, "done_with_open_pr", "ECHO-1"))

    def test_in_progress_but_the_commits_are_old(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-2", 9)], []), TODAY)
        m = self.find(ms, "stalled", "ECHO-2")
        self.assertTrue(m)
        self.assertIn("9 days ago", m[0]["detail"])

    def test_a_recent_commit_is_not_a_stall(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-2", 1)], []), TODAY)
        self.assertFalse(self.find(ms, "stalled"))

    def test_to_do_but_there_are_commits(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-3", 1)], []), TODAY)
        self.assertTrue(self.find(ms, "undeclared_progress", "ECHO-3"))

    def test_in_progress_with_no_commits_at_all(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-2", 1)], []), TODAY)
        self.assertTrue(self.find(ms, "no_code_activity", "ECHO-4"))

    def test_a_pull_request_waiting_on_review(self):
        t = tasks()
        ms = signals.mismatches(
            t,
            signals.link(
                t, [commit("ECHO-2", 1)], [pull(7, "ECHO-2", updated_days=4, reviewers=["Ada"])]
            ),
            TODAY,
        )
        m = self.find(ms, "review_waiting", "ECHO-2")
        self.assertTrue(m)
        self.assertIn("4 days", m[0]["detail"])
        self.assertIn("Ada", m[0]["detail"])

    def test_a_draft_pull_request_is_not_waiting_on_review(self):
        t = tasks()
        ms = signals.mismatches(
            t,
            signals.link(t, [commit("ECHO-2", 1)], [pull(8, "ECHO-2", updated_days=9, draft=True)]),
            TODAY,
        )
        self.assertFalse(self.find(ms, "review_waiting"))

    def test_it_hands_back_the_evidence_links(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [], [pull(1, "ECHO-1")]), TODAY)
        self.assertTrue(ms[0]["evidence"])

    def test_it_hands_back_the_owner_and_the_status(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-3", 1)], []), TODAY)
        m = self.find(ms, "undeclared_progress")[0]
        self.assertEqual(m["assignee"], "Ada")
        self.assertEqual(m["status"], "To Do")


class TestIdentityMerge(unittest.TestCase):
    """One person once split across a git name and a login, dragging concentration down."""

    def test_the_same_email_is_the_same_person(self):
        cs = [
            commit("ECHO-1", 1, email="a@t.test", login=None, name="shji"),
            commit("ECHO-1", 2, email="a@t.test", login="Sihyeon-Ji", name="Sihyeon Ji"),
        ]
        m = signals.merge_identities(cs)
        self.assertEqual(len(m), 1)
        row = next(iter(m.values()))
        self.assertEqual(row["commits"], 2)
        self.assertEqual(row["author"], "Sihyeon-Ji")  # the login becomes the display name
        self.assertIn("shji", row["aliases"])

    def test_different_emails_are_different_people(self):
        cs = [
            commit("ECHO-1", 1, email="a@t.test"),
            commit("ECHO-1", 1, email="b@t.test", author="Bo"),
        ]
        self.assertEqual(len(signals.merge_identities(cs)), 2)

    def test_concentration_rises_after_the_merge(self):
        cs = [
            commit("ECHO-1", 1, email="a@t.test", name="shji"),
            commit("ECHO-1", 1, email="a@t.test", login="Sihyeon-Ji"),
            commit("ECHO-1", 1, email="b@t.test", author="Bo"),
        ]
        team = signals.team_activity({"commits": cs, "pulls": [], "branches": []}, TODAY)
        self.assertEqual(team["concentration"], 0.67)


class TestTeamActivity(unittest.TestCase):
    def test_it_flags_work_piling_onto_one_person(self):
        cs = [commit("ECHO-1", 1) for _ in range(5)]
        t = signals.team_activity({"commits": cs, "pulls": [], "branches": []}, TODAY)
        self.assertEqual(t["concentration"], 1.0)
        self.assertTrue(any("one person" in n for n in t["notes"]))

    def test_no_pull_requests_means_no_review_process(self):
        t = signals.team_activity(
            {"commits": [commit("ECHO-1", 1)], "pulls": [], "branches": []}, TODAY
        )
        self.assertTrue(any("not a single pull request" in n for n in t["notes"]))

    def test_no_commits_is_a_signal_too(self):
        t = signals.team_activity({"commits": [], "pulls": [], "branches": []}, TODAY)
        self.assertTrue(any("no commits at all" in n for n in t["notes"]))

    def test_commits_outside_the_window_are_not_counted(self):
        cs = [commit("ECHO-1", 30), commit("ECHO-2", 1)]
        self.assertEqual(
            signals.team_activity({"commits": cs, "pulls": [], "branches": []}, TODAY)["commits"], 1
        )


class TestEvidenceRequired(unittest.TestCase):
    """Stay quiet without evidence — call "unknown" "nothing" and it is all noise."""

    def test_without_evidence_it_produces_no_task_signal(self):
        snap = {
            "repo": "x/y",
            "commits": [
                {
                    "sha": "1",
                    "date": TODAY.isoformat(),
                    "author": "nobody we know",
                    "login": None,
                    "name": "nobody we know",
                    "email": "a@t",
                    "message": "just a commit",
                    "url": "",
                }
            ],
            "pulls": [],
            "branches": ["main"],
        }
        s = signals.summary(tasks(), snap, TODAY)
        self.assertFalse(s["key_convention_in_use"])
        self.assertEqual(s["mismatches"], [])
        self.assertIn("absence of evidence", s["note"])

    def test_with_evidence_the_signal_appears(self):
        snap = {"repo": "x/y", "commits": [commit("ECHO-2", 9)], "pulls": [], "branches": []}
        s = signals.summary(tasks(), snap, TODAY)
        self.assertTrue(s["key_convention_in_use"])
        self.assertTrue(s["mismatches"])
        self.assertIsNone(s["note"])

    def test_repository_signals_do_not_depend_on_a_key_convention(self):
        snap = {"repo": "x/y", "commits": [], "pulls": [], "branches": []}
        self.assertTrue(signals.summary(tasks(), snap, TODAY)["team"]["notes"])


class TestMemoryRepo(unittest.TestCase):
    """It has to match the GitHub adapter's shape for signals to stay backend-agnostic."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "repo.json")
        seed_repo.write(self.path, TODAY)
        self.repo = MemoryRepo(self.path)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_the_snapshot_shape_matches(self):
        s = self.repo.snapshot()
        # `people` is what ties commit authors to board assignees
        self.assertEqual(set(s), {"repo", "info", "commits", "pulls", "branches", "people"})
        self.assertIn("default_branch", s["info"])

    def test_commits_come_back_newest_first(self):
        ds = [c["date"] for c in self.repo.commits(10)]
        self.assertEqual(ds, sorted(ds, reverse=True))

    def test_it_filters_pull_requests_by_state(self):
        self.assertTrue(all(p["state"] == "open" for p in self.repo.pulls("open")))

    def test_there_are_no_write_methods(self):
        for name in ("create_issue", "comment", "set_fields", "transition", "link", "push"):
            self.assertFalse(hasattr(self.repo, name), name)

    def test_a_missing_file_does_not_break_it(self):
        r = MemoryRepo(os.path.join(self.dir, "nope.json"))
        self.assertEqual(r.snapshot()["commits"], [])


class TestSeededRepo(unittest.TestCase):
    """Is the planted divergence really detected — this test is the demo's pre-flight check."""

    def setUp(self):
        self.data = seed_repo.build(TODAY)
        self.tasks = schedule.from_jira_issues(seed.build(TODAY))
        self.summary = signals.summary(self.tasks, self.data, TODAY)

    def test_the_same_seed_builds_the_same_repository(self):
        self.assertEqual(seed_repo.build(TODAY), seed_repo.build(TODAY))

    def test_it_links_without_any_key(self):
        # Real repositories carry no ticket key. Author, timing, vocabulary and path have to do it.
        self.assertFalse(self.summary["key_convention_in_use"])
        self.assertGreater(self.summary["linked_tasks"], 5)
        quality = self.summary["link_quality"]
        self.assertEqual(quality["by_key"], 0)
        self.assertGreater(quality["inferred"], 20)
        self.assertGreater(quality["mean_confidence"], 0.5)

    def test_every_planted_divergence_is_detected(self):
        found = {(m["key"], m["kind"]) for m in self.summary["mismatches"]}
        for p in self.data["planted"]:
            self.assertIn((p["key"], p["kind"]), found, f"{p['key']} {p['kind']} not detected")

    def test_all_four_kinds_show_up(self):
        kinds = {m["kind"] for m in self.summary["mismatches"]}
        self.assertEqual(
            kinds & {"stalled", "done_with_open_pr", "undeclared_progress", "review_waiting"},
            {"stalled", "done_with_open_pr", "undeclared_progress", "review_waiting"},
        )

    def test_only_fictional_people_appear(self):
        authors = {c["author"] for c in self.data["commits"]}
        self.assertEqual(authors, set(seed_repo.LOGIN.values()))

    def test_it_serialises_to_json(self):
        json.dumps(self.summary, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
