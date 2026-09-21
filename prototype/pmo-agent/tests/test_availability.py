"""Available-time tests — does the calendar really reach the schedule.

Three things to check:
  1. are meeting hours converted into availability correctly
  2. does low availability really stretch a task out
  3. with no calendar, does everything behave exactly as before (nothing broken)

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile

import pytest

from pmo_agent import availability as av
from pmo_agent import capacity, schedule
from pmo_agent.adapters.memory_calendar import MemoryCalendar
from pmo_agent.seeds import calendar as cal_seed

TODAY = dt.date(2026, 9, 21)  # a Monday


def solo(n=2, points=5, who="Ada"):
    return schedule.to_tasks(
        [
            {"key": f"T{i}", "summary": f"task {i}", "assignee": who, "points": points}
            for i in range(1, n + 1)
        ]
    )


def busy(who, hours, days=20, today=TODAY):
    return {who: {schedule.add_workdays(today, i).isoformat(): hours for i in range(days)}}


class TestFraction:
    def test_no_meetings_means_fully_available(self):
        assert av.fraction_from_hours(0) == 1.0

    def test_half_the_day_in_meetings_leaves_half(self):
        assert av.fraction_from_hours(4, 8) == 0.5

    def test_a_completely_eaten_day_is_still_not_zero(self):
        # Zero would push that person's schedule out forever — keep a floor
        assert av.fraction_from_hours(8, 8) == av.MIN_FRACTION
        assert av.fraction_from_hours(99, 8) == av.MIN_FRACTION

    def test_negative_hours_are_ignored(self):
        assert av.fraction_from_hours(-3) == 1.0


class TestConversion:
    def test_it_turns_a_busy_hours_table_into_availability(self):
        out = av.from_busy_hours({"Ada": {"2026-09-21": 2.0}})
        assert out["Ada"]["2026-09-21"] == 0.75

    def test_several_on_one_day_are_summed(self):
        events = [
            {"attendee": "Ada", "date": "2026-09-21", "hours": 1.0},
            {"attendee": "Ada", "date": "2026-09-21", "hours": 3.0},
        ]
        assert av.from_events(events)["Ada"]["2026-09-21"] == 0.5

    def test_a_missing_person_or_date_is_dropped(self):
        assert av.from_events([{"attendee": "", "date": "2026-09-21", "hours": 1}]) == {}
        assert av.from_events([{"attendee": "Ada", "date": "", "hours": 1}]) == {}

    def test_empty_input_is_handled(self):
        assert av.from_events([]) == {}
        assert av.from_busy_hours(None) == {}


class TestSpan:
    def test_fully_available_takes_exactly_the_work(self):
        assert av.span_end([1.0] * 10, 0.0, 3.0) == pytest.approx(3.0)

    def test_half_available_takes_twice_as_long(self):
        assert av.span_end([0.5] * 10, 0.0, 3.0) == pytest.approx(6.0)

    def test_one_busy_day_pushes_it_by_that_day(self):
        rates = [1.0, 0.0, 1.0, 1.0, 1.0]
        assert av.span_end(rates, 0.0, 2.0) == pytest.approx(3.0)

    def test_zero_work_stays_put(self):
        assert av.span_end([1.0] * 5, 2.0, 0.0) == 2.0

    def test_past_the_horizon_it_assumes_full_availability(self):
        # The two days in the table are 0.5 each = 1.0 of work; the other 4.0 are free → 2 + 4 = 6
        assert av.span_end([0.5, 0.5], 0.0, 5.0) == pytest.approx(6.0)


class TestMeetingLoad:
    def test_it_reports_what_was_lost_in_days_and_hours(self):
        load = av.meeting_load(av.from_busy_hours(busy("Ada", 4.0)), "Ada", TODAY, 10)
        assert load["lost_days"] == 5.0
        assert load["lost_hours"] == 40.0
        assert load["available_days"] == 5.0

    def test_someone_not_in_the_calendar_is_fully_available(self):
        assert av.meeting_load({}, "Bo", TODAY, 10)["lost_days"] == 0.0


class TestSchedulerIntegration:
    def test_with_no_calendar_nothing_changes(self):
        tasks = solo(2, points=5)
        before = capacity.levelled(tasks, TODAY)
        after = capacity.levelled(tasks, TODAY, availability=None)
        assert before["project_finish"] == after["project_finish"]

    def test_plenty_of_meetings_push_the_finish_out(self):
        tasks = solo(2, points=5)
        plain = capacity.levelled(tasks, TODAY)
        heavy = capacity.levelled(tasks, TODAY, availability=av.from_busy_hours(busy("Ada", 4.0)))
        assert heavy["project_finish"] > plain["project_finish"]

    def test_half_availability_roughly_doubles_the_duration(self):
        tasks = solo(1, points=4)
        plain = schedule.workdays_between(TODAY, capacity.levelled(tasks, TODAY)["project_finish"])
        half = schedule.workdays_between(
            TODAY,
            capacity.levelled(tasks, TODAY, availability=av.from_busy_hours(busy("Ada", 4.0)))[
                "project_finish"
            ],
        )
        assert half == plain * 2

    def test_someone_elses_meetings_change_nothing(self):
        tasks = solo(2, points=5, who="Ada")
        same = capacity.levelled(tasks, TODAY, availability=av.from_busy_hours(busy("Bo", 6.0)))
        assert same["project_finish"] == capacity.levelled(tasks, TODAY)["project_finish"]

    def test_what_meetings_cost_rides_in_the_resource_rows(self):
        tasks = solo(2, points=5)
        r = capacity.levelled(tasks, TODAY, availability=av.from_busy_hours(busy("Ada", 2.0)))
        assert r["resources"][0]["lost_to_meetings"] > 0

    def test_rebalancing_looks_at_availability_too(self):
        tasks = schedule.to_tasks(
            [{"key": f"T{i}", "assignee": "Ada", "points": 5} for i in range(1, 5)]
            + [{"key": "Z", "assignee": "Bo", "points": 1}]
        )
        r = capacity.rebalance(
            tasks, TODAY, max_moves=2, availability=av.from_busy_hours(busy("Ada", 4.0))
        )
        assert r["gain_days"] > 0
        assert r["moves"][0]["from"] == "Ada"


class TestMemoryCalendar:
    def setup_method(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "cal.json")
        cal_seed.write(self.path, TODAY)
        self.cal = MemoryCalendar(self.path)

    def teardown_method(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_it_returns_events_in_date_order(self):
        days = [e["date"] for e in self.cal.events(20)]
        assert days == sorted(days)

    def test_it_filters_by_person(self):
        who = self.cal.events(20)[0]["attendee"]
        assert all(e["attendee"] == who for e in self.cal.events(20, attendee=who))

    def test_it_returns_a_busy_hours_table(self):
        table = self.cal.busy_hours(20)
        assert table
        assert all(isinstance(v, dict) for v in table.values())

    def test_there_are_no_write_methods(self):
        for name in ("create_event", "delete", "update", "set_fields"):
            assert not hasattr(self.cal, name), name

    def test_a_missing_file_does_not_break_it(self):
        assert MemoryCalendar(os.path.join(self.dir, "nope.json")).events() == []


class TestCalendarSeed:
    def test_the_same_seed_builds_the_same_calendar(self):
        assert cal_seed.build(TODAY) == cal_seed.build(TODAY)

    def test_meetings_pile_onto_the_bottleneck_owner(self):
        data = cal_seed.build(TODAY)
        avail = av.from_events(data["events"])
        planted = next(p for p in data["planted"] if p["kind"] == "meeting_overload")
        loads = {
            p: av.meeting_load(avail, p, TODAY, 10)["lost_days"]
            for p in {e["attendee"] for e in data["events"]}
        }
        assert max(loads, key=lambda p: loads[p]) == planted["assignee"]

    def test_there_is_a_day_that_disappears_entirely(self):
        data = cal_seed.build(TODAY)
        workshop = next(p for p in data["planted"] if p["kind"] == "workshop")
        that_day = [e for e in data["events"] if e["date"] == workshop["date"]]
        assert any(e["hours"] >= av.WORKDAY_HOURS for e in that_day)

    def test_only_fictional_people_appear(self):
        tasks = schedule.from_jira_issues(
            __import__("pmo_agent.seeds.board", fromlist=["build"]).build(TODAY)
        )
        people = {t.assignee for t in tasks.values() if t.assignee}
        assert {e["attendee"] for e in cal_seed.build(TODAY)["events"]} <= people

    def test_it_serialises_to_json(self):
        json.dumps(cal_seed.build(TODAY), ensure_ascii=False)
