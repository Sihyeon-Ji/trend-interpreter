"""Tool-layer unit tests — a fake Jira is slotted in, so no credentials are needed.

Run: python -m pytest tests/test_tools.py -q
"""

from __future__ import annotations

import datetime as dt
import inspect
import json
import unittest

from pmo_agent import tools  # noqa: E402

TODAY = "2026-09-21"  # a Monday


def issue(key, summary="", status="To Do", assignee=None, duedate=None, points=None, blocks=()):
    """Imitate one Jira search() issue. blocks = the keys this issue holds up."""
    return {
        "key": key,
        "fields": {
            "summary": summary or key,
            "status": {"name": status},
            "assignee": {"displayName": assignee} if assignee else None,
            "duedate": duedate,
            "customfield_10016": points,
            "issuelinks": [
                {"type": {"name": "Blocks"}, "outwardIssue": {"key": k}} for k in blocks
            ],
        },
    }


SAMPLE = [
    issue("ECHO-1", "Requirements", "Done", "Kim", points=3, blocks=["ECHO-2"]),
    issue(
        "ECHO-2",
        "Schema design",
        "In Progress",
        "Lee",
        duedate="2026-09-24",
        points=4,
        blocks=["ECHO-3"],
    ),
    issue("ECHO-3", "API build", "To Do", "Park", duedate="2026-09-29", points=5),
]


class FakeJira:
    """The stub that stands in for a real Jira. Writes are recorded, never executed."""

    project = "ECHO"

    def __init__(self, issues=None):
        self.issues = SAMPLE if issues is None else issues
        self.calls = []

    def search(self, jql=None, limit=100):
        self.calls.append(("search", jql, limit))
        return self.issues[:limit]

    def issue(self, key):
        self.calls.append(("issue", key))
        return next(i for i in self.issues if i["key"] == key)

    def comment(self, key, text, approve=False):
        self.calls.append(("comment", key, text, approve))
        return {"dry_run": not approve, "would_comment_on": key, "text": text}

    def set_fields(self, key, fields, approve=False):
        self.calls.append(("set_fields", key, fields, approve))
        return {"dry_run": not approve, "issue": key, "would_set": fields}

    def transition(self, key, to_name, approve=False):
        self.calls.append(("transition", key, to_name, approve))
        return {"dry_run": not approve, "issue": key, "would_transition_to": to_name}


class ToolTestCase(unittest.TestCase):
    """Slot in a fake Jira for each test and put it back afterwards."""

    issues = None

    def setUp(self):
        self.fake = FakeJira(self.issues)
        tools.pin(board=self.fake)

    def tearDown(self):
        tools.pin(board=None)


class TestDeclarations(ToolTestCase):
    def test_every_declaration_has_an_implementation(self):
        self.assertEqual({d["name"] for d in tools.DECLARATIONS}, set(tools.REGISTRY))

    def test_the_declared_parameters_exist_in_the_real_signature(self):
        for d in tools.DECLARATIONS:
            params = inspect.signature(tools.REGISTRY[d["name"]]).parameters
            for name in d["parameters"].get("properties", {}):
                self.assertIn(
                    name, params, f"{d['name']} declares an argument that is not there: {name}"
                )
            for name in d["parameters"].get("required", []):
                self.assertIn(name, params)

    def test_write_tools_are_exposed_only_as_propose_(self):
        names = set(tools.REGISTRY)
        self.assertFalse({n for n in names if n.startswith(("create_", "update_", "delete_"))})
        self.assertEqual(
            {n for n in names if "propose" in n},
            {"propose_comment", "propose_field_update", "propose_transition"},
        )


class TestListTasks(ToolTestCase):
    def test_it_returns_the_dependencies_too(self):
        rows = {t["key"]: t for t in tools.list_tasks()["tasks"]}
        self.assertEqual(rows["ECHO-2"]["deps"], ["ECHO-1"])
        self.assertEqual(rows["ECHO-3"]["deps"], ["ECHO-2"])
        self.assertEqual(rows["ECHO-1"]["deps"], [])

    def test_the_filters_reach_the_jql(self):
        tools.list_tasks(status="In Progress", assignee="Lee")
        jql = self.fake.calls[0][1]
        self.assertIn('status = "In Progress"', jql)
        self.assertIn('assignee = "Lee"', jql)


class TestAnalyzeSchedule(ToolTestCase):
    def test_it_computes_the_critical_path_and_the_risks(self):
        r = tools.analyze_schedule(today=TODAY)
        self.assertEqual(r["critical_path"], ["ECHO-1", "ECHO-2", "ECHO-3"])
        self.assertEqual(r["done"], 1)
        self.assertEqual(r["total"], 3)
        self.assertTrue(r["risks"])

    def test_it_serialises_straight_to_json(self):
        json.dumps(tools.analyze_schedule(today=TODAY), ensure_ascii=False)

    def test_each_risk_carries_its_evidence(self):
        r = tools.analyze_schedule(today=TODAY)
        self.assertTrue(all(x["reasons"] for x in r["risks"]))

    def test_an_empty_reference_date_means_today(self):
        self.assertEqual(tools.analyze_schedule()["today"], dt.date.today().isoformat())


class TestEmptyProject(ToolTestCase):
    issues = []

    def test_no_tasks_comes_back_as_an_error(self):
        self.assertIn("error", tools.analyze_schedule(today=TODAY))


class TestCycle(ToolTestCase):
    issues = [issue("A", blocks=["B"]), issue("B", blocks=["A"])]

    def test_a_cycle_comes_back_as_an_error_not_an_exception(self):
        r = tools.analyze_schedule(today=TODAY)
        self.assertIn("error", r)
        self.assertIn("hint", r)

    def test_the_simulation_behaves_the_same_way(self):
        self.assertIn("error", tools.simulate_delay("A", 2, today=TODAY))


