"""Flat rows for a warehouse — because the agent only ever knows *today*.

Every calculation here answers about the moment it runs. That is the right shape for a
question like "why did this stop", and the wrong shape for every question a director
actually asks at a quarterly review:

  · is the gap between what the board promises and what is achievable **getting worse**?
  · which team has been the bottleneck **most often**, not just today?
  · do incidents of one kind take longer to close than another, **over a quarter**?
  · how long does a decision sit open before somebody makes it?

None of those can be computed from one snapshot, and none of them belongs in `schedule.py`.
They are questions about a *history*, and a history is rows in a table.

So this turns one day's state into flat rows with a date on them. Run it daily and the
rows accumulate; the questions above become SQL over a few thousand rows rather than new
Python over none. That is the point at which BigQuery earns its place, and not before —
a single project's forty tasks is a dictionary, not a warehouse.

**Nothing here computes anything.** Every value was produced by a module that already had
to defend it, and is copied out with its date attached. If a number is wrong in the
warehouse it was wrong upstream, which is where it should be fixed.

Types are declared alongside the rows so the table can be created before a single row
lands, and so a column whose meaning is not obvious carries its description into the
schema rather than living only in somebody's memory.
"""

from __future__ import annotations

import datetime as _dt

# The tables. `description` goes into BigQuery's own schema, so the column explains
# itself in the console rather than in a wiki nobody opens.
SCHEMAS: dict = {
    "snapshots": [
        ("snapshot_date", "DATE", "the day this reading was taken"),
        ("project", "STRING", "board key"),
        ("project_name", "STRING", ""),
        ("kind", "STRING", "build (has a finish) or run (a queue)"),
        ("state", "STRING", "risk, watch, ok or unknown"),
        ("forecast_finish", "DATE", "dependencies only — what most tools would print"),
        ("achievable_finish", "DATE", "with one task per person and meeting time"),
        ("slip_days", "INT64", "business days between the two. The honest gap"),
        ("tasks_total", "INT64", ""),
        ("tasks_done", "INT64", ""),
        ("tasks_at_risk", "INT64", ""),
        ("critical_path", "INT64", "tasks with no slack"),
        ("bottleneck", "STRING", "the owner the finish date waits on"),
        ("bottleneck_team", "STRING", ""),
        ("unexplained_days", "FLOAT64", "of the worst stall, the part nothing accounts for"),
        ("open_tickets", "INT64", "run projects only"),
        ("arrived", "INT64", "run projects only, in the window"),
        ("closed", "INT64", "run projects only, in the window"),
    ],
    "tasks": [
        ("snapshot_date", "DATE", ""),
        ("project", "STRING", ""),
        ("task_key", "STRING", ""),
        ("summary", "STRING", ""),
        ("phase", "STRING", "from the summary prefix, when the board uses one"),
        ("status", "STRING", ""),
        ("assignee", "STRING", ""),
        ("team", "STRING", "the owner's team, when the board records it"),
        ("duedate", "DATE", ""),
        ("predicted_finish", "DATE", ""),
        ("delay_days", "FLOAT64", "forecast minus due date, when it is late"),
        ("at_risk", "BOOL", ""),
        ("on_critical_path", "BOOL", ""),
        ("points", "FLOAT64", ""),
        ("progress", "FLOAT64", "0-1"),
        ("dep_count", "INT64", ""),
        (
            "cross_team_deps",
            "INT64",
            "dependencies owned by another team. Where coordination fails",
        ),
    ],
    "issues": [
        ("snapshot_date", "DATE", ""),
        ("project", "STRING", ""),
        ("issue_id", "STRING", "project:kind:task — stable across runs"),
        ("kind", "STRING", ""),
        ("task_key", "STRING", ""),
        ("owner", "STRING", ""),
        ("state", "STRING", "open, resolved or lapsed. Lapsed is not resolved"),
        ("days", "FLOAT64", "business days this is currently accounting for"),
        ("peak_days", "FLOAT64", "the worst it ever got"),
        ("first_seen", "DATE", ""),
        ("last_seen", "DATE", ""),
        ("times_seen", "INT64", "runs on which it was reported"),
        ("affects_people", "INT64", "owners downstream of it"),
        ("affects_other_teams", "INT64", "how many of those are on another team"),
    ],
    "links": [
        ("snapshot_date", "DATE", ""),
        ("project", "STRING", ""),
        ("task_key", "STRING", ""),
        ("sha", "STRING", ""),
        ("author", "STRING", ""),
        ("committed_on", "DATE", ""),
        ("how", "STRING", "key, inferred or model"),
        ("confidence", "FLOAT64", "0-1. An inferred link is never presented as a fact"),
    ],
    "meetings": [
        ("snapshot_date", "DATE", ""),
        ("project", "STRING", ""),
        ("attendee", "STRING", ""),
        ("team", "STRING", ""),
        ("meeting_date", "DATE", ""),
        ("title", "STRING", ""),
        ("hours", "FLOAT64", ""),
    ],
}


def _d(value) -> str | None:
    """A date as BigQuery wants it, or None. Never a guess."""
    if isinstance(value, _dt.date):
        return value.isoformat()
    text = str(value or "")[:10]
    try:
        return _dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _phase(summary: str) -> str:
    """`[Build] Authentication` -> `Build`. Empty when the board does not use prefixes."""
    text = (summary or "").strip()
    return text[1 : text.index("]")].strip() if text.startswith("[") and "]" in text else ""


