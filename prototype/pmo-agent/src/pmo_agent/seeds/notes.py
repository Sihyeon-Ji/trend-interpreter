"""The fictional notes archive — the projection of what was *written down*.

The board, the repository and the calendar are all machine records or status fields. This
is the only one made of sentences, and it is the only place a decision exists: the calendar
can say three hours went into an incident call, but not what the incident was.

Notes here carry no ticket key, for the same reason the commits do not. A team writing
minutes does not annotate them with issue IDs, and working out which task a paragraph is
about is the agent's job (`linking.mentions`, used by `cause.py`).

Read-only data — nothing here writes anywhere.

Run:
  python -m pmo_agent.seeds.notes            write data/notes_state.json
  python -m pmo_agent.seeds.notes --print    summary only, save nothing
"""

from __future__ import annotations

import datetime as dt
import json
import sys

from pmo_agent.adapters.memory_notes import DEFAULT
from pmo_agent.env import data_dir
from pmo_agent.seeds import world as world_mod


def build(today: dt.date | None = None) -> dict:
    return world_mod.to_notes(world_mod.simulate(today))


def write(path: str | None = None, today: dt.date | None = None) -> dict:
    """Write the archive to the local notes file, overwriting whatever is there."""
    data = build(today)
    target = path or str(data_dir() / DEFAULT)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    return {"path": target, "notes": len(data["notes"]), "planted": data["planted"]}


def describe(today: dt.date | None = None) -> dict:
    data = build(today)
    authors = sorted({n["author"] for n in data["notes"]})
    titles: dict[str, int] = {}
    for note in data["notes"]:
        head = note["title"].split(" — ")[0]
        titles[head] = titles.get(head, 0) + 1
    return {
        "source": data["source"],
        "notes": len(data["notes"]),
        "authors": authors,
        "by_meeting": titles,
        "planted": data["planted"],
    }


if __name__ == "__main__":
    print(json.dumps(describe(), ensure_ascii=False, indent=1))
    if "--print" not in sys.argv:
        result = write()
        print(f"\nsaved: {result['path']}  ({result['notes']} notes)")
        print("use: cause reads this archive whenever it is present.")
