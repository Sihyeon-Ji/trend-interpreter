"""The weekly report — schedule.py's results, moved into Markdown.

There is no calculation here. Every number comes from schedule.py; this file does layout and prose.
It does not use Gemini either — a report should look the same every week, and the same board
should produce the same text.
One limitation is written into the report itself: the board has no record of *when* something was
completed, so "finished this week" cannot be derived. Instead the approval log
(logs/approvals.jsonl) shows what was actually applied this week.
Run:
  PMO_BACKEND=memory python -m pmo_agent.report            print the report
  PMO_BACKEND=memory python -m pmo_agent.report --save     write it to reports/
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import availability as avail_mod
from pmo_agent import capacity as cap
from pmo_agent import schedule, signals
from pmo_agent.env import logs_dir, reports_dir

OUT_DIR = str(reports_dir())
LOG = str(logs_dir() / "approvals.jsonl")
TOP_RISKS = 8


def _d(v) -> str:
    return v.isoformat() if isinstance(v, dt.date) else (v or "-")


def question_for(r: dict) -> str:
    """One risk → one sentence to put to its owner (SYSTEM rule 4, pinned down in code)."""
    who = r.get("assignee") or "the owner"
    if r.get("delay_days"):
        base = (
            f"{who}: {r['key']} ({r['summary']}) looks like it will finish "
            f"{r['delay_days']} days past its due date of {_d(r['duedate'])}"
        )
    elif r.get("critical"):
        base = f"{who}: {r['key']} ({r['summary']}) is on the critical path with no slack"
    else:
        base = f"{who}: {r['key']} ({r['summary']}) has only {r['slack_days']} days of slack"
    if r.get("blocks"):
        base += f" — {', '.join(r['blocks'][:3])} cannot start until it lands"
    return base + ". Could you share where it stands and when you expect it to finish?"


def workload(tasks: dict) -> list:
    """Work left per owner. For seeing where it has piled up."""
    by: dict[str, dict] = {}
    for t in tasks.values():
        if t.is_done:
            continue
        row = by.setdefault(
            t.assignee or "(unassigned)",
            {"assignee": t.assignee or "(unassigned)", "count": 0, "days": 0.0},
        )
        row["count"] += 1
        row["days"] += t.remaining
    for row in by.values():
        row["days"] = round(row["days"], 1)
    return sorted(by.values(), key=lambda r: -r["days"])


def due_soon(tasks: dict, today: dt.date, within: int = 5) -> list:
    """Unfinished tasks due within the next N business days."""
    limit = schedule.add_workdays(today, within)
    out = [t for t in tasks.values() if not t.is_done and t.duedate and today <= t.duedate <= limit]
    return sorted(out, key=lambda t: (t.duedate, t.key))


def committed_finish(tasks: dict) -> dt.date | None:
    """The finish the team committed to = the latest task due date.

    Using CPM's "if we started today, when would we finish" as the plan makes it almost identical
    to the forecast, so the comparison says nothing. The comparison worth printing is
    "the date we promised vs. what we now forecast".
    """
    ds = [t.duedate for t in tasks.values() if t.duedate]
    return max(ds) if ds else None


def overdue(tasks: dict, today: dt.date) -> list:
    """Past its due date and still not finished."""
    out = [t for t in tasks.values() if not t.is_done and t.duedate and t.duedate < today]
    return sorted(out, key=lambda t: (t.duedate, t.key))


def recent_approvals(since: dt.date, path: str | None = None) -> list:
    """Changes actually applied since `since`. Empty when there is no approval log."""
    p = path or LOG
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("ok") and (r.get("at") or "")[:10] >= since.isoformat():
                out.append(r)
    return out


def weekly(
    tasks: dict,
    today: dt.date | None = None,
    approvals_path: str | None = None,
    project: str = "ECHO",
    rebalance: bool = True,
    done_recent: list | None = None,
    code: dict | None = None,
    availability: dict | None = None,
    stalls: list | None = None,
    stalls_note: str = "",
    can_take=None,
) -> str:
    """The whole weekly report, as Markdown."""
    today = today or dt.date.today()
    since = schedule.add_workdays(today, -5)
    c = schedule.cpm(tasks, today)
    f = schedule.forecast(tasks, today)
    rs = schedule.risks(tasks, today)
    done = sum(1 for t in tasks.values() if t.is_done)
    committed = committed_finish(tasks)
    slip = schedule.workdays_between(committed, f["project_finish"]) if committed else 0
    late = overdue(tasks, today)

    L = [f"# {project} weekly report — {today.isoformat()}", ""]

    L += [
        "## At a glance",
        "",
        "| item | value |",
        "|---|---|",
        f"| progress | {done}/{len(tasks)} done ({round(done / max(len(tasks), 1) * 100)}%) |",
        f"| committed finish | {_d(committed)} |",
        f"| forecast finish | **{_d(f['project_finish'])}** "
        f"({'+' if slip > 0 else ''}{slip} business days) |",
        f"| critical path | {len(c['critical_path'])} tasks |",
        f"| at risk of slipping | {len(rs)} |",
        f"| past due | {len(late)} |",
        "",
    ]

    if slip > 0:
        L += [
            f"> The forecast is **{slip} business days** past the committed finish. "
            f"The risks below are why.",
            "",
        ]
    elif slip < 0:
        L += [f"> The forecast is {abs(slip)} business days ahead of the committed finish.", ""]

    if done_recent is not None:
        L += ["## Finished this week", ""]
        if done_recent:
            L += ["| task | owner |", "|---|---|"]
            L += [f"| {t.key} {t.summary} | {t.assignee or '-'} |" for t in done_recent]
        else:
            L.append("Nothing.")
        L.append("")

    L += ["## At risk of slipping", ""]
    if not rs:
        L += ["Nothing.", ""]
    else:
        L += [
            "| task | owner | due | forecast | slip | slack | why |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rs[:TOP_RISKS]:
            L.append(
                f"| {r['key']} {r['summary']} | {r['assignee'] or '-'} | {_d(r['duedate'])} | "
                f"{_d(r['predicted_finish'])} | {r['delay_days'] or 0}d | {r['slack_days']}d | "
                f"{r['reasons'][0]} |"
            )
        if len(rs) > TOP_RISKS:
            L.append(f"| … | | | | | | and {len(rs) - TOP_RISKS} more |")
        L.append("")

    L += [
        "## Critical path",
        "",
        (" → ".join(f"`{k}`" for k in c["critical_path"]) if c["critical_path"] else "none"),
        "",
        "If this path slips, the project finish slips with it.",
        "",
    ]

    soon = due_soon(tasks, today)
    L += ["## Due this week", ""]
    if soon:
        L += ["| task | owner | due |", "|---|---|---|"]
        L += [f"| {t.key} {t.summary} | {t.assignee or '-'} | {_d(t.duedate)} |" for t in soon]
    else:
        L.append("Nothing.")
    L.append("")

    if late:
        L += ["## Past due", "", "| task | owner | due | status |", "|---|---|---|---|"]
        L += [
            f"| {t.key} {t.summary} | {t.assignee or '-'} | {_d(t.duedate)} | {t.status} |"
            for t in late[:TOP_RISKS]
        ]
        if len(late) > TOP_RISKS:
            L.append(f"| … | | | and {len(late) - TOP_RISKS} more |")
        L.append("")

    L += ["## Work left per owner", "", "| owner | tasks | business days left |", "|---|---|---|"]
    L += [f"| {w['assignee']} | {w['count']} | {w['days']} |" for w in workload(tasks)]
    L.append("")

    # --- the schedule with people's capacity applied ---
    lv = cap.levelled(tasks, today, availability=availability)
    lv_plain = cap.levelled(tasks, today) if availability else lv
    L += [
        "## The achievable schedule",
        "",
        "| constraint | finish |",
        "|---|---|",
        f"| dependencies only | {_d(lv['unconstrained_finish'])} |",
    ]
    if availability:
        # Show what each constraint adds on its own — rolled together, the cause is invisible
        meeting_slip = schedule.workdays_between(lv_plain["project_finish"], lv["project_finish"])
        L += [
            f"| plus people's capacity | {_d(lv_plain['project_finish'])} |",
            f"| **plus meeting time** | **{_d(lv['project_finish'])}** "
            f"(+{lv['slip_vs_unconstrained']} business days, {meeting_slip} of them meetings) |",
            "",
        ]
    else:
        L += [
            f"| **plus people's capacity** | **{_d(lv['project_finish'])}** "
            f"(+{lv['slip_vs_unconstrained']} business days) |",
            "",
            "> No calendar is connected, so everyone is assumed to have whole days. "
            "With meetings it gets later.",
            "",
        ]
    if lv["bottleneck"]:
        b = lv["bottleneck"]
        L += [
            f"> The bottleneck is **{b['assignee']}** — {b['busy_days']} business days left, "
            f"{b['utilization']}. "
            f"They free up on {_d(b['free_at'])}, which is the floor for the project.",
            "",
        ]
    if availability:
        L += [
            "| owner | days left | lost to meetings | usable | utilisation | last finish |",
            "|---|---|---|---|---|---|",
        ]
        for r in lv["resources"]:
            m = avail_mod.meeting_load(availability, r["assignee"], today, 10)
            L.append(
                f"| {r['assignee']} | {r['busy_days']} | {m['lost_hours']}h |"
                f" {m['available_days']}/10d | {r['utilization']} | {_d(r['free_at'])} |"
            )
    else:
        L += [
            "| owner | concurrent | business days left | utilisation | last finish |",
            "|---|---|---|---|---|",
        ]
        L += [
            f"| {r['assignee']} | {r['capacity']} | {r['busy_days']} | {r['utilization']} | "
            f"{_d(r['free_at'])} |"
            for r in lv["resources"]
        ]
    L.append("")
    waiting = cap.blocked_by_people(lv)
    if waiting:
        L += [
            "Tasks whose dependencies are met but whose **owner is busy**. The cause is a person, "
            "not a dependency.",
            "",
            "| task | owner | waiting | starts |",
            "|---|---|---|---|",
        ]
        L += [
            f"| {w['key']} {w['summary']} | {w['assignee']} | {w['waiting_days']}d | "
            f"{_d(w['start'])} |"
            for w in waiting
        ]
        L.append("")

    if rebalance:
        # `can_take` decides which handovers are worth offering. Without it the moves are
        # arithmetic on availability alone, and the section below says so rather than
        # letting "move this to Leo" read the same either way.
        rb = cap.rebalance(tasks, today, availability=availability, can_take=can_take)
        rb["handovers_vetted"] = bool(can_take)
        L += ["## Rebalancing proposal", ""]
        if rb["moves"]:
            L += [
                f"Moving the {len(rb['moves'])} tasks below brings the finish from "
                f"**{_d(rb['before'])} → "
                f"{_d(rb['after'])}"
                f" ({rb['gain_days']} business days earlier)**.",
                "",
                "| task | move | gain | finish after |",
                "|---|---|---|---|",
            ]
            L += [
                f"| {m['key']} {m['summary']} | {m['from']} → {m['to']} | {m['gain_days']}d | "
                f"{_d(m['new_finish'])} |"
                for m in rb["moves"]
            ]
            L += [
                "",
                (
                    "A proposal only; nothing has been applied. A real move needs the owners "
                    "to agree."
                ),
                (
                    "Each move is offered only to someone the repository shows has worked in "
                    "that area."
                )
                if rb.get("handovers_vetted")
                else (
                    f"These moves were **not** vetted against who has worked where "
                    f"({rb.get('handover_note') or 'no repository history'}), so they are "
                    f"arithmetic on availability alone."
                ),
                "",
            ]
        else:
            L += ["No task can be moved to pull the finish in.", ""]

    if code:
        L += [
            "## Board against code",
            "",
            f"From repository `{code.get('repo', '?')}`. The status written on the board, "
            f"lined up against the actual commits and pull requests.",
            "",
        ]
        t = code.get("team") or {}
        L += [
            "| item | value |",
            "|---|---|",
            f"| commits in the last {t.get('window_days', 14)} days | {t.get('commits', 0)} |",
            f"| contribution concentration | {t.get('concentration', 0)} (1.0 = one person) |",
            f"| open pull requests | {t.get('open_prs', 0)} "
            f"({t.get('stale_prs', 0)} stuck in review) |",
            f"| last commit | {t.get('last_commit') or '-'} |",
            "",
        ]
        for n in t.get("notes") or []:
            L.append(f"> {n}")
        if t.get("notes"):
            L.append("")
        if code.get("note"):
            L += [f"> {code['note']}", ""]
        ms = code.get("mismatches") or []
        if ms:
            L += [
                "Tasks where the board and the code disagree. Neither side shows this alone.",
                "",
                "| task | owner | kind | detail |",
                "|---|---|---|---|",
            ]
            L += [
                f"| {m['key']} {m['summary']} | {m['assignee'] or '-'} | `{m['kind']}` | "
                f"{m['detail']} |"
                for m in ms[:TOP_RISKS]
            ]
            if len(ms) > TOP_RISKS:
                L.append(f"| … | | | and {len(ms) - TOP_RISKS} more |")
            L.append("")
        elif code.get("key_convention_in_use"):
            L += ["Nothing disagrees.", ""]

    if stalls:
        L += [
            "## Why the stalled work stopped",
            "",
            "Reconstructed by lining the board, the repository, the calendar and the "
            "meeting notes up against each other. Each cause carries the business days it "
            "accounts for; whatever is left over is stated rather than filled in. A written "
            "decision names the reason rather than the duration, so it carries no days.",
            "",
        ]
        if stalls_note:
            L += [f"> {stalls_note}, so no cause below can say what was decided.", ""]
        for row in stalls:
            L += [
                f"**{row['key']} {row['summary']}** — silent {row['window']['days']} business "
                f"days since {_d(row['window']['since'])} ({row['assignee'] or 'unassigned'})",
                "",
            ]
            for c in row["causes"]:
                weight = (
                    "written down"
                    if c["kind"] == "decision_recorded"
                    else f"accounts for {c['days']} days on its own"
                )
                L.append(f"- `{c['source']}` {c['detail']} — {weight}")
            if not row["causes"]:
                L.append("- nothing in any tool accounts for it")
            if row.get("overlap"):
                # Each cause states its own claim, and they land on the same days. Saying so
                # is the only way the list above and the total below can both be read as true.
                L.append(
                    f"- *these overlap by {row['overlap']} days — a day in meetings that also "
                    f"carried a commit elsewhere is still one day*"
                )
            L += ["", f"> {row['note']}", ""]

    L += ["## Needs checking", ""]
    if rs:
        L += [f"{i}. {question_for(r)}" for i, r in enumerate(rs[:5], 1)]
    else:
        L.append("Nothing.")
    L.append("")

    ap = recent_approvals(since, approvals_path)
    L += [f"## Applied recently (since {_d(since)})", ""]
    if ap:
        L += ["| time | change | target |", "|---|---|---|"]
        L += [
            f"| {r['at']} | {r['tool'].replace('propose_', '')} | "
            f"{r['args'].get('key', '-')} "
            f"{json.dumps({k: v for k, v in r['args'].items() if k != 'key'}, ensure_ascii=False)} "
            f"|"
            for r in ap
        ]
    else:
        L.append("Nothing.")
    L += [
        "",
        "---",
        "",
        "Every number came from `schedule.py` (CPM, business days) and `capacity.py` "
        "(resource constraints). Weekends are excluded.",
        "Board-to-code links do not need a ticket key; where one is missing the link is inferred "
        "and declared as such, with a confidence.",
        "The capacity schedule assumes one concurrent task per person. Adjust the `capacity` "
        "argument if the team works differently.",
        '"Finished this week" comes from the board\'s status history — including changes that '
        "never went through the agent.",
        "",
    ]
    return "\n".join(L)


def save(text: str, today: dt.date | None = None, out_dir: str | None = None) -> str:
    today = today or dt.date.today()
    d = out_dir or OUT_DIR
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"weekly-{today.isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


if __name__ == "__main__":
    from pmo_agent.tools import _availability, _fetch, jira

    today = dt.date.today()
    board = jira()
    done_recent = None
    try:
        done_recent = list(schedule.from_jira_issues(board.done_since(7)).values())
    except Exception as e:  # a backend with no history support just loses this section
        print(f"(skipping completion history: {str(e)[:80]})", file=sys.stderr)
    code = None
    try:
        from pmo_agent.tools import _snapshot

        code = signals.summary(_fetch(), _snapshot(100), today)
    except Exception as e:  # no repository or no credentials loses only this section
        print(f"(skipping code signals: {str(e)[:80]})", file=sys.stderr)
    text = weekly(
        _fetch(),
        today,
        project=getattr(board, "project", "ECHO"),
        done_recent=done_recent,
        code=code,
        availability=_availability(),
    )
    print(text)
    if "--save" in sys.argv:
        print(f"\nsaved: {save(text, today)}")
