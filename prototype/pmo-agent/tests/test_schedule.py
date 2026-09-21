"""schedule.py unit tests — pure calculation, runs with no credentials (SETUP.md 2-3).

Run: python -m pytest tests/test_schedule.py -q
"""

from __future__ import annotations

import datetime as dt
import json
import unittest

from pmo_agent.schedule import (  # noqa: E402
    CycleError,
    add_workdays,
    cpm,
    forecast,
    from_jira_issues,
    iso,
    propagate,
    risks,
    status_alike,
    summary,
    to_tasks,
    topo_order,
    workdays_between,
)

MON = dt.date(2026, 9, 21)  # the reference Monday


def chain():
    """A(2) → B(3) → C(1) in a straight line. All of it critical."""
    return to_tasks(
        [
            {"key": "A", "points": 2},
            {"key": "B", "points": 3, "deps": ["A"]},
            {"key": "C", "points": 1, "deps": ["B"]},
        ]
    )


def diamond():
    """A(2) → B(5) → E(1) and A(2) → C(1) → E(1). B is critical; C has 4 days of slack."""
    return to_tasks(
        [
            {"key": "A", "points": 2},
            {"key": "B", "points": 5, "deps": ["A"]},
            {"key": "C", "points": 1, "deps": ["A"]},
            {"key": "E", "points": 1, "deps": ["B", "C"]},
        ]
    )


class TestWorkdays(unittest.TestCase):
    def test_the_reference_date_is_a_monday(self):
        self.assertEqual(MON.weekday(), 0)

    def test_it_skips_the_weekend(self):
        # Monday + 5 business days = the following Monday
        self.assertEqual(add_workdays(MON, 5), MON + dt.timedelta(days=7))

    def test_zero_days_stays_put_and_nudges_off_a_weekend(self):
        self.assertEqual(add_workdays(MON, 0), MON)
        sat = MON + dt.timedelta(days=5)
        self.assertEqual(add_workdays(sat, 0), MON + dt.timedelta(days=7))

    def test_a_negative_count_goes_backwards(self):
        self.assertEqual(add_workdays(MON, -5), MON - dt.timedelta(days=7))
        self.assertEqual(add_workdays(MON, -1), MON - dt.timedelta(days=3))  # Friday
        self.assertEqual(add_workdays(add_workdays(MON, -20), 20), MON)

    def test_the_business_day_gap_excludes_weekends(self):
        self.assertEqual(workdays_between(MON, MON + dt.timedelta(days=7)), 5)
        self.assertEqual(workdays_between(MON + dt.timedelta(days=7), MON), -5)

    def test_holidays_are_excluded_too(self):
        wed = MON + dt.timedelta(days=2)
        self.assertEqual(add_workdays(MON, 2, holidays=[wed]), MON + dt.timedelta(days=3))


class TestCPM(unittest.TestCase):
    def test_a_straight_line_is_all_critical(self):
        c = cpm(chain(), MON)
        self.assertEqual(c["duration_days"], 6)
        self.assertEqual(c["critical_path"], ["A", "B", "C"])
        self.assertEqual(c["finish"], add_workdays(MON, 6))
        self.assertTrue(all(r["slack_days"] == 0 for r in c["tasks"].values()))

    def test_the_short_branch_gets_slack(self):
        c = cpm(diamond(), MON)
        self.assertEqual(c["duration_days"], 8)  # A2 + B5 + E1
        self.assertEqual(c["critical_path"], ["A", "B", "E"])
        self.assertEqual(c["tasks"]["C"]["slack_days"], 4)
        self.assertFalse(c["tasks"]["C"]["critical"])

    def test_no_points_means_the_default_duration(self):
        c = cpm(to_tasks([{"key": "X"}]), MON)
        self.assertEqual(c["duration_days"], 2)

    def test_a_cycle_is_refused(self):
        t = to_tasks([{"key": "A", "deps": ["B"]}, {"key": "B", "deps": ["A"]}])
        with self.assertRaises(CycleError):
            topo_order(t)

    def test_dependencies_on_unknown_keys_are_dropped(self):
        t = to_tasks([{"key": "A", "deps": ["NOPE-1", "A"]}])
        self.assertEqual(t["A"].deps, [])


class TestStatusAliases(unittest.TestCase):
    """A Jira site's language splits status names; models tend to answer in English."""

    def test_korean_and_english_mean_the_same(self):
        self.assertTrue(status_alike("Done", "완료"))
        self.assertTrue(status_alike("완료", "done"))
        self.assertTrue(status_alike("In Progress", "진행 중"))
        self.assertTrue(status_alike("To Do", "할 일"))

    def test_it_absorbs_spacing_and_case(self):
        self.assertTrue(status_alike("진행중", "진행 중"))
        self.assertTrue(status_alike("IN PROGRESS", "in progress"))

    def test_different_meanings_stay_apart(self):
        self.assertFalse(status_alike("Done", "진행 중"))
        self.assertFalse(status_alike("Blocked", "완료"))

    def test_empty_is_not_equal_to_anything(self):
        self.assertFalse(status_alike("", "완료"))


