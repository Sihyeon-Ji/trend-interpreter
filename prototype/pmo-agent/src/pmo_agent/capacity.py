"""Resource-constrained scheduling — one person cannot do five things at once.

schedule.py's forecast() only looks at dependencies. So it assumes one person runs eight tasks
in parallel, and answers that a project finishes in 22 days even when somebody is holding 38
business days of work. This module adds a per-owner capacity (1 concurrent task by default)
and produces a finish date that is actually achievable.

Method: serial schedule generation (serial SGS). Among tasks whose dependencies are met, take
      the one with the least slack and drop it into the owner's next free interval. A standard
      heuristic, fully deterministic — same input, same answer.

This module does not know about Jira either. It takes schedule.Task and nothing else.
"""

from __future__ import annotations

import datetime as _dt

from pmo_agent import availability as avail_mod
from pmo_agent import schedule

DEFAULT_CAPACITY = 1  # tasks one person holds at once
UNASSIGNED = "(unassigned)"


def _caps(tasks: dict, capacity) -> dict:
    """owner → how many tasks they can run at once."""
    people = {t.assignee or UNASSIGNED for t in tasks.values()}
    if isinstance(capacity, int):
        return {p: max(1, capacity) for p in people}
    out = {p: DEFAULT_CAPACITY for p in people}
    out.update({k: max(1, v) for k, v in (capacity or {}).items() if k in people})
    return out


def levelled(
    tasks: dict, today: _dt.date, capacity=None, holidays=(), availability: dict | None = None
) -> dict:
    """A finish forecast with resource constraints applied.

    Returns project_finish (achievable), unconstrained_finish (the old forecast), tasks, resources,
    bottleneck.
    tasks[key].waiting_days = dependencies met but the owner was busy — pure capacity loss.

    Pass `availability` to account for time eaten by meetings ({person: {ISO date: fraction}}).
    A run of days at 0.5 makes one day of work take two. Without it, everyone sits at 1.0.
    """
    order = schedule.topo_order(tasks)  # a cycle raises CycleError right here
    caps = _caps(tasks, capacity)
    cpm = schedule.cpm(tasks, today, holidays)["tasks"]
    # Per owner: a few "slots", each holding the intervals already taken. New tasks slot into gaps.
    # (Append after the last finish instead and a late-starting task claims the slot, leaving the
    #  whole front of it empty.)
    slots: dict[str, list[list[tuple[float, float]]]] = {
        p: [[] for _ in range(n)] for p, n in caps.items()
    }
    finish: dict[str, float] = {}
    rows: dict[str, dict] = {}
    busy = {p: 0.0 for p in caps}
    pending = set(order)

    # Flatten the availability table onto business-day offsets. Horizon = total work plus slack.
    horizon = int(sum(t.remaining for t in tasks.values()) * 2) + 60
    rates = avail_mod.table(availability, set(caps), today, horizon, holidays)

    def place(intervals: list, ready: float, work: float, who: str) -> tuple[float, float]:
        """The earliest (start, finish) at or after `ready` that fits `work` in one piece.

        Where it ends depends on availability — crossing a meeting-heavy stretch pushes it out.
        So we repeat: fix a start, compute the finish, and if it overlaps, move the start.
        """
        t = ready
        for _ in range(len(intervals) + 2):
            end = avail_mod.span_end(rates[who], t, work)
            clash = next(
                (iv for iv in sorted(intervals) if iv[0] < end - 1e-9 and iv[1] > t + 1e-9), None
            )
            if clash is None:
                return t, end
            t = clash[1]
        return t, avail_mod.span_end(rates[who], t, work)

    def priority(k):  # least slack, then earliest due date, then key
        t = tasks[k]
        return (cpm[k]["slack_days"], t.duedate or _dt.date.max, k)

    while pending:
        eligible = [k for k in pending if all(d in finish for d in tasks[k].deps)]
        if not eligible:  # cannot happen once topo_order has passed
            raise schedule.CycleError("schedule cannot advance: " + ", ".join(sorted(pending)))
        k = min(eligible, key=priority)
        pending.discard(k)
        t = tasks[k]
        who = t.assignee or UNASSIGNED
        dep_ready = max([finish[d] for d in t.deps], default=0.0)
        if t.remaining <= 0:  # finished tasks consume nobody
            start = end = dep_ready
        else:
            fits = [(*place(iv, dep_ready, t.remaining, who), i) for i, iv in enumerate(slots[who])]
            start, end, slot = min(fits)
            slots[who][slot].append((start, end))
            busy[who] += t.remaining
        finish[k] = end
        rows[k] = {
            "key": k,
            "summary": t.summary,
            "assignee": t.assignee,
            "status": t.status,
            "remaining_days": round(t.remaining, 2),
            "start": schedule.add_workdays(today, start, holidays),
            "finish": schedule.add_workdays(today, finish[k], holidays),
            "waiting_days": round(max(0.0, start - dep_ready), 2),
            "duedate": t.duedate,
            "late": bool(
                t.duedate and schedule.add_workdays(today, finish[k], holidays) > t.duedate
            ),
        }

    total = max(finish.values(), default=0.0)
    plain = schedule.forecast(tasks, today, holidays)
    resources = sorted(
        (
            {
                "assignee": p,
                "capacity": caps[p],
                "busy_days": round(busy[p], 1),
                "lost_to_meetings": (
                    avail_mod.meeting_load(availability, p, today)["lost_days"]
                    if availability
                    else 0.0
                ),
                "free_at": schedule.add_workdays(
                    today, max([e for iv in slots[p] for _, e in iv] or [0.0]), holidays
                ),
                "utilization": round(busy[p] / total, 2) if total else 0.0,
            }
            for p in caps
            if busy[p] > 0
        ),
        key=lambda r: -r["busy_days"],
    )
    return {
        "project_finish": schedule.add_workdays(today, total, holidays),
        "unconstrained_finish": plain["project_finish"],
        "slip_vs_unconstrained": schedule.workdays_between(
            plain["project_finish"], schedule.add_workdays(today, total, holidays), holidays
        ),
        "duration_days": int(round(total)),
        "tasks": rows,
        "resources": resources,
        "bottleneck": resources[0] if resources else None,
        "waiting_total": round(sum(r["waiting_days"] for r in rows.values()), 1),
    }


