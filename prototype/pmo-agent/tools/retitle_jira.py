"""Bring an already-seeded Jira project in line with the current world.

The sandbox is seeded once and then frozen, while the world regenerates its dates
from today every run. Within a day or two that drift is invisible; after a week the
board says a task is due next Wednesday when the simulation has it three weeks late,
and every explanation built on top reads wrong.

Re-running the seed would create a second set of issues, so this updates the existing
ones in place: the keys stay put, and the summary, the owner label, the due date and the
status are brought back in line.

The status matters for more than tidiness. Run the demo with --approve and it moves a
task to Done; run it again and that step has nothing left to change, so the "what would
this do to the schedule" line comes out as a no-op. Putting the board back is what makes
the demo repeatable.

Status names are still not touched at the project level — those come from the Jira
workflow, in whatever language it was created in, and `schedule.status_alike` bridges
them. This only moves issues between the statuses that already exist.

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
    """[(key, old, new, labels, duedate, status)] for every issue that drifted."""
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
        was_due = (issue["fields"].get("duedate") or "")[:10]
        due = (target.get("duedate") or "")[:10]
        now_status = ((issue["fields"].get("status") or {}).get("name") or "").strip()
        want_status = ((target.get("status") or {}).get("name") or "").strip()
        moved = bool(want_status) and not schedule.status_alike(now_status, want_status)
        if old != new or sorted(labels) != sorted(had) or was_due != due or moved:
            rows.append((key, old, new, labels, due, want_status if moved else ""))
    return rows


def _site_status(j: Jira, key: str, wanted: str) -> str:
    """What this project calls the status the world wants, or "" if it has no such column."""
    for t in j.transitions(key):
        name = (t.get("to") or {}).get("name") or t.get("name") or ""
        if schedule.status_alike(name, wanted):
            return name
    return ""


def main(argv: list) -> int:
    j = Jira()
    rows = plan(j)
    print(f"target: {j.site} / project {j.project}")
    print(f"{len(rows)} issues differ from the current world\n")
    for key, old, new, _labels, due, status in rows[:8]:
        move = f"  → {status}" if status else ""
        print(f"  {key:<8} {old[:30]:<30} → {new[:30]:<30} due {due}{move}")
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
    for key, _old, new, labels, due, status in rows:
        fields: dict = {"summary": new, "labels": labels}
        if due:
            fields["duedate"] = due
        try:
            j.set_fields(key, fields, approve=True)
            if status:
                target = _site_status(j, key, status)
                if target:
                    j.transition(key, target, approve=True)
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
