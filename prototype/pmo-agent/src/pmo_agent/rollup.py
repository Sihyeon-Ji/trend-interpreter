"""Every project on one screen, for somebody who will not open five of them.

An executive is not asking for charts. They are asking three things: what is in trouble,
why, and when it clears. This project already produces all three — `cause.py` writes the
sentence, `capacity.py` writes the date — so a roll-up needs no new calculation. It needs
the same answers, one line each, worst first.

Two things are easy to get wrong here and both are refused.

**The finish date is not the only headline.** A delivery project is judged on a date; work
that runs has no date, and printing one would be confident nonsense. Each kind gets the
line that means something for it.

**The unexplained part is not hidden.** The temptation grows with the seniority of the
reader: a tidy dashboard is what gets asked for, and "3.5 of 13 days accounted for" is not
tidy. Folding it away would make every other number here look more certain than it is, so
it rides along on the row. Collapse it in the interface if you like; do not drop it.

Nothing here calls a model or a network. It asks the tool layer for each project's numbers
and arranges them.
"""

from __future__ import annotations

import datetime as _dt

OK = "ok"
WATCH = "watch"
RISK = "risk"
UNKNOWN = "unknown"
ORDER = {RISK: 0, WATCH: 1, UNKNOWN: 2, OK: 3}

SLIP_WATCH = 3  # business days later than the dependency-only forecast
SLIP_RISK = 10


def _state_build(schedule_: dict, capacity_: dict) -> str:
    """How a delivery project is doing: how far capacity pushes the honest date out."""
    slip = capacity_.get("slip_vs_unconstrained")
    at_risk = len(schedule_.get("risks") or [])
    if slip is None:
        return UNKNOWN
    if slip >= SLIP_RISK or at_risk >= 5:
        return RISK
    if slip >= SLIP_WATCH or at_risk:
        return WATCH
    return OK


def _state_run(health_: dict) -> str:
    """How a queue is doing: keeping up, and whether anything keeps coming back."""
    if not health_:
        return UNKNOWN
    stuck = [r for r in health_.get("recurring") or [] if r.get("open", 0) >= 2]
    if not health_.get("keeping_up") and (health_.get("aged") or stuck):
        return RISK
    if not health_.get("keeping_up") or stuck or health_.get("aged"):
        return WATCH
    return OK


def build_row(project, schedule_: dict, capacity_: dict, stalls: dict | None = None) -> dict:
    """One delivery project's line: the date, how far it moved, and why."""
    worst = (stalls or {}).get("worst") or []
    top = worst[0] if worst else None
    return {
        "key": project.key,
        "name": project.label,
        "kind": project.kind,
        "state": _state_build(schedule_, capacity_),
        "headline": capacity_.get("capacity_finish") or schedule_.get("predicted_finish") or "",
        "headline_label": "achievable finish",
        "baseline": schedule_.get("predicted_finish") or "",
        "slip_days": capacity_.get("slip_vs_unconstrained"),
        "at_risk": len(schedule_.get("risks") or []),
        "total": schedule_.get("total"),
        "done": schedule_.get("done"),
        "bottleneck": (capacity_.get("bottleneck") or {}).get("assignee", ""),
        "why": (top or {}).get("note", ""),
        "why_key": (top or {}).get("key", ""),
        # The part nobody accounted for, carried rather than folded away. A tidy number
        # is what gets asked for and is exactly what would make the rest look surer.
        "unexplained_days": (top or {}).get("unexplained_days"),
        # What that sentence was built from. A reader in another language needs it
        # written again from the same numbers, not translated out of the English.
        "why_facts": {
            "window": {"days": ((top or {}).get("window") or {}).get("days", 0)},
            "explained_days": (top or {}).get("explained_days", 0),
            "causes": [{"kind": c.get("kind")} for c in ((top or {}).get("causes") or [])],
            "trace": (top or {}).get("trace"),
        }
        if top
        else None,
    }


def run_row(project, health_: dict) -> dict:
    """One operations project's line. No finish date, because there is no finish."""
    stuck = next((r for r in health_.get("recurring") or [] if r.get("open", 0) >= 2), None)
    return {
        "key": project.key,
        "name": project.label,
        "kind": project.kind,
        "state": _state_run(health_),
        "headline": str(health_.get("open", 0)),
        "headline_label": "open now",
        "baseline": str(health_.get("open_was", 0)),
        "arrived": health_.get("arrived"),
        "closed": health_.get("closed"),
        "keeping_up": health_.get("keeping_up"),
        "median_age_days": health_.get("median_age_days"),
        "aged": len(health_.get("aged") or []),
        "recurring": stuck["fault"] if stuck else "",
        "why": health_.get("note", ""),
        "why_facts": {
            k: health_.get(k)
            for k in ("open", "open_was", "arrived", "closed", "window_days", "recurring")
        }
        if health_
        else None,
    }


def error_row(project, why: str) -> dict:
    """A project that could not be read. Present and unknown, never quietly absent.

    A missing row reads as a project with nothing wrong, which is the worst thing this
    screen could say about one it failed to open.
    """
    return {
        "key": project.key,
        "name": project.label,
        "kind": project.kind,
        "state": UNKNOWN,
        "headline": "—",
        "headline_label": "could not read",
        "why": why,
    }


def summary(rows: list, today: _dt.date | None = None) -> dict:
    """The rows, worst first, with one sentence over the top."""
    today = today or _dt.date.today()
    ordered = sorted(rows, key=lambda r: (ORDER.get(r.get("state"), 9), r.get("key", "")))
    counts = {s: sum(1 for r in ordered if r.get("state") == s) for s in (RISK, WATCH, OK, UNKNOWN)}
    return {
        "today": today.isoformat(),
        "projects": ordered,
        "counts": counts,
        "note": _note(ordered, counts),
    }


def _note(rows: list, counts: dict) -> str:
    if not rows:
        return "No projects are configured."
    if counts[RISK]:
        worst = next(r for r in rows if r["state"] == RISK)
        said = f"{counts[RISK]} of {len(rows)} projects need attention, worst is {worst['name']}"
        return f"{said} — {worst.get('why') or 'no explanation available'}"
    if counts[WATCH]:
        return f"Nothing is in trouble. {counts[WATCH]} of {len(rows)} are worth watching."
    if counts[UNKNOWN] == len(rows):
        return "None of the projects could be read."
    return f"All {len(rows)} projects are on track."
