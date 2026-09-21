"""Why did this task stop? — reconstructed by lining all three tools up.

The rest of the project answers "what is wrong": the schedule says a task will slip,
signals says the board and the code disagree. Neither answers **why**, and "why" is the
question a PM actually has to act on.

No single tool can answer it. The board knows a dependency is still open. The repository
knows the last commit was three weeks ago and that its owner kept committing elsewhere.
The calendar knows that person spent those same days in incident calls. And a meeting
note, if anyone wrote one, holds the only sentence that says what the incident *was*.
Put them side by side and the explanation appears:

    ECHO-16 has been silent for 8 business days.
      · its owner lost 14.0h to meetings over that stretch, 9.0h of it "Incident response"
      · its owner made 6 commits in that stretch, all to other tasks

Every cause carries the number of business days it accounts for, so they can be ranked by
how much of the silence they actually explain — and so the leftover can be stated plainly
rather than papered over. A cause with no evidence is never invented; when nothing
explains the gap, that is the answer, and it is said out loud.

Pure calculation. The model may quote this; it does not produce it.
"""

from __future__ import annotations

import datetime as _dt

from pmo_agent import availability as _av
from pmo_agent import linking, schedule

REVIEW_WAIT_DAYS = 2  # a pull request idle this long is a cause in its own right
MEETING_SHARE = 0.25  # below a quarter of the workday, meetings are not the explanation
LOOKBACK_DAYS = 30  # how far back to look when the repository shows nothing at all
MENTION = 0.5  # a note has to carry at least half a task's vocabulary to be about it
MENTION_MARGIN = 0.1  # and it has to beat the next-best task by this much


def _clip(text: str, limit: int = 200) -> str:
    """Trim to a word boundary. A sentence cut mid-word reads like a bug, not a quote."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{cut}…"


def _date(value):
    try:
        return _dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def window(task, commits: list, today: _dt.date) -> dict:
    """The stretch to explain, and where it starts.

    For a task that is merely quiet, the question is "why has nothing happened lately", so
    it starts at the last sign of life. For one that is past its due date the question is
    different — "why is this still not finished" — and the honest answer covers everything
    since the day it should have been done. A task blocked for a fortnight, unblocked, then
    touched once last week would otherwise have that fortnight fall outside the window and
    go unexplained.

    So an overdue task's window reaches back to its due date, even when there are commits
    after it.
    """
    dates = sorted(d for d in (_date(c.get("date")) for c in commits) if d)
    since = dates[-1] if dates else (task.duedate or schedule.add_workdays(today, -LOOKBACK_DAYS))
    origin = "last commit" if dates else ("due date" if task.duedate else "lookback")
    if task.duedate and task.duedate < today and task.duedate < since:
        since, origin = task.duedate, "overdue since"
    since = min(since, today)
    return {
        "since": since.isoformat(),
        "until": today.isoformat(),
        "days": max(0, schedule.workdays_between(since, today)),
        "from": origin,
    }


def _meetings(events: list, who: str, since: _dt.date, until: _dt.date) -> dict:
    """What the owner's calendar held during the silence."""
    hours = 0.0
    by_title: dict[str, float] = {}
    days: set = set()
    for e in events:
        if e.get("attendee") != who:
            continue
        day = _date(e.get("date"))
        if not day or not (since <= day < until):
            continue
        h = float(e.get("hours") or 0.0)
        hours += h
        title = (e.get("title") or "").strip() or "(untitled)"
        by_title[title] = by_title.get(title, 0.0) + h
        days.add(day)
    top = max(by_title.items(), key=lambda kv: kv[1]) if by_title else ("", 0.0)
    return {
        "hours": round(hours, 1),
        "days_with_meetings": len(days),
        "top_title": top[0],
        "top_hours": round(top[1], 1),
        # Keep the unrounded share for the threshold. Comparing the rounded value makes
        # the boundary wobble: round(0.25, 1) is 0.2, so exactly a quarter-day would fail.
        "lost_days": round(hours / _av.WORKDAY_HOURS, 1),
        "share": hours / _av.WORKDAY_HOURS,
    }


def _elsewhere(linked: dict, key: str, who: str, since: _dt.date, until: _dt.date) -> dict:
    """Commits the owner made to *other* tasks while this one sat still.

    This is the difference between "could not" and "did not". A blocked person has no
    commits at all; a person who was pulled onto something else has plenty, just not here.
    """
    hits = 0
    days: set = set()
    by_task: dict[str, int] = {}
    for other, bundle in linked.items():
        if other == key:
            continue
        for commit in bundle["commits"]:
            if (commit.get("name") or commit.get("author") or "") != who:
                continue
            day = _date(commit.get("date"))
            if not day or not (since <= day < until):
                continue
            hits += 1
            days.add(day)
            by_task[other] = by_task.get(other, 0) + 1
    top = sorted(by_task.items(), key=lambda kv: -kv[1])[:2]
    return {"commits": hits, "days": len(days), "tasks": [k for k, _n in top]}


