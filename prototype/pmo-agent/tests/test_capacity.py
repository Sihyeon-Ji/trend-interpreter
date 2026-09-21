"""Resource-constrained scheduling tests.

Two things to check:
  1) does one person ever run two tasks at once (do the intervals overlap)
  2) does work sit idle while its owner is free (are the gaps filled)

Run: python -m pytest tests/test_capacity.py -q
"""

from __future__ import annotations

import datetime as dt
import json
import unittest

from pmo_agent import capacity, schedule  # noqa: E402
from pmo_agent.seeds import board as seed  # noqa: E402

TODAY = dt.date(2026, 9, 21)  # a Monday


def solo(n=4, points=5, assignee="Maya"):
    """n independent tasks for one person. No dependencies, so the only cause is capacity."""
    return schedule.to_tasks(
        [
            {"key": f"T{i}", "summary": f"task {i}", "assignee": assignee, "points": points}
            for i in range(1, n + 1)
        ]
    )


def two_people():
    """A(5) → B(5) in series, with C(5) and D(5) beside them. C and D share an owner."""
    return schedule.to_tasks(
        [
            {"key": "A", "summary": "A", "assignee": "Ada", "points": 5},
            {"key": "B", "summary": "B", "assignee": "Ada", "points": 5, "deps": ["A"]},
            {"key": "C", "summary": "C", "assignee": "Bo", "points": 5},
            {"key": "D", "summary": "D", "assignee": "Bo", "points": 5},
        ]
    )


def intervals(result, who):
    rows = [r for r in result["tasks"].values() if r["assignee"] == who and r["remaining_days"] > 0]
    return sorted((r["start"], r["finish"]) for r in rows)


class TestCapacityConstraint(unittest.TestCase):
    def test_one_persons_work_never_overlaps(self):
        r = capacity.levelled(seed_tasks(), TODAY)
        for who in {t["assignee"] for t in r["tasks"].values() if t["assignee"]}:
            iv = intervals(r, who)
            for (s1, e1), (s2, e2) in zip(iv, iv[1:], strict=False):
                self.assertLessEqual(e1, s2, f"{who}: {s1}-{e1} overlaps {s2}-{e2}")

    def test_four_tasks_alone_stretch_out_in_series(self):
        r = capacity.levelled(solo(4, points=5), TODAY)
        # No dependencies, so the old forecast says 5 days; with capacity it is 20
        self.assertEqual(schedule.workdays_between(TODAY, r["unconstrained_finish"]), 5)
        self.assertEqual(schedule.workdays_between(TODAY, r["project_finish"]), 20)
        self.assertEqual(r["slip_vs_unconstrained"], 15)

    def test_raising_the_concurrency_pulls_it_in(self):
        r1 = capacity.levelled(solo(4), TODAY, capacity=1)
        r2 = capacity.levelled(solo(4), TODAY, capacity=2)
        r4 = capacity.levelled(solo(4), TODAY, capacity=4)
        self.assertGreater(r1["project_finish"], r2["project_finish"])
        self.assertEqual(r4["project_finish"], r4["unconstrained_finish"])

    def test_capacity_can_differ_per_owner(self):
        t = solo(4, assignee="Ada")
        r = capacity.levelled(t, TODAY, capacity={"Ada": 4})
        self.assertEqual(r["project_finish"], r["unconstrained_finish"])

    def test_different_people_run_in_parallel(self):
        r = capacity.levelled(two_people(), TODAY)
        self.assertEqual(
            schedule.workdays_between(TODAY, r["project_finish"]), 10
        )  # Ada A→B, Bo C→D

    def test_a_finished_task_consumes_nobody(self):
        t = solo(4)
        for k in ("T1", "T2", "T3"):
            t[k].status = "Done"
        r = capacity.levelled(t, TODAY)
        self.assertEqual(schedule.workdays_between(TODAY, r["project_finish"]), 5)
        self.assertEqual(len(r["resources"]), 1)


class TestNoIdleWaste(unittest.TestCase):
    """A late-starting task must not claim a slot and leave the front of it empty."""

    def tasks(self):
        # X cannot start for 10 days because of a long predecessor. Y can start now. Both Bo's.
        return schedule.to_tasks(
            [
                {"key": "P", "summary": "predecessor", "assignee": "Ada", "points": 10},
                {
                    "key": "X",
                    "summary": "starts late",
                    "assignee": "Bo",
                    "points": 3,
                    "deps": ["P"],
                },
                {"key": "Y", "summary": "can start now", "assignee": "Bo", "points": 3},
            ]
        )

    def test_it_does_not_waste_the_time_at_the_front(self):
        r = capacity.levelled(self.tasks(), TODAY)
        y = r["tasks"]["Y"]
        self.assertEqual(y["start"], schedule.add_workdays(TODAY, 0))  # it should start at once
        self.assertEqual(y["waiting_days"], 0)

    def test_the_project_finish_is_the_minimum(self):
        r = capacity.levelled(self.tasks(), TODAY)
        self.assertEqual(schedule.workdays_between(TODAY, r["project_finish"]), 13)  # P10 + X3


