"""The choices in front of a person, and what each one costs.

"Why did this stop" is a diagnosis. It says what happened. It does not help anybody
*choose*, and choosing is the work a delivery lead is actually paid for. The question they
are holding is not "what happened to authentication" — they know — it is:

  *do we let it slip, hand it to somebody else, cut it, or move the date — and what does
  each of those cost?*

Nobody computes that. It gets argued about in a meeting with no numbers on the table,
because working out the cost of four options means running the schedule four times and
nobody has an afternoon.

So this lays the options side by side, each with:

  **what it costs**     the finish date under that choice, against the date today
  **what it breaks**    which other work moves, and whose
  **what it needs**     the person who would have to agree, or take it on
  **when it expires**   the last day the option is still worth taking

That last one is the part that surprised me. **An option has a deadline of its own.**
Handing a task to somebody else buys you nothing once it is nearly done, and "we could
still have moved it in September" is a sentence teams say every October. So each option
carries the date after which it stops being worth doing, computed rather than guessed.

Every number comes from `schedule.py` and `capacity.py`. Nothing here asks a model which
option is better — that is the person's decision, and handing it over would be exactly the
wrong kind of help. The agent lays out the table; the person picks.
"""

from __future__ import annotations

import datetime as _dt

from pmo_agent import capacity, schedule

# An option that buys less than this is noise, not a choice.
WORTH_DAYS = 1
# How far ahead to look for the day an option stops being worth taking.
HORIZON = 60


def _copy(tasks: dict) -> dict:
    return {k: schedule.Task(**dict(t.__dict__)) for k, t in tasks.items()}


def _moved(tasks: dict, today: _dt.date, availability=None) -> str:
    """The achievable finish, not the dependency-only one. Options are judged on reality."""
    return capacity.summary(tasks, today, availability=availability)["capacity_finish"]


def _downstream(tasks: dict, key: str, today: _dt.date, slip: float) -> list:
    """Whose work moves if this one slips, and by how much. The task itself is not news."""
    out = schedule.propagate(tasks, key, slip, today)
    rows = [
        {
            "key": r["key"],
            "summary": r["summary"],
            "owner": r.get("assignee", ""),
            "days": r.get("slip_days", 0),
            "breaks_duedate": bool(r.get("breaks_duedate")),
        }
        for r in (out.get("affected") or [])
        if r.get("key") != key and r.get("slip_days")
    ]
    return sorted(rows, key=lambda r: -r["days"])[:5]


def accept(tasks: dict, key: str, today: _dt.date, slip: float, availability=None) -> dict:
    """Do nothing and let it land where it lands."""
    after = _copy(tasks)
    task = after[key]
    task.points = (tasks[key].remaining + slip) / schedule.DAYS_PER_POINT
    task.progress, task.status = 0.0, ""
    return {
        "option": "accept",
        "what": f"let {key} slip by {schedule.iso(slip)} days",
        "finish": _moved(after, today, availability),
        "needs": "",
        "breaks": _downstream(tasks, key, today, slip),
        "expires": "",  # doing nothing never expires
    }


def hand_over(
    tasks: dict, key: str, today: _dt.date, to: str, availability=None, can_take=None
) -> dict | None:
    """Give it to somebody else. None when that person could not plausibly take it."""
    if can_take and not can_take(tasks[key], to):
        return None
    after = _copy(tasks)
    after[key].assignee = to
    return {
        "option": "hand_over",
        "what": f"move {key} to {to}",
        "finish": _moved(after, today, availability),
        "needs": to,
        "breaks": [],
        "vetted": bool(can_take),
    }


def cut(tasks: dict, key: str, today: _dt.date, availability=None) -> dict:
    """Drop it. Cheap on the schedule, expensive on whatever depended on it."""
    after = _copy(tasks)
    after.pop(key, None)
    blocked = []
    for other, task in tasks.items():
        if key in task.deps and not task.is_done:
            blocked.append({"key": other, "summary": task.summary, "owner": task.assignee})
        if other in after:
            after[other].deps = [d for d in after[other].deps if d != key]
    return {
        "option": "cut",
        "what": f"drop {key} from this release",
        "finish": _moved(after, today, availability),
        "needs": "whoever owns the scope",
        # Not "breaks" in the sense of moving — these stop making sense at all.
        "breaks": blocked,
        "orphans": len(blocked),
    }


def _expiry(tasks: dict, key: str, today: _dt.date, gain: float, availability=None) -> str:
    """The last day handing this over still buys most of what it buys today.

    An option is not permanently available. Moving a task that is nearly done saves
    nobody anything, and the day that stops being true is computable rather than a thing
    to find out afterwards.
    """
    task = tasks.get(key)
    if not task or gain < WORTH_DAYS:
        return ""
    # Each business day that passes, the remaining work shrinks by roughly a day of
    # someone's time. The option is worth taking while at least half the gain survives.
    left = task.remaining
    keep = max(0.0, left - (gain / 2))
    days = int(max(0.0, left - keep))
    return schedule.add_workdays(today, min(days, HORIZON)).isoformat()


