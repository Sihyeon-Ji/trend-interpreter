"""Available time — what is actually left to work with once meetings have taken their share.

capacity.py has so far assumed "one business day = one full day of work".
In reality half of it goes to meetings and other projects. That data is in neither the board nor
the repo — only the calendar has it.

There is one number here: **availability** — the fraction of a given day a given person can spend
on project work (0-1).

    4 hours of meetings / an 8-hour day  →  availability 0.5  →  a one-day task takes two

This module knows nothing about calendar APIs. It takes {person: {date: meeting hours}} —
the adapters (MS Graph, local) put it in that shape.
"""

from __future__ import annotations

import datetime as _dt

WORKDAY_HOURS = 8.0
MIN_FRACTION = 0.05  # even a fully booked day is not zero (zero pushes the schedule out forever)


def fraction_from_hours(meeting_hours: float, workday_hours: float = WORKDAY_HOURS) -> float:
    """Meeting hours → that day's availability. Overrunning the workday still never goes below 0."""
    if workday_hours <= 0:
        return 0.0
    free = (workday_hours - max(0.0, meeting_hours)) / workday_hours
    return max(MIN_FRACTION, min(1.0, free))


def from_busy_hours(busy: dict, workday_hours: float = WORKDAY_HOURS) -> dict:
    """{person: {ISO date: meeting hours}} → {person: {ISO date: availability}}."""
    return {
        who: {day: fraction_from_hours(hours, workday_hours) for day, hours in days.items()}
        for who, days in (busy or {}).items()
    }


def from_events(events, workday_hours: float = WORKDAY_HOURS) -> dict:
    """A list of calendar events → the availability table.

    One event: {"attendee": name, "date": "YYYY-MM-DD", "hours": 1.5}
    For an all-day event, put the whole workday in hours.
    Several on one day are summed — overlapping meetings are the adapter's job to resolve.
    """
    busy: dict[str, dict[str, float]] = {}
    for e in events or []:
        who = (e.get("attendee") or "").strip()
        day = (e.get("date") or "")[:10]
        if not who or not day:
            continue
        busy.setdefault(who, {})[day] = busy.setdefault(who, {}).get(day, 0.0) + float(
            e.get("hours") or 0.0
        )
    return from_busy_hours(busy, workday_hours)


def table(
    availability: dict | None,
    people,
    today: _dt.date,
    horizon: int,
    holidays=(),
) -> dict:
    """Expand the table so it can be looked up by business-day offset instead of by date.

    The scheduler runs on business-day offsets, so this is unrolled once rather than per lookup.
    Days missing from the calendar count as 1.0 (fully available) — not knowing is not being busy.
    """
    from pmo_agent import schedule

    days = [schedule.add_workdays(today, i, holidays).isoformat() for i in range(horizon + 1)]
    out: dict[str, list[float]] = {}
    for who in people:
        per_day = (availability or {}).get(who, {})
        out[who] = [float(per_day.get(d, 1.0)) for d in days]
    return out


def span_end(rates: list, start: float, work: float) -> float:
    """Where `work` (in whole business days) finishes, starting from business-day offset `start`.

    Low-availability days stretch it. A run of days at 0.5 makes one day of work take two.
    """
    if work <= 1e-9:
        return start
    pos, remaining = start, work
    limit = len(rates)
    while remaining > 1e-9:
        day = int(pos)
        if day >= limit:  # past the horizon, assume full availability
            return pos + remaining
        rate = rates[day]
        left_today = (1.0 - (pos - day)) * rate
        if rate > 0 and left_today >= remaining - 1e-9:
            return pos + remaining / rate
        remaining -= max(0.0, left_today)
        pos = day + 1
    return pos


def meeting_load(availability: dict | None, who: str, today: _dt.date, days: int = 10) -> dict:
    """How much this person loses to meetings over the next N business days. Report evidence."""
    from pmo_agent import schedule

    per_day = (availability or {}).get(who, {})
    lost = 0.0
    for i in range(days):
        d = schedule.add_workdays(today, i).isoformat()
        lost += 1.0 - float(per_day.get(d, 1.0))
    return {
        "assignee": who,
        "window_days": days,
        "lost_days": round(lost, 1),
        "lost_hours": round(lost * WORKDAY_HOURS, 1),
        "available_days": round(days - lost, 1),
    }
