"""The demo board — the projection of what *people wrote down* in the world simulation.

This used to generate tasks at random. That got as far as "ECHO-5 is stuck" and had no data
at all for "why". Now the world comes first and the board is one cross-section of it.

The board carries **deliberate recording errors** — work that has actually started but still
says To Do, or something closed as done with its pull request open. Finding that divergence
is the agent's job.

SETUP.md 3: every person here is fictional.

Run:
  python -m pmo_agent.seeds.board            write data/seed_state.json
  python -m pmo_agent.seeds.board --print    summary only, save nothing
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import schedule
from pmo_agent.adapters.memory import STORE
from pmo_agent.seeds import world as world_mod

PEOPLE = [name for name, _login, _email in world_mod.PEOPLE]  # fictional people
PHASES = world_mod.PHASES


def build(today: dt.date | None = None, project: str = "ECHO", seed: int = 20260922) -> list:
    """The issue list (shaped like a Jira search() response)."""
    return world_mod.to_board(world_mod.simulate(today, seed), project)["issues"]


def planted(today: dt.date | None = None) -> list:
    """The recording errors planted on the board — the answer key for tests and cases."""
    return world_mod.to_board(world_mod.simulate(today))["planted"]


def write(path: str | None = None, today: dt.date | None = None, project: str = "ECHO") -> dict:
    """Write to the local board file, overwriting whatever is there."""
    issues = build(today, project)
    target = path or STORE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "project": project,
                "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
                "issues": issues,
            },
            handle,
            ensure_ascii=False,
            indent=1,
        )
    return {"path": target, "count": len(issues)}


def describe(issues: list, today: dt.date) -> dict:
    tasks = schedule.from_jira_issues(issues)
    summary = schedule.summary(tasks, today)
    return {
        "tasks": len(issues),
        "owners": sorted({t.assignee for t in tasks.values() if t.assignee}),
        "done": summary["done"],
        "critical_path": len(summary["critical_path"]),
        "at_risk": len(summary["risks"]),
        "planned_finish": summary["planned_finish"],
        "forecast_finish": summary["predicted_finish"],
    }


if __name__ == "__main__":
    today = dt.date.today()
    issues = build(today)
    print(json.dumps(describe(issues, today), ensure_ascii=False, indent=1))
    print("\nplanted recording errors:", json.dumps(planted(today), ensure_ascii=False))
    if "--print" not in sys.argv:
        result = write(today=today)
        print(f"\nsaved: {result['path']} ({result['count']} issues)")
        print("use: with PMO_BACKEND=memory, tools and approve read this board.")