def _trace(
    commits: list, events: list, who: str, since: _dt.date, until: _dt.date, calendar: bool
) -> dict | None:
    """Business days in the window where the owner left no trace in any connected tool.

    "Unexplained" covers two situations worth keeping apart. On some days the person was
    demonstrably at work and simply did not touch this task — commits to other tasks,
    meetings on the calendar. On others there is nothing at all: no commit anywhere, no
    meeting, nothing this agent can see. That is not a smaller version of the same thing.
    It is leave, or a handover, or a system nobody connected, and saying "invisible" is
    more useful than folding it into one number that reads like ignorance.

    Every commit counts, not only the ones that linked to a task. A commit the linker
    could not place is still proof the person was working that day, and using the linked
    set here would turn the agent's own uncertainty into somebody's missing week.

    Returns None rather than a count when the owner cannot be found in the tools at all.
    A Jira assignee whose name never matches a git author would otherwise come out
    invisible on every single day, which says nothing about them and everything about the
    name matching.
    """
    if not who:
        return None
    mine = [c for c in commits or [] if (c.get("name") or c.get("author") or "") == who]
    theirs = [e for e in events or [] if e.get("attendee") == who] if calendar else []
    if not mine and not theirs:
        return None  # this person is not in these tools under this name

    seen: set = set()
    for commit in mine:
        day = _date(commit.get("date"))
        if day and since <= day < until:
            seen.add(day)
    for event in theirs:
        day = _date(event.get("date"))
        if day and since <= day < until:
            seen.add(day)

    workdays = [
        d
        for d in (since + _dt.timedelta(days=i) for i in range((until - since).days))
        if schedule.is_workday(d)
    ]
    dark = [d for d in workdays if d not in seen]
    looked = ["the repository"] + (["the calendar"] if calendar else [])
    return {
        "workdays": len(workdays),
        "with_trace": len(workdays) - len(dark),
        "no_trace": len(dark),
        "looked_in": looked,
        "first": dark[0].isoformat() if dark else "",
        "last": dark[-1].isoformat() if dark else "",
    }


def _workdays(since: _dt.date, until: _dt.date) -> list:
    return [
        d
        for d in (since + _dt.timedelta(days=i) for i in range((until - since).days))
        if schedule.is_workday(d)
    ]


def _account(
    causes: list,
    events: list,
    linked: dict,
    key: str,
    who: str,
    since: _dt.date,
    until: _dt.date,
) -> float:
    """How much of the silence is accounted for, counted **per day** rather than summed.

    Adding the causes up double-counts, and badly. A person in meetings on Tuesday who
    also committed to another task on Tuesday has Tuesday claimed twice; on real data the
    two together came to 15.4 days of a 16-day silence when the honest figure was 6.6.

    Worse, it was invisible. The total was capped at the length of the window, so an
    overcount did not look like an error — it came out as "all 14 silent business days are
    accounted for", which is the most confident sentence this module can say and it was
    wrong. A cap is not a check.

    So each business day is worth one day and no more, and what is claimed against it is:

      · a whole day, if the work could not legitimately have moved — a dependency still
        open, or a pull request sitting in review
      · otherwise the share of the day that went to meetings, plus a whole day if the
        owner spent it committing somewhere else, capped at one

    Each cause still reports what *it* accounts for, because that is its own evidence.
    They no longer add up to the total, and `overlap` says by how much.
    """
    days = _workdays(since, until)
    if not days:
        return 0.0

    stuck: set = set()
    if any(c["kind"] == "dependency_open" for c in causes):
        stuck |= set(days)  # the work could not start at all, so the whole window counts
    for c in causes:
        if c["kind"] != "waiting_on_review":
            continue
        # the wait runs back from today by the days the pull request sat untouched
        stuck |= set(_workdays(schedule.add_workdays(until, -c["days"]), until))

    meetings: dict = {}
    for e in events or []:
        if e.get("attendee") != who:
            continue
        day = _date(e.get("date"))
        if day:
            meetings[day] = meetings.get(day, 0.0) + float(e.get("hours") or 0.0)

    elsewhere: set = set()
    for other, bundle in (linked or {}).items():
        if other == key:
            continue
        for commit in bundle.get("commits") or []:
            if (commit.get("name") or commit.get("author") or "") != who:
                continue
            day = _date(commit.get("date"))
            if day:
                elsewhere.add(day)

    total = 0.0
    for day in days:
        if day in stuck:
            total += 1.0
            continue
        share = meetings.get(day, 0.0) / _av.WORKDAY_HOURS + (1.0 if day in elsewhere else 0.0)
        total += min(1.0, share)
    return round(min(total, float(len(days))), 1)


