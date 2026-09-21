"""Approval gate unit tests — verified against a fake Jira, with no real writes.

One thing matters: is only what a person explicitly chose ever applied.

Run: python -m pytest tests/test_approve.py -q
"""

from __future__ import annotations

import contextlib
import inspect
import io
import json
import os
import tempfile
import unittest

from test_tools import FakeJira  # noqa: E402

from pmo_agent import approve, tools  # noqa: E402
from pmo_agent.adapters.jira import WriteBlocked  # noqa: E402

PROPOSALS = [
    {"tool": "propose_field_update", "args": {"key": "ECHO-2", "duedate": "2026-09-28"}},
    {
        "tool": "propose_comment",
        "args": {"key": "ECHO-2", "text": "due date moved, DB choice late"},
    },
    {"tool": "propose_transition", "args": {"key": "ECHO-3", "to_status": "In Progress"}},
    {"tool": "note", "args": {"text": "team sync cancelled"}},
]


def answers(*seq):
    """Something to slot in place of input() — it returns the given answers in order."""
    it = iter(seq)
    return lambda _prompt="": next(it, "")


class GateTestCase(unittest.TestCase):
    """Point the log at a temp file and slot in a fake Jira."""

    def setUp(self):
        self.fake = FakeJira()
        tools.pin(board=self.fake)
        self.dir = tempfile.mkdtemp()
        self.keep_log, approve.LOG = approve.LOG, os.path.join(self.dir, "approvals.jsonl")

    def tearDown(self):
        tools.pin(board=None)
        approve.LOG = self.keep_log

    def logged(self):
        if not os.path.exists(approve.LOG):
            return []
        with open(approve.LOG, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def run_gate(self, *inputs, proposals=None, impact=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = approve.gate(
                proposals if proposals is not None else PROPOSALS,
                impact,
                source="test",
                ask=answers(*inputs),
            )
        return out, buf.getvalue()


class TestModelCannotApprove(unittest.TestCase):
    """That the model cannot touch the approval path is this project's central safeguard."""

    def test_the_tool_layer_never_passes_approve_true(self):
        self.assertNotIn("approve=True", inspect.getsource(tools))

    def test_the_approve_functions_are_not_exposed_to_gemini(self):
        names = set(tools.REGISTRY) | {d["name"] for d in tools.DECLARATIONS}
        self.assertFalse(names & {"apply", "gate", "approve", "select"})

    def test_every_apply_function_is_called_with_approve_true(self):
        for name, fn in approve.APPLIERS.items():
            self.assertIn("approve=True", inspect.getsource(fn), name)


class TestSelect(unittest.TestCase):
    def test_enter_chooses_nothing(self):
        for s in ("", "  ", "n", "no", "q"):
            self.assertEqual(approve.select(s, 3), [], s)

    def test_it_takes_numbers(self):
        self.assertEqual(approve.select("1,3", 3), [0, 2])
        self.assertEqual(approve.select("2", 3), [1])

    def test_spaces_work_as_separators(self):
        self.assertEqual(approve.select("1 3", 3), [0, 2])

    def test_it_takes_a_range(self):
        self.assertEqual(approve.select("1-3", 3), [0, 1, 2])

    def test_only_all_approves_everything(self):
        self.assertEqual(approve.select("all", 3), [0, 1, 2])
        self.assertEqual(approve.select("a", 2), [0, 1])
        self.assertEqual(approve.select("y", 3), [])  # yes is not approve-everything

    def test_numbers_out_of_range_are_dropped(self):
        self.assertEqual(approve.select("0,5,2", 3), [1])

    def test_junk_input_chooses_nothing(self):
        self.assertEqual(approve.select("blah blah blah", 3), [])

    def test_duplicates_count_once(self):
        self.assertEqual(approve.select("2,2,2", 3), [1])


class TestRender(GateTestCase):
    def test_only_applicable_proposals_are_numbered(self):
        s = approve.render(PROPOSALS)
        self.assertIn("[ 1]", s)
        self.assertIn("[ 3]", s)
        self.assertNotIn("[ 4]", s)  # a note gets no number
        self.assertIn("not applied", s)

    def test_it_says_nothing_has_been_applied_yet(self):
        self.assertIn("nothing has been applied yet", approve.render(PROPOSALS))

    def test_it_shows_the_schedule_impact_too(self):
        s = approve.render(
            PROPOSALS,
            {
                "predicted_finish_before": "2026-10-02",
                "predicted_finish_after": "2026-10-07",
                "risks_before": 2,
                "risks_after": 3,
                "newly_at_risk": [{"key": "ECHO-5", "summary": "Integration tests"}],
            },
        )
        self.assertIn("2026-10-02 → 2026-10-07", s)
        self.assertIn("ECHO-5", s)

    def test_no_proposals_does_not_break_it(self):
        self.assertIn("nothing proposed", approve.render([]))


class TestApply(GateTestCase):
    def test_only_what_was_chosen_goes_out_with_approve_true(self):
        out = approve.apply(PROPOSALS, [0], jira=self.fake, source="t")
        self.assertEqual(out["applied"], 1)
        self.assertEqual(
            self.fake.calls[-1], ("set_fields", "ECHO-2", {"duedate": "2026-09-28"}, True)
        )

    def test_what_was_not_chosen_is_untouched(self):
        approve.apply(PROPOSALS, [0], jira=self.fake)
        self.assertEqual([c[0] for c in self.fake.calls], ["set_fields"])

    def test_a_note_has_no_number_and_is_never_applied(self):
        out = approve.apply(PROPOSALS, [0, 1, 2], jira=self.fake)
        self.assertEqual(out["applied"], 3)
        self.assertNotIn("note", [c[0] for c in self.fake.calls])

    def test_an_empty_choice_does_nothing(self):
        out = approve.apply(PROPOSALS, [], jira=self.fake)
        self.assertEqual((out["applied"], self.fake.calls), (0, []))

    def test_a_number_that_does_not_exist_is_recorded_as_a_failure(self):
        out = approve.apply(PROPOSALS, [99], jira=self.fake)
        self.assertEqual((out["applied"], out["failed"]), (0, 1))

    def test_one_failure_does_not_stop_the_rest(self):
        def boom(*a, **k):
            raise RuntimeError("Jira 500")

        self.fake.set_fields = boom
        out = approve.apply(PROPOSALS, [0, 1], jira=self.fake)
        self.assertEqual((out["applied"], out["failed"]), (1, 1))

    def test_a_blocked_write_is_recorded_as_an_incident(self):
        def blocked(*a, **k):
            raise WriteBlocked("cytur.atlassian.net is not in WRITE_ALLOWLIST")

        self.fake.set_fields = blocked
        out = approve.apply(PROPOSALS, [0], jira=self.fake, source="t")
        self.assertEqual(out["failed"], 1)
        rec = self.logged()[-1]
        self.assertTrue(rec["blocked"])
        self.assertIn("cytur", rec["error"])


class TestAuditLog(GateTestCase):
    def test_each_applied_change_gets_a_line(self):
        approve.apply(PROPOSALS, [0, 2], jira=self.fake, source="memo.json")
        rows = self.logged()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["source"] for r in rows}, {"memo.json"})
        self.assertTrue(all(r["ok"] and r["at"] for r in rows))

    def test_the_record_includes_the_arguments(self):
        approve.apply(PROPOSALS, [0], jira=self.fake)
        self.assertEqual(self.logged()[0]["args"], {"key": "ECHO-2", "duedate": "2026-09-28"})

    def test_nothing_applied_means_nothing_logged(self):
        approve.apply(PROPOSALS, [], jira=self.fake)
        self.assertEqual(self.logged(), [])


