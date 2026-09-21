"""The layer that lines the board up against the code — to find what neither shows alone.

Jira holds the status a person wrote down; GitHub holds what actually happened.
They should agree. Where they diverge, that is the signal:

  · the ticket is in progress but there is no code activity  → stalled, and nobody knows
  · the ticket is still to do but commits already exist       → the status lags reality
  · the ticket is done but a pull request is still open       → closed too early
  · a pull request has been waiting days for review           → blocked on a person
    (the same shape of problem as capacity)

This layer only calculates. The model quotes the result; writes go through the approval gate.
Task-to-commit links come from linking.py, which does not need a key convention. If a team
does use keys they are honoured; if not, the links are inferred and declared as such.
"""

from __future__ import annotations

import datetime as _dt
import re

from pmo_agent import linking, schedule

KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")
STALE_DAYS = 5  # in progress with no commit for longer than this counts as stalled
REVIEW_WAIT_DAYS = 2  # a pull request waiting longer than this is a bottleneck


def keys_in(text: str) -> set:
    """Pull task keys out of a string (re-exported from linking.py for existing callers)."""
    return linking.keys_in(text)


def link(tasks: dict, commits: list, pulls: list, people: dict | None = None) -> dict:
    """{task key: {commits, pulls, links}} — linking.py does the joining.

    This used to look for a ticket key in the commit message and nothing else. Real
    repositories far more often have no key at all, so it joined nothing — an
    integration tool that presupposed the integration. Now a key is used when it is
    there, and author, timing, vocabulary and path are used when it is not.
    """
    return linking.link(tasks, commits, pulls, people)


def _days(a: str, today: _dt.date) -> int | None:
    """ISO date string → days elapsed until today (calendar days)."""
    if not a:
        return None
    try:
        return (today - _dt.date.fromisoformat(a[:10])).days
    except ValueError:
        return None


def mismatches(tasks: dict, linked: dict, today: _dt.date) -> list:
    """Tasks where the board status and the code activity disagree, with the evidence."""
    out = []
    for k, t in tasks.items():
        cs, ps = linked.get(k, {}).get("commits", []), linked.get(k, {}).get("pulls", [])
        last = max((c["date"] for c in cs), default="")
        idle = _days(last, today)
        open_prs = [p for p in ps if p["state"] == "open"]
        # "Not done and not still To Do." The alias table is schedule's, so a site
        # reporting its statuses in another language is handled in one place.
        in_progress = (
            not t.is_done
            and bool((t.status or "").strip())
            and not schedule.status_alike(t.status, "To Do")
        )

        if t.is_done and open_prs:
            out.append(
                _m(
                    k,
                    t,
                    "done_with_open_pr",
                    f"closed as done while PR #{open_prs[0]['number']} is still open",
                    [p["url"] for p in open_prs],
                    number=open_prs[0]["number"],
                )
            )
        elif in_progress and not cs:
            out.append(
                _m(k, t, "no_code_activity", "in progress with no linked commits at all", [])
            )
        elif in_progress and idle is not None and idle >= STALE_DAYS:
            out.append(
                _m(
                    k,
                    t,
                    "stalled",
                    f"in progress, but the last commit was {idle} days ago ({last})",
                    [c["url"] for c in cs[:2]],
                    idle_days=idle,
                    last=last,
                    status=t.status,
                )
            )
        elif not in_progress and not t.is_done and cs:
            out.append(
                _m(
                    k,
                    t,
                    "undeclared_progress",
                    f"the board says '{t.status}' but there are {len(cs)} commits (last {last})",
                    [c["url"] for c in cs[:2]],
                    commits=len(cs),
                    last=last,
                    status=t.status,
                )
            )

        for p in open_prs:
            wait = _days(p["updated"], today)
            if not p["draft"] and wait is not None and wait >= REVIEW_WAIT_DAYS:
                out.append(
                    _m(
                        k,
                        t,
                        "review_waiting",
                        f"PR #{p['number']} has waited {wait} days for review"
                        + (
                            f" (reviewers: {', '.join(p['reviewers'])})"
                            if p["reviewers"]
                            else " (no reviewer assigned)"
                        ),
                        [p["url"]],
                        number=p["number"],
                        waited=wait,
                        reviewers=list(p["reviewers"]),
                    )
                )
    order = {
        "done_with_open_pr": 0,
        "stalled": 1,
        "review_waiting": 2,
        "no_code_activity": 3,
        "undeclared_progress": 4,
    }
    out.sort(key=lambda r: (order.get(r["kind"], 9), r["key"]))
    return out


def _m(key, t, kind, detail, evidence, **facts):
    """One mismatch. `detail` is the English sentence; `facts` is what it was built from.

    Both, because they are for different readers. A person wants the sentence; anything
    that has to render it differently — another language, a chart, a different medium —
    needs the numbers, and pulling them back out of the prose is how that goes wrong.
    """
    return {
        "key": key,
        "summary": t.summary,
        "assignee": t.assignee,
        "status": t.status,
        "kind": kind,
        "detail": detail,
        "facts": facts,
        "evidence": evidence,
    }