class TestForecast(unittest.TestCase):
    def test_a_finished_task_has_zero_remaining(self):
        t = chain()
        t["A"].status = "Done"
        f = forecast(t, MON)
        self.assertEqual(f["tasks"]["A"]["remaining_days"], 0)
        self.assertEqual(f["tasks"]["B"]["predicted_finish"], add_workdays(MON, 3))

    def test_progress_reduces_what_is_left(self):
        t = chain()
        t["A"].progress = 0.5
        self.assertEqual(forecast(t, MON)["tasks"]["A"]["remaining_days"], 1.0)

    def test_it_picks_out_overruns_with_the_day_count(self):
        t = chain()
        t["C"].duedate = add_workdays(MON, 4)  # the real forecast is 6 business days
        f = forecast(t, MON)["tasks"]["C"]
        self.assertTrue(f["late"])
        self.assertEqual(f["delay_days"], 2)

    def test_no_due_date_means_no_delay_verdict(self):
        f = forecast(chain(), MON)["tasks"]["C"]
        self.assertFalse(f["late"])
        self.assertIsNone(f["delay_days"])


class TestPropagate(unittest.TestCase):
    def test_slack_stops_it_spreading_downstream(self):
        p = propagate(diamond(), "C", 2, MON)  # C has 4 days of slack
        self.assertIn("C", [r["key"] for r in p["affected"]])
        self.assertNotIn("E", [r["key"] for r in p["affected"]])
        self.assertEqual(p["project_finish_before"], p["project_finish_after"])

    def test_a_slip_on_the_critical_path_moves_the_project(self):
        p = propagate(diamond(), "B", 3, MON)
        moved = {r["key"]: r["slip_days"] for r in p["affected"]}
        self.assertEqual(moved["B"], 3)
        self.assertEqual(moved["E"], 3)
        self.assertEqual(workdays_between(p["project_finish_before"], p["project_finish_after"]), 3)

    def test_it_flags_whether_a_due_date_breaks(self):
        t = diamond()
        t["E"].duedate = add_workdays(MON, 8)
        p = propagate(t, "B", 3, MON)
        self.assertTrue(next(r for r in p["affected"] if r["key"] == "E")["breaks_duedate"])

    def test_the_original_tasks_are_untouched(self):
        t = diamond()
        propagate(t, "B", 3, MON)
        self.assertEqual(t["B"].points, 5)

    def test_an_unknown_key_comes_back_as_an_error(self):
        self.assertIn("error", propagate(diamond(), "NOPE", 1, MON))


class TestRisks(unittest.TestCase):
    def test_a_finished_task_drops_out_of_the_risks(self):
        t = chain()
        t["A"].status = "Done"
        self.assertNotIn("A", [r["key"] for r in risks(t, MON)])

    def test_it_gives_the_evidence_and_what_is_blocked(self):
        t = chain()
        t["B"].duedate = add_workdays(MON, 1)
        r = next(x for x in risks(t, MON) if x["key"] == "B")
        self.assertTrue(r["reasons"])
        self.assertEqual(r["blocks"], ["C"])
        self.assertTrue(r["critical"])

    def test_they_sort_by_size_of_delay(self):
        t = chain()
        t["A"].duedate = add_workdays(MON, 1)  # 1 day over
        t["C"].duedate = MON  # 6 days over
        self.assertEqual([r["key"] for r in risks(t, MON)][0], "C")


class TestJiraMapping(unittest.TestCase):
    def test_blocks_links_become_dependencies_in_both_directions(self):
        issues = [
            {
                "key": "ECHO-1",
                "fields": {
                    "summary": "Design",
                    "status": {"name": "Done"},
                    "assignee": {"displayName": "Choi"},
                    "duedate": "2026-09-25",
                    "customfield_10016": 3,
                    "issuelinks": [{"type": {"name": "Blocks"}, "outwardIssue": {"key": "ECHO-2"}}],
                },
            },
            {
                "key": "ECHO-2",
                "fields": {
                    "summary": "Build",
                    "status": {"name": "To Do"},
                    "issuelinks": [{"type": {"name": "Blocks"}, "inwardIssue": {"key": "ECHO-1"}}],
                },
            },
        ]
        t = from_jira_issues(issues)
        self.assertEqual(t["ECHO-2"].deps, ["ECHO-1"])
        self.assertEqual(t["ECHO-1"].deps, [])
        self.assertTrue(t["ECHO-1"].is_done)
        self.assertEqual(t["ECHO-1"].duedate, dt.date(2026, 9, 25))
        self.assertEqual(t["ECHO-1"].points, 3)

    def test_links_that_are_not_blocks_are_ignored(self):
        issues = [
            {
                "key": "E-1",
                "fields": {
                    "issuelinks": [{"type": {"name": "Relates"}, "outwardIssue": {"key": "E-2"}}]
                },
            },
            {"key": "E-2", "fields": {}},
        ]
        self.assertEqual(from_jira_issues(issues)["E-2"].deps, [])

    def test_empty_fields_do_not_break_it(self):
        t = from_jira_issues([{"key": "E-1", "fields": {}}])
        self.assertEqual(t["E-1"].summary, "")
        self.assertIsNone(t["E-1"].duedate)


class TestSummary(unittest.TestCase):
    def test_it_serialises_straight_to_json(self):
        t = chain()
        t["C"].duedate = MON
        s = summary(t, MON)
        json.dumps(s, ensure_ascii=False)  # no exception = pass
        self.assertEqual(s["today"], MON.isoformat())
        self.assertEqual(s["critical_path"], ["A", "B", "C"])
        self.assertEqual(s["total"], 3)

    def test_it_reports_the_plan_forecast_gap_in_days(self):
        t = chain()
        t["A"].status = "Done"  # two days disappear
        self.assertEqual(summary(t, MON)["slip_days"], -2)

    def test_iso_does_not_mutate_the_original(self):
        o = {"d": MON, "xs": [MON]}
        self.assertEqual(iso(o)["d"], MON.isoformat())
        self.assertEqual(o["d"], MON)


if __name__ == "__main__":
    unittest.main(verbosity=2)
