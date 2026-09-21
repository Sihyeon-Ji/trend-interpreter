"""The fictional repository — the projection of what was *actually done* in the simulation.

The board is what a person wrote, so it can be wrong; commits and pull requests are the
machine's record of fact. Line the two up and the divergence shows — which is what
signals.py looks for.

A commit exists only on a day that person **really pushed that task** in the world.
On a day a meeting ate, there is no commit. That gap is the evidence behind "why did
nothing move".

Read-only data — this module pushes nothing anywhere.

Run:
  python -m pmo_agent.seeds.repo            write data/repo_state.json
  python -m pmo_agent.seeds.repo --print    summary only, save nothing
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent.adapters.memory_repo import STORE
from pmo_agent.seeds import world as world_mod

REPO = "echo-team/echo-app"
LOGIN = {name: login for name, login, _email in world_mod.PEOPLE}
EMAIL = {name: email for name, _login, email in world_mod.PEOPLE}


def build(today: dt.date | None = None, seed_value: int = 20260922) -> dict:
    """The repository snapshot. `planted` also carries **what only shows against the board**.

    review_waiting is visible from the repository alone, but undeclared_progress and
    done_with_open_pr need the board status too. The answer key stays in one place.
    """
    world = world_mod.simulate(today, seed_value)
    board = world_mod.to_board(world)
    data = world_mod.to_repo(world, board, REPO)
    data["planted"] = board["planted"] + data["planted"]
    return data


def write(path: str | None = None, today: dt.date | None = None) -> dict:
    data = build(today)
    target = path or STORE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    return {
        "path": target,
        "commits": len(data["commits"]),
        "pulls": len(data["pulls"]),
        "planted": len(data["planted"]),
    }


def describe(data: dict) -> dict:
    return {
        "repo": data["repo"],
        "commits": len(data["commits"]),
        "PR": len(data["pulls"]),
        "branches": len(data["branches"]),
        "planted": data["planted"],
    }


if __name__ == "__main__":
    data = build()
    print(json.dumps(describe(data), ensure_ascii=False, indent=1))
    if "--print" not in sys.argv:
        result = write()
        print(
            f"\nsaved: {result['path']}  "
            f"({result['commits']} commits · {result['pulls']} PRs · {result['planted']} planted)"
        )
        print("use: with REPO_BACKEND=memory, signals reads this repository.")
