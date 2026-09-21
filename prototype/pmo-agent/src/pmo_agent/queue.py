"""What is waiting for a person today — the screen the research says should be first.

The dashboard used to open with state: a forecast, a load chart, a list of risks. That is
the wrong front door, and the survey data says why. Knowledge workers lose 60% of their
time to "work about work" and 352 hours a year to *talking about* work, not to a shortage
of information. Another status panel adds to that number.

What the coordination labour actually consists of is a handful of small decisions and
messages nobody has got round to: somebody should be told their work is blocked, a date
the team agreed in a meeting is not on the board, a handover is still worth making but
will not be next week. Each is five minutes of thinking and twenty of chasing.

So the front door is the queue of those, already prepared, each with the one thing the
person has to supply: **a yes or a no.**

Three rules, each earned from a finding in that research:

  · **every item carries where it came from.** 40% of desk workers received AI output
    that looked finished and was not, at two hours each to unpick. An item a person
    cannot check is one they have to take on trust, and trust is what that statistic
    destroys
  · **nothing is done, only prepared.** The agent drafts the message and costs the
    option; pressing send and pressing apply stay with a person
  · **an empty queue says so.** Manufacturing three things to look at on a quiet day is
    how a tool becomes another thing to check

Pure assembly. Every item was computed by a module that already had to defend it.
"""

from __future__ import annotations

import datetime as _dt

# What kind of attention an item needs. Ordered: a closing door first, because it is the
# only one that gets worse by being left.
DECIDE = "decide"
TELL = "tell"
APPLY = "apply"
CHECK = "check"
ORDER = {DECIDE: 0, TELL: 1, APPLY: 2, CHECK: 3}

SOON_DAYS = 5  # a decision closing within a week is the top of the queue

# What each source answers, so a source that did not run can be named rather than counted
# as a clean sweep. The order is the order the reassuring sentence makes its claims in.
CHECKS = ("decisions", "blocked", "notes")


def _item(kind: str, title: str, why: str, **extra) -> dict:
    return {"kind": kind, "title": title, "why": why, "done": False, **extra}


def from_decisions(closing: dict, today: _dt.date) -> list:
    """Options that stop being worth taking. The only items that decay."""
    out = []
    for row in (closing or {}).get("decisions") or []:
        left = row.get("days_left", 0)
        out.append(
            _item(
                DECIDE,
                row["decision"],
                f"buys {row['buys_days']} business days, and stops being worth doing "
                f"in {left} — by {row['expires']}",
                key=row.get("key", ""),
                summary=row.get("summary", ""),
                owner=row.get("owner", ""),
                days_left=left,
                urgent=left <= SOON_DAYS,
                source="schedule + capacity",
                action="weigh_options",
                # Whether one colleague takes work is one question, however many tasks
                # it is asked about, and it is their capacity that pays for it. Asking it
                # five times is the busy-day version of inventing items on a quiet one.
                group_on=row.get("to", ""),
                facts={
                    "owner": row.get("owner", ""),
                    "to": row.get("to", ""),
                    "buys": row.get("buys_days", 0),
                    "left": left,
                    "expires": row.get("expires", ""),
                },
            )
        )
    return out


def from_alerts(alerts: list) -> list:
    """People whose own work is blocked and who will not hear about it otherwise.

    Only the ones that cross a team boundary. Somebody on the same team finds out at
    standup; somebody on another team finds out in three weeks.
    """
    out = []
    for row in alerts or []:
        crossing = row.get("crosses_teams") or []
        if not crossing or not row.get("tell"):
            continue
        who = ", ".join(p["who"] for p in row["tell"][:3])
        out.append(
            _item(
                TELL,
                f"tell {who} that {row['key']} is blocking them",
                f"it crosses into {', '.join(crossing)}, so it will not come up in a standup",
                key=row.get("key", ""),
                summary=row.get("summary", ""),
                people=row.get("tell") or [],
                draft=row.get("draft", ""),
                source="board dependencies",
                action="who_to_tell",
                # The same people told twice is one message, not two.
                group_on="|".join(sorted(p["who"] for p in row["tell"])),
                facts={"who": who, "teams": list(crossing)},
            )
        )
    return out


