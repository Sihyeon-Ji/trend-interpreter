"""Export the simulated meeting notes as a CSV that Notion can merge into a database.

The Notion adapter is read-only, on purpose: an agent has no business writing into
someone's workspace. But a demo needs rows in there, and typing them out by hand is ten
minutes of nobody's time well spent.

Notion can merge a CSV into an existing database (database → ⋯ → Merge with CSV). It adds
the rows and creates any column the file has and the database does not, which is how the
Date and Author columns arrive without anyone configuring them.

The notes carry no ticket keys, exactly as `seeds/notes.py` writes them — working out which
task a paragraph is about is the agent's job, and a key in the file would delete the problem.

Run:
  python tools/notion_csv.py            write samples/notion-notes.csv
  python tools/notion_csv.py --print    show the rows without writing
"""

from __future__ import annotations

import csv
import datetime as dt
import sys

from pmo_agent.env import samples_dir
from pmo_agent.seeds import world as world_mod

OUT = "notion-notes.csv"
# Column names Notion will create on merge. They are only defaults: the adapter matches
# columns by type, so a workspace that renames them keeps working.
COLUMNS = ("Name", "Date", "Author", "Body")


def rows(today: dt.date | None = None, limit: int = 12) -> list:
    """The notes, newest first, trimmed to what a demo needs."""
    notes = world_mod.to_notes(world_mod.simulate(today))["notes"]
    notes.sort(key=lambda n: n["date"], reverse=True)
    return [
        {
            "Name": note["title"],
            "Date": note["date"],
            "Author": note["author"],
            "Body": " ".join((note["body"] or "").split()),
        }
        for note in notes[:limit]
    ]


def write(path: str | None = None, today: dt.date | None = None, limit: int = 12) -> dict:
    target = path or str(samples_dir() / OUT)
    data = rows(today, limit)
    with open(target, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS))
        writer.writeheader()
        writer.writerows(data)
    return {"path": target, "rows": len(data)}


def main(argv: list) -> int:
    data = rows()
    print(f"{len(data)} notes from the current world\n")
    for note in data[:4]:
        print(f"  {note['Date']}  {note['Author']:<14} {note['Name'][:44]}")
        print(f"      {note['Body'][:96]}")
    if len(data) > 4:
        print(f"  … and {len(data) - 4} more")

    if "--print" in argv:
        return 0

    result = write()
    print(f"\nwrote {result['rows']} rows to {result['path']}")
    print("\nTo load them into Notion, by hand:")
    print("  open the notes database → ⋯ (top right) → Merge with CSV → pick that file")
    print("  Notion creates the Date and Author columns for you.")
    print("\nOr in one command: python tools/notion_seed.py --approve")
    print("Then: NOTES_BACKEND=notion python tools/check_env.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