def options(
    tasks: dict,
    key: str,
    today: _dt.date | None = None,
    slip: float = 5,
    availability=None,
    can_take=None,
) -> dict:
    """The choices for one task at risk, each costed against doing nothing.

    Deliberately not ranked by "best". Cheapest on the calendar is not best — cutting
    scope always wins on days and is usually the wrong answer — so they are ordered by
    how disruptive they are and the person weighs them.
    """
    today = today or _dt.date.today()
    if key not in tasks:
        return {"error": f"unknown task: {key}", "available": sorted(tasks)[:20]}
    task = tasks[key]
    now = _moved(tasks, today, availability)

    rows = [accept(tasks, key, today, slip, availability)]

    # Who else could take it: anybody with room who is allowed to.
    others = sorted(
        {t.assignee for t in tasks.values() if t.assignee and t.assignee != task.assignee}
    )
    handovers = []
    for who in others:
        found = hand_over(tasks, key, today, who, availability, can_take)
        if found:
            found["gain_days"] = schedule.workdays_between(
                _dt.date.fromisoformat(found["finish"]), _dt.date.fromisoformat(now)
            )
            handovers.append(found)
    handovers.sort(key=lambda r: -r["gain_days"])
    best = next((h for h in handovers if h["gain_days"] >= WORTH_DAYS), None)
    if best:
        best["expires"] = _expiry(tasks, key, today, best["gain_days"], availability)
        rows.append(best)

    rows.append(cut(tasks, key, today, availability))

    for row in rows:
        row.setdefault("gain_days", 0)
        if row["option"] != "hand_over":
            row["gain_days"] = schedule.workdays_between(
                _dt.date.fromisoformat(row["finish"]), _dt.date.fromisoformat(now)
            )

    return {
        "key": key,
        "summary": task.summary,
        "owner": task.assignee,
        "today": today.isoformat(),
        "finish_now": now,
        "options": rows,
        "considered_handovers": len(handovers),
        "vetted": bool(can_take),
        "note": _note(rows, now, bool(can_take), len(others), len(handovers)),
        # Said out loud because it is the thing an agent is most tempted to do here.
        "chosen": None,
        "why_not_chosen": (
            "This is a person's decision. The agent costs the options; it does not pick."
        ),
    }


def _note(rows: list, now: str, vetted: bool, people: int, plausible: int) -> str:
    """One sentence about what the table does and does not settle."""
    hand = next((r for r in rows if r["option"] == "hand_over"), None)
    cut_row = next((r for r in rows if r["option"] == "cut"), None)
    said = f"Doing nothing finishes {now}."
    if hand:
        said += (
            f" Moving it to {hand['needs']} buys {hand['gain_days']} business days"
            + (f", and that option is gone after {hand['expires']}" if hand.get("expires") else "")
            + "."
        )
    elif people:
        said += f" None of the other {people} people would pull the date in" + (
            " among those the repository shows could take it." if vetted else "."
        )
    if cut_row and cut_row.get("orphans"):
        said += f" Dropping it would leave {cut_row['orphans']} tasks depending on nothing."
    if not vetted and plausible:
        said += " Handovers were not checked against who has worked where."
    return said


# ------------------------------------------------------------------ the deadline
def deadlines(tasks: dict, today: _dt.date | None = None, availability=None, top: int = 5) -> dict:
    """Decisions that get cheaper to make now than later, soonest expiry first.

    A PM is rarely short of information and often short of the knowledge that a door is
    closing. "We could still have moved it in September" is a sentence teams say every
    October, and it is avoidable arithmetic.
    """
    today = today or _dt.date.today()
    risks = schedule.risks(tasks, today)
    rows = []
    for risk in risks:
        found = options(tasks, risk["key"], today, availability=availability)
        hand = next((o for o in found.get("options") or [] if o["option"] == "hand_over"), None)
        if not hand or not hand.get("expires"):
            continue
        rows.append(
            {
                "key": risk["key"],
                "summary": risk["summary"],
                "owner": risk.get("assignee", ""),
                "decision": hand["what"],
                "buys_days": hand["gain_days"],
                "expires": hand["expires"],
                "days_left": schedule.workdays_between(
                    today, _dt.date.fromisoformat(hand["expires"])
                ),
            }
        )
    rows.sort(key=lambda r: (r["days_left"], -r["buys_days"]))
    return {
        "today": today.isoformat(),
        "decisions": rows[:top],
        "note": _deadline_note(rows),
    }


def _deadline_note(rows: list) -> str:
    if not rows:
        return "No decision is about to get more expensive. Nothing here is urgent today."
    soonest = rows[0]
    return (
        f"{len(rows)} decisions are still open. The soonest to close is "
        f"{soonest['key']} — {soonest['decision']} buys {soonest['buys_days']} days and "
        f"stops being worth doing in {soonest['days_left']} business days."
    )
