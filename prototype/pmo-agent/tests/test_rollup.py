"""The executive roll-up — no network.

An executive is not asking for charts. They are asking what is in trouble, why, and when
it clears. So there is no new calculation here, only arrangement, and the tests are about
the two things that are easy to get wrong when a senior person is the reader.

**Each kind gets the line that means something for it.** Printing a finish date next to
work that never finishes is confident nonsense.

**The unexplained part is not hidden.** The temptation grows with the seniority of the
reader, because a tidy dashboard is what gets asked for and "3.5 of 13 days" is not tidy.
Folding it away would make every other number on the screen look surer than it is.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt

from pmo_agent import projects, rollup

TODAY = dt.date(2026, 9, 21)
BUILD = projects.Project("ECHO", "Echo PMO", "build")
RUN = projects.Project("OPS", "Platform operations", "run")


def sched(risks=0, finish="2026-10-13", total=40, done=20):
    return {
        "predicted_finish": finish,
        "risks": [{"key": f"E-{i}"} for i in range(risks)],
        "total": total,
        "done": done,
    }


def cap(slip=0, finish="2026-10-13", who="Maya"):
    return {
        "capacity_finish": finish,
        "slip_vs_unconstrained": slip,
        "bottleneck": {"assignee": who},
    }


def queue(open_=5, was=5, arrived=3, closed=3, aged=(), recurring=()):
    return {
        "open": open_,
        "open_was": was,
        "arrived": arrived,
        "closed": closed,
        "keeping_up": closed >= arrived,
        "median_age_days": 4,
        "aged": list(aged),
        "recurring": list(recurring),
        "note": "a sentence",
    }


class TestDeliveryRows:
    def test_a_project_on_plan_is_ok(self):
        row = rollup.build_row(BUILD, sched(), cap())
        assert row["state"] == rollup.OK

    def test_a_small_slip_is_worth_watching(self):
        assert rollup.build_row(BUILD, sched(), cap(slip=4))["state"] == rollup.WATCH

    def test_a_big_slip_is_trouble(self):
        assert rollup.build_row(BUILD, sched(), cap(slip=19))["state"] == rollup.RISK

    def test_enough_tasks_at_risk_is_trouble_even_without_a_slip(self):
        assert rollup.build_row(BUILD, sched(risks=6), cap())["state"] == rollup.RISK

    def test_the_headline_is_the_achievable_date_not_the_optimistic_one(self):
        row = rollup.build_row(BUILD, sched(finish="2026-10-13"), cap(finish="2026-11-09", slip=19))
        assert row["headline"] == "2026-11-09"
        assert row["baseline"] == "2026-10-13"

    def test_a_missing_capacity_reading_is_unknown_rather_than_ok(self):
        # Silence must not read as good news
        assert rollup.build_row(BUILD, sched(), {})["state"] == rollup.UNKNOWN


class TestOperationsRows:
    def test_a_queue_keeping_up_with_nothing_ageing_is_ok(self):
        assert rollup.run_row(RUN, queue())["state"] == rollup.OK

    def test_falling_behind_with_things_ageing_is_trouble(self):
        got = rollup.run_row(RUN, queue(arrived=9, closed=2, aged=[{"key": "1"}]))
        assert got["state"] == rollup.RISK

    def test_falling_behind_alone_is_worth_watching(self):
        assert rollup.run_row(RUN, queue(arrived=9, closed=2))["state"] == rollup.WATCH

    def test_a_fault_that_keeps_coming_back_is_worth_watching(self):
        got = rollup.run_row(RUN, queue(recurring=[{"fault": "Checkout times out", "open": 3}]))
        assert got["state"] == rollup.WATCH
        assert got["recurring"] == "Checkout times out"

    def test_a_repeat_that_was_fixed_every_time_is_not_flagged(self):
        got = rollup.run_row(RUN, queue(recurring=[{"fault": "old thing", "open": 0}]))
        assert got["state"] == rollup.OK and got["recurring"] == ""

    def test_the_headline_is_the_backlog_not_a_date(self):
        # A queue does not finish, and printing a date would be confident nonsense
        row = rollup.run_row(RUN, queue(open_=11, was=2))
        assert row["headline"] == "11" and row["headline_label"] == "open now"
        assert "finish" not in row["headline_label"]
        assert "slip_days" not in row

    def test_a_queue_nobody_could_read_is_unknown(self):
        assert rollup.run_row(RUN, {})["state"] == rollup.UNKNOWN


class TestHonesty:
    def test_the_unexplained_days_ride_along_on_the_row(self):
        # The temptation to fold this away grows with the seniority of the reader
        stalls = {"worst": [{"key": "E-1", "note": "why", "unexplained_days": 6.5}]}
        row = rollup.build_row(BUILD, sched(), cap(), stalls)
        assert row["unexplained_days"] == 6.5
        assert row["why"] == "why" and row["why_key"] == "E-1"

    def test_a_project_that_could_not_be_read_is_shown_not_dropped(self):
        # A missing row reads as a project with nothing wrong, which is the worst thing
        # this screen could say about one it failed to open
        row = rollup.error_row(BUILD, "the repository was unreachable")
        assert row["state"] == rollup.UNKNOWN
        assert "unreachable" in row["why"]
        got = rollup.summary([row], TODAY)
        assert len(got["projects"]) == 1

    def test_all_unknown_says_so_rather_than_all_on_track(self):
        rows = [rollup.error_row(BUILD, "x"), rollup.error_row(RUN, "y")]
        note = rollup.summary(rows, TODAY)["note"]
        assert note == "None of the projects could be read."
        assert "on track" not in note


class TestOrdering:
    def rows(self):
        return [
            rollup.build_row(projects.Project("A"), sched(), cap()),
            rollup.build_row(projects.Project("B"), sched(risks=6), cap(slip=19)),
            rollup.build_row(projects.Project("C"), sched(), cap(slip=4)),
            rollup.error_row(projects.Project("D"), "x"),
        ]

    def test_the_worst_comes_first(self):
        got = rollup.summary(self.rows(), TODAY)
        assert [r["key"] for r in got["projects"]] == ["B", "C", "D", "A"]

    def test_the_counts_add_up_to_the_projects(self):
        got = rollup.summary(self.rows(), TODAY)
        assert sum(got["counts"].values()) == len(got["projects"])

    def test_the_sentence_names_the_worst_one_and_why(self):
        stalls = {"worst": [{"key": "E-1", "note": "the provider has not replied"}]}
        rows = [rollup.build_row(BUILD, sched(risks=6), cap(slip=19), stalls)]
        assert "the provider has not replied" in rollup.summary(rows, TODAY)["note"]

    def test_nothing_in_trouble_says_so_plainly(self):
        rows = [rollup.build_row(BUILD, sched(), cap())]
        assert "on track" in rollup.summary(rows, TODAY)["note"]

    def test_no_projects_is_not_an_error(self):
        assert "No projects" in rollup.summary([], TODAY)["note"]


class TestTheTwoKindsTogether:
    def test_delivery_and_operations_sit_on_one_screen_with_different_headlines(self):
        rows = [
            rollup.build_row(BUILD, sched(finish="2026-10-13"), cap(finish="2026-11-09", slip=19)),
            rollup.run_row(RUN, queue(open_=11, was=2, arrived=16, closed=7)),
        ]
        got = rollup.summary(rows, TODAY)
        labels = {r["kind"]: r["headline_label"] for r in got["projects"]}
        assert labels == {"build": "achievable finish", "run": "open now"}
