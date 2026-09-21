"""The issue register — what went sideways on a project, remembered.

The agent already *finds* the things that matter: a task that stopped, an incident written
into a meeting note, a board that disagrees with the code. It has never remembered any of
them. Every run recalculates from scratch, which means three questions nobody can ask:

  · has this happened before? (an external spec change, three times this quarter)
  · how many days has it cost, in total, across everything it touched?
  · which of these are still open, and which quietly resolved themselves?

The job this replaces is a person searching chat, minutes and mail for "that thing from a
few weeks ago", and usually not finding it.

**An entry is a memory of a finding, not a new finding.** Everything in it was computed
elsewhere and is copied in with its evidence. This module decides three things only:
identity (is this the same issue as one we already have), state (open, resolved, or
lapsed) and impact (days, accumulated). No model is involved.

Identity is the hard part and it is deliberately conservative: two findings are the same
issue when they are the same **kind** on the same **task** in the same project. A looser
rule — matching on words, say — would merge two different problems and then report their
days as one, which is worse than filing them twice.

Storage is a JSON file today. It is the first thing here that has to persist between runs,
so it is also the first that would move to Firestore.
"""

from __future__ import annotations

import datetime as _dt
import json

from pmo_agent import schedule
from pmo_agent.env import data_dir

FILE = "issues.json"
LAPSE_DAYS = 14  # unseen for this long and an open issue is stale, not closed

OPEN = "open"
RESOLVED = "resolved"
LAPSED = "lapsed"


def ident(project: str, kind: str, key: str) -> str:
    """The identity of an issue: same kind, same task, same project.

    Deliberately narrow. Matching on wording would merge two different problems and then
    add their days together, and a wrong total is worse than two rows.
    """
    return f"{project}:{kind}:{key}"


def _today(value=None) -> _dt.date:
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return _dt.date.today()


def load(path=None) -> dict:
    """{id: entry}. A file that cannot be read is an empty register, never an exception."""
    try:
        with open(path or (data_dir() / FILE), encoding="utf-8") as handle:
            found = json.load(handle)
    except (OSError, ValueError):
        return {}
    rows = found.get("issues") if isinstance(found, dict) else found
    return {r["id"]: r for r in rows or [] if isinstance(r, dict) and r.get("id")}


def save(entries: dict, path=None) -> str:
    target = str(path or (data_dir() / FILE))
    rows = sorted(entries.values(), key=lambda r: (r.get("first_seen", ""), r.get("id", "")))
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"issues": rows}, handle, ensure_ascii=False, indent=1)
    except OSError:
        pass  # a register that cannot be written is a forgetful run, not a failed one
    return target


def _entry(finding: dict, project: str, today: _dt.date) -> dict:
    return {
        "id": ident(project, finding["kind"], finding.get("key", "")),
        "project": project,
        "kind": finding["kind"],
        "key": finding.get("key", ""),
        "summary": finding.get("summary", ""),
        "owner": finding.get("assignee", ""),
        "detail": finding.get("detail", ""),
        "evidence": list(finding.get("evidence") or [])[:3],
        "first_seen": today.isoformat(),
        "last_seen": today.isoformat(),
        "seen": 1,
        "days": float(finding.get("days") or 0.0),
        "peak_days": float(finding.get("days") or 0.0),
        "state": OPEN,
        "affects": list(finding.get("affects") or []),
    }


def _state(entry: dict, today: _dt.date, lapse: int) -> str:
    """Open, resolved, or lapsed — and the third is not a euphemism for the second.

    An issue stops being reported for two very different reasons: it got fixed, or
    everyone stopped looking. Calling both "resolved" is the comfortable lie that makes a
    register useless after a quarter, so an issue that simply went quiet says so.
    """
    if entry.get("state") == RESOLVED:
        return RESOLVED
    gone = (today - _today(entry.get("last_seen"))).days
    return LAPSED if gone >= lapse else OPEN


def update(
    findings: list,
    project: str,
    today: _dt.date | None = None,
    entries: dict | None = None,
    lapse: int = LAPSE_DAYS,
) -> dict:
    """Fold this run's findings into the register and return it.

    A finding seen again updates its entry; one that stops appearing is marked resolved
    rather than deleted, because "this happened and then stopped" is the fact worth
    keeping. Pure calculation — nothing here reads or writes a file.
    """
    today = _today(today)
    out = {k: dict(v) for k, v in (entries or {}).items()}
    seen_now = set()

    for finding in findings or []:
        if not finding.get("kind"):
            continue
        entry_id = ident(project, finding["kind"], finding.get("key", ""))
        seen_now.add(entry_id)
        if entry_id not in out:
            out[entry_id] = _entry(finding, project, today)
            continue
        row = out[entry_id]
        days = float(finding.get("days") or 0.0)
        # `days` is how long this issue has been costing, recomputed each run, so it is
        # the latest reading rather than something to add up. Adding would double-count
        # the same fortnight once per run.
        row["days"] = days
        row["peak_days"] = max(float(row.get("peak_days") or 0.0), days)
        if row.get("last_seen") != today.isoformat():
            row["seen"] = int(row.get("seen") or 0) + 1
        row["last_seen"] = today.isoformat()
        row["detail"] = finding.get("detail", row.get("detail", ""))
        row["state"] = OPEN
        if finding.get("evidence"):
            row["evidence"] = list(finding["evidence"])[:3]
        if finding.get("affects"):
            row["affects"] = list(finding["affects"])

    for entry_id, row in out.items():
        if row.get("project") != project or entry_id in seen_now:
            continue
        # Not reported this run. It either got fixed or nobody is looking any more.
        row["state"] = RESOLVED if row.get("state") == OPEN else _state(row, today, lapse)
        if row["state"] == RESOLVED and not row.get("resolved_on"):
            row["resolved_on"] = today.isoformat()
    return out


