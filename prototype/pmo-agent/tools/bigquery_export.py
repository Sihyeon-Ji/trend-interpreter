"""Export daily snapshots for BigQuery, and print what to run to load them.

The agent answers about today. A director asks about a quarter: is the gap between the
promised date and the achievable one getting *worse*, which team has been the bottleneck
*most often*, how long does a decision sit before somebody makes it. Those need a history,
and a history is rows in a table.

So this walks the simulated world backwards, takes a reading on each business day, and
writes one newline-delimited JSON file per table. Ninety days across two projects is a few
thousand rows — small for BigQuery and large enough that the questions above stop being
answerable by reading the screen, which is the honest reason to have a warehouse at all.

The backfill is only possible because the world is simulated: it can be asked what it
looked like on any date. Against live tools there is no history to walk, so a real
deployment runs this once a day and accumulates — which is the same rows, arriving slower.

Nothing here computes. Every value comes from the module that already had to defend it.

Run:
  python tools/bigquery_export.py                 90 days, into data/warehouse/
  python tools/bigquery_export.py --days 180      a longer history
  python tools/bigquery_export.py --ddl           print CREATE TABLE and stop
  python tools/bigquery_export.py --load          also print the bq commands
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import availability as avail_mod
from pmo_agent import (
    capacity,
    cause,
    linking,
    projects,
    register,
    rollup,
    schedule,
    signals,
    warehouse,
)
from pmo_agent.env import data_dir
from pmo_agent.seeds import ops as ops_seed
from pmo_agent.seeds import world as world_mod

DAYS = 90
OUT = "warehouse"
DATASET = "pmo"


def _teams() -> dict:
    return {p[0]: p[3] for p in world_mod.PEOPLE}


def _build_day(day: dt.date) -> dict:
    """One business day's reading of the simulated delivery project."""
    world = world_mod.simulate(day)
    projected = world_mod.project(world)
    tasks = schedule.from_jira_issues(projected["board"]["issues"])
    sched = schedule.summary(tasks, day)
    # The real meeting hours, not an empty table. `slip_days` is the headline column of
    # the whole warehouse and it is the difference capacity makes — without availability
    # every row would understate it by exactly the thing worth measuring.
    avail = avail_mod.from_events(projected["calendar"]["events"])
    cap = capacity.summary(tasks, day, availability=avail)
    linked = linking.link(
        tasks,
        projected["repo"]["commits"],
        projected["repo"]["pulls"],
        projected["repo"].get("people"),
    )

    pr = projects.Project("ECHO", "Echo PMO", "build")
    row = rollup.build_row(pr, sched, cap)
    row["critical_path"] = len(sched.get("critical_path") or [])
    row["bottleneck_team"] = _teams().get(row.get("bottleneck", ""), "")

    # What went wrong that day, filed the same way a live run files it — so the warehouse
    # can be asked how long issues stay open, which one snapshot can never answer.
    stalls = cause.worst(
        tasks,
        projected["repo"],
        projected["calendar"]["events"],
        day,
        top=5,
        notes=projected["notes"]["notes"],
    )
    findings = register.from_stalls(stalls) + register.from_signals(
        signals.summary(tasks, projected["repo"], day).get("mismatches") or []
    )
    for finding in findings:
        finding["affects"] = register.affected(finding.get("key", ""), tasks)
    entries = register.update(findings, "ECHO", day, {})

    return {
        "snapshots": warehouse.snapshot_rows(row, day),
        "tasks": warehouse.task_rows(
            tasks, sched.get("risks") or [], sched.get("critical_path") or [], "ECHO", day
        ),
        "issues": warehouse.issue_rows(entries, "ECHO", day),
        "links": warehouse.link_rows(linked, "ECHO", day),
        "meetings": warehouse.meeting_rows(projected["calendar"]["events"], _teams(), "ECHO", day),
    }


def _run_day(day: dt.date) -> dict:
    """One reading of the simulated operations queue."""
    from pmo_agent import health

    data = ops_seed.build(day)
    found = health.summary(data["issues"], day)
    pr = projects.Project(ops_seed.KEY, ops_seed.NAME, "run")
    row = rollup.run_row(pr, found)
    row["open_tickets"] = found.get("open")
    return {"snapshots": warehouse.snapshot_rows(row, day)}