class TestWaiting(unittest.TestCase):
    def test_it_counts_the_days_spent_waiting_on_a_person(self):
        r = capacity.levelled(solo(2, points=5), TODAY)
        rows = {k: v for k, v in r["tasks"].items()}
        self.assertEqual(sorted(x["waiting_days"] for x in rows.values()), [0.0, 5.0])

    def test_it_lists_what_is_waiting_and_why(self):
        r = capacity.levelled(solo(3, points=5), TODAY)
        w = capacity.blocked_by_people(r)
        self.assertEqual(len(w), 2)
        self.assertGreater(w[0]["waiting_days"], w[1]["waiting_days"])

    def test_no_waiting_means_an_empty_list(self):
        r = capacity.levelled(solo(1), TODAY)
        self.assertEqual(capacity.blocked_by_people(r), [])


class TestBottleneck(unittest.TestCase):
    def test_whoever_holds_the_most_is_the_bottleneck(self):
        t = schedule.to_tasks(
            [
                {"key": "A", "assignee": "Ada", "points": 10},
                {"key": "B", "assignee": "Bo", "points": 2},
            ]
        )
        self.assertEqual(capacity.levelled(t, TODAY)["bottleneck"]["assignee"], "Ada")

    def test_utilisation_stays_between_0_and_1(self):
        r = capacity.levelled(seed_tasks(), TODAY)
        for x in r["resources"]:
            self.assertTrue(0 < x["utilization"] <= 1.0, x)


class TestRebalance(unittest.TestCase):
    def test_moving_work_off_a_loaded_person_pulls_the_finish_in(self):
        t = schedule.to_tasks(
            [
                {"key": f"T{i}", "summary": f"task {i}", "assignee": "Ada", "points": 5}
                for i in range(1, 5)
            ]
            + [{"key": "Z", "summary": "Z", "assignee": "Bo", "points": 1}]
        )
        r = capacity.rebalance(t, TODAY, max_moves=2)
        self.assertGreater(r["gain_days"], 0)
        self.assertTrue(r["moves"])
        self.assertEqual(r["moves"][0]["from"], "Ada")

    def test_nothing_movable_means_an_empty_proposal(self):
        r = capacity.rebalance(solo(3), TODAY)  # only one person
        self.assertEqual(r["moves"], [])
        self.assertEqual(r["before"], r["after"])

    def test_a_task_already_under_way_is_not_moved(self):
        t = schedule.to_tasks(
            [
                {
                    "key": "A",
                    "assignee": "Ada",
                    "points": 10,
                    "status": "In Progress",
                    "progress": 0.5,
                },
                {"key": "B", "assignee": "Ada", "points": 5},
                {"key": "C", "assignee": "Bo", "points": 1},
            ]
        )
        moved = {m["key"] for m in capacity.rebalance(t, TODAY)["moves"]}
        self.assertNotIn("A", moved)

    def test_a_finished_task_is_not_moved(self):
        t = schedule.to_tasks(
            [
                {"key": "A", "assignee": "Ada", "points": 10, "status": "Done"},
                {"key": "B", "assignee": "Ada", "points": 5},
                {"key": "C", "assignee": "Bo", "points": 1},
            ]
        )
        self.assertNotIn("A", {m["key"] for m in capacity.rebalance(t, TODAY)["moves"]})

    def test_the_original_is_untouched(self):
        t = schedule.to_tasks(
            [{"key": f"T{i}", "assignee": "Ada", "points": 5} for i in range(1, 5)]
            + [{"key": "Z", "assignee": "Bo", "points": 1}]
        )
        capacity.rebalance(t, TODAY)
        self.assertTrue(all(x.assignee == "Ada" for k, x in t.items() if k != "Z"))


class TestSummary(unittest.TestCase):
    def test_it_serialises_straight_to_json(self):
        s = capacity.summary(seed_tasks(), TODAY)
        json.dumps(s, ensure_ascii=False)
        self.assertIsInstance(s["capacity_finish"], str)

    def test_it_gives_both_forecasts_side_by_side(self):
        s = capacity.summary(seed_tasks(), TODAY)
        self.assertIn("unconstrained_finish", s)
        self.assertIn("capacity_finish", s)
        self.assertGreaterEqual(s["capacity_finish"], s["unconstrained_finish"])

    def test_a_cycle_raises(self):
        t = schedule.to_tasks([{"key": "A", "deps": ["B"]}, {"key": "B", "deps": ["A"]}])
        with self.assertRaises(schedule.CycleError):
            capacity.levelled(t, TODAY)

    def test_an_empty_board_does_not_break_it(self):
        r = capacity.levelled({}, TODAY)
        self.assertIsNone(r["bottleneck"])
        self.assertEqual(r["resources"], [])


def seed_tasks():
    return schedule.from_jira_issues(seed.build(TODAY))


class TestOnSeed(unittest.TestCase):
    def test_on_the_seed_the_capacity_finish_is_later(self):
        r = capacity.levelled(seed_tasks(), TODAY)
        self.assertGreater(r["project_finish"], r["unconstrained_finish"])
        self.assertGreater(r["slip_vs_unconstrained"], 0)

    def test_rebalancing_really_pulls_it_in(self):
        self.assertGreater(capacity.rebalance(seed_tasks(), TODAY, max_moves=2)["gain_days"], 0)

    def test_the_same_input_gives_the_same_answer(self):
        a = capacity.summary(seed_tasks(), TODAY)
        b = capacity.summary(seed_tasks(), TODAY)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