class TestGate(GateTestCase):
    def test_pressing_enter_applies_nothing(self):
        out, text = self.run_gate("")
        self.assertEqual(out["applied"], 0)
        self.assertEqual(self.fake.calls, [])
        self.assertIn("Nothing was applied", text)

    def test_choosing_a_number_still_needs_the_final_confirmation(self):
        out, text = self.run_gate("1", "nope")
        self.assertEqual(out["applied"], 0)
        self.assertEqual(self.fake.calls, [])
        self.assertIn("Cancelled", text)

    def test_only_yes_applies_it(self):
        out, _ = self.run_gate("1", "yes")
        self.assertEqual(out["applied"], 1)
        self.assertEqual(self.fake.calls[-1][-1], True)

    def test_it_shows_what_will_change_before_applying(self):
        _, text = self.run_gate("1", "no")
        self.assertIn("ECHO-2", text)
        self.assertIn("2026-09-28", text)

    def test_approve_everything_still_needs_confirmation(self):
        out, _ = self.run_gate("all", "yes")
        self.assertEqual(out["applied"], 3)

    def test_with_nothing_to_apply_it_does_not_even_ask(self):
        out, text = self.run_gate(proposals=[{"tool": "note", "args": {"text": "a note"}}])
        self.assertEqual(out["applied"], 0)
        self.assertNotIn("Really apply", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
