"""Warehouse rows — no network, no BigQuery.

The agent answers about today. A director asks about a quarter, and those are questions
about a history, which is rows in a table. This module flattens one day's state; these
tests are about the flattening being lossless in the ways that matter and honest in the
ways it cannot be.

Two things carry the weight:

  · **nothing here computes.** Every value was defended upstream and is copied with a
    date attached. A test that lets this module derive a number would be permitting the
    one thing that makes a warehouse untrustworthy
  · **a queue has no finish date.** The columns that would hold one stay empty rather
    than being filled with something that looks like an answer

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json

from pmo_agent import schedule, warehouse

TODAY = dt.date(2026, 9, 21)


def tasks():
    return schedule.to_tasks(
        [
            {
                "key": "A",
                "summary": "[Build] Auth",
                "assignee": "Ada",
                "team": "Platform",
                "points": 8,
                "duedate": "2026-09-25",
            },
            {
                "key": "B",
                "summary": "[Build] API",
                "assignee": "Bo",
                "team": "Product",
                "points": 5,
                "deps": ["A"],
            },
            {
                "key": "C",
                "summary": "Docs",
                "assignee": "Cal",
                "team": "Product",
                "points": 1,
                "deps": ["B"],
            },
        ]
    )


class TestSchemas:
    def test_every_table_starts_with_the_snapshot_date(self):
        # Everything is partitioned on it, so a table without it cannot be queried cheaply
        for table, columns in warehouse.SCHEMAS.items():
            assert columns[0][0] == "snapshot_date", table

    def test_every_table_carries_the_project(self):
        for table, columns in warehouse.SCHEMAS.items():
            assert any(c[0] == "project" for c in columns), table

    def test_the_bq_schema_is_the_shape_bq_wants(self):
        got = warehouse.bq_schema("snapshots")
        assert all({"name", "type", "mode"} <= set(c) for c in got)
        assert {c["type"] for c in got} <= {"DATE", "STRING", "INT64", "FLOAT64", "BOOL"}

    def test_a_column_whose_meaning_is_not_obvious_explains_itself(self):
        # The description reaches BigQuery's own console, rather than a wiki nobody opens
        slip = next(c for c in warehouse.bq_schema("snapshots") if c["name"] == "slip_days")
        assert "description" in slip and slip["description"]

    def test_the_ddl_partitions_and_clusters(self):
        sql = warehouse.ddl("tasks")
        assert "PARTITION BY snapshot_date" in sql
        assert "CLUSTER BY project" in sql


class TestSnapshotRows:
    def build(self, **kw):
        row = {
            "key": "ECHO",
            "name": "Echo PMO",
            "kind": "build",
            "state": "risk",
            "baseline": "2026-10-13",
            "headline": "2026-11-09",
            "slip_days": 19,
            "total": 40,
            "done": 20,
            "at_risk": 12,
            "bottleneck": "Maya",
            "bottleneck_team": "Platform",
            "unexplained_days": 6.5,
        }
        row.update(kw)
        return warehouse.snapshot_rows(row, TODAY)[0]

    def test_both_dates_are_kept_because_the_gap_is_the_point(self):
        got = self.build()
        assert got["forecast_finish"] == "2026-10-13"
        assert got["achievable_finish"] == "2026-11-09"
        assert got["slip_days"] == 19

    def test_the_unexplained_part_survives_into_the_warehouse(self):
        # Dropping it here would make every other number in the table look surer
        assert self.build()["unexplained_days"] == 6.5

    def test_a_queue_gets_no_finish_date_at_all(self):
        got = warehouse.snapshot_rows(
            {
                "key": "OPS",
                "kind": "run",
                "headline": "11",
                "baseline": "2",
                "arrived": 16,
                "closed": 7,
                "state": "risk",
            },
            TODAY,
        )[0]
        assert got["forecast_finish"] is None and got["achievable_finish"] is None
        assert got["open_tickets"] == 11
        assert (got["arrived"], got["closed"]) == (16, 7)

    def test_a_headline_that_is_not_a_number_does_not_become_one(self):
        got = warehouse.snapshot_rows({"key": "X", "kind": "run", "headline": "—"}, TODAY)[0]
        assert got["open_tickets"] is None


class TestTaskRows:
    def rows(self):
        return warehouse.task_rows(
            tasks(),
            [{"key": "A", "delay_days": 21, "predicted_finish": "2026-10-01"}],
            ["A", "B"],
            "ECHO",
            TODAY,
        )

    def test_one_row_per_task(self):
        assert len(self.rows()) == 3

    def test_the_phase_comes_out_of_the_summary_prefix(self):
        by_key = {r["task_key"]: r for r in self.rows()}
        assert by_key["A"]["phase"] == "Build"
        assert by_key["C"]["phase"] == "", "a summary with no prefix has no phase"

    def test_dependencies_across_a_team_boundary_are_counted(self):
        # The column the others exist to contextualise
        by_key = {r["task_key"]: r for r in self.rows()}
        assert by_key["B"]["cross_team_deps"] == 1, "B is Product, depends on Platform"
        assert by_key["C"]["cross_team_deps"] == 0, "C and B are both Product"
        assert by_key["A"]["cross_team_deps"] == 0, "A depends on nothing"

    def test_risk_and_the_critical_path_are_flags_not_guesses(self):
        by_key = {r["task_key"]: r for r in self.rows()}
        assert by_key["A"]["at_risk"] and by_key["A"]["on_critical_path"]
        assert not by_key["C"]["at_risk"]
        assert by_key["A"]["delay_days"] == 21

    def test_a_task_nobody_flagged_has_no_forecast_invented_for_it(self):
        by_key = {r["task_key"]: r for r in self.rows()}
        assert by_key["C"]["predicted_finish"] is None


class TestIssueRows:
    def entries(self):
        return {
            "ECHO:stalled:A": {
                "id": "ECHO:stalled:A",
                "project": "ECHO",
                "kind": "stalled",
                "key": "A",
                "owner": "Ada",
                "state": "open",
                "days": 3.0,
                "peak_days": 8.0,
                "first_seen": "2026-09-01",
                "last_seen": "2026-09-21",
                "seen": 4,
                "affects": [{"who": "Bo", "other_team": True}, {"who": "Cal"}],
            },
            "OPS:stalled:X": {"id": "OPS:stalled:X", "project": "OPS", "kind": "stalled"},
        }

    def test_only_this_projects_issues_come_out(self):
        got = warehouse.issue_rows(self.entries(), "ECHO", TODAY)
        assert [r["issue_id"] for r in got] == ["ECHO:stalled:A"]

    def test_the_worst_it_ever_got_is_kept_beside_where_it_is_now(self):
        got = warehouse.issue_rows(self.entries(), "ECHO", TODAY)[0]
        assert (got["days"], got["peak_days"]) == (3.0, 8.0)

    def test_how_many_of_the_affected_are_on_another_team(self):
        got = warehouse.issue_rows(self.entries(), "ECHO", TODAY)[0]
        assert got["affects_people"] == 2 and got["affects_other_teams"] == 1


class TestLinkRows:
    def test_the_confidence_travels_with_the_link(self):
        # A warehouse that drops it turns every inference into a fact
        linked = {
            "A": {
                "commits": [{"sha": "abc", "name": "Ada", "date": "2026-09-15"}],
                "links": [{"sha": "abc", "how": "inferred", "confidence": 0.83}],
            }
        }
        got = warehouse.link_rows(linked, "ECHO", TODAY)[0]
        assert got["how"] == "inferred" and got["confidence"] == 0.83

    def test_a_commit_with_no_link_record_still_comes_through_without_a_confidence(self):
        linked = {"A": {"commits": [{"sha": "abc", "name": "Ada"}], "links": []}}
        got = warehouse.link_rows(linked, "ECHO", TODAY)[0]
        assert got["confidence"] is None and got["how"] == ""


class TestDates:
    def test_an_unreadable_date_becomes_null_rather_than_a_guess(self):
        assert warehouse._d("not a date") is None
        assert warehouse._d("") is None
        assert warehouse._d(None) is None

    def test_a_timestamp_is_cut_to_the_day(self):
        assert warehouse._d("2026-09-21T14:03:00Z") == "2026-09-21"

    def test_a_real_date_object_survives(self):
        assert warehouse._d(TODAY) == "2026-09-21"


class TestItIsAllJson:
    def test_every_table_serialises(self):
        rows = {
            "tasks": warehouse.task_rows(tasks(), [], [], "ECHO", TODAY),
            "meetings": warehouse.meeting_rows(
                [{"attendee": "Ada", "date": "2026-09-15", "hours": 2.0, "title": "Sync"}],
                {"Ada": "Platform"},
                "ECHO",
                TODAY,
            ),
        }
        for table, data in rows.items():
            for row in data:
                json.loads(json.dumps(row, ensure_ascii=False)), table

    def test_every_row_matches_its_declared_columns(self):
        # A column in the data that the schema does not declare would be dropped on load
        checks = {
            "tasks": warehouse.task_rows(tasks(), [], [], "ECHO", TODAY),
            "meetings": warehouse.meeting_rows([], {}, "ECHO", TODAY),
            "links": warehouse.link_rows({}, "ECHO", TODAY),
        }
        for table, data in checks.items():
            declared = {c[0] for c in warehouse.SCHEMAS[table]}
            for row in data:
                assert set(row) == declared, (table, set(row) ^ declared)
