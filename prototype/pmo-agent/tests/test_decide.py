"""The options table — no network.

"Why did this stop" is a diagnosis, and a diagnosis does not help anybody *choose*.
Choosing is the work: accept the slip, hand it over, cut it. Each has a cost and nobody
computes them, because costing four options means running the schedule four times.

Two things here are worth defending in tests.

**The agent does not pick.** Cheapest on the calendar is not best — cutting scope always
wins on days and is usually the wrong answer — so there is no ranking and no
recommendation, and `chosen` is None on purpose.

**An option expires.** Handing over a task that is nearly done buys nobody anything, and
"we could still have moved it in September" is a sentence teams say every October.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt

from pmo_agent import decide, schedule

TODAY = dt.date(2026, 9, 21)


def tasks(rows=None):
    return schedule.to_tasks(
        rows
        or [
            # Ada is the bottleneck: A and D are independent but she can only do one at
            # a time, so moving A to Bo genuinely pulls the date in. B waits on A either
            # way, which is what makes "accept" cost somebody something.
            {
                "key": "A",
                "summary": "Auth",
                "assignee": "Ada",
                "points": 8,
                "duedate": "2026-09-25",
            },
            {"key": "B", "summary": "API", "assignee": "Ada", "points": 5, "deps": ["A"]},
            {"key": "D", "summary": "Billing", "assignee": "Ada", "points": 8},
            {"key": "C", "summary": "Docs", "assignee": "Bo", "points": 1},
        ]
    )


class TestTheOptionsAreLaidOutNotChosen:
    def test_every_option_is_costed_against_doing_nothing(self):
        got = decide.options(tasks(), "A", TODAY)
        assert got["finish_now"]
        assert all("finish" in o and "gain_days" in o for o in got["options"])

    def test_the_three_choices_are_all_there(self):
        got = decide.options(tasks(), "A", TODAY)
        assert {o["option"] for o in got["options"]} == {"accept", "hand_over", "cut"}

    def test_the_agent_says_plainly_that_it_did_not_pick(self):
        # The thing an agent is most tempted to do here
        got = decide.options(tasks(), "A", TODAY)
        assert got["chosen"] is None
        assert "does not pick" in got["why_not_chosen"]

    def test_they_are_not_ranked_by_cheapest(self):
        # Cutting scope always wins on days and is usually the wrong answer
        got = decide.options(tasks(), "A", TODAY)
        order = [o["option"] for o in got["options"]]
        assert order[0] == "accept", "doing nothing is the baseline, listed first"
        assert order[-1] == "cut", "the most disruptive is last, not first"

    def test_an_unknown_task_is_refused_with_the_keys_it_does_know(self):
        got = decide.options(tasks(), "NOPE", TODAY)
        assert "unknown task" in got["error"] and got["available"]


class TestWhatEachOptionCosts:
    def test_accepting_a_slip_names_whose_work_moves(self):
        got = decide.options(tasks(), "A", TODAY, slip=10)
        accept = next(o for o in got["options"] if o["option"] == "accept")
        assert [b["key"] for b in accept["breaks"]] == ["B"]
        assert accept["breaks"][0]["owner"] == "Ada"

    def test_accepting_never_expires(self):
        got = decide.options(tasks(), "A", TODAY)
        assert next(o for o in got["options"] if o["option"] == "accept")["expires"] == ""

    def test_cutting_names_what_would_depend_on_nothing(self):
        got = decide.options(tasks(), "A", TODAY)
        cut = next(o for o in got["options"] if o["option"] == "cut")
        assert cut["orphans"] == 1 and cut["breaks"][0]["key"] == "B"
        assert "depending on nothing" in got["note"]

    def test_cutting_something_nothing_depends_on_orphans_nobody(self):
        got = decide.options(tasks(), "C", TODAY)
        assert next(o for o in got["options"] if o["option"] == "cut")["orphans"] == 0

    def test_a_handover_names_the_person_who_has_to_agree(self):
        got = decide.options(tasks(), "A", TODAY)
        hand = next((o for o in got["options"] if o["option"] == "hand_over"), None)
        assert hand and hand["needs"] == "Bo"


class TestAnOptionExpires:
    def test_a_handover_carries_the_day_it_stops_being_worth_it(self):
        got = decide.options(tasks(), "A", TODAY)
        hand = next(o for o in got["options"] if o["option"] == "hand_over")
        assert hand["expires"] > TODAY.isoformat()

    def test_the_note_says_when_the_door_closes(self):
        got = decide.options(tasks(), "A", TODAY)
        assert "gone after" in got["note"]

    def test_nearly_finished_work_is_not_worth_moving(self):
        nearly = tasks()
        nearly["A"].points = 0.2
        got = decide.options(nearly, "A", TODAY)
        hand = next((o for o in got["options"] if o["option"] == "hand_over"), None)
        assert hand is None or hand["gain_days"] < decide.WORTH_DAYS

    def test_the_expiry_never_runs_past_the_horizon(self):
        huge = tasks()
        huge["A"].points = 400
        got = decide.options(huge, "A", TODAY)
        hand = next((o for o in got["options"] if o["option"] == "hand_over"), None)
        if hand and hand["expires"]:
            assert hand["expires"] <= schedule.add_workdays(TODAY, decide.HORIZON).isoformat()


class TestVetting:
    def test_a_handover_to_somebody_unsuitable_is_not_offered(self):
        got = decide.options(tasks(), "A", TODAY, can_take=lambda task, who: False)
        assert not any(o["option"] == "hand_over" for o in got["options"])
        assert got["vetted"] is True

    def test_without_a_check_the_table_says_it_was_not_vetted(self):
        got = decide.options(tasks(), "A", TODAY)
        assert got["vetted"] is False
        assert "not checked against who has worked where" in got["note"]

    def test_with_a_check_that_passes_it_does_not_add_the_caveat(self):
        got = decide.options(tasks(), "A", TODAY, can_take=lambda task, who: True)
        assert "not checked" not in got["note"]

    def test_when_nobody_can_take_it_the_note_says_so(self):
        got = decide.options(tasks(), "A", TODAY, can_take=lambda task, who: False)
        assert "None of the other" in got["note"]


class TestDeadlines:
    def test_the_soonest_to_close_comes_first(self):
        got = decide.deadlines(tasks(), TODAY)
        left = [d["days_left"] for d in got["decisions"]]
        assert left == sorted(left)

    def test_each_one_says_what_it_buys_and_by_when(self):
        got = decide.deadlines(tasks(), TODAY)
        for row in got["decisions"]:
            assert row["buys_days"] >= decide.WORTH_DAYS
            assert row["expires"] and row["decision"]

    def test_a_board_with_nothing_urgent_says_so_rather_than_inventing_urgency(self):
        calm = schedule.to_tasks(
            [
                {
                    "key": "X",
                    "summary": "Later",
                    "assignee": "Ada",
                    "points": 1,
                    "duedate": "2027-12-31",
                }
            ]
        )
        got = decide.deadlines(calm, TODAY)
        assert got["decisions"] == []
        assert "Nothing here is urgent" in got["note"]

    def test_the_note_names_the_one_closing_soonest(self):
        got = decide.deadlines(tasks(), TODAY)
        if got["decisions"]:
            assert got["decisions"][0]["key"] in got["note"]


class TestItNeverDecides:
    def test_no_model_is_involved(self):
        source = __import__("inspect").getsource(decide)
        for word in ("llm", "gemini", "generate(", "caller"):
            assert word not in source.lower(), word

    def test_nothing_is_applied(self):
        source = __import__("inspect").getsource(decide)
        assert "approve" not in source and "transition(" not in source

    def test_the_original_tasks_are_never_edited(self):
        # Every option is a what-if on a copy; the board must come back untouched
        original = tasks()
        before = {k: (t.assignee, t.points, list(t.deps)) for k, t in original.items()}
        decide.options(original, "A", TODAY)
        after = {k: (t.assignee, t.points, list(t.deps)) for k, t in original.items()}
        assert before == after
