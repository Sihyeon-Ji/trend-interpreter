"""What the meeting said, against what the board records — and the difference, as proposals.

The agent already reads meeting notes and already works out which task a note is about.
Until now it only used that to *explain* a stall. But the same pair of facts supports a
more useful move: a note says the team agreed to push authentication to next sprint, the
board still has it due last Tuesday, and somebody has to go and change it.

That somebody is the job this replaces. Reading minutes, working out which ticket each
paragraph is about, opening the board, comparing, and editing only the ones that differ —
every week, for every meeting. It is not hard work. It is work nobody does reliably, which
is why boards drift.

**Only the differences.** A note that agrees with the board produces nothing. That is the
whole value: a list of twenty notes is not a list of twenty proposals, it is usually a list
of two, and finding those two by hand is the tedious part.

Three restraints, all of them the same ones the rest of the agent already applies:

  · a note carries no ticket key, so the link is inferred. Below the threshold, or too
    close to the runner-up, it becomes a **question** rather than a proposal
  · the note's own sentence rides along as evidence. A proposal a person cannot check
    against the source is one they have to take on trust, which defeats the approval gate
  · nothing is applied. These go to the same gate as everything else

The model reads the prose and says what it claims. Whether that differs from the board is
arithmetic, and it happens here.
"""

from __future__ import annotations

import datetime as _dt

from pmo_agent import ingest, linking, schedule

MENTION = 0.5  # a note has to carry half a task's vocabulary to be about it
MARGIN = 0.1  # and beat the next-best task by this much
WINDOW = 21  # days of notes to reconcile; older than that and the board has moved on


def match(text: str, tasks: dict) -> tuple:
    """(task key, coverage) for the task a note is about, or ("", best) when unsure.

    The same rule `cause.py` uses to quote a decision, for the same reason: a note that
    fits two tasks equally well is about neither, as far as this is concerned. Returning
    the runner-up score too lets the caller say *how* unsure it was.
    """
    ranked = sorted(
        ((linking.mentions(text, t), k) for k, t in (tasks or {}).items()), key=lambda r: -r[0]
    )
    if not ranked:
        return "", 0.0
    (top, key), (second, _) = ranked[0], (ranked[1] if len(ranked) > 1 else (0.0, ""))
    if top < MENTION or top - second < MARGIN:
        return "", round(top, 2)
    return key, round(top, 2)


def _same_date(claim: str, task) -> bool:
    on_board = task.duedate.isoformat() if task.duedate else ""
    return (claim or "") == on_board


def differs(item: dict, tasks: dict) -> dict:
    """Strip the parts of a claim the board already agrees with. {} when nothing is left.

    This is the arithmetic the model is not asked to do. It said what the note claims;
    whether that is *news* is a comparison, and a comparison is not a judgement call.
    """
    task = tasks.get(item.get("key", ""))
    if not task:
        return {}
    out = {k: v for k, v in item.items() if k in ("key", "summary", "assignee", "confidence")}
    if item.get("duedate") and not _same_date(item["duedate"], task):
        out["duedate"] = item["duedate"]
        out["duedate_was"] = task.duedate.isoformat() if task.duedate else None
    if item.get("status") and not schedule.status_alike(item["status"], task.status):
        out["status"] = item["status"]
        out["status_was"] = task.status
    if item.get("note"):
        out["note"] = item["note"]
    return out if len(out) > 4 else {}


def _date(value) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def recent(notes: list, today: _dt.date, days: int = WINDOW) -> list:
    """Notes from the last `days`, newest first. Older than that and the board has moved on."""
    since = today - _dt.timedelta(days=days)
    rows = [n for n in notes or [] if (d := _date(n.get("date"))) and since <= d <= today]
    return sorted(rows, key=lambda n: n.get("date", ""), reverse=True)


def review(
    notes: list,
    tasks: dict,
    today: _dt.date | None = None,
    days: int = WINDOW,
    caller=ingest.call,
    limit: int = 8,
) -> dict:
    """Meeting notes → the board changes they imply but the board does not yet have.

    `caller` is the model call, swappable, so all of this is testable without a network —
    the same arrangement `ingest.py` uses.
    """
    today = today or _dt.date.today()
    rows, questions, skipped = [], [], []

    for note in recent(notes, today, days)[:limit]:
        text = f"{note.get('title', '')} {note.get('body', '')}".strip()
        if not text:
            continue
        key, coverage = match(text, tasks)
        where = f"{note.get('title', '')} — {note.get('author', '')}, {note.get('date', '')}"
        if not key:
            # Not a failure. The note may simply not be about one task, and guessing which
            # would be exactly the wrong kind of helpful.
            skipped.append({"note": where, "best_coverage": coverage})
            continue

        try:
            read = ingest.ingest(text, tasks=tasks, today=today, caller=caller)
        except Exception as e:  # one unreadable note must not lose the others
            skipped.append({"note": where, "error": str(e)[:120]})
            continue

        questions += [f"{q} (from the note: {where})" for q in read.get("questions") or []]
        for item in read.get("resolved") or []:
            if item.get("key") != key:
                # The model named a different task from the one the note is about. Its
                # claim may be right, but this is not the evidence for it.
                skipped.append({"note": where, "claimed": item.get("key"), "matched": key})
                continue
            news = differs(item, tasks)
            if not news:
                continue  # the board already says this, which is the common and good case
            news["evidence"] = where
            news["quote"] = " ".join((note.get("body") or "").split())[:240]
            news["coverage"] = coverage
            rows.append(news)

    return {
        "today": today.isoformat(),
        "window_days": days,
        "changes": rows,
        "questions": questions,
        "skipped": skipped,
        "proposals": ingest.to_proposals({"resolved": rows}),
        "impact": ingest.impact(rows, tasks, today) if rows else None,
        "applied": False,  # same gate as everything else
        "note": _summary(rows, skipped, notes, days),
    }


def _summary(rows: list, skipped: list, notes: list, days: int) -> str:
    """One sentence about what was read and what came of it."""
    if not notes:
        return "There are no meeting notes to reconcile."
    unsure = len([s for s in skipped if "best_coverage" in s])
    if not rows:
        said = f"Nothing in the last {days} days of notes disagrees with the board."
    else:
        said = (
            f"{len(rows)} change{'s' if len(rows) > 1 else ''} the notes imply that the board "
            f"does not have yet."
        )
    if unsure:
        said += (
            f" {unsure} note{'s' if unsure > 1 else ''} could not be tied to one task with "
            f"enough margin, so {'they were' if unsure > 1 else 'it was'} left alone."
        )
    return said