def _decision(notes: list, key: str, tasks: dict, since: _dt.date, until: _dt.date):
    """A note written during the silence that is about this task, or nothing.

    Notes carry no ticket key, so which task one belongs to has to be inferred — the same
    problem as a commit, measured differently. A commit subject and a task title are two
    short strings and should look alike; a note is a paragraph that names the task once,
    so what counts is how much of the task's vocabulary the note contains.

    The restraint is the same as everywhere else: the winner has to clear the runner-up.
    A note that fits two tasks equally well is about neither, as far as this is concerned.
    """
    best = None
    for note in notes:
        day = _date(note.get("date"))
        if not day or not (since <= day < until):
            continue
        text = f"{note.get('title', '')} {note.get('body', '')}"
        ranked = sorted(
            ((linking.mentions(text, t), k) for k, t in tasks.items()), key=lambda r: -r[0]
        )
        if not ranked:
            continue
        (top, top_key), (second, _) = ranked[0], (ranked[1] if len(ranked) > 1 else (0.0, ""))
        if top_key != key or top < MENTION or top - second < MENTION_MARGIN:
            continue
        if best is None or (top, note.get("date", "")) > (best[0], best[1].get("date", "")):
            best = (round(top, 2), note)
    return best


def explain(
    key: str,
    tasks: dict,
    snapshot: dict,
    events: list | None = None,
    today: _dt.date | None = None,
    linked: dict | None = None,
    notes: list | None = None,
) -> dict:
    """Why `key` stopped, with the evidence from all four tools."""
    today = today or _dt.date.today()
    task = tasks.get(key)
    if not task:
        return {"error": f"unknown task: {key}", "available": sorted(tasks)[:20]}

    linked = linked or linking.link(
        tasks, snapshot.get("commits", []), snapshot.get("pulls", []), snapshot.get("people")
    )
    bundle = linked.get(key) or {"commits": [], "pulls": [], "links": []}
    span = window(task, bundle["commits"], today)
    since, until = _date(span["since"]) or today, today
    who = task.assignee or ""

    causes: list[dict] = []

    open_deps = [d for d in task.deps if d in tasks and not tasks[d].is_done]
    if open_deps:
        # A dependency accounts for the whole silence: the work could not legitimately start.
        causes.append(
            {
                "kind": "dependency_open",
                "days": span["days"],
                "detail": f"{len(open_deps)} dependencies are not done yet",
                # The numbers the sentence was built from. A caller that has to say this
                # some other way — another language, a chart — should not have to parse
                # English back out of it.
                "facts": {"open": len(open_deps)},
                "evidence": [f"{d} {tasks[d].summary} ({tasks[d].status})" for d in open_deps[:3]],
                "source": "board",
            }
        )

    for pull in bundle["pulls"]:
        if pull.get("state") != "open" or pull.get("draft"):
            continue
        waited = schedule.workdays_between(_date(pull.get("updated")) or today, today)
        if waited >= REVIEW_WAIT_DAYS:
            causes.append(
                {
                    "kind": "waiting_on_review",
                    "days": waited,
                    "detail": f"PR #{pull.get('number')} has been open with no movement",
                    "facts": {"number": pull.get("number"), "waited": waited},
                    "evidence": [pull.get("url", "")] if pull.get("url") else [],
                    "source": "repo",
                }
            )

    met = _meetings(events or [], who, since, until)
    if who and met["share"] >= MEETING_SHARE:
        detail = f"{who} lost {met['hours']}h to meetings over this stretch"
        if met["top_title"]:
            detail += f', {met["top_hours"]}h of it "{met["top_title"]}"'
        causes.append(
            {
                "kind": "owner_in_meetings",
                "days": met["lost_days"],
                "detail": detail,
                "facts": {
                    "who": who,
                    "hours": met["hours"],
                    "top_title": met["top_title"],
                    "top_hours": met["top_hours"],
                    "days_with_meetings": met["days_with_meetings"],
                },
                "evidence": [f"{met['days_with_meetings']} days carried meetings"],
                "source": "calendar",
            }
        )

    other = _elsewhere(linked, key, who, since, until)
    if other["commits"]:
        causes.append(
            {
                "kind": "owner_worked_elsewhere",
                "days": other["days"],
                "detail": (
                    f"{who} made {other['commits']} commits in this stretch, none of them here"
                ),
                "facts": {"who": who, "commits": other["commits"], "days": other["days"]},
                "evidence": [f"{k} {tasks[k].summary}" for k in other["tasks"] if k in tasks],
                "source": "repo",
            }
        )

    # A task with nothing overdue still has a story if someone wrote one down. Looking for
    # the note over a fixed lookback rather than the (possibly empty) silence means "what is
    # blocking this" has an answer before the due date passes, which is when it is useful.
    note_since = min(since, schedule.add_workdays(today, -LOOKBACK_DAYS))
    found = _decision(notes or [], key, tasks, note_since, until)
    if found:
        # A written decision explains nothing about the *duration* — it names the reason.
        # Giving it days would double-count the meetings it was written in, so it carries
        # zero and is pinned to the front instead: this is the sentence a person wants.
        score, note = found
        causes.insert(
            0,
            {
                "kind": "decision_recorded",
                "days": 0,
                "detail": _clip(note.get("body") or ""),
                "facts": {
                    "title": note.get("title", ""),
                    "author": note.get("author", ""),
                    "date": note.get("date", ""),
                    "coverage": score,
                },
                "evidence": [
                    f"{note.get('title', '')} — {note.get('author', '')}, {note.get('date', '')}",
                    f"matched to this task by inference, coverage {score}",
                ],
                "source": "notes",
            },
        )

    causes.sort(key=lambda c: (c["kind"] != "decision_recorded", -c["days"]))
    explained = _account(causes, events or [], linked, key, who, since, until)
    claimed = round(sum(c["days"] for c in causes), 1)
    dark = _trace(snapshot.get("commits", []), events or [], who, since, until, bool(events))
    return {
        "key": key,
        "summary": task.summary,
        "assignee": who,
        "status": task.status,
        "window": span,
        "causes": causes,
        "explained_days": explained,
        "unexplained_days": round(max(0.0, span["days"] - explained), 1),
        # what the causes claim between them, minus what the days can actually carry
        "overlap": round(max(0.0, claimed - explained), 1),
        "trace": dark,
        "note": _note(span, causes, explained, dark),
    }


