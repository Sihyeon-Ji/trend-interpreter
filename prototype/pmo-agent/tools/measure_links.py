"""Measure how often the keyless linking is right, against the simulation's answer key.

The README leads with a number — precision, recall, mean confidence — and until this
existed nothing produced it. A project whose argument is "it does not say what it cannot
show" cannot have its headline figure be a remembered one, so here is the thing that
shows it, and `test_linking_accuracy.py` holds the README to what it prints.

The measurement is only possible because the world is simulated: `link_truth` records
which task each commit actually belonged to, and the adapters never expose it. The linker
sees exactly what a real repository would give it — author, date, message, paths — and
never the key.

Three numbers, and the third is the one that matters:

  precision  of the links it made, how many were right. A wrong link is the expensive
             mistake: it puts a commit on somebody else's task and every number built on
             top inherits it quietly
  recall     of the commits that had a task, how many it found. A miss is cheap — the
             commit stays unlinked and is reported as such
  unlinked   the commits it refused to place, which is the restraint working, not a gap

Run:
  python tools/measure_links.py             today's world
  python tools/measure_links.py --dates 8   eight dates, to show the numbers are stable
  python tools/measure_links.py --assist    also measure with the model filling the gaps
"""

from __future__ import annotations

import datetime as dt
import sys

from pmo_agent import linking, schedule
from pmo_agent.seeds import world as world_mod


def measure(today: dt.date | None = None, assist=None) -> dict:
    """Link the world's own commits and score them against `link_truth`."""
    world = world_mod.simulate(today)
    board = world_mod.to_board(world)
    repo = world_mod.to_repo(world, board)
    tasks = schedule.from_jira_issues(board["issues"])
    truth = repo["link_truth"]

    linked = linking.link(tasks, repo["commits"], repo["pulls"], repo.get("people"), assist=assist)

    # {sha: key} as the linker decided it, so a commit placed on two tasks would show up
    got: dict[str, str] = {}
    confidence: dict[str, float] = {}
    for key, bundle in linked.items():
        for commit in bundle["commits"]:
            got[commit["sha"]] = key
        for record in bundle["links"]:
            if record.get("sha"):
                confidence[record["sha"]] = float(record.get("confidence") or 0.0)

    answerable = [c for c in repo["commits"] if truth.get(c["sha"])]
    right = [c for c in answerable if got.get(c["sha"]) == truth[c["sha"]]]
    wrong = [c for c in answerable if c["sha"] in got and got[c["sha"]] != truth[c["sha"]]]
    unlinked = [c for c in answerable if c["sha"] not in got]
    made = len(right) + len(wrong)
    scores = [confidence.get(c["sha"], 0.0) for c in right + wrong]

    return {
        "date": world.today.isoformat(),
        "commits": len(answerable),
        "right": len(right),
        "wrong": len(wrong),
        "unlinked": len(unlinked),
        "precision": round(len(right) / made, 3) if made else 1.0,
        "recall": round(len(right) / len(answerable), 3) if answerable else 1.0,
        "confidence": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "assist": dict(getattr(assist, "stats", {})) if assist else None,
        "wrong_examples": [
            {
                "sha": c["sha"][:7],
                "message": c["message"][:52],
                "got": got[c["sha"]],
                "want": truth[c["sha"]],
            }
            for c in wrong[:5]
        ],
    }


def over_dates(count: int = 8, step: int = 11, assist=None) -> list:
    """The same measurement at several dates. One good day is not a result."""
    start = dt.date.today()
    return [measure(start + dt.timedelta(days=i * step), assist) for i in range(count)]


def line(row: dict) -> str:
    return (
        f"  {row['date']}  {row['commits']:>3} commits  "
        f"right {row['right']:>3} / wrong {row['wrong']:>2} / unlinked {row['unlinked']:>2}  "
        f"precision {row['precision']:.2f} | recall {row['recall']:.2f} | "
        f"confidence {row['confidence']:.2f}"
    )


def assist_note(rows: list) -> str:
    """What the model actually contributed \u2014 or that it did not, which is the same number
    as a rules-only run wearing a different label.

    A rate-limited or refused call leaves the commit unlinked, which is honest at runtime.
    Printing that run as "with model assist" is not: it is the rules-only figure under a
    name that claims otherwise, and nobody reading it could tell.
    """
    asked = sum((r["assist"] or {}).get("asked", 0) for r in rows)
    answered = sum((r["assist"] or {}).get("answered", 0) for r in rows)
    failed = sum((r["assist"] or {}).get("failed_batches", 0) for r in rows)
    errors = [
        (r["assist"] or {}).get("error", "") for r in rows if (r["assist"] or {}).get("error")
    ]
    if not asked:
        return "the rules left nothing unresolved, so the model was never called."
    why = f" ({errors[0]})" if errors else ""
    broke = f"{failed} batch{'' if failed == 1 else 'es'} failed{why}"
    if not answered:
        return (
            f"THE MODEL ANSWERED NOTHING: {asked} commits put to it, {broke}. The figures "
            f"above are the rules on their own — do not report them as assisted."
        )
    note = f"the model placed {answered} of the {asked} commits the rules left open"
    return f"{note}; {broke}." if failed else f"{note}."


def main(argv: list) -> int:
    assist = None
    if "--assist" in argv:
        from pmo_agent import link_assist

        assist = link_assist.assistant()

    count = 1
    if "--dates" in argv:
        at = argv.index("--dates")
        count = int(argv[at + 1]) if len(argv) > at + 1 else 8

    rows = over_dates(count, assist=assist) if count > 1 else [measure(assist=assist)]
    print(f"keyless linking against the answer key{' (with model assist)' if assist else ''}\n")
    for row in rows:
        print(line(row))

    worst_p = min(r["precision"] for r in rows)
    worst_r = min(r["recall"] for r in rows)
    print(f"\n  worst of {len(rows)}: precision {worst_p:.2f} | recall {worst_r:.2f}")

    if assist:
        print(f"  {assist_note(rows)}")

    bad = [w for r in rows for w in r["wrong_examples"]]
    if bad:
        print("\n  wrong links:")
        for w in bad[:8]:
            print(f"    {w['sha']}  {w['message']:<52} -> {w['got']} (really {w['want']})")
    else:
        print("  no wrong links at any date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
