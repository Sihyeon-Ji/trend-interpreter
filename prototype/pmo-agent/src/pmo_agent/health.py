"""How an operations project is doing — because "when does it finish" has no answer.

Everything else here answers a delivery question: a fixed scope, dependencies, a finish
date, and how far that date has moved. Point the same code at work that *runs* and the
headline number is not wrong so much as meaningless. A queue does not finish. Asking is a
category error, and answering anyway is the kind of confident nonsense this project exists
to avoid.

So a `run` project gets different numbers, from the same board:

  arriving / closing   the only pair that says whether a team is keeping up. One without
                       the other is a vanity metric — closing forty is good news or bad
                       depending entirely on how many arrived
  backlog              open now, and whether that is more or less than a fortnight ago
  age                  how long the open ones have been sitting. The median, not the mean:
                       one ticket open since March would drag a mean into fiction
  time to close        how long the closed ones took
  recurring            the same fault on several tickets. Five tickets are one problem,
                       and counting open items alone hides that completely

No forecast. Nothing here predicts next month's arrivals, because the honest basis for
that is a seasonality model nobody has, and a straight-line guess dressed up as a forecast
is exactly the thing this codebase refuses elsewhere.

Pure calculation. No model, no network.
"""

from __future__ import annotations

import datetime as _dt
import re

WINDOW = 14  # the fortnight the rates are measured over
AGED = 21  # open longer than this and a ticket is ageing, not in flight
RECURS = 2  # the same fault this many times is a pattern


def _date(value):
    try:
        return _dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _fault(summary: str) -> str:
    """A ticket's title with its category prefix stripped: the fault, not the ticket.

    `[Incident] Checkout times out under load` and `[Bug] Checkout times out under load`
    are the same problem filed twice, and grouping on the raw summary would miss it.
    """
    return re.sub(r"^\s*\[[^\]]+\]\s*", "", summary or "").strip().lower()


def _rows(issues: list) -> list:
    """The board's issues in the shape this module wants, whatever the adapter gave."""
    out = []
    for issue in issues or []:
        fields = issue.get("fields") or {}
        status = ((fields.get("status") or {}).get("name") or "").strip()
        out.append(
            {
                "key": issue.get("key", ""),
                "summary": fields.get("summary", ""),
                "fault": _fault(fields.get("summary", "")),
                "status": status,
                "assignee": ((fields.get("assignee") or {}).get("displayName") or "").strip(),
                "created": _date(fields.get("created")),
                "resolved": _date(fields.get("resolutiondate")),
            }
        )
    return out


def _between(rows: list, field: str, start: _dt.date, end: _dt.date) -> list:
    return [r for r in rows if r[field] and start <= r[field] < end]


def _median(values: list) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return round((ordered[middle - 1] + ordered[middle]) / 2, 1)


def recurring(rows: list, least: int = RECURS) -> list:
    """Faults filed more than once. Five tickets are one problem."""
    groups: dict = {}
    for row in rows:
        if row["fault"]:
            groups.setdefault(row["fault"], []).append(row)
    out = [
        {
            "fault": rows_[0]["summary"],
            "times": len(rows_),
            "open": sum(1 for r in rows_ if not r["resolved"]),
            "keys": [r["key"] for r in rows_],
            "first": min((r["created"] for r in rows_ if r["created"]), default=None),
        }
        for fault, rows_ in groups.items()
        if len(rows_) >= least
    ]
    for row in out:
        row["first"] = row["first"].isoformat() if row["first"] else ""
    return sorted(out, key=lambda r: (-r["open"], -r["times"]))


def summary(issues: list, today: _dt.date | None = None, days: int = WINDOW) -> dict:
    """The state of a queue: is it keeping up, how old is what is waiting, what recurs."""
    today = today or _dt.date.today()
    rows = _rows(issues)
    start = today - _dt.timedelta(days=days)
    before = start - _dt.timedelta(days=days)

    live = [r for r in rows if not r["resolved"]]
    arrived = len(_between(rows, "created", start, today + _dt.timedelta(days=1)))
    closed = len(_between(rows, "resolved", start, today + _dt.timedelta(days=1)))
    arrived_before = len(_between(rows, "created", before, start))
    closed_before = len(_between(rows, "resolved", before, start))

    # What the backlog was a fortnight ago: open now, minus what arrived since, plus what
    # closed since. Reconstructed rather than remembered, so it needs no stored history.
    was = len(live) - arrived + closed
    ages = [(today - r["created"]).days for r in live if r["created"]]
    took = [
        (r["resolved"] - r["created"]).days
        for r in rows
        if r["resolved"] and r["created"] and r["resolved"] >= start
    ]
    aged = sorted(
        (r for r in live if r["created"] and (today - r["created"]).days >= AGED),
        key=lambda r: r["created"],
    )

    repeats = recurring(rows)
    return {
        "today": today.isoformat(),
        "window_days": days,
        "open": len(live),
        "open_was": max(0, was),
        "arrived": arrived,
        "closed": closed,
        "arrived_before": arrived_before,
        "closed_before": closed_before,
        "keeping_up": closed >= arrived,
        "median_age_days": _median(ages),
        "oldest_days": max(ages, default=0),
        "median_close_days": _median(took),
        "aged": [
            {
                "key": r["key"],
                "summary": r["summary"],
                "assignee": r["assignee"],
                "days": (today - r["created"]).days,
            }
            for r in aged[:6]
        ],
        "recurring": repeats,
        "by_owner": _by_owner(live),
        "note": _note(len(live), max(0, was), arrived, closed, repeats, days),
    }


def _by_owner(live: list) -> list:
    counts: dict = {}
    for row in live:
        counts[row["assignee"] or "unassigned"] = counts.get(row["assignee"] or "unassigned", 0) + 1
    return sorted(
        ({"assignee": who, "open": n} for who, n in counts.items()), key=lambda r: -r["open"]
    )


def _note(now: int, was: int, arrived: int, closed: int, repeats: list, days: int) -> str:
    """One sentence: is the queue keeping up, and is anything repeating."""
    if not now and not arrived:
        return "Nothing is open and nothing arrived. There is no queue to report on."
    moved = now - was
    if closed >= arrived:
        said = (
            f"{closed} closed against {arrived} that arrived in {days} days — the queue is "
            f"keeping up, and the backlog is {now}"
        )
        said += f", down from {was}." if moved < 0 else "."
    else:
        said = (
            f"{arrived} arrived against {closed} closed in {days} days, so the backlog grew "
            f"from {was} to {now}."
        )
    worst = next((r for r in repeats if r["open"]), None)
    if worst:
        said += (
            f" “{worst['fault']}” has been filed {worst['times']} times, "
            f"{worst['open']} of them still open — one problem, not {worst['times']}."
        )
    return said