def blocked_by_people(result: dict, top: int = 5) -> list:
    """Tasks waiting on a busy owner, not on a dependency — the constraint made visible."""
    rows = [r for r in result["tasks"].values() if r["waiting_days"] > 0]
    return sorted(rows, key=lambda r: -r["waiting_days"])[:top]


def _copy(tasks: dict) -> dict:
    return {k: schedule.Task(**dict(t.__dict__)) for k, t in tasks.items()}


def rebalance(
    tasks: dict,
    today: _dt.date,
    capacity=None,
    max_moves: int = 3,
    holidays=(),
    availability: dict | None = None,
    can_take=None,
) -> dict:
    """Search for a task to move off the bottleneck owner that would pull the finish date in.

    Greedy, one move at a time, taking whichever pulls hardest. A proposal only; nothing is applied.
    Finished tasks and already-started ones (progress>0) stay put — handing those over rarely works.

    `can_take(task, person) -> bool` filters out handovers that would not survive contact
    with the team. Without it the search treats people as interchangeable units of time,
    which is how you end up proposing that the person who has never touched the API take
    over the migration. What makes a handover plausible is not capacity's business to
    decide, so the caller supplies the judgement; `tools.py` builds it from who has
    actually committed where.
    """
    base = levelled(tasks, today, capacity, holidays, availability)
    cur, moves = _copy(tasks), []
    best = base
    people = sorted({t.assignee for t in tasks.values() if t.assignee})
    for _ in range(max_moves):
        b = best.get("bottleneck")
        if not b or len(people) < 2:
            break
        movable = [
            k
            for k, t in cur.items()
            if t.assignee == b["assignee"] and not t.is_done and t.progress <= 0
        ]
        found = None
        for k in movable:
            for other in people:
                if other == b["assignee"]:
                    continue
                if can_take and not can_take(cur[k], other):
                    continue
                trial = _copy(cur)
                trial[k].assignee = other
                r = levelled(trial, today, capacity, holidays, availability)
                gain = schedule.workdays_between(
                    r["project_finish"], best["project_finish"], holidays
                )
                if gain > 0 and (found is None or gain > found["gain_days"]):
                    found = {
                        "key": k,
                        "summary": cur[k].summary,
                        "from": b["assignee"],
                        "to": other,
                        "gain_days": gain,
                        "new_finish": r["project_finish"],
                        "_tasks": trial,
                        "_res": r,
                    }
        if not found:
            break
        cur, best = found.pop("_tasks"), found.pop("_res")
        moves.append(found)
    return {
        "before": base["project_finish"],
        "after": best["project_finish"],
        "gain_days": schedule.workdays_between(
            best["project_finish"], base["project_finish"], holidays
        ),
        "moves": moves,
        "resources_before": base["resources"],
        "resources_after": best["resources"],
    }


def summary(
    tasks: dict, today: _dt.date, capacity=None, holidays=(), availability: dict | None = None
) -> dict:
    """One bundle the report and the tools can use as-is (dates as ISO strings).

    Pass a calendar and three numbers come back side by side, so each constraint's cost shows:
      dependencies only  <  plus people's capacity  <  plus meetings
    """
    r = levelled(tasks, today, capacity, holidays, availability)
    # Also report what it would have been without meetings, to separate out their cost.
    no_cal = levelled(tasks, today, capacity, holidays, None) if availability else r
    meeting_slip = schedule.workdays_between(
        no_cal["project_finish"], r["project_finish"], holidays
    )
    return schedule.iso(
        {
            "today": today,
            "unconstrained_finish": r["unconstrained_finish"],
            "capacity_finish": r["project_finish"],
            "finish_without_meetings": no_cal["project_finish"],
            "meeting_slip_days": meeting_slip,
            "calendar_applied": bool(availability),
            "slip_vs_unconstrained": r["slip_vs_unconstrained"],
            "waiting_total_days": r["waiting_total"],
            "bottleneck": r["bottleneck"],
            "resources": r["resources"],
            "waiting_tasks": blocked_by_people(r),
        }
    )