def snapshot_rows(project: dict, day: _dt.date) -> list:
    """One row: the day's headline for one project. Everything is copied, not computed."""
    row = {
        "snapshot_date": _d(day),
        "project": project.get("key", ""),
        "project_name": project.get("name", ""),
        "kind": project.get("kind", ""),
        "state": project.get("state", ""),
        "forecast_finish": _d(project.get("baseline")),
        "achievable_finish": _d(project.get("headline")),
        "slip_days": project.get("slip_days"),
        "tasks_total": project.get("total"),
        "tasks_done": project.get("done"),
        "tasks_at_risk": project.get("at_risk"),
        "critical_path": project.get("critical_path"),
        "bottleneck": project.get("bottleneck", ""),
        "bottleneck_team": project.get("bottleneck_team", ""),
        "unexplained_days": project.get("unexplained_days"),
        "open_tickets": project.get("open_tickets"),
        "arrived": project.get("arrived"),
        "closed": project.get("closed"),
    }
    if project.get("kind") == "run":
        # A queue has no finish date, so the columns that would hold one stay empty
        # rather than being filled with something that looks like an answer.
        row["forecast_finish"] = row["achievable_finish"] = None
        row["open_tickets"] = _int(project.get("headline"))
        row["arrived"], row["closed"] = project.get("arrived"), project.get("closed")
    return [row]


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def task_rows(tasks: dict, risks: list, critical: list, project: str, day: _dt.date) -> list:
    """One row per task. `cross_team_deps` is the column the others exist to contextualise."""
    at_risk = {r["key"]: r for r in risks or []}
    on_path = set(critical or [])
    team_of = {k: (t.team or "") for k, t in tasks.items()}
    out = []
    for key, task in tasks.items():
        mine = team_of.get(key, "")
        crossing = sum(1 for d in task.deps if team_of.get(d) and mine and team_of[d] != mine)
        risk = at_risk.get(key, {})
        out.append(
            {
                "snapshot_date": _d(day),
                "project": project,
                "task_key": key,
                "summary": task.summary,
                "phase": _phase(task.summary),
                "status": task.status,
                "assignee": task.assignee,
                "team": mine,
                "duedate": _d(task.duedate),
                "predicted_finish": _d(risk.get("predicted_finish")),
                "delay_days": risk.get("delay_days"),
                "at_risk": key in at_risk,
                "on_critical_path": key in on_path,
                "points": task.points,
                "progress": task.progress,
                "dep_count": len(task.deps),
                "cross_team_deps": crossing,
            }
        )
    return out


def issue_rows(entries: dict, project: str, day: _dt.date) -> list:
    out = []
    for row in (entries or {}).values():
        if row.get("project") != project:
            continue
        affects = row.get("affects") or []
        out.append(
            {
                "snapshot_date": _d(day),
                "project": project,
                "issue_id": row.get("id", ""),
                "kind": row.get("kind", ""),
                "task_key": row.get("key", ""),
                "owner": row.get("owner", ""),
                "state": row.get("state", ""),
                "days": row.get("days"),
                "peak_days": row.get("peak_days"),
                "first_seen": _d(row.get("first_seen")),
                "last_seen": _d(row.get("last_seen")),
                "times_seen": row.get("seen"),
                "affects_people": len(affects),
                "affects_other_teams": sum(1 for a in affects if a.get("other_team")),
            }
        )
    return out


def link_rows(linked: dict, project: str, day: _dt.date) -> list:
    """One row per commit-to-task link, with how it was made and how sure.

    `how` and `confidence` travel together on purpose: an inferred link is never a fact,
    and a warehouse that drops the confidence turns every inference into one.
    """
    out = []
    for key, bundle in (linked or {}).items():
        by_sha = {r.get("sha"): r for r in bundle.get("links") or [] if r.get("sha")}
        for commit in bundle.get("commits") or []:
            record = by_sha.get(commit.get("sha"), {})
            out.append(
                {
                    "snapshot_date": _d(day),
                    "project": project,
                    "task_key": key,
                    "sha": commit.get("sha", ""),
                    "author": commit.get("name") or commit.get("author", ""),
                    "committed_on": _d(commit.get("date")),
                    "how": record.get("how", ""),
                    "confidence": record.get("confidence"),
                }
            )
    return out


def meeting_rows(events: list, teams: dict, project: str, day: _dt.date) -> list:
    return [
        {
            "snapshot_date": _d(day),
            "project": project,
            "attendee": e.get("attendee", ""),
            "team": teams.get(e.get("attendee", ""), ""),
            "meeting_date": _d(e.get("date")),
            "title": e.get("title", ""),
            "hours": float(e.get("hours") or 0.0),
        }
        for e in events or []
    ]


# --------------------------------------------------------------------- schema output
def bq_schema(table: str) -> list:
    """The table's schema in the shape `bq mk --schema` and the API both accept."""
    return [
        {"name": name, "type": kind, "mode": "NULLABLE", **({"description": why} if why else {})}
        for name, kind, why in SCHEMAS[table]
    ]


def ddl(table: str, dataset: str = "pmo") -> str:
    """CREATE TABLE, for anyone who would rather read SQL than JSON.

    Partitioned by the snapshot date and clustered by project, because every question
    this warehouse exists for filters on one or both, and an unpartitioned daily-snapshot
    table is the classic way to turn a cheap query into an expensive one.
    """
    cols = ",\n".join(
        f"  {name} {kind}" + (f"  -- {why}" if why else "") for name, kind, why in SCHEMAS[table]
    )
    return (
        f"CREATE TABLE IF NOT EXISTS `{dataset}.{table}` (\n{cols}\n)\n"
        f"PARTITION BY snapshot_date\n"
        f"CLUSTER BY project;"
    )
