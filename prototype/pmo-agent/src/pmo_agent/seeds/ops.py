"""A simulated operations board — work that arrives, gets handled, and never finishes.

Every other seed here describes delivery: a fixed scope, dependencies, a finish date. An
operations project is not a smaller version of that, it is a different shape. Tickets
arrive at some rate, get closed at some rate, and the only interesting questions are
whether those two rates match and whether the same thing keeps coming back.

That matters because the agent has quietly assumed delivery everywhere. "When does this
finish" is not a hard question about an operations board, it is a **category error**, and
the only way to be sure the code stops asking it is to have a board where the answer would
be nonsense.

What is planted here, so a check can find it:

  · a **backlog that is growing** — more arrives each week than is closed
  · a **recurring fault**, the same failure on five separate tickets, which is one problem
    wearing five ticket numbers and is invisible if you only count open items
  · a handful of tickets **older than they should be**, which is what ages a queue

No dependencies and no due dates, deliberately. A due date on an incident is a fiction
somebody typed, and building the demo on one would hide exactly the thing being shown.

Run:
  python -m pmo_agent.seeds.ops            write data/seed_state_OPS.json
  python -m pmo_agent.seeds.ops --print    summary only, save nothing
"""

from __future__ import annotations

import datetime as dt
import json
import random
import sys

from pmo_agent import schedule
from pmo_agent.env import data_dir

KEY = "OPS"
NAME = "Platform operations"
BACK_DAYS = 60  # how much history to invent
PEOPLE = ("Priya Raman", "Noah Brandt", "Leo Fischer")

# The recurring one is first on purpose: five tickets, one problem.
RECURRING = "Checkout times out under load"
KINDS = (
    (RECURRING, "incident", 5),
    ("Password reset email not delivered", "incident", 3),
    ("Report export fails for large accounts", "bug", 3),
    ("Stale cache after a price change", "bug", 2),
    ("Onboarding webhook retries forever", "incident", 2),
    ("Duplicate invoice on a retried payment", "bug", 2),
    ("Search returns deleted items", "bug", 2),
    ("Nightly sync ran twice", "incident", 1),
    ("Access request for the billing dashboard", "request", 4),
    ("Add a column to the monthly export", "request", 3),
)

OPEN = "In Progress"
WAITING = "To Do"
CLOSED = "Done"


def build(today: dt.date | None = None) -> dict:
    """Sixty days of a queue: what arrived, what closed, and what is still sitting there."""
    today = today or dt.date.today()
    rnd = random.Random(7)
    issues, number = [], 0

    for title, kind, count in KINDS:
        for _ in range(count):
            number += 1
            # Arrivals speed up towards the present, which is what a growing backlog is.
            age = int(abs(rnd.gauss(0, 1)) * BACK_DAYS / 2.2)
            opened = today - dt.timedelta(days=min(age, BACK_DAYS))
            issues.append(_ticket(number, title, kind, opened, today, rnd))

    issues.sort(key=lambda i: i["fields"]["created"])
    for position, issue in enumerate(issues, start=1):
        issue["key"] = f"{KEY}-{position}"
    return {
        "project": KEY,
        "name": NAME,
        "kind": "run",
        "issues": issues,
        "planted": _planted(issues, today),
    }


def _ticket(number: int, title: str, kind: str, opened: dt.date, today: dt.date, rnd) -> dict:
    """One ticket. Older ones are mostly closed; the recurring fault is mostly not."""
    days_open = (today - opened).days
    sticky = title == RECURRING
    # A queue that is keeping up closes most of what arrives. This one does not quite.
    closes = rnd.random() < (0.34 if sticky else 0.72) and days_open > 2
    resolved = (
        opened + dt.timedelta(days=rnd.randint(1, max(2, min(days_open, 9)))) if closes else None
    )

    fields = {
        "summary": f"[{kind.title()}] {title}",
        "status": {"name": CLOSED if resolved else (OPEN if rnd.random() < 0.55 else WAITING)},
        "assignee": {"displayName": PEOPLE[number % len(PEOPLE)]},
        "created": opened.isoformat(),
        "labels": [kind, f"owner-{schedule.owner_tag(PEOPLE[number % len(PEOPLE)])}"],
        # No duedate and no dependencies, on purpose. An incident's due date is a fiction
        # somebody typed, and a demo built on one would hide what this board is for.
        "issuelinks": [],
    }
    if resolved:
        fields["resolutiondate"] = resolved.isoformat()
    return {"key": f"{KEY}-{number}", "fields": fields}


def _planted(issues: list, today: dt.date) -> list:
    """The answer key, the same way the delivery world keeps one."""
    live = [i for i in issues if i["fields"]["status"]["name"] != CLOSED]
    recurring = [i for i in issues if RECURRING in i["fields"]["summary"]]
    oldest = sorted(live, key=lambda i: i["fields"]["created"])[:3]
    return [
        {
            "kind": "recurring_fault",
            "detail": RECURRING,
            "count": len(recurring),
            "expect": "five tickets are one problem; counting open items alone hides that",
        },
        {
            "kind": "backlog_growing",
            "open": len(live),
            "expect": "more arrives each week than is closed",
        },
        {
            "kind": "aged_tickets",
            "keys": [i["key"] for i in oldest],
            "expect": f"open since {oldest[0]['fields']['created']}" if oldest else "",
        },
        {
            "kind": "no_finish_date",
            "expect": "this board has no due dates; asking when it finishes is a category error",
        },
    ]


def write(path: str | None = None, today: dt.date | None = None) -> dict:
    data = build(today)
    target = path or str(data_dir() / f"seed_state_{KEY}.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    return {"path": target, "issues": len(data["issues"])}


def main(argv: list) -> int:
    data = build()
    live = [i for i in data["issues"] if i["fields"]["status"]["name"] != CLOSED]
    print(f"{NAME} ({KEY}) — {len(data['issues'])} tickets, {len(live)} still open\n")
    for row in data["planted"]:
        print(f"  planted  {row['kind']:<18} {row.get('detail') or row.get('expect', '')}"[:96])
    print()
    for issue in live[:6]:
        f = issue["fields"]
        print(f"  {issue['key']:<8} {f['status']['name']:<12} {f['created']}  {f['summary'][:48]}")
    if len(live) > 6:
        print(f"  … and {len(live) - 6} more open")

    if "--print" in argv:
        return 0
    out = write()
    print(f"\nsaved: {out['path']}  ({out['issues']} tickets)")
    print("use: add OPS to data/projects.json and it appears in the roll-up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
