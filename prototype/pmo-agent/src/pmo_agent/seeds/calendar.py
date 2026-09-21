"""The fictional calendar — the projection of *where the time went* in the world simulation.

What makes it different from the other two tools: **it holds both past and future.**

  past meetings   → answer "why did nothing move over those two weeks"
  future meetings → compute "how much time is left" (the input to capacity.py)

Read-only data — nothing here creates or edits anyone's events.

Run:
  python -m pmo_agent.seeds.calendar            write data/calendar_state.json
  python -m pmo_agent.seeds.calendar --print    summary only, save nothing
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import availability as av
from pmo_agent.adapters.memory_calendar import STORE
from pmo_agent.seeds import world as world_mod

HORIZON = world_mod.FWD_DAYS


def build(today: dt.date | None = None, seed_value: int = 20260922) -> dict:
    return world_mod.to_calendar(world_mod.simulate(today, seed_value))


def write(path: str | None = None, today: dt.date | None = None) -> dict:
    data = build(today)
    target = path or STORE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    return {"path": target, "events": len(data["events"]), "planted": len(data["planted"])}


def describe(data: dict, today: dt.date) -> dict:
    avail = av.from_events(data["events"])
    people = sorted({e["attendee"] for e in data["events"]})
    past = [e for e in data["events"] if e["date"] < today.isoformat()]
    return {
        "events": len(data["events"]),
        "past/future": f"{len(past)} / {len(data['events']) - len(past)}",
        "window": f"{data['horizon_days']} business days ahead",
        "meeting_load": [av.meeting_load(avail, p, today, 10) for p in people],
    }


if __name__ == "__main__":
    today = dt.date.today()
    data = build(today)
    print(json.dumps(describe(data, today), ensure_ascii=False, indent=1))
    if "--print" not in sys.argv:
        result = write(today=today)
        print(f"\nsaved: {result['path']}  ({result['events']} events)")
        print("use: with CALENDAR_BACKEND=memory, capacity reads this calendar.")
