"""The Gemini function-calling tool layer.
Design rule: the model only picks *what to do* and explains it.
Schedule and delay numbers come from schedule.py (pure Python); anything actually applied goes
through the Jira adapter after approval. Read tools run straight away; write tools return a
dry-run proposal and reach the board only once a person approves."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import time

from pmo_agent import availability as avail_mod
from pmo_agent import (
    capacity,
    cause,
    decide,
    extract,
    familiarity,
    health,
    linking,
    projects,
    reconcile,
    register,
    render,
    rollup,
    schedule,
    signals,
)
from pmo_agent.adapters.jira import Jira
from pmo_agent.env import env
from pmo_agent.ports import Board, Calendar, Repo

# One adapter per project, built once and kept. Keyed by project so a roll-up across
# five boards does not build five clients per question — and so that asking about one
# project can never hand back another one's client.
_boards: dict = {}
_repos: dict = {}
_archives: dict = {}

# An adapter pinned here is used for every project, whatever the configuration says.
# Tests and the offline loop need to hand in a prepared board; before this they reached
# into the module's private globals, which meant the seam was invisible from the outside
# and broke the moment the caching changed shape — as it just did.
_pinned: dict = {}


def pin(**adapters) -> None:
    """Force adapters for every project: `pin(board=fake)`. `pin(board=None)` releases one."""
    for kind, adapter in adapters.items():
        if adapter is None:
            _pinned.pop(kind, None)
        else:
            _pinned[kind] = adapter
    forget_adapters()


def forget_adapters() -> None:
    """Drop everything built so far, so the next call reads the configuration again."""
    _boards.clear()
    _repos.clear()
    _archives.clear()
    global _c
    _c = None
    forget_snapshot()


def _local(name: str, default: str) -> bool:
    return env(name, default).lower() in ("memory", "local", "file")


def jira(project: str = "") -> Board:
    """The PM-tool backend for one project. PMO_BACKEND=memory gives the local board.

    Both adapters return the same shapes, so nothing above here needs to know which is
    in use. An empty `project` means the default one, which is what a single-project
    setup has always meant.
    """
    if "board" in _pinned:
        return _pinned["board"]
    pr = projects.resolve(project)
    if pr.key not in _boards:
        if _local("PMO_BACKEND", "jira"):
            from pmo_agent.adapters.memory import MemoryBoard

            _boards[pr.key] = MemoryBoard(project=pr.key)
        else:
            _boards[pr.key] = Jira(project=pr.key)
    return _boards[pr.key]


def repo(project: str = "") -> Repo:
    """The code-signal backend for one project. REPO_BACKEND=memory gives the local repo.

    Each project names its own repository, because a team running three rarely keeps them
    in one. Pointing them all at the same one would make linking quietly worse: commits
    from another project become plausible candidates and the margin thins.
    """
    if "repo" in _pinned:
        return _pinned["repo"]
    pr = projects.resolve(project)
    if pr.key not in _repos:
        if _local("REPO_BACKEND", "github"):
            from pmo_agent.adapters.memory_repo import MemoryRepo

            _repos[pr.key] = MemoryRepo()
        else:
            from pmo_agent.adapters.github import GitHub

            _repos[pr.key] = GitHub(repo=pr.repo) if pr.repo else GitHub()
    return _repos[pr.key]


_c: Calendar | None = None


def calendar() -> Calendar:
    """The available-time backend. CALENDAR_BACKEND=msgraph reads Graph, else local.

    Local by default, unlike the board and the repository. Those two have one obvious
    live service and a token in .env is enough; a work calendar needs an Azure app
    registration a tenant admin has to approve, so the honest default is the one that
    works. Defaulting to Graph meant an unconfigured run lost the "where did the time
    go" half of every explanation — correctly labelled, and still the thinner answer.
    """
    if "calendar" in _pinned:
        return _pinned["calendar"]
    global _c
    if _c is None:
        if env("CALENDAR_BACKEND", "memory").lower() in ("memory", "local", "file"):
            from pmo_agent.adapters.memory_calendar import MemoryCalendar

            _c = MemoryCalendar()
        else:
            from pmo_agent.adapters.ms_calendar import MSCalendar

            _c = MSCalendar()
    return _c


def _availability() -> dict | None:
    """The availability table when a calendar is connected, None (everyone free) when not.

    A failed calendar connection must not stop the whole schedule calculation — without one,
    it simply calculates without one.
    """
    try:
        return avail_mod.from_busy_hours(calendar().busy_hours(30))
    except Exception:
        return None


def notes(project: str = ""):
    """The meeting-notes archive for one project. NOTES_BACKEND=notion reads Notion.

    The only tool that holds sentences. A missing archive costs the explanation its
    "what was decided" half and nothing else, so it is never fatal.
    """
    if "notes" in _pinned:
        return _pinned["notes"]
    pr = projects.resolve(project)
    if pr.key not in _archives:
        if env("NOTES_BACKEND", "memory").lower() == "notion":
            from pmo_agent.adapters.notion import NotionNotes

            _archives[pr.key] = NotionNotes(database=pr.notes) if pr.notes else NotionNotes()
        else:
            from pmo_agent.adapters.memory_notes import MemoryNotes

            _archives[pr.key] = MemoryNotes()
    return _archives[pr.key]


def _past_notes(days: int = 45, project: str = "") -> tuple:
    """What was written down behind us, and why there is none when there is none.

    Losing the notes costs an explanation its "what was decided" half. Losing them
    *quietly* is worse: the answer simply comes back thinner and nothing says so. A
    backend that is configured but empty looks exactly like one that is not configured,
    until someone checks — so the reason travels with the result.
    """
    backend = env("NOTES_BACKEND", "memory").lower()
    try:
        start = schedule.add_workdays(dt.date.today(), -int(days))
        found = notes(project).notes(days=int(days) * 2, start=start)
    except Exception as e:
        return [], f"{backend} archive could not be read: {str(e)[:120]}"
    if found:
        return found, ""
    return [], f"the {backend} archive holds no notes in this window"


def _past_events(days: int = 45) -> list:
    """The calendar behind us. Explaining a stall needs where the time already went,
    which is the opposite of what capacity asks the calendar for."""
    try:
        start = schedule.add_workdays(dt.date.today(), -int(days))
        return calendar().events(days=int(days) * 2, start=start)
    except Exception:
        return []


def _today(today: str = "") -> dt.date:
    """A date string from a tool argument → date. Empty means today; an invented date dies here."""
    return schedule.parse_date(today) or dt.date.today()


def _fetch(jql: str = "", limit: int = 200, project: str = "") -> dict:
    """Read one project's Jira issues and convert to {key: Task}.

    The shared entry point for the schedule functions — tests swap out this one place.
    """
    board = jira(project)
    return schedule.from_jira_issues(board.search(jql or f"project = {board.project}", limit=limit))


# ---- the implementations (these names are what Gemini sees) ----
def list_tasks(status: str = "", assignee: str = "", limit: int = 50) -> dict:
    jql = [f"project = {jira().project}"]
    if status:
        jql.append(f'status = "{status}"')
    if assignee:
        jql.append(f'assignee = "{assignee}"')
    issues = jira().search(" AND ".join(jql) + " ORDER BY duedate ASC", limit=limit)
    deps = schedule.from_jira_issues(issues)
    return {
        "count": len(issues),
        "tasks": [
            {
                "key": i["key"],
                "summary": i["fields"]["summary"],
                "status": (i["fields"].get("status") or {}).get("name"),
                "assignee": ((i["fields"].get("assignee") or {}) or {}).get("displayName"),
                "duedate": i["fields"].get("duedate"),
                "points": i["fields"].get("customfield_10016"),
                "deps": deps[i["key"]].deps if i["key"] in deps else [],
            }
            for i in issues
        ],
    }


def get_task(key: str) -> dict:
    i = jira().issue(key)
    f = i["fields"]
    return {
        "key": i["key"],
        "summary": f["summary"],
        "status": (f.get("status") or {}).get("name"),
        "assignee": ((f.get("assignee") or {}) or {}).get("displayName"),
        "duedate": f.get("duedate"),
        "links": [
            {
                "type": link["type"]["name"],
                "inward": (link.get("inwardIssue") or {}).get("key"),
                "outward": (link.get("outwardIssue") or {}).get("key"),
            }
            for link in (f.get("issuelinks") or [])
        ],
    }


def analyze_schedule(today: str = "", limit: int = 200, project: str = "") -> dict:
    """The whole schedule — planned and forecast finish, critical path, tasks at risk.

    Every number is computed by schedule.py.
    """
    tasks = _fetch(limit=limit, project=project)
    if not tasks:
        return {"error": "no tasks. Check the project key and the seed data."}
    try:
        return schedule.summary(tasks, _today(today))
    except schedule.CycleError as e:
        return {
            "error": str(e),
            "hint": "The Blocks links form a cycle. Fix them before computing a schedule.",
        }


def simulate_delay(key: str, days: float, today: str = "") -> dict:
    """Simulate "if this task slips N business days, what moves and by how much".

    Whatever slack absorbs does not propagate.
    """
    tasks = _fetch()
    if key not in tasks:
        return {"error": f"cannot find {key}.", "available": sorted(tasks)[:20]}
    try:
        return schedule.iso(schedule.propagate(tasks, key, float(days), _today(today)))
    except schedule.CycleError as e:
        return {"error": str(e)}


def analyze_capacity(today: str = "", limit: int = 200, project: str = "") -> dict:
    """The achievable finish, with owner capacity applied, next to the dependency-only forecast.
    One person cannot run several tasks at once, so this is usually later — and that is reality."""
    tasks = _fetch(limit=limit, project=project)
    if not tasks:
        return {"error": "no tasks."}
    try:
        return capacity.summary(tasks, _today(today), availability=_availability())
    except schedule.CycleError as e:
        return {"error": str(e)}


def _handover_check(tasks: dict, project: str = ""):
    """Who could plausibly pick up whose work, from the repository's own history.

    A move is only worth proposing if the person could actually take it. The repository
    knows who has committed where, so that judgement costs nothing extra — but it needs
    file paths, which a GitHub read only has with REPO_FILES on. Returns (check, why not).
    """
    try:
        snapshot = _snapshot(100, project=project)
    except Exception as e:
        return None, f"the repository could not be read ({str(e)[:80]})"
    linked = linking.link(
        tasks, snapshot.get("commits", []), snapshot.get("pulls", []), snapshot.get("people")
    )
    check = familiarity.checker(linked, snapshot.get("commits", []))
    if check:
        return check, ""
    if not _with_files():
        return None, "no file paths in the commits — set REPO_FILES=on to vet the handovers"
    return None, "no commit history to judge a handover by"


def suggest_rebalance(today: str = "", max_moves: int = 3, project: str = "") -> dict:
    """Work out who a bottleneck owner's task could move to, and how many days that saves.

    A move is only offered to someone the repository shows has worked in that area. A
    proposal only; nothing is applied.
    """
    tasks = _fetch(project=project)
    if not tasks:
        return {"error": "no tasks."}
    check, why = _handover_check(tasks, project=project)
    try:
        out = capacity.rebalance(tasks, _today(today), max_moves=int(max_moves), can_take=check)
    except schedule.CycleError as e:
        return {"error": str(e)}
    out["handovers_vetted"] = bool(check)
    # Saying a move was not vetted matters as much as vetting it. "Move this to Leo" reads
    # like advice either way; only one of them has been checked against what Leo has done.
    out["handover_note"] = why
    return schedule.iso(out)


def _with_files() -> bool:
    """Whether to spend an API call per commit on the paths it touched.

    Worth about a quarter more links and a good deal more confidence, because the path is
    what separates two tasks the same person has open. It also costs a call per commit,
    which on a real repository is the slowest thing the agent does — so the caller decides.
    The local backend has the paths already and ignores this entirely.
    """
    return env("REPO_FILES", "off").strip().lower() in ("on", "true", "1", "yes")


SNAPSHOT_TTL = 60  # seconds; override with REPO_SNAPSHOT_TTL
_snap: dict = {}


def _ttl() -> float:
    try:
        return float(env("REPO_SNAPSHOT_TTL", str(SNAPSHOT_TTL)))
    except ValueError:
        return float(SNAPSHOT_TTL)


def forget_snapshot() -> None:
    """Drop the remembered reading. For tests, and for anyone who wants the next one fresh."""
    _snap.clear()


def _snapshot(limit: int = 100, project: str = "") -> dict:
    """The repository as it was a moment ago — one reading, briefly remembered.

    Not only for speed, though it is that: a live demo took three snapshots and paid for
    all three. The better reason is consistency. "The board disagrees with the code" and
    "why did this task stop" are two halves of one answer, and taking a separate reading
    for each means the halves can describe different repositories — a commit that lands
    between them appears in one and not the other, and nothing says so.

    Kept for a minute, not for the process's life. Long enough that one question is
    answered from one reading; short enough that a dashboard left open still moves.
    Set REPO_SNAPSHOT_TTL=0 to turn it off.
    """
    key = (projects.resolve(project).key, limit, _with_files())
    ttl = _ttl()
    found = _snap.get(key)
    if found and ttl > 0 and (time.monotonic() - found[0]) < ttl:
        return found[1]
    got = repo(project).snapshot(limit, with_files=_with_files())
    _snap[key] = (time.monotonic(), got)
    return got


def _link_assist():
    """Turn on model assistance only when LINK_ASSIST=on.

    Off by default — a model call costs money and latency, and is less precise than the rules.
    Whether to turn it on is the caller's decision.
    """
    if env("LINK_ASSIST", "off").strip().lower() not in ("on", "true", "1", "yes"):
        return None
    from pmo_agent import link_assist

    return link_assist.assistant()


def analyze_signals(today: str = "", days: int = 14, project: str = "") -> dict:
    """Line the board status up against real code activity and find where they disagree.
    "Ticket in progress with no commits", "done with an open PR", "PR waiting on review", and so on.
    None of it is visible from the board alone, so use it when progress looks doubtful."""
    tasks = _fetch(project=project)
    if not tasks:
        return {"error": "no tasks."}
    try:
        return signals.summary(
            tasks,
            _snapshot(100, project=project),
            _today(today),
            days=int(days),
            assist=_link_assist(),
        )
    except Exception as e:
        return {
            "error": f"could not read the repository: {str(e)[:200]}",
            "hint": (
                "Check GITHUB_REPO and the gh login, or use REPO_BACKEND=memory for the local repo."
            ),
        }


def explain_stall(key: str = "", today: str = "", project: str = "") -> dict:
    """Why a task stopped, reconstructed from the board, the repository and the calendar.

    With no key, it reports the tasks that have been silent longest. This is the question
    "why", which no single tool can answer — and where there is no evidence it says so
    rather than naming a cause.
    """
    tasks = _fetch(project=project)
    if not tasks:
        return {"error": "no tasks."}
    try:
        snapshot = _snapshot(100, project=project)
    except Exception as e:
        return {
            "error": f"could not read the repository: {str(e)[:200]}",
            "hint": (
                "Check GITHUB_REPO and the gh login, or use REPO_BACKEND=memory for the local repo."
            ),
        }
    events, when = _past_events(), _today(today)
    written, why = _past_notes(project=project)
    if key:
        return cause.explain(key, tasks, snapshot, events, when, notes=written)

    rows = cause.worst(tasks, snapshot, events, when, notes=written)
    # The longest silence is not always the one a PM asks about. Whatever the schedule
    # calls the worst risk belongs in the answer too, even if it never started — that is
    # usually the headline, and it is the one with a story behind it.
    risks = schedule.risks(tasks, when)
    if risks and risks[0]["key"] not in [r["key"] for r in rows]:
        top = cause.explain(risks[0]["key"], tasks, snapshot, events, when, notes=written)
        if "error" not in top:
            rows.insert(0, top)
    return {
        "worst": rows,
        "calendar_read": bool(events),
        "notes_read": bool(written),
        "notes_backend": env("NOTES_BACKEND", "memory").lower(),
        "notes_note": why,
    }


def reconcile_notes(today: str = "", days: int = 0, project: str = "") -> dict:
    """What the meeting notes say that the board does not have yet, as proposals.

    The job this replaces: reading minutes, working out which ticket each paragraph is
    about, opening the board and editing only the ones that differ. Notes that agree with
    the board produce nothing, which is the point — twenty notes are usually two changes.

    Nothing is applied. A note carries no ticket key, so every link is inferred, and one
    that is not clear enough comes back as a question instead.
    """
    tasks = _fetch(project=project)
    if not tasks:
        return {"error": "no tasks."}
    written, why = _past_notes(days=max(int(days) or reconcile.WINDOW, 1), project=project)
    if not written:
        return {"today": _today(today).isoformat(), "changes": [], "proposals": [], "note": why}
    return reconcile.review(written, tasks, _today(today), days=int(days) or reconcile.WINDOW)


def project_health(today: str = "", project: str = "", days: int = 0) -> dict:
    """How an operations project is doing — the numbers that replace a finish date.

    A queue does not finish, so asking when it will is a category error. What matters is
    whether as much is closing as arriving, how old the waiting ones are, and whether the
    same fault keeps coming back under new ticket numbers.
    """
    pr = projects.resolve(project)
    board = jira(project)
    issues = board.search(f"project = {board.project}", limit=500)
    out = health.summary(issues, _today(today), days=int(days) or health.WINDOW)
    out["project"] = pr.key
    out["kind"] = pr.kind
    return out


def rollup_projects(today: str = "") -> dict:
    """Every project on one line, worst first — what is in trouble, why, and when it clears.

    No new calculation: the same answers the per-project views give, arranged. A delivery
    project is judged on a date; work that runs has no date and gets the numbers that do
    mean something for it. A project that cannot be read is shown as unknown rather than
    left out, because a missing row reads as one with nothing wrong.
    """
    when = _today(today)
    rows = []
    for pr in projects.all():
        try:
            if pr.is_run:
                rows.append(rollup.run_row(pr, project_health(today=today, project=pr.key)))
                continue
            tasks = _fetch(project=pr.key)
            if not tasks:
                rows.append(rollup.error_row(pr, "the board has no tasks"))
                continue
            sched = schedule.summary(tasks, when)
            cap = capacity.summary(tasks, when, availability=_availability())
            stalls = {}
            try:
                stalls = explain_stall(today=today, project=pr.key)
            except Exception:
                pass  # the "why" is the nice-to-have; the date is the point
            rows.append(rollup.build_row(pr, sched, cap, stalls))
        except Exception as e:
            rows.append(rollup.error_row(pr, str(e)[:120]))
    return rollup.summary(rows, when)


def weigh_options(key: str, today: str = "", slip: float = 5, project: str = "") -> dict:
    """The choices for one task at risk, each costed — accept, hand over, or cut.

    "Why did this stop" is a diagnosis. This is the decision: what the options are, what
    each costs on the finish date, whose work moves, and — for a handover — the day after
    which it stops being worth doing.

    Deliberately unranked. Cutting scope always wins on days and is usually the wrong
    answer, so the agent lays the table out and a person picks.
    """
    tasks = _fetch(project=project)
    if not tasks:
        return {"error": "no tasks."}
    check, _why = _handover_check(tasks, project=project)
    return decide.options(
        tasks,
        key,
        _today(today),
        slip=float(slip),
        availability=_availability(),
        can_take=check,
    )


def closing_decisions(today: str = "", project: str = "") -> dict:
    """Decisions that get more expensive to make later, soonest to close first.

    A delivery lead is rarely short of information and often short of knowing that a door
    is closing. "We could still have moved it in September" is a sentence teams say every
    October, and it is avoidable arithmetic.
    """
    tasks = _fetch(project=project)
    if not tasks:
        return {"error": "no tasks."}
    return decide.deadlines(tasks, _today(today), availability=_availability())


def track_issues(today: str = "", project: str = "", save: bool = True) -> dict:
    """File this run's findings in the issue register and report what is open.

    The agent has always found these things and never remembered any of them. Keeping
    them answers three questions it could not before: has this happened before, what has
    it cost in total, and which are still open.

    An issue that stops being reported is marked resolved rather than deleted — "this
    happened and then stopped" is the fact worth keeping. One nobody has looked at for a
    fortnight says *lapsed*, because that is a different thing from fixed.
    """
    pr = projects.resolve(project)
    when = _today(today)
    tasks = _fetch(project=project)
    if not tasks:
        return {"error": "no tasks."}

    findings, missed = [], []
    try:
        stalls = explain_stall(today=today, project=project)
        findings += register.from_stalls(stalls.get("worst") or [])
    except Exception as e:
        missed.append(f"stalls: {str(e)[:90]}")
    try:
        found = signals.summary(tasks, _snapshot(100, project=project), when)
        findings += register.from_signals(found.get("mismatches") or [])
    except Exception as e:
        missed.append(f"repository: {str(e)[:90]}")

    for row in findings:
        row["affects"] = register.affected(row.get("key", ""), tasks)

    entries = register.update(findings, pr.key, when, register.load())
    if save:
        register.save(entries)
    out = register.summary(entries, pr.key, when)
    # What could not be read this run matters: an issue absent because the repository was
    # unreachable would otherwise read as one that got fixed.
    out["unread"] = missed
    if missed:
        out["note"] += (
            f" {len(missed)} source(s) could not be read this run, so anything only they "
            f"would have reported is missing rather than closed."
        )
    return out


def who_to_tell(key: str, project: str = "") -> dict:
    """Who has a claim on hearing about this task, and a draft to send them.

    Not a guess about who cares — a walk of the dependency graph the board already holds.
    Somebody whose own work cannot start until this moves has a claim on being told.

    The agent does not send anything. It names the people and writes the draft; a person
    presses send, the same way a person presses apply.
    """
    tasks = _fetch(project=project)
    if key not in tasks:
        return {"error": f"unknown task: {key}", "available": sorted(tasks)[:20]}
    task = tasks[key]
    people = register.affected(key, tasks)
    why = ""
    try:
        told = explain_stall(key=key, project=project)
        why = told.get("note", "")
    except Exception:
        pass
    return {
        "key": key,
        "summary": task.summary,
        "owner": task.assignee,
        "tell": people,
        "team": task.team,
        "crosses_teams": sorted(
            {p["team"] for p in people if p.get("other_team") and p.get("team")}
        ),
        "why": why,
        "draft": _draft(key, task, people, why),
        "sent": False,  # this agent does not send. A person does
    }


def _draft(key: str, task, people: list, why: str) -> str:
    """The message a person would have written, so they can edit rather than compose."""
    if not people:
        return ""
    names = ", ".join(p["who"] for p in people)
    waiting = "; ".join(f"{p['task']} {p['summary']}" for p in people[:3])
    body = f"{names} — {key} ({task.summary}) is holding up work of yours: {waiting}."
    # Somebody on the same team hears about this at standup. Somebody on another team
    # finds out in three weeks, when their own work will not start.
    crossing = sorted({p["team"] for p in people if p.get("other_team") and p.get("team")})
    if crossing:
        body += f" This crosses into {', '.join(crossing)}, so it will not come up in our standup."
    return f"{body} {why}".strip() if why else body


def report_template(path: str) -> dict:
    """An existing weekly report → the template it was written to.

    Every company already has a format, and it is never the one a tool ships with. Hand
    it last week's report and it works out the shape: headings, their order, the tables.

    A .docx is read exactly — the format records what is a heading, so no model is
    involved. A PDF or a photo has no structure to read, so a model reads the marks on
    the page and what it returns is labelled as inferred.

    A heading nothing here can fill is **kept and named**, not dropped and not invented.
    A real template always has some — budget, hiring — and dropping them lets a reader
    believe their template was applied when it was not.
    """
    if not os.path.exists(path):
        return {"error": f"no such file: {path}"}
    try:
        found = extract.read(path)
    except Exception as e:
        return {"error": f"could not read {os.path.basename(path)}: {str(e)[:120]}"}
    return extract.template(found)


def make_report(
    ask: str = "", fmt: str = "md", today: str = "", project: str = "", like: str = ""
) -> dict:
    """A report in the shape somebody asked for, in the format they need to hand over.

    `ask` is plain words — "executive, one page, only what is in trouble". The model turns
    that into a layout: which sections, in what order, how long. It writes none of the
    content, because a restated figure is a new figure, close enough to look right and no
    longer traceable to the calculation that produced it.

    Formats: md, docx, xlsx, pptx. Each is a different arrangement of the same rows.
    """
    # `like` is an existing report to copy the shape of; `ask` describes one in words.
    # A document wins over a sentence when both are given: it is a more exact statement
    # of what somebody wants than a description of it.
    spec = report_template(like) if like else render.template(ask)
    if spec.get("error"):
        return spec
    when = _today(today)
    data: dict = {"questions": []}

    try:
        data["rollup"] = rollup_projects(today=today)
    except Exception as e:
        data["questions"].append(f"the roll-up could not be read: {str(e)[:80]}")

    tasks = _fetch(project=project)
    if tasks:
        pr = projects.resolve(project)
        if pr.is_run:
            with contextlib.suppress(Exception):
                data["health"] = project_health(today=today, project=project)
        else:
            data["schedule"] = schedule.summary(tasks, when)
            data["capacity"] = capacity.summary(tasks, when, availability=_availability())
            with contextlib.suppress(Exception):
                data["stalls"] = explain_stall(today=today, project=project)
            with contextlib.suppress(Exception):
                data["signals"] = signals.summary(tasks, _snapshot(100, project=project), when)
        with contextlib.suppress(Exception):
            data["issues"] = track_issues(today=today, project=project, save=False)

    doc = render.compose(spec, data, when)
    out = render.write(doc, fmt)
    out["spec"] = spec
    out["note"] = doc["note"]
    return out


def propose_comment(key: str, text: str) -> dict:
    """Propose a comment for the owner (not applied immediately)."""
    return jira().comment(key, text, approve=False)


def propose_field_update(key: str, duedate: str = "", summary: str = "") -> dict:
    """Propose a due date or summary change (not applied immediately)."""
    fields = {}
    if duedate:
        fields["duedate"] = duedate
    if summary:
        fields["summary"] = summary
    return jira().set_fields(key, fields, approve=False)


def propose_transition(key: str, to_status: str) -> dict:
    """Propose a status transition (not applied immediately)."""
    return jira().transition(key, to_status, approve=False)


REGISTRY = {
    f.__name__: f
    for f in (
        list_tasks,
        get_task,
        analyze_schedule,
        simulate_delay,
        analyze_capacity,
        suggest_rebalance,
        analyze_signals,
        explain_stall,
        reconcile_notes,
        project_health,
        rollup_projects,
        make_report,
        report_template,
        weigh_options,
        closing_decisions,
        track_issues,
        who_to_tell,
        propose_comment,
        propose_field_update,
        propose_transition,
    )
}

# ---- Gemini declarations (dicts compatible with google-genai types.FunctionDeclaration) ----
DECLARATIONS = [
    {
        "name": "list_tasks",
        "description": (
            "List the project's tasks in due-date order. Can be filtered by status or assignee. "
            "deps holds the keys that must finish first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "assignee": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_task",
        "description": "Read one task in detail, along with its dependencies (blocks and so on).",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "e.g. ECHO-12"}},
            "required": ["key"],
        },
    },
    {
        "name": "analyze_schedule",
        "description": (
            "Compute the whole project schedule. Returns the planned finish, the forecast finish, "
            "days of slip, the critical path, and the tasks at risk with their evidence. Any "
            "question about schedule or delay must call this tool first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {
                    "type": "string",
                    "description": "reference date YYYY-MM-DD, empty for today",
                },
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "simulate_delay",
        "description": (
            "Compute how far downstream tasks and the project finish move if one task slips N "
            "business days. Use it for 'what if' questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "days": {"type": "number", "description": "business days of slip"},
                "today": {"type": "string"},
            },
            "required": ["key", "days"],
        },
    },
    {
        "name": "analyze_capacity",
        "description": (
            "Compute the achievable finish with per-owner capacity and the calendar (time eaten "
            "by meetings) applied. Returns the gap against the dependency-only forecast, the "
            "bottleneck owner, and the tasks waiting on a busy person. Use it for 'who is "
            "overloaded' and 'is this schedule actually possible'."
        ),
        "parameters": {
            "type": "object",
            "properties": {"today": {"type": "string"}, "limit": {"type": "integer"}},
        },
    },
    {
        "name": "suggest_rebalance",
        "description": (
            "Work out whether moving a bottleneck owner's tasks to someone else pulls the finish "
            "in. Returns which task, to whom, and how many days it saves. A proposal only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {"type": "string"},
                "max_moves": {"type": "integer", "description": "moves to search (default 3)"},
            },
        },
    },
    {
        "name": "analyze_signals",
        "description": (
            "Line the board status up against real code activity (commits, pull requests) and "
            "find the tasks that disagree. Returns stalled work, work closed too early, pull "
            "requests waiting on review, and contribution concentration."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {"type": "string"},
                "days": {"type": "integer", "description": "activity window in days, default 14"},
            },
        },
    },
    {
        "name": "explain_stall",
        "description": (
            "Explain why a task stopped, by lining the board, the repository and the "
            "calendar up against each other: an open dependency, a pull request waiting on "
            "review, meetings that ate the owner's time, or the owner committing to other "
            "tasks instead. Each cause carries the business days it accounts for, and the "
            "leftover is reported rather than hidden. Use it for any 'why' question. With "
            "no key it returns the tasks that have been silent longest."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "e.g. ECHO-16. Empty for the worst offenders",
                },
                "today": {
                    "type": "string",
                    "description": "reference date YYYY-MM-DD, empty for today",
                },
            },
        },
    },
    {
        "name": "reconcile_notes",
        "description": (
            "Read the recent meeting notes and report the board changes they imply that "
            "the board does not have yet — a date the team agreed to move, a status "
            "somebody announced. Notes that agree with the board produce nothing, which "
            "is the point. Every change carries the sentence it came from. Nothing is "
            "applied; a note that cannot be tied to one task becomes a question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {
                    "type": "string",
                    "description": "reference date YYYY-MM-DD, empty for today",
                },
                "days": {
                    "type": "integer",
                    "description": "how many days of notes to read, 0 for the default",
                },
            },
        },
    },
    {
        "name": "track_issues",
        "description": (
            "File what went wrong on this project in the issue register and report what "
            "is open. Answers what a single run cannot: has this happened before, what "
            "has it cost in total, which are still open. An issue that stops being "
            "reported is closed; one nobody has looked at for a fortnight says lapsed, "
            "which is a different thing from fixed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {
                    "type": "string",
                    "description": "reference date YYYY-MM-DD, empty for today",
                },
            },
        },
    },
    {
        "name": "who_to_tell",
        "description": (
            "Who has a claim on hearing about a task, and a draft to send them. The "
            "people are the owners of everything downstream of it on the board, so this "
            "is a walk of the dependency graph rather than a guess about who cares. "
            "Nothing is sent — a person presses send."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "e.g. ECHO-16"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "rollup_projects",
        "description": (
            "Every project on one line, worst first — what is in trouble, why, and when it "
            "clears. A delivery project is judged on a date; work that runs has no finish "
            "and gets the numbers that do mean something for it. A project that could not "
            "be read is shown as unknown rather than left out."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {
                    "type": "string",
                    "description": "reference date YYYY-MM-DD, empty for today",
                },
            },
        },
    },
    {
        "name": "project_health",
        "description": (
            "How an operations project is doing: whether as much is closing as arriving, "
            "how old the waiting tickets are, and whether the same fault keeps coming back "
            "under new numbers. No finish date — a queue does not finish, and asking when "
            "it will is a category error."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "project key, e.g. OPS"},
                "today": {
                    "type": "string",
                    "description": "reference date YYYY-MM-DD, empty for today",
                },
            },
        },
    },
    {
        "name": "make_report",
        "description": (
            "A report in the shape somebody asks for, in the format they need. `ask` is "
            "plain words — 'executive, one page, only what is in trouble'. The model "
            "chooses the layout; every number is written by the calculation, because a "
            "restated figure is a new figure. Formats: md, docx, xlsx, pptx."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ask": {
                    "type": "string",
                    "description": "what the report should look like, in words",
                },
                "like": {
                    "type": "string",
                    "description": "path to an existing report to copy the shape of",
                },
                "fmt": {"type": "string", "description": "md, docx, xlsx or pptx"},
                "today": {
                    "type": "string",
                    "description": "reference date YYYY-MM-DD, empty for today",
                },
            },
        },
    },
    {
        "name": "propose_comment",
        "description": (
            "Propose a comment for the owner. Nothing is posted; a person has to approve it."
        ),
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "text": {"type": "string"}},
            "required": ["key", "text"],
        },
    },
    {
        "name": "propose_field_update",
        "description": "Propose a due date or summary change. Nothing changes before approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "duedate": {"type": "string", "description": "YYYY-MM-DD"},
                "summary": {"type": "string"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "propose_transition",
        "description": "Propose a status transition. Nothing changes before approval.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "to_status": {"type": "string"}},
            "required": ["key", "to_status"],
        },
    },
    {
        "name": "weigh_options",
        "description": (
            "The choices for one task at risk, each costed: accept the slip, hand it to "
            "somebody else, or cut it. Gives the finish date under each, whose work "
            "moves, who would have to agree, and the day a handover stops being worth "
            "doing. Deliberately unranked — the agent costs the options, a person picks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "e.g. ECHO-16"},
                "slip": {"type": "number", "description": "days to assume if nothing is done"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "closing_decisions",
        "description": (
            "Decisions that get more expensive to make later, soonest to close first. A "
            "handover buys nothing once the work is nearly done, and the day that stops "
            "being true is computable rather than something to find out afterwards."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {
                    "type": "string",
                    "description": "reference date YYYY-MM-DD, empty for today",
                },
            },
        },
    },
    {
        "name": "report_template",
        "description": (
            "Read an existing weekly report and work out the template it was written to: "
            "its headings, their order, its tables. A .docx is read exactly; a PDF or a "
            "photo needs a model and is labelled as inferred. A heading nothing here can "
            "fill is kept and named rather than dropped or invented."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "path to the sample report"},
            },
            "required": ["path"],
        },
    },
]

SYSTEM = """You are a project PMO assistant. Rules:
1) You do not produce the numbers for schedule, delay, critical path, load or code activity.
Quote only what analyze_schedule / simulate_delay / analyze_capacity / suggest_rebalance /
analyze_signals returned. If a calculation is needed, call the tool; if you cannot,
say you do not know.
2) Changes are only ever *proposed*, through the propose_* tools. Never apply anything yourself.
3) Give evidence with task keys (e.g. ECHO-12 blocks ECHO-19).
4) When something needs checking, propose a one-sentence question to put to the owner.
5) When you state a finish date, use capacity_finish from analyze_capacity (owner capacity
applied), and if it differs from the dependency-only forecast, say by how much.
6) For any question of the form "why", call explain_stall and quote its causes with the days
each accounts for. If it reports unexplained days, say so — do not fill the gap yourself.
Answer in English, concisely."""


def dispatch(name: str, args: dict) -> dict:
    fn = REGISTRY.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**(args or {}))
    except Exception as e:
        return {"error": str(e)[:300]}


if __name__ == "__main__":
    print(json.dumps(analyze_schedule(), ensure_ascii=False, indent=1))
