"""Operations metrics — no network.

Point the delivery code at a queue and the headline number is not wrong so much as
meaningless. A queue does not finish. So this module answers different questions from the
same board, and the tests are mostly about which questions those are.

The one that carries the most weight: **arriving and closing are a pair**. Forty closed is
good news or bad depending entirely on how many arrived, and a dashboard that shows one
without the other is a vanity metric.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt

from pmo_agent import health

TODAY = dt.date(2026, 9, 21)


def ticket(key, summary, created, resolved=None, status="In Progress", who="Ada"):
    fields = {
        "summary": summary,
        "status": {"name": "Done" if resolved else status},
        "assignee": {"displayName": who},
        "created": created,
    }
    if resolved:
        fields["resolutiondate"] = resolved
    return {"key": key, "fields": fields}


def days_ago(n):
    return (TODAY - dt.timedelta(days=n)).isoformat()


class TestKeepingUp:
    def test_closing_more_than_arrives_is_keeping_up(self):
        rows = [
            ticket("1", "a", days_ago(20), days_ago(5)),
            ticket("2", "b", days_ago(19), days_ago(4)),
            ticket("3", "c", days_ago(3)),
        ]
        got = health.summary(rows, TODAY)
        assert (got["arrived"], got["closed"]) == (1, 2)
        assert got["keeping_up"]

    def test_more_arriving_than_closing_is_not(self):
        rows = [ticket(str(i), "a", days_ago(2)) for i in range(5)]
        got = health.summary(rows, TODAY)
        assert not got["keeping_up"]
        assert "grew" in got["note"]

    def test_the_note_never_gives_one_number_without_the_other(self):
        # Forty closed is good or bad depending entirely on how many arrived
        rows = [ticket("1", "a", days_ago(3), days_ago(1)), ticket("2", "b", days_ago(2))]
        note = health.summary(rows, TODAY)["note"]
        assert "arrived" in note and "closed" in note

    def test_an_empty_board_says_there_is_no_queue(self):
        assert "no queue" in health.summary([], TODAY)["note"]


class TestTheBacklog:
    def test_what_it_was_is_reconstructed_not_remembered(self):
        # open now, minus what arrived since, plus what closed since
        rows = [
            ticket("old", "a", days_ago(40)),  # was open then, still open
            ticket("new", "b", days_ago(3)),  # arrived inside the window
            ticket("shut", "c", days_ago(30), days_ago(2)),  # was open then, closed since
        ]
        got = health.summary(rows, TODAY)
        assert got["open"] == 2
        assert got["open_was"] == 2, "old + shut were both open a fortnight ago"

    def test_it_never_reports_a_negative_backlog(self):
        rows = [ticket(str(i), "a", days_ago(1), days_ago(0)) for i in range(4)]
        assert health.summary(rows, TODAY)["open_was"] >= 0


class TestAge:
    def test_the_age_is_the_median_not_the_mean(self):
        # One ticket open since March would drag a mean into fiction
        rows = [
            ticket("1", "a", days_ago(2)),
            ticket("2", "b", days_ago(4)),
            ticket("3", "c", days_ago(300)),
        ]
        assert health.summary(rows, TODAY)["median_age_days"] == 4
        assert health.summary(rows, TODAY)["oldest_days"] == 300

    def test_tickets_past_the_threshold_are_named(self):
        rows = [ticket("old", "ancient", days_ago(40)), ticket("new", "fresh", days_ago(1))]
        aged = health.summary(rows, TODAY)["aged"]
        assert [a["key"] for a in aged] == ["old"]
        assert aged[0]["days"] == 40

    def test_closed_tickets_are_not_ageing(self):
        rows = [ticket("shut", "x", days_ago(40), days_ago(1))]
        assert health.summary(rows, TODAY)["aged"] == []

    def test_how_long_closing_takes_counts_only_recent_closures(self):
        rows = [
            ticket("1", "a", days_ago(10), days_ago(4)),  # took 6, inside the window
            ticket("2", "b", days_ago(300), days_ago(280)),  # took 20, long ago
        ]
        assert health.summary(rows, TODAY)["median_close_days"] == 6


class TestRecurring:
    def test_the_same_fault_twice_is_one_problem(self):
        rows = [
            ticket("1", "[Incident] Checkout times out", days_ago(9)),
            ticket("2", "[Incident] Checkout times out", days_ago(3)),
        ]
        found = health.summary(rows, TODAY)["recurring"]
        assert found[0]["times"] == 2 and found[0]["open"] == 2
        assert found[0]["keys"] == ["1", "2"]

    def test_the_category_prefix_does_not_split_a_fault_in_two(self):
        # The same problem filed once as an incident and once as a bug is still one problem
        rows = [
            ticket("1", "[Incident] Checkout times out", days_ago(9)),
            ticket("2", "[Bug] Checkout times out", days_ago(3)),
        ]
        assert health.summary(rows, TODAY)["recurring"][0]["times"] == 2

    def test_a_one_off_is_not_a_pattern(self):
        rows = [ticket("1", "[Bug] Something odd", days_ago(3))]
        assert health.summary(rows, TODAY)["recurring"] == []

    def test_a_fault_that_was_fixed_every_time_ranks_below_a_live_one(self):
        rows = [
            ticket("1", "[Bug] Closed thing", days_ago(30), days_ago(20)),
            ticket("2", "[Bug] Closed thing", days_ago(25), days_ago(18)),
            ticket("3", "[Bug] Live thing", days_ago(9)),
            ticket("4", "[Bug] Live thing", days_ago(3)),
        ]
        assert health.summary(rows, TODAY)["recurring"][0]["fault"].endswith("Live thing")

    def test_the_note_calls_a_repeat_one_problem_not_several(self):
        rows = [ticket(str(i), "[Incident] Checkout times out", days_ago(3)) for i in range(4)]
        assert "one problem, not 4" in health.summary(rows, TODAY)["note"]


class TestWhatItDoesNotDo:
    def test_it_never_produces_a_finish_date(self):
        # Asking when a queue finishes is a category error, and answering is worse
        got = health.summary([ticket("1", "a", days_ago(3))], TODAY)
        assert not any("finish" in k for k in got)

    def test_it_does_not_forecast(self):
        source = __import__("inspect").getsource(health)
        assert "forecast" not in source.split('"""', 2)[2], "no prediction in the code"

    def test_an_unreadable_date_does_not_take_the_board_down(self):
        rows = [{"key": "1", "fields": {"summary": "x", "created": "not a date"}}]
        assert health.summary(rows, TODAY)["open"] == 1


class TestByOwner:
    def test_open_work_is_counted_per_person(self):
        rows = [
            ticket("1", "a", days_ago(3), who="Ada"),
            ticket("2", "b", days_ago(3), who="Ada"),
            ticket("3", "c", days_ago(3), who="Bo"),
        ]
        assert health.summary(rows, TODAY)["by_owner"][0] == {"assignee": "Ada", "open": 2}

    def test_nobody_assigned_is_named_rather_than_dropped(self):
        rows = [ticket("1", "a", days_ago(3), who="")]
        assert health.summary(rows, TODAY)["by_owner"][0]["assignee"] == "unassigned"