class TestSimulateDelay(ToolTestCase):
    def test_downstream_tasks_and_the_project_finish_move_together(self):
        r = tools.simulate_delay("ECHO-2", 3, today=TODAY)
        moved = {x["key"]: x["slip_days"] for x in r["affected"]}
        self.assertEqual(moved["ECHO-2"], 3)
        self.assertEqual(moved["ECHO-3"], 3)
        self.assertNotEqual(r["project_finish_before"], r["project_finish_after"])

    def test_it_marks_the_tasks_whose_due_date_breaks(self):
        r = tools.simulate_delay("ECHO-2", 3, today=TODAY)
        self.assertTrue(next(x for x in r["affected"] if x["key"] == "ECHO-3")["breaks_duedate"])

    def test_dates_come_back_as_iso_strings(self):
        r = tools.simulate_delay("ECHO-2", 1, today=TODAY)
        self.assertIsInstance(r["project_finish_after"], str)
        json.dumps(r, ensure_ascii=False)

    def test_an_unknown_key_comes_back_with_candidates(self):
        r = tools.simulate_delay("NOPE", 1, today=TODAY)
        self.assertIn("error", r)
        self.assertIn("ECHO-1", r["available"])


class TestWriteGate(ToolTestCase):
    def test_a_comment_is_called_without_approval(self):
        r = tools.propose_comment("ECHO-2", "could you confirm the schedule")
        self.assertTrue(r["dry_run"])
        self.assertEqual(
            self.fake.calls[-1], ("comment", "ECHO-2", "could you confirm the schedule", False)
        )

    def test_a_field_change_is_called_without_approval(self):
        r = tools.propose_field_update("ECHO-3", duedate="2026-10-02")
        self.assertTrue(r["dry_run"])
        self.assertIs(self.fake.calls[-1][-1], False)
        self.assertEqual(r["would_set"], {"duedate": "2026-10-02"})

    def test_a_transition_is_called_without_approval(self):
        self.assertTrue(tools.propose_transition("ECHO-3", "In Progress")["dry_run"])
        self.assertIs(self.fake.calls[-1][-1], False)

    def test_no_read_tool_ever_calls_a_write(self):
        tools.list_tasks()
        tools.analyze_schedule(today=TODAY)
        tools.simulate_delay("ECHO-2", 1, today=TODAY)
        self.assertEqual({c[0] for c in self.fake.calls}, {"search"})


class TestDispatch(ToolTestCase):
    def test_an_unknown_tool_name_is_an_error(self):
        self.assertIn("error", tools.dispatch("no_such_tool", {}))

    def test_it_swallows_the_exception_and_returns_an_error(self):
        self.assertIn(
            "error", tools.dispatch("simulate_delay", {"key": "ECHO-2", "days": "not a number"})
        )

    def test_calling_with_no_arguments_does_not_kill_it(self):
        self.assertIn("count", tools.dispatch("list_tasks", None))

    def test_a_normal_call_passes_straight_through(self):
        self.assertEqual(tools.dispatch("analyze_schedule", {"today": TODAY})["total"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestTheRepositoryIsReadOnce:
    """One question, one reading.

    A live demo took three separate snapshots of the same repository and paid for all
    three. Speed is the obvious reason to stop doing that; consistency is the better one.
    "The board disagrees with the code" and "why did this stop" are halves of one answer,
    and reading twice lets a commit that lands in between appear in one half and not the
    other, with nothing to say so.

    It is remembered for a minute, not for good — a dashboard left open still moves.
    """

    def counter(self, monkeypatch):
        """Replace the repository with something that counts how often it is read."""
        seen = {"n": 0}

        class Counting:
            def snapshot(self, limit=100, with_files=False):
                seen["n"] += 1
                return {"commits": [], "pulls": [], "reading": seen["n"]}

        monkeypatch.setattr(tools, "repo", lambda *_a, **_k: Counting())
        tools.forget_snapshot()
        return seen

    def test_two_reads_in_a_row_are_one_reading(self, monkeypatch):
        seen = self.counter(monkeypatch)
        first, second = tools._snapshot(10), tools._snapshot(10)
        assert seen["n"] == 1
        assert first["reading"] == second["reading"] == 1

    def test_a_different_question_gets_its_own_reading(self, monkeypatch):
        seen = self.counter(monkeypatch)
        tools._snapshot(10)
        tools._snapshot(50)
        assert seen["n"] == 2

    def test_it_is_forgotten_once_the_time_is_up(self, monkeypatch):
        seen = self.counter(monkeypatch)
        monkeypatch.setattr(tools, "_ttl", lambda: 0.0)
        tools._snapshot(10)
        tools._snapshot(10)
        assert seen["n"] == 2, "a zero lifetime should mean no memory at all"

    def test_forgetting_it_on_purpose_forces_a_fresh_one(self, monkeypatch):
        seen = self.counter(monkeypatch)
        tools._snapshot(10)
        tools.forget_snapshot()
        tools._snapshot(10)
        assert seen["n"] == 2

    def test_the_lifetime_comes_from_the_environment(self, monkeypatch):
        monkeypatch.setattr(tools, "env", lambda k, d="": "5" if k == "REPO_SNAPSHOT_TTL" else d)
        assert tools._ttl() == 5.0

    def test_a_lifetime_that_is_not_a_number_falls_back(self, monkeypatch):
        # A typo in .env should slow the agent down, not stop it
        monkeypatch.setattr(
            tools, "env", lambda k, d="": "a while" if k == "REPO_SNAPSHOT_TTL" else d
        )
        assert tools._ttl() == float(tools.SNAPSHOT_TTL)