def from_reconcile(found: dict) -> list:
    """Board changes the meeting notes imply and the board does not have yet."""
    out = []
    for row in (found or {}).get("changes") or []:
        what = []
        if row.get("duedate"):
            what.append(f"due {row.get('duedate_was') or '—'} → {row['duedate']}")
        if row.get("status"):
            what.append(f"status {row.get('status_was') or '—'} → {row['status']}")
        out.append(
            _item(
                APPLY,
                f"{row['key']}: {'; '.join(what) or 'a comment'}",
                row.get("evidence", "from a meeting note"),
                key=row.get("key", ""),
                summary=row.get("summary", ""),
                quote=row.get("quote", ""),
                coverage=row.get("coverage"),
                source="meeting notes",
                action="reconcile_notes",
                facts={
                    "key": row.get("key", ""),
                    "duedate": row.get("duedate", ""),
                    "duedate_was": row.get("duedate_was", ""),
                    "status": row.get("status", ""),
                    "status_was": row.get("status_was", ""),
                    "where": row.get("evidence", ""),
                },
            )
        )
    return out


def from_questions(questions: list, source: str = "") -> list:
    """What the agent could not settle. A question is work too, and it is honest work."""
    return [
        _item(
            CHECK,
            q,
            "the agent could not settle this on its own",
            source=source or "the agent",
            facts={"question": q},
        )
        for q in questions or []
    ]


def fold(items: list) -> list:
    """Collapse rows that are really the same question asked again.

    The soonest one leads, because that is what makes the group worth looking at now;
    the rest ride along in `also` so nothing is lost, only stacked. Input must already
    be in the order you want the survivors to appear.
    """
    out: list = []
    heads: dict = {}
    for row in items:
        on = row.get("group_on")
        if not on:
            out.append(row)
            continue
        at = (row["kind"], on)
        head = heads.get(at)
        if head is None:
            heads[at] = row
            out.append(row)
            continue
        head.setdefault("also", []).append(
            {"key": row.get("key", ""), "summary": row.get("summary", "")}
        )
    # Scaffolding for the fold, and meaningless to anyone reading the payload.
    for row in out:
        row.pop("group_on", None)
    return out


def build(
    closing: dict | None = None,
    alerts: list | None = None,
    reconciled: dict | None = None,
    questions: list | None = None,
    today: _dt.date | None = None,
    limit: int = 8,
    blind: list | None = None,
) -> dict:
    """The day's queue, most perishable first.

    `blind` names the checks that could not be run at all. An item that is absent because
    nothing was wrong and one that is absent because nobody looked are different facts,
    and only the first is worth being reassured by.
    """
    today = today or _dt.date.today()
    items = (
        from_decisions(closing or {}, today)
        + from_alerts(alerts or [])
        + from_reconcile(reconciled or {})
        + from_questions(questions or [])
    )
    items.sort(key=lambda r: (ORDER.get(r["kind"], 9), r.get("days_left", 99)))
    items = fold(items)
    shown = items[:limit]
    return {
        "today": today.isoformat(),
        "items": shown,
        "more": max(0, len(items) - limit),
        "counts": {k: sum(1 for i in items if i["kind"] == k) for k in ORDER},
        "blind": list(blind or []),
        "note": _note(items, blind or []),
        "note_facts": _note_facts(items, blind or []),
        # Said out loud because it is what separates this from a tool that acts.
        "nothing_was_done": True,
    }


def _note_facts(items: list, blind: list | None = None) -> dict:
    """The same sentence as numbers, so another language can be written from them."""
    urgent = [i for i in items if i.get("urgent")]
    soonest = min(urgent, key=lambda i: i.get("days_left", 99)) if urgent else None
    return {
        "total": len(items),
        "key": (soonest or {}).get("key", ""),
        "left": (soonest or {}).get("days_left"),
        "blind": [b.get("check", "") for b in blind or []],
    }


BLIND_SAYS = {
    "decisions": "whether any option is about to close",
    "blocked": "whether anybody is blocked across a team",
    "notes": "whether the notes agree with the board",
}


def _note(items: list, blind: list | None = None) -> str:
    """One sentence. An empty queue is a real answer, not a gap to fill.

    Unless it is empty because nothing ran, in which case the reassurance would be three
    claims about three things nobody looked at.
    """
    missed = [BLIND_SAYS.get(b.get("check", ""), b.get("check", "")) for b in blind or []]
    if not items:
        if missed:
            return (
                "Nothing came back, but that is not the same as nothing to do: "
                + ", ".join(missed)
                + " could not be checked."
            )
        return (
            "Nothing needs you today. No decision is about to close, nobody is blocked "
            "across a team, and the notes agree with the board."
        )
    urgent = [i for i in items if i.get("urgent")]
    said = f"{len(items)} things are waiting on you"
    if urgent:
        soonest = min(urgent, key=lambda i: i.get("days_left", 99))
        said += (
            f". The one that cannot wait is {soonest.get('key', '')} — "
            f"{soonest['days_left']} business days before that option is gone"
        )
    said += "."
    if missed:
        said += " There may be more: " + ", ".join(missed) + " could not be checked."
    return said