def merge_identities(commits: list) -> dict:
    """Do not count one person twice.

    When a commit email is not tied to a GitHub account the login comes back empty and
    only the git name remains, which once split a single person across two identities
    and dragged a concentration figure down to 0.71. So email decides who is who, and
    the login, when there is one, decides the display name.
    """
    groups: dict[str, dict] = {}
    for c in commits:
        gid = c.get("email") or c.get("login") or c.get("author") or "?"
        g = groups.setdefault(gid, {"commits": 0, "login": None, "names": set()})
        g["commits"] += 1
        if c.get("login"):
            g["login"] = c["login"]
        if c.get("name"):
            g["names"].add(c["name"])
    out: dict[str, dict] = {}
    for g in groups.values():
        label = g["login"] or (sorted(g["names"])[0] if g["names"] else "?")
        row = out.setdefault(label, {"author": label, "commits": 0, "aliases": set()})
        row["commits"] += g["commits"]
        row["aliases"] |= g["names"] - {label}
    for row in out.values():
        row["aliases"] = sorted(row["aliases"])
    return out


def team_activity(snapshot: dict, today: _dt.date, days: int = 14) -> dict:
    """Repository-level signals. These hold up even without a task key convention."""
    commits = [c for c in snapshot.get("commits", []) if (_days(c["date"], today) or 999) <= days]
    merged = merge_identities(commits)
    by = {k: v["commits"] for k, v in merged.items()}
    total = sum(by.values())
    top = max(by.values()) if by else 0
    pulls = snapshot.get("pulls", [])
    open_prs = [p for p in pulls if p["state"] == "open"]
    stale_prs = [
        p
        for p in open_prs
        if not p["draft"] and (_days(p["updated"], today) or 0) >= REVIEW_WAIT_DAYS
    ]
    last = max((c["date"] for c in snapshot.get("commits", [])), default="")

    notes = []
    if total and len(by) == 1:
        notes.append(
            f"all {total} commits in the last {days} days came from one person, {next(iter(by))}"
        )
    elif total and top / total >= 0.8:
        who = max(by, key=lambda name: by[name])
        notes.append(
            f"{round(top / total * 100)}% of commits in the last {days} days"
            f" came from one person, {who}"
        )
    if not pulls:
        notes.append("there is not a single pull request — no review process is running yet")
    if stale_prs:
        notes.append(
            f"{len(stale_prs)} pull requests have waited more than"
            f" {REVIEW_WAIT_DAYS} days for review"
        )
    gap = _days(last, today)
    if gap is not None and gap >= STALE_DAYS:
        notes.append(f"the last commit was {gap} days ago ({last})")
    if not total:
        notes.append(f"no commits at all in the last {days} days")

    return {
        "window_days": days,
        "commits": total,
        "contributors": sorted(merged.values(), key=lambda r: -r["commits"]),
        "concentration": round(top / total, 2) if total else 0.0,
        "open_prs": len(open_prs),
        "stale_prs": len(stale_prs),
        "branches": len(snapshot.get("branches", [])),
        "last_commit": last,
        "notes": notes,
    }


def summary(
    tasks: dict,
    snapshot: dict,
    today: _dt.date | None = None,
    days: int = 14,
    assist=None,
) -> dict:
    """One bundle that the tool layer and the report use as-is.

    Pass `assist` and only the links the rules could not settle go to the model
    (see link_assist.assistant()).
    """
    today = today or _dt.date.today()
    linked = linking.link(
        tasks,
        snapshot.get("commits", []),
        snapshot.get("pulls", []),
        snapshot.get("people"),
        assist=assist,
    )
    quality = linking.quality(linked)
    covered = quality["linked_tasks"]
    in_use = covered > 0

    # Say how the links were made. Inferred links are estimates and carry a confidence.
    # When nothing could be linked, say "no evidence", not "no activity".
    if not in_use:
        note = (
            "No commit or pull request could be tied to a task, so the per-task comparison "
            "was skipped — that is an absence of evidence, not an absence of work."
        )
    elif quality["by_model"]:
        # If model-decided links are in the mix, say so. They are less precise than rules.
        note = (
            f"{quality['by_model']} of {quality['total']} links were beyond the rules and "
            f"were decided by the model ({quality['inferred']} inferred by rule, mean "
            f"confidence {quality['mean_confidence']}). Model calls can be wrong — check them."
        )
    elif quality["inferred"] > quality["by_key"]:
        # Even when some links came from keys, say so if most were inferred. This note
        # used to vanish the moment a single key showed up — 54 of 58 were inferred and
        # the whole thing read as confirmed.
        note = (
            f"{quality['inferred']} of {quality['total']} links had no task key in the commit "
            f"and were inferred from author, timing, vocabulary and path (mean confidence "
            f"{quality['mean_confidence']}). The weak ones need checking."
        )
    else:
        note = None

    return schedule.iso(
        {
            "repo": snapshot.get("repo"),
            "today": today,
            "linked_tasks": covered,
            "total_tasks": len(tasks),
            "key_convention_in_use": quality["by_key_convention"],
            "link_quality": quality,
            "mismatches": mismatches(tasks, linked, today) if in_use else [],
            "note": note,
            "team": team_activity(snapshot, today, days),
        }
    )