def collect(days: int = DAYS, today: dt.date | None = None) -> dict:
    """Walk backwards a business day at a time and gather every table's rows."""
    today = today or dt.date.today()
    out: dict = {name: [] for name in warehouse.SCHEMAS}
    for step in range(days):
        day = schedule.add_workdays(today, -step)
        for part in (_build_day(day), _run_day(day)):
            for table, rows in part.items():
                out[table].extend(rows)
    return out


def write(rows: dict, where: str = "") -> dict:
    """One newline-delimited JSON file per table, which is what `bq load` wants."""
    target = where or str(data_dir() / OUT)
    os.makedirs(target, exist_ok=True)
    written = {}
    for table, data in rows.items():
        path = os.path.join(target, f"{table}.jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            for row in data:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        written[table] = {"path": path, "rows": len(data), "bytes": os.path.getsize(path)}
        schema_path = os.path.join(target, f"{table}.schema.json")
        with open(schema_path, "w", encoding="utf-8") as handle:
            json.dump(warehouse.bq_schema(table), handle, ensure_ascii=False, indent=1)
    return written


def load_commands(written: dict, dataset: str = DATASET) -> list:
    """What to run once a project exists. Printed rather than executed — this writes
    into somebody's cloud account, and that is a decision, not a side effect."""
    out = [f"bq --location=asia-northeast1 mk --dataset {dataset}"]
    for table, info in written.items():
        out.append(
            f"bq load --source_format=NEWLINE_DELIMITED_JSON "
            f"--time_partitioning_field=snapshot_date --clustering_fields=project "
            f"{dataset}.{table} {info['path']} {info['path'].replace('.jsonl', '.schema.json')}"
        )
    return out


# Deliberately not "is the gap getting worse". A simulated backfill holds the project at
# one maturity, so a time series over it is flat by construction, and offering the query
# would be selling an artefact as a finding.
QUESTIONS = {
    "how big is the gap between promised and achievable": """
SELECT project_name, forecast_finish, achievable_finish, slip_days
FROM `pmo.snapshots`
WHERE kind = 'build'
  AND snapshot_date = (SELECT MAX(snapshot_date) FROM `pmo.snapshots`);""",
    "who is the bottleneck most often": """
SELECT bottleneck, bottleneck_team, COUNT(*) AS days_as_bottleneck
FROM `pmo.snapshots`
WHERE bottleneck != ''
GROUP BY bottleneck, bottleneck_team
ORDER BY days_as_bottleneck DESC;""",
    "which work crosses team boundaries most": """
SELECT team, COUNT(*) AS tasks, SUM(cross_team_deps) AS deps_on_other_teams
FROM `pmo.tasks`
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM `pmo.tasks`)
GROUP BY team ORDER BY deps_on_other_teams DESC;""",
    "how sure are the links we act on": """
SELECT how, COUNT(*) AS links, ROUND(AVG(confidence), 2) AS mean_confidence
FROM `pmo.links`
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM `pmo.links`)
GROUP BY how ORDER BY links DESC;""",
    "where does meeting time actually go": """
SELECT team, title, ROUND(SUM(hours), 1) AS hours
FROM `pmo.meetings`
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM `pmo.meetings`)
GROUP BY team, title ORDER BY hours DESC LIMIT 10;""",
}


def main(argv: list) -> int:
    if "--ddl" in argv:
        for table in warehouse.SCHEMAS:
            print(warehouse.ddl(table, DATASET), "\n")
        return 0

    days = DAYS
    if "--days" in argv:
        at = argv.index("--days")
        days = int(argv[at + 1]) if len(argv) > at + 1 else DAYS

    print(f"reading {days} business days of the simulated world…")
    rows = collect(days)
    written = write(rows)

    print()
    total = 0
    for table, info in written.items():
        total += info["rows"]
        print(f"  {table:<11} {info['rows']:>6} rows  {info['bytes'] / 1024:>7.0f} KB")
    print(f"  {'total':<11} {total:>6} rows")

    print("\nquestions this data answers:")
    for question in QUESTIONS:
        print(f"  · {question}")
    print(
        "\nnot a trend: the simulated world has no fixed origin, so every snapshot sits"
        "\nat the same project maturity. A real trend needs a real daily run."
    )
    if "--why" in argv:
        print("\n" + (__doc__ or "").split("Run:")[0].strip())
    if "--sql" in argv:
        for question, query in QUESTIONS.items():
            print(f"\n-- {question}{query}")

    if "--load" in argv:
        print("\nto load it (needs a GCP project):")
        for line in load_commands(written):
            print(f"  {line}")
    else:
        print("\n--load prints the bq commands. --ddl prints CREATE TABLE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
