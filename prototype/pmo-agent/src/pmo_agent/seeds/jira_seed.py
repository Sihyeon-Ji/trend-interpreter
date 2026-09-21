"""Create the seed in a real Jira sandbox.

It pushes the 40 issues the board seed built straight into Jira — summary, due date, story
points, status and Blocks dependencies.

Assignees: the sandbox has exactly one real account, so four fictional people cannot be
           assigned. They ride on an `owner-<name>` label instead, which
           schedule.owner_label() reads back as the owner.

Status: the seed names statuses in English. What the target project calls them is its
        own business, so the transition is looked up on the issue itself.

Safety: writes must pass WRITE_ALLOWLIST, and this script creates nothing without --approve.

Run:
  python -m pmo_agent.seeds.jira_seed                       preview only (dry run)
  python -m pmo_agent.seeds.jira_seed --approve             create for real
  python -m pmo_agent.seeds.jira_seed --approve --limit 3   the first 3 only
  python -m pmo_agent.seeds.jira_seed --approve --from 3    skip the first 3 and carry on
"""

from __future__ import annotations

import datetime as dt
import sys

from pmo_agent import schedule
from pmo_agent.adapters.jira import Jira, WriteBlocked
from pmo_agent.seeds import board as seed

# The seed names its statuses in English. What the target site calls them is the site's
# own business — the name is fixed when the project is created, in whatever language
# that was — so nothing is hardcoded here. schedule.status_alike() matches the two, and
# the transition is looked up on the issue, the only place that knows what it offers.
SEED_STATUS = {"In Review": "In Progress"}  # the board has no review column


def _wanted(name: str) -> str:
    """The status the seed wants, in the seed's own words."""
    name = (name or "").strip() or "To Do"
    return SEED_STATUS.get(name, name)


def _site_name(jira: Jira, key: str, wanted: str) -> str:
    """What this project calls the status the seed asked for.

    A site set up in another language offers its own wording where the seed says
    In Progress. Asking the issue what transitions it has is the only reliable way to
    find out, and it keeps the seed working whatever language the project was made in.
    """
    for t in jira.transitions(key):
        name = (t.get("to") or {}).get("name") or t.get("name") or ""
        if schedule.status_alike(name, wanted):
            return name
    return wanted


def plan(today: dt.date | None = None, limit: int = 0) -> list:
    """The issues to create, arranged as Jira fields."""
    issues = seed.build(today or dt.date.today())
    if limit:
        keys = {i["key"] for i in issues[:limit]}
        issues = issues[:limit]
        for i in issues:  # drop links that point outside the range
            i["fields"]["issuelinks"] = [
                link
                for link in i["fields"]["issuelinks"]
                if link.get("outwardIssue", {}).get("key") in keys
            ]
    out = []
    for i in issues:
        f = i["fields"]
        out.append(
            {
                "seed_key": i["key"],
                "summary": f["summary"],
                "duedate": f["duedate"],
                "points": f["customfield_10016"],
                "owner": (f.get("assignee") or {}).get("displayName", ""),
                "status": _wanted((f.get("status") or {}).get("name", "")),
                "blocks": [
                    link["outwardIssue"]["key"]
                    for link in f["issuelinks"]
                    if "outwardIssue" in link
                ],
            }
        )
    return out


def create(
    jira: Jira,
    rows: list,
    approve: bool = False,
    pre: dict | None = None,
    link_rows: list | None = None,
) -> dict:
    """Create issues → transition status → link them. Returns seed_key → real Jira key.

    pre: seed_key → real key for issues already created (when continuing a seed).
    link_rows: the rows to link (defaults to the rows created now). When continuing, pass them all.
    """
    mapping, errors = dict(pre or {}), []
    fresh = set()
    for r in rows:
        extra = {"labels": [schedule.owner_tag(r["owner"])] if r["owner"] else []}
        if r["points"]:
            extra["customfield_10016"] = r["points"]
        try:
            res = jira.create_issue(
                r["summary"], duedate=r["duedate"], extra=extra, approve=approve
            )
        except WriteBlocked as e:
            return {"error": f"write blocked: {e}", "created": mapping}
        except Exception as e:
            errors.append({"seed_key": r["seed_key"], "step": "create", "error": str(e)[:200]})
            continue
        if not approve:
            mapping[r["seed_key"]] = "(dry-run)"
            continue
        mapping[r["seed_key"]] = res["key"]
        fresh.add(r["seed_key"])
        if not schedule.status_alike(r["status"], "To Do"):
            try:
                jira.transition(res["key"], _site_name(jira, res["key"], r["status"]), approve=True)
            except Exception as e:
                errors.append(
                    {"seed_key": r["seed_key"], "step": "transition", "error": str(e)[:200]}
                )
    if approve:
        for r in link_rows or rows:
            for b in r["blocks"]:
                # Link only if at least one side was created now — avoids duplicating links
                if (
                    r["seed_key"] in mapping
                    and b in mapping
                    and (r["seed_key"] in fresh or b in fresh)
                ):
                    try:
                        jira.link(mapping[r["seed_key"]], mapping[b], approve=True)
                    except Exception as e:
                        errors.append(
                            {"seed_key": r["seed_key"], "step": "link", "error": str(e)[:200]}
                        )
    return {"created": mapping, "errors": errors}


def main(argv) -> None:
    approve = "--approve" in argv
    limit = 0
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    start = int(argv[argv.index("--from") + 1]) if "--from" in argv else 0
    all_rows = plan(limit=limit)
    # Skip what was already created. The keys map 1:1, so seed_key doubles as the real key.
    pre = {r["seed_key"]: r["seed_key"] for r in all_rows[:start]}
    rows = all_rows[start:]
    j = Jira()
    print(f"target: {j.site} / project {j.project}")
    print(f"{len(rows)} issues to create  (owners recorded as owner-* labels)")
    for r in rows[:5]:
        print(
            f"  {r['seed_key']:>8}  {r['summary'][:34]:<34} {r['status']:<6} "
            f"due {r['duedate']} · {r['points']} points · {r['owner']}"
            + (f" · blocks {','.join(r['blocks'])}" if r["blocks"] else "")
        )
    if len(rows) > 5:
        print(f"  … and {len(rows) - 5} more")
    if not approve:
        print("\nThis is a preview. Add --approve to create them.")
        return
        print("\ncreating…")
    out = create(j, rows, approve=True, pre=pre, link_rows=all_rows)
    if out.get("error"):
        print(" ", out["error"])
        return
    print(f" created {len(out['created']) - len(pre)}, errors {len(out['errors'])}")
    for e in out["errors"][:5]:
        print("  error:", e)


if __name__ == "__main__":
    main(sys.argv[1:])
