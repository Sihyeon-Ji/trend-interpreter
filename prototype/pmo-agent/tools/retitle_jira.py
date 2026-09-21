"""Bring an already-seeded Jira project in line with the current world.

The sandbox was seeded before the demo data moved to English, so it still holds
the old summaries. Re-running the seed would create a second set of issues, so
this updates the existing ones in place: the keys stay put, only the summary and
the owner label change.

It matches by position, not by text. `world._tasks()` is deterministic, so
ECHO-1 on the board is the first task the world generates, whatever language the
titles happen to be in.

Status names are not touched. Those come from the Jira project's workflow (which
is in the site's own language), and `schedule.STATUS_ALIASES` already bridges
them — renaming a workflow status is a Jira admin job, not ours.

Run:
  python tools/retitle_jira.py             show what would change (dry run)
  python tools/retitle_jira.py --approve   apply it
"""

from __future__ import annotations

import sys

from pmo_agent import schedule
from pmo_agent.adapters.jira import Jira, WriteBlocked
from pmo_agent.seeds import world as world_mod


def plan(j: Jira) -> list:
    """[(key, old summary, new summary, new owner label)] for everything that differs."""
    world = world_mod.simulate()
    board = world_mod.to_board(world, project=j.project)
    wanted = {i["key"]: i["fields"] for i in board["issues"]}

    rows = []
    for issue in j.search(f"project = {j.project} ORDER BY key ASC", limit=200):
        key = issue["key"]
        target = wanted.get(key)
        if not target:
            continue
        old = (issue["fields"].get("summary") or "").strip()
        new = target["summary"]
        had = list(issue["fields"].get("labels") or [])
        # Drop every owner-* label, stale ones included, before adding the current owner.
        # Leave one behind and owner_label() may well read that one instead.
        keep = [x for x in had if not x.startswith(schedule.OWNER_PREFIX)]
        want = schedule.owner_tag(schedule.owner_label(target))
        labels = [*keep, want] if want else keep
        if old != new or sorted(labels) != sorted(had):
            rows.append((key, old, new, labels))
    return rows


def main(argv: list) -> int:
    j = Jira()
    rows = plan(j)
    print(f"target: {j.site} / project {j.project}")
    print(f"{len(rows)} issues differ from the current world\n")
    for key, old, new, _labels in rows[:8]:
        print(f"  {key:<8} {old[:38]:<38} → {new[:38]}")
    if len(rows) > 8:
        print(f"  … and {len(rows) - 8} more")
    if not rows:
        print("Nothing to do — the board already matches.")
        return 0

    if "--approve" not in argv:
        print("\nThis is a preview. Add --approve to apply it.")
        return 0

    print("\napplying…")
    done = failed = 0
    for key, _old, new, labels in rows:
        try:
            j.set_fields(key, {"summary": new, "labels": labels}, approve=True)
            done += 1
        except WriteBlocked as e:
            print(f"  write blocked: {e}")
            return 1
        except Exception as e:
            failed += 1
            print(f"  {key}: {str(e)[:100]}")
    print(f"\nupdated {done}, failed {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
