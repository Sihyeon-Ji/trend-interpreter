"""The issue register — no network, no real file.

The agent has always *found* these things and never remembered any of them. What the
memory buys is three questions nobody could ask before: has this happened before, what has
it cost in total, and which of these are still open.

Two decisions carry most of the weight and both are tested hard here:

  · **identity** is narrow on purpose. Merging two different problems and adding their
    days together is worse than filing them twice
  · **an issue that stops being reported** is not automatically fixed. It may be that
    nobody is looking, and calling that "resolved" is the comfortable lie that makes a
    register useless after a quarter

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json

from pmo_agent import register, schedule

TODAY = dt.date(2026, 9, 21)


def finding(kind="stalled", key="ECHO-1", days=3.0, **kw):
    return {
        "kind": kind,
        "key": key,
        "summary": kw.get("summary", "Authentication"),
        "assignee": kw.get("assignee", "Ada"),
        "detail": kw.get("detail", "no commits for 12 days"),
        "days": days,
        "evidence": kw.get("evidence", []),
    }


class TestIdentity:
    def test_the_same_kind_on_the_same_task_is_the_same_issue(self):
        first = register.update([finding()], "ECHO", TODAY)
        again = register.update([finding()], "ECHO", TODAY + dt.timedelta(days=1), first)
        assert len(again) == 1
        assert list(again.values())[0]["seen"] == 2

    def test_the_same_kind_on_a_different_task_is_a_different_issue(self):
        both = register.update([finding(key="ECHO-1"), finding(key="ECHO-2")], "ECHO", TODAY)
        assert len(both) == 2

    def test_a_different_kind_on_the_same_task_is_a_different_issue(self):
        both = register.update(
            [finding(kind="stalled"), finding(kind="review_waiting")], "ECHO", TODAY
        )
        assert len(both) == 2

    def test_two_projects_do_not_share_an_issue(self):
        one = register.update([finding()], "ECHO", TODAY)
        two = register.update([finding()], "OPS", TODAY, one)
        assert len(two) == 2

    def test_a_finding_with_no_kind_is_dropped(self):
        assert register.update([{"key": "ECHO-1"}], "ECHO", TODAY) == {}


class TestDays:
    def test_the_day_count_is_the_latest_reading_not_a_running_total(self):
        # `days` is recomputed each run, so adding it up would count the same fortnight
        # once per run and the totals would climb forever
        one = register.update([finding(days=3)], "ECHO", TODAY)
        two = register.update([finding(days=5)], "ECHO", TODAY + dt.timedelta(days=1), one)
        assert list(two.values())[0]["days"] == 5

    def test_the_worst_it_ever_got_is_kept_separately(self):
        one = register.update([finding(days=8)], "ECHO", TODAY)
        two = register.update([finding(days=2)], "ECHO", TODAY + dt.timedelta(days=1), one)
        row = list(two.values())[0]
        assert (row["days"], row["peak_days"]) == (2, 8)

    def test_seen_counts_runs_not_calls_on_the_same_day(self):
        one = register.update([finding()], "ECHO", TODAY)
        twice = register.update([finding()], "ECHO", TODAY, one)
        assert list(twice.values())[0]["seen"] == 1, "two runs in one day is still one day"


class TestStates:
    def test_an_issue_that_stops_being_reported_is_closed(self):
        one = register.update([finding()], "ECHO", TODAY)
        gone = register.update([], "ECHO", TODAY + dt.timedelta(days=1), one)
        row = list(gone.values())[0]
        assert row["state"] == register.RESOLVED
        assert row["resolved_on"] == "2026-09-22"

    def test_it_comes_back_open_if_it_comes_back(self):
        one = register.update([finding()], "ECHO", TODAY)
        gone = register.update([], "ECHO", TODAY + dt.timedelta(days=1), one)
        again = register.update([finding()], "ECHO", TODAY + dt.timedelta(days=2), gone)
        assert list(again.values())[0]["state"] == register.OPEN

    def test_another_projects_issues_are_not_closed_by_this_run(self):
        # A run that only looked at ECHO knows nothing about whether OPS is fixed
        one = register.update([finding()], "OPS", TODAY)
        after = register.update([], "ECHO", TODAY + dt.timedelta(days=1), one)
        assert list(after.values())[0]["state"] == register.OPEN

    def test_an_issue_nobody_has_looked_at_lapses_rather_than_resolving(self):
        # "It got fixed" and "everyone stopped looking" are different facts
        stale = {
            "x": {
                "id": "x",
                "project": "ECHO",
                "kind": "stalled",
                "key": "E-1",
                "state": register.OPEN,
                "last_seen": "2026-08-01",
                "first_seen": "2026-08-01",
            }
        }
        after = register.update([finding(key="E-9")], "ECHO", TODAY, stale)
        assert after["x"]["state"] == register.RESOLVED  # first run after it stopped
        again = register.update([finding(key="E-9")], "ECHO", TODAY, after)
        assert again["x"]["state"] == register.RESOLVED

    def test_a_long_silent_open_issue_reads_as_lapsed(self):
        row = {"state": register.OPEN, "last_seen": "2026-08-01"}
        assert register._state(row, TODAY, register.LAPSE_DAYS) == register.LAPSED
        row2 = {"state": register.OPEN, "last_seen": "2026-09-20"}
        assert register._state(row2, TODAY, register.LAPSE_DAYS) == register.OPEN


class TestPatterns:
    def test_the_same_kind_on_several_tasks_is_a_pattern(self):
        entries = register.update(
            [finding(key="E-1", days=3), finding(key="E-2", days=5), finding(key="E-3", days=1)],
            "ECHO",
            TODAY,
        )
        found = register.recurring(entries)
        assert found[0]["kind"] == "stalled"
        assert found[0]["times"] == 3
        assert found[0]["days"] == 9

    def test_a_one_off_is_not_a_pattern(self):
        entries = register.update([finding()], "ECHO", TODAY)
        assert register.recurring(entries) == []

    def test_patterns_are_ranked_by_what_they_cost(self):
        entries = register.update(
            [
                finding(kind="a", key="1", days=1),
                finding(kind="a", key="2", days=1),
                finding(kind="b", key="3", days=20),
                finding(kind="b", key="4", days=20),
            ],
            "ECHO",
            TODAY,
        )
        assert [r["kind"] for r in register.recurring(entries)] == ["b", "a"]


class TestSummary:
    def test_it_separates_open_from_closed_from_lapsed(self):
        one = register.update([finding(key="E-1"), finding(key="E-2")], "ECHO", TODAY)
        after = register.update([finding(key="E-1")], "ECHO", TODAY + dt.timedelta(days=1), one)
        got = register.summary(after, "ECHO")
        assert [r["key"] for r in got["open"]] == ["E-1"]
        assert [r["key"] for r in got["resolved"]] == ["E-2"]

    def test_the_open_days_add_up_across_issues(self):
        entries = register.update(
            [finding(key="E-1", days=3), finding(key="E-2", days=4.5)], "ECHO", TODAY
        )
        assert register.summary(entries, "ECHO")["days_open"] == 7.5

    def test_an_empty_register_says_so_rather_than_showing_zeroes(self):
        assert "Nothing has been filed" in register.summary({}, "ECHO")["note"]

    def test_the_note_names_the_oldest_open_issue(self):
        one = register.update([finding()], "ECHO", dt.date(2026, 9, 1))
        again = register.update([finding()], "ECHO", TODAY, one)
        assert "2026-09-01" in register.summary(again, "ECHO")["note"]


class TestTheFileOnDisk:
    def test_it_survives_a_round_trip(self, tmp_path):
        path = tmp_path / "issues.json"
        entries = register.update([finding()], "ECHO", TODAY)
        register.save(entries, path)
        assert register.load(path) == entries

    def test_a_corrupt_file_is_an_empty_register_not_a_crash(self, tmp_path):
        path = tmp_path / "issues.json"
        path.write_text("{not json", encoding="utf-8")
        assert register.load(path) == {}

    def test_a_missing_file_is_an_empty_register(self, tmp_path):
        assert register.load(tmp_path / "nope.json") == {}

    def test_an_entry_with_no_id_is_dropped_rather_than_guessed_at(self, tmp_path):
        path = tmp_path / "issues.json"
        path.write_text(json.dumps({"issues": [{"kind": "stalled"}]}), encoding="utf-8")
        assert register.load(path) == {}


class TestWhatGetsFiled:
    def test_a_stall_is_one_issue_not_one_per_cause(self):
        # Four causes on one task would otherwise become four issues and the totals
        # would stop meaning anything
        worst = [
            {
                "key": "E-1",
                "summary": "Authentication",
                "assignee": "Ada",
                "explained_days": 4.5,
                "window": {"days": 11},
                "causes": [
                    {"kind": "owner_in_meetings", "days": 2.8, "detail": "meetings"},
                    {"kind": "owner_worked_elsewhere", "days": 2, "detail": "elsewhere"},
                ],
            }
        ]
        got = register.from_stalls(worst)
        assert len(got) == 1
        assert got[0]["kind"] == "owner_in_meetings", "the biggest cause is the headline"
        assert got[0]["days"] == 4.5

    def test_a_stall_nothing_explains_still_gets_filed(self):
        got = register.from_stalls([{"key": "E-1", "window": {"days": 6}, "causes": []}])
        assert got[0]["kind"] == "unexplained_silence"
        assert got[0]["days"] == 6

    def test_signals_come_across_with_their_numbers(self):
        got = register.from_signals(
            [{"kind": "stalled", "key": "E-1", "detail": "x", "facts": {"idle_days": 12}}]
        )
        assert got[0]["days"] == 12

    def test_a_signal_with_no_kind_is_dropped(self):
        assert register.from_signals([{"key": "E-1"}]) == []


class TestWhoIsAffected:
    def build(self):
        return schedule.to_tasks(
            [
                {"key": "A", "summary": "Auth", "assignee": "Ada"},
                {"key": "B", "summary": "API", "assignee": "Bo", "deps": ["A"]},
                {"key": "C", "summary": "UI", "assignee": "Cal", "deps": ["B"]},
                {"key": "Z", "summary": "Docs", "assignee": "Zed"},
            ]
        )

    def test_it_walks_the_whole_chain_downstream(self):
        who = register.affected("A", self.build())
        assert [p["who"] for p in who] == ["Bo", "Cal"]

    def test_somebody_unrelated_is_not_told(self):
        assert "Zed" not in [p["who"] for p in register.affected("A", self.build())]

    def test_finished_work_downstream_needs_no_warning(self):
        tasks = self.build()
        tasks["B"].status = "Done"
        assert [p["who"] for p in register.affected("A", tasks)] == ["Cal"]

    def test_each_person_is_named_once(self):
        tasks = schedule.to_tasks(
            [
                {"key": "A", "summary": "Auth", "assignee": "Ada"},
                {"key": "B", "summary": "b", "assignee": "Bo", "deps": ["A"]},
                {"key": "C", "summary": "c", "assignee": "Bo", "deps": ["A"]},
            ]
        )
        assert [p["who"] for p in register.affected("A", tasks)] == ["Bo"]

    def test_a_task_nobody_depends_on_affects_nobody(self):
        assert register.affected("Z", self.build()) == []

    def test_an_unknown_task_is_empty_rather_than_an_error(self):
        assert register.affected("NOPE", self.build()) == []