def _note(span: dict, causes: list, explained: float, dark: dict | None = None) -> str:
    """One honest sentence about how much of the silence is actually accounted for."""
    if not span["days"]:
        written = [c for c in causes if c["kind"] == "decision_recorded"]
        if written:
            return (
                "Nothing is overdue here yet, so there is no silence to account for — but "
                "this was written down about it."
            )
        return "There is no gap to explain — the task has activity up to today."
    if not causes:
        return (
            f"{span['days']} business days with no activity, and nothing in the board, the "
            f"repository or the calendar accounts for it. That is a question for its owner, "
            f"not a conclusion."
        )
    left = span["days"] - explained
    if left > 0:
        said = (
            f"{explained} of {span['days']} silent business days are accounted for; "
            f"{round(left, 1)} are not."
        )
        return f"{said} {_blind(dark)}" if _blind(dark) else said
    return f"All {span['days']} silent business days are accounted for."


def _blind(dark: dict | None) -> str:
    """The half-sentence that says which kind of leftover this is.

    An unaccounted day means one of two opposite things, and the difference decides what
    the reader does next. If the owner left a trace somewhere on that day — a commit to
    another task, a meeting — then they were at work and did not come here, and the
    remainder is a question to ask them. If they left none, the day is not unexplained so
    much as unobserved, and the question is which system nobody connected.

    Collapsing both into "6.2 days unexplained" reads like ignorance in either case. It is
    only ignorance in the second.
    """
    if not dark or not dark["workdays"]:
        return ""
    where = " or ".join(dark["looked_in"])
    if not dark["no_trace"]:
        return (
            "They were visibly at work every one of those days, so the rest is a question "
            "for them rather than a gap in what can be seen."
        )
    return (
        f"They left a trace in {where} on {dark['with_trace']} of those {dark['workdays']} "
        f"days; on the other {dark['no_trace']} there is none at all, which is a blind spot "
        f"rather than a reason."
    )


def worst(
    tasks: dict,
    snapshot: dict,
    events: list | None = None,
    today: _dt.date | None = None,
    top: int = 3,
    notes: list | None = None,
) -> list:
    """The tasks that stopped, each with its explanation, worst first.

    Only unfinished work is considered — a finished task going quiet is the point.

    Work that *started and then stopped* comes first, ahead of work that was never
    picked up. Both are silent, but only the first is a stall: a release task with no
    commits three weeks before its phase begins is a schedule question, not a mystery.
    Within each group the longest silence wins.
    """
    today = today or _dt.date.today()
    linked = linking.link(
        tasks, snapshot.get("commits", []), snapshot.get("pulls", []), snapshot.get("people")
    )
    rows = [
        explain(key, tasks, snapshot, events, today, linked, notes)
        for key, task in tasks.items()
        if not task.is_done
    ]
    rows = [r for r in rows if r.get("window", {}).get("days")]
    started = ("last commit", "overdue since")
    rows.sort(key=lambda r: (r["window"]["from"] not in started, -r["window"]["days"], r["key"]))
    return rows[:top]