def recurring(entries: dict, project: str = "", least: int = 2) -> list:
    """Kinds that have come up on more than one task — a pattern rather than an incident.

    The same problem on three different tasks is a different conversation from three
    unrelated problems, and it is the one nobody has because nobody remembers.
    """
    counts: dict = {}
    for row in entries.values():
        if project and row.get("project") != project:
            continue
        counts.setdefault(row["kind"], []).append(row)
    return sorted(
        (
            {
                "kind": kind,
                "times": len(rows),
                "tasks": [r["key"] for r in rows if r.get("key")],
                "days": round(sum(float(r.get("peak_days") or 0.0) for r in rows), 1),
                "open": sum(1 for r in rows if r.get("state") == OPEN),
            }
            for kind, rows in counts.items()
            if len(rows) >= least
        ),
        key=lambda r: (-r["days"], -r["times"]),
    )


def summary(entries: dict, project: str = "", today=None) -> dict:
    """The register as a reader wants it: what is open, what it cost, what keeps happening."""
    today = _today(today)
    rows = [r for r in entries.values() if not project or r.get("project") == project]
    live = [r for r in rows if r.get("state") == OPEN]
    return {
        "today": today.isoformat(),
        "project": project,
        "open": sorted(live, key=lambda r: -float(r.get("days") or 0.0)),
        "resolved": [r for r in rows if r.get("state") == RESOLVED],
        "lapsed": [r for r in rows if r.get("state") == LAPSED],
        "days_open": round(sum(float(r.get("days") or 0.0) for r in live), 1),
        "recurring": recurring(entries, project),
        "note": _note(rows, live),
    }


def _note(rows: list, live: list) -> str:
    if not rows:
        return "Nothing has been filed yet. The register fills as the agent runs."
    if not live:
        return f"Nothing is open. {len(rows)} issues have been filed and closed."
    days = round(sum(float(r.get("days") or 0.0) for r in live), 1)
    oldest = min((r.get("first_seen", "") for r in live), default="")
    said = f"{len(live)} open, accounting for {days} business days between them"
    return f"{said}. The oldest has been open since {oldest}." if oldest else said + "."


# ---------------------------------------------------------------- what to file
def from_stalls(worst: list) -> list:
    """Stalls that `cause.py` explained, as findings. One per task, not one per cause.

    The cause with the most days is the headline; the rest are its detail. Filing each
    cause separately would turn one stall into four issues and the totals would stop
    meaning anything.
    """
    out = []
    for row in worst or []:
        causes = row.get("causes") or []
        top = max(causes, key=lambda c: c.get("days") or 0, default=None)
        out.append(
            {
                "kind": (top or {}).get("kind") or "unexplained_silence",
                "key": row.get("key", ""),
                "summary": row.get("summary", ""),
                "assignee": row.get("assignee", ""),
                "detail": (top or {}).get("detail") or row.get("note", ""),
                "days": row.get("explained_days") or row.get("window", {}).get("days") or 0,
                "evidence": [c.get("detail", "") for c in causes[:3]],
            }
        )
    return out


def from_signals(mismatches: list) -> list:
    """Board-against-code disagreements, as findings."""
    return [
        {
            "kind": m.get("kind", ""),
            "key": m.get("key", ""),
            "summary": m.get("summary", ""),
            "assignee": m.get("assignee", ""),
            "detail": m.get("detail", ""),
            "days": (m.get("facts") or {}).get("idle_days")
            or (m.get("facts") or {}).get("waited")
            or 0,
            "evidence": list(m.get("evidence") or [])[:2],
        }
        for m in mismatches or []
        if m.get("kind")
    ]


def affected(key: str, tasks: dict) -> list:
    """Who else this lands on: the owners of everything downstream of the blocked task.

    Not a guess about who cares — a walk of the dependency graph the board already holds.
    Somebody whose own work cannot start until this moves has a claim on being told.
    """
    if key not in (tasks or {}):
        return []
    after = schedule.successors(tasks)
    seen, queue, people = set(), [key], []
    while queue:
        current = queue.pop()
        for nxt in after.get(current, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
            task = tasks.get(nxt)
            if task and task.assignee and not task.is_done:
                people.append(
                    {
                        "who": task.assignee,
                        "team": task.team,
                        "task": nxt,
                        "summary": task.summary,
                    }
                )
    mine = (tasks[key].team or "").strip()
    out, named = [], set()
    for person in people:
        if person["who"] in named:
            continue
        named.add(person["who"])
        # Crossing a team boundary is the case worth flagging. Somebody on your own
        # team hears about it at standup; somebody on another team finds out in three
        # weeks, when their own work will not start.
        person["other_team"] = bool(mine and person["team"] and person["team"] != mine)
        out.append(person)
    return out
