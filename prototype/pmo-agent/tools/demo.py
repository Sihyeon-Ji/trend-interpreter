"""The three-minute demo — one command that walks the whole loop.

This is the team workflow document's "three-minute demo path", pinned down as a script.
Same order and same screens every time, so the demo never has to improvise.

    1. what the schedule looks like now          (dependencies only)
    2. what changes once capacity and meetings go in   ← the differentiator
    3. what moving something would buy
    4. what shows when the board meets the code  ← invisible from either side alone
    5. why it stopped                            ← needs all three at once
    6. what a photo of a meeting note gives      (Gemini multimodal)
    7. what gets proposed / still not applied
    8. approval is what applies it               (without --approve it stops here)

Run:
  python tools/demo.py                  read-only (changes nothing)
  python tools/demo.py --approve        also applies the first of the step-7 proposals
  PMO_BACKEND=memory python tools/demo.py   with the local board, no accounts
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import textwrap
import time

from pmo_agent import approve as approve_mod  # noqa: E402
from pmo_agent import availability as avail_mod
from pmo_agent import capacity, ingest, schedule, signals, tools
from pmo_agent.env import samples_dir
from pmo_agent.llm import LLMError

NOTE = str(samples_dir() / "meeting-note.png")
W = 74


def step(n: int, title: str, why: str = "") -> None:
    print("\n" + "=" * W)
    print(f" {n}. {title}")
    if why:
        print(f"    {why}")
    print("=" * W)


def main(argv) -> int:
    do_approve = "--approve" in argv
    today = dt.date.today()
    t0 = time.time()

    board = tools.jira()
    print(
        f"board: {getattr(board, 'site', '?')} / {getattr(board, 'project', '?')}"
        f"   ({type(board).__name__})"
    )
    tasks = tools._fetch()
    if not tasks:
        print("no tasks. Build the seed first:  python -m pmo_agent.seeds.jira_seed --approve")
        return 1

    # ---- 1 ----
    step(1, "the schedule now", "dependencies (Blocks) only — where most PM tools stop")
    s = schedule.summary(tasks, today)
    print(f"  {s['total']} tasks ({s['done']} done)")
    print(
        f"  forecast finish {s['predicted_finish']}   critical path {len(s['critical_path'])}"
        f"   at risk {len(s['risks'])}"
    )
    for r in s["risks"][:3]:
        print(f"    - {r['key']} {r['summary'][:24]:<24} {r['assignee']}  {r['reasons'][0]}")

    # ---- 2 ----
    step(
        2,
        "adding the constraints one at a time",
        "one task at a time, plus the hours meetings ate. No tool looks at both",
    )
    availability = tools._availability()
    c = capacity.summary(tasks, today, availability=availability)
    b = c["bottleneck"]
    print(f"  dependencies only   {c['unconstrained_finish']}")
    if c["calendar_applied"]:
        print(f"  plus capacity       {c['finish_without_meetings']}")
        print(
            f"  plus meetings       {c['capacity_finish']}   "
            f"(+{c['slip_vs_unconstrained']} days, {c['meeting_slip_days']} from meetings)"
        )
    else:
        print(
            f"  plus capacity       {c['capacity_finish']}   (+{c['slip_vs_unconstrained']} days)"
        )
    if b:
        print(f"\n  bottleneck: {b['assignee']} — {b['busy_days']} d left, {b['utilization']} used")
        print(f"        they free up on {b['free_at']}, the floor for the project")
    if availability:
        print("\n  hours lost to meetings (next 10 business days):")
        for who in sorted({t.assignee for t in tasks.values() if t.assignee}):
            m = avail_mod.meeting_load(availability, who, today, 10)
            print(f"    - {who}  {m['lost_hours']}h meetings → {m['available_days']}/10 usable")

    print("\n  dependencies met, but waiting on a busy owner:")
    for w in c["waiting_tasks"][:3]:
        print(
            f"    - {w['key']} {w['summary'][:22]:<22} {w['assignee']}  waited {w['waiting_days']}d"
        )

    # ---- 3 ----
    step(
        3,
        "what moving something would buy",
        "offered only to someone who has worked in that area — a proposal, not a decision",
    )
    # The repository decides who could plausibly take a task, so the demo vets the moves
    # the same way the tool layer does rather than quietly skipping the check.
    handover, _why = tools._handover_check(tasks)
    rb = capacity.rebalance(tasks, today, max_moves=3, availability=availability, can_take=handover)
    rb["handovers_vetted"] = bool(handover)
    if rb["moves"]:
        print(
            f"  {len(rb['moves'])} moves → {rb['before']} → {rb['after']} "
            f"({rb['gain_days']} business days earlier)"
            + ("" if rb.get("handovers_vetted") else "   [handovers not vetted]")
        )
        for m in rb["moves"]:
            print(
                f"    - {m['key']} {m['summary'][:24]:<24} {m['from']} → {m['to']}  "
                f"{m['gain_days']}d"
            )
    else:
        print("  no task can be moved to pull the finish in")

    # ---- 3.5 ----
    step(4, "the board against the code", "invisible from one side — a different kind of signal")
    try:
        sig = signals.summary(tasks, tools._snapshot(100), today)
        t = sig["team"]
        print(
            f"  repo {sig['repo']}  {t['commits']} commits in {t['window_days']} days, "
            f"concentration {t['concentration']}, {t['open_prs']} open pull requests"
        )
        for n in t["notes"][:3]:
            print(f"    · {n}")
        if sig["note"]:
            print(f"    · {sig['note']}")
        for m in sig["mismatches"][:4]:
            print(f"    - {m['key']:<9} [{m['kind']}] {m['detail']}")
    except Exception as e:
        print(f"  (could not read the repository: {str(e)[:90]})")

    # ---- 3.7 ----
    step(5, "why it stopped", "the only answer that needs every tool at once")
    try:
        found = tools.explain_stall(today=today.isoformat())
        if not found.get("calendar_read"):
            print("  (no calendar behind us, so the 'where did the time go' half is missing)")
        if not found.get("notes_read"):
            why = found.get("notes_note") or "no meeting notes"
            print(f"  ({why} — so nothing here can say what was actually decided)")
        for row in found.get("worst", [])[:3]:
            print("")
            print(
                f"  {row['key']} {row['summary'][:34]}  silent {row['window']['days']}d"
                f"  ({row['assignee'] or 'unassigned'})"
            )
            for c in row["causes"]:
                print(f"    [{c['source']:<8}] {c['detail'][:110]}")
                if c["source"] == "notes":
                    print(f"              written in: {c['evidence'][0]}")
            if not row["causes"]:
                print("    (nothing in any tool accounts for it)")
            lines = textwrap.wrap(row["note"], 86)
            for i, line in enumerate(lines):
                print(f"    {'->' if not i else '  '} {line}")
    except Exception as e:
        print(f"  (could not explain: {str(e)[:90]})")

    # ---- 4 ----
    step(6, "a photo of a meeting note", "Gemini multimodal — the model reads, the code decides")
    if not os.path.exists(NOTE):
        print("  no sample note. First run:  python tools/make_note.py")
        return 1
    print(f"  input: {os.path.relpath(NOTE)}  ({os.path.getsize(NOTE) // 1024}KB)")
    try:
        r = ingest.ingest("", [NOTE], tasks=tasks, today=today)
    except LLMError as e:
        if getattr(e, "daily", False):
            print("  every model's free daily quota is used up, so this step cannot run.")
            print("  It comes back tomorrow; a billed key or Vertex has no such cap.")
        else:
            print(f"  the model call failed: {' '.join(str(e).split())[:150]}")
        return 1

    # ---- 5 ----
    step(7, "what was read out", "applied=false — nothing has been applied yet")
    for x in r["resolved"]:
        what = (
            f"due {x.get('duedate_was')} → {x['duedate']}"
            if x.get("duedate")
            else f"status → {x['status']}"
            if x.get("status")
            else "comment"
        )
        print(f"    {x['key']:<9} {x['summary'][:24]:<24} {what}  (confidence {x['confidence']})")
    for n in r["notes"]:
        print(f"    (note)    {n}")
    for q in r["questions"]:
        print(f"    (question) {q}")
    if r["impact"]:
        i = r["impact"]
        print(
            f"\n  if applied: forecast finish {i['predicted_finish_before']} → "
            f"{i['predicted_finish_after']}, "
            f"at risk {i['risks_before']} → {i['risks_after']}"
        )

    # ---- 6 ----
    step(8, "approval", "only what a person picked is written. The model cannot call this step")
    print(approve_mod.render(r["proposals"], r["impact"]))
    items = approve_mod.appliable(r["proposals"])
    if not do_approve:
        print("\n  (read-only demo. Add --approve to see it actually applied)")
    elif not items:
        print("\n  nothing to apply")
    else:
        print(f"\n  applying number 1 only → {approve_mod.describe(items[0])}")
        out = approve_mod.apply(r["proposals"], [0], source="demo")
        print(f"  applied {out['applied']} / failed {out['failed']} — log: {approve_mod.LOG}")

    print(
        f"\n{'=' * W}\n  {time.time() - t0:.1f}s. Every number came from schedule.py / "
        f"capacity.py.\n{'=' * W}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
