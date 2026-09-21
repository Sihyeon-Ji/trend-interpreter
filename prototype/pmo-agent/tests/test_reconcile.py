"""Meeting notes against the board — no network, fake model responses.

The job being replaced is a person reading minutes, working out which ticket each
paragraph is about, opening the board and editing only the ones that differ. So the tests
are mostly about the "only the ones that differ" half, which is the part that makes this
worth using: twenty notes are usually two proposals, and finding those two is the tedium.

The other half is refusal. A note carries no ticket key, so every link is inferred, and an
inference that is not clear enough has to become a question rather than an edit.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json

from pmo_agent import reconcile, schedule

TODAY = dt.date(2026, 9, 21)


def tasks(rows=None):
    return schedule.to_tasks(
        rows
        or [
            {
                "key": "ECHO-1",
                "summary": "Authentication",
                "assignee": "Ada",
                "status": "To Do",
                "duedate": "2026-09-02",
            },
            {
                "key": "ECHO-2",
                "summary": "Search ranking",
                "assignee": "Bo",
                "status": "In Progress",
                "duedate": "2026-09-30",
            },
        ]
    )


def note(body, title="Team sync", author="Ada", date="2026-09-15"):
    return {"title": title, "body": body, "author": author, "date": date}


def envelope(payload):
    """The shape Gemini actually returns, which is what `ingest.parse` is given."""
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}]
    }


def model(updates, notes=()):
    """Stand in for the model: it returns what it claims the note says."""

    def call(parts, system=""):
        return envelope({"updates": list(updates), "notes": list(notes)})

    return call


def says(key="ECHO-1", **fields):
    return {"task": key, "confidence": 0.9, **fields}


class TestOnlyTheDifferences:
    def test_a_new_date_the_board_lacks_becomes_a_proposal(self):
        got = reconcile.review(
            [note("Authentication is pushed to the 28th")],
            tasks(),
            TODAY,
            caller=model([says(duedate="2026-09-28")]),
        )
        assert [c["key"] for c in got["changes"]] == ["ECHO-1"]
        assert got["changes"][0]["duedate"] == "2026-09-28"
        assert got["changes"][0]["duedate_was"] == "2026-09-02"

    def test_a_date_the_board_already_has_produces_nothing(self):
        # The common case, and the reason this is worth running: silence is the answer
        got = reconcile.review(
            [note("Authentication is still due on the 2nd")],
            tasks(),
            TODAY,
            caller=model([says(duedate="2026-09-02")]),
        )
        assert got["changes"] == []
        assert got["proposals"] == []
        assert "Nothing" in got["note"]

    def test_a_status_the_board_already_has_produces_nothing(self):
        got = reconcile.review(
            [note("Authentication has not started")],
            tasks(),
            TODAY,
            caller=model([says(status="To Do")]),
        )
        assert got["changes"] == []

    def test_a_status_that_only_differs_in_spelling_is_not_news(self):
        # Boards spell the same state a dozen ways; schedule.status_alike knows that
        got = reconcile.review(
            [note("Authentication is still to do")],
            tasks(),
            TODAY,
            caller=model([says(status="to do")]),
        )
        assert got["changes"] == []

    def test_a_real_status_change_does_come_through(self):
        got = reconcile.review(
            [note("Authentication is done")],
            tasks(),
            TODAY,
            caller=model([says(status="Done")]),
        )
        assert got["changes"][0]["status"] == "Done"
        assert got["changes"][0]["status_was"] == "To Do"

    def test_the_date_and_the_status_can_both_be_news_at_once(self):
        got = reconcile.review(
            [note("Authentication started, and it moves to the 28th")],
            tasks(),
            TODAY,
            caller=model([says(status="In Progress", duedate="2026-09-28")]),
        )
        assert {"status", "duedate"} <= set(got["changes"][0])


class TestItCarriesItsEvidence:
    def test_every_change_names_the_note_it_came_from(self):
        got = reconcile.review(
            [note("Authentication is pushed to the 28th", author="Maya", date="2026-09-16")],
            tasks(),
            TODAY,
            caller=model([says(duedate="2026-09-28")]),
        )
        row = got["changes"][0]
        assert "Maya" in row["evidence"] and "2026-09-16" in row["evidence"]
        assert "pushed to the 28th" in row["quote"]
        assert row["coverage"] >= reconcile.MENTION

    def test_it_says_what_applying_would_do_to_the_schedule(self):
        got = reconcile.review(
            [note("Authentication is pushed to the 28th")],
            tasks(),
            TODAY,
            caller=model([says(duedate="2026-09-28")]),
        )
        assert got["impact"]["predicted_finish_before"]
        assert got["applied"] is False


class TestWhatItRefuses:
    def test_a_note_that_fits_two_tasks_is_left_alone(self):
        # "search" appears in both, so neither wins by the margin
        both = schedule.to_tasks(
            [
                {"key": "A", "summary": "Search ranking", "status": "To Do"},
                {"key": "B", "summary": "Search indexing", "status": "To Do"},
            ]
        )
        got = reconcile.review(
            [note("Search moves to next sprint")],
            both,
            TODAY,
            caller=model([says("A", status="Done")]),
        )
        assert got["changes"] == []
        assert got["skipped"] and "best_coverage" in got["skipped"][0]
        assert "could not be tied" in got["note"]

    def test_a_note_about_nothing_on_the_board_is_left_alone(self):
        got = reconcile.review(
            [note("We ordered new laptops")], tasks(), TODAY, caller=model([says(status="Done")])
        )
        assert got["changes"] == []

    def test_a_claim_about_a_different_task_is_not_taken_as_evidence(self):
        # The model may be right, but this note is not the evidence for it
        got = reconcile.review(
            [note("Authentication is blocked")],
            tasks(),
            TODAY,
            caller=model([says("ECHO-2", status="Done")]),
        )
        assert got["changes"] == []
        assert got["skipped"][0]["claimed"] == "ECHO-2"
        assert got["skipped"][0]["matched"] == "ECHO-1"

    def test_a_question_from_the_reader_survives_with_its_source(self):
        got = reconcile.review(
            [note("Authentication is pushed", author="Leo")],
            tasks(),
            TODAY,
            caller=model([{"task": "whatever that thing was", "confidence": 0.4}]),
        )
        assert got["questions"] and "Leo" in got["questions"][0]

    def test_one_unreadable_note_does_not_take_the_others_down(self):
        calls = {"n": 0}

        def flaky(parts, system=""):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("the model call failed")
            return envelope({"updates": [says(duedate="2026-09-28")], "notes": []})

        got = reconcile.review(
            [
                note("Authentication is broken", date="2026-09-17"),
                note("Authentication is pushed to the 28th", date="2026-09-16"),
            ],
            tasks(),
            TODAY,
            caller=flaky,
        )
        assert len(got["changes"]) == 1
        assert any("error" in s for s in got["skipped"])

    def test_nothing_is_ever_applied_here(self):
        source = __import__("inspect").getsource(reconcile)
        assert "approve=True" not in source
        assert "confirm" not in source


class TestTheWindow:
    def test_notes_older_than_the_window_are_not_reconciled(self):
        # Past a few weeks the board has moved on and the note is history, not news
        old = note("Authentication is pushed to the 28th", date="2026-07-01")
        got = reconcile.review([old], tasks(), TODAY, caller=model([says(duedate="2026-09-28")]))
        assert got["changes"] == []

    def test_a_note_dated_in_the_future_is_not_reconciled(self):
        ahead = note("Authentication is pushed", date="2027-01-01")
        assert reconcile.recent([ahead], TODAY) == []

    def test_the_newest_notes_are_read_first(self):
        rows = [note("a", date="2026-09-10"), note("b", date="2026-09-18")]
        assert [n["body"] for n in reconcile.recent(rows, TODAY)] == ["b", "a"]

    def test_an_unreadable_date_drops_the_note_rather_than_the_run(self):
        assert reconcile.recent([note("x", date="not a date")], TODAY) == []


class TestProposals:
    def test_the_changes_come_out_as_the_same_proposals_everything_else_uses(self):
        got = reconcile.review(
            [note("Authentication is pushed to the 28th")],
            tasks(),
            TODAY,
            caller=model([says(duedate="2026-09-28")]),
        )
        assert [p["tool"] for p in got["proposals"]] == ["propose_field_update"]
        assert got["proposals"][0]["args"] == {"key": "ECHO-1", "duedate": "2026-09-28"}

    def test_the_result_is_json(self):
        got = reconcile.review(
            [note("Authentication is pushed to the 28th")],
            tasks(),
            TODAY,
            caller=model([says(duedate="2026-09-28")]),
        )
        assert json.loads(json.dumps(got))["changes"]
