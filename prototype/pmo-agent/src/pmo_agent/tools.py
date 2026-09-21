"""The Gemini function-calling tool layer.
Design rule: the model only picks *what to do* and explains it.
Schedule and delay numbers come from schedule.py (pure Python); anything actually applied goes
through the Jira adapter after approval. Read tools run straight away; write tools return a
dry-run proposal and reach the board only once a person approves."""

from __future__ import annotations

import datetime as dt
import json

from pmo_agent import availability as avail_mod
from pmo_agent import capacity, schedule, signals
from pmo_agent.adapters.jira import Jira
from pmo_agent.env import env
from pmo_agent.ports import Board, Calendar, Repo

_j: Board | None = None


def jira() -> Board:
    """The PM-tool backend. PMO_BACKEND=memory gives the local board, otherwise Jira.
    Both adapters return the same shapes, so nothing above here needs to know which is in use."""
    global _j
    if _j is None:
        if env("PMO_BACKEND", "jira").lower() in ("memory", "local", "file"):
            from pmo_agent.adapters.memory import MemoryBoard

            _j = MemoryBoard(project=env("JIRA_PROJECT_KEY", "ECHO"))
        else:
            _j = Jira()
    return _j


_r: Repo | None = None


def repo() -> Repo:
    """The code-signal backend. REPO_BACKEND=memory gives the local repo, otherwise GitHub.
    Same arrangement as the board adapter — the layer above does not care which."""
    global _r
    if _r is None:
        if env("REPO_BACKEND", "github").lower() in ("memory", "local", "file"):
            from pmo_agent.adapters.memory_repo import MemoryRepo

            _r = MemoryRepo()
        else:
            from pmo_agent.adapters.github import GitHub

            _r = GitHub()
    return _r


_c: Calendar | None = None


def calendar() -> Calendar:
    """The available-time backend. CALENDAR_BACKEND=memory is local, else MS Graph."""
    global _c
    if _c is None:
        if env("CALENDAR_BACKEND", "msgraph").lower() in ("memory", "local", "file"):
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


def _today(today: str = "") -> dt.date:
    """A date string from a tool argument → date. Empty means today; an invented date dies here."""
    return schedule.parse_date(today) or dt.date.today()


def _fetch(jql: str = "", limit: int = 200) -> dict:
    """Read Jira issues and convert to {key: Task}.

    The shared entry point for the schedule functions — tests swap out this one place.
    """
    return schedule.from_jira_issues(
        jira().search(jql or f"project = {jira().project}", limit=limit)
    )


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


def analyze_schedule(today: str = "", limit: int = 200) -> dict:
    """The whole schedule — planned and forecast finish, critical path, tasks at risk.

    Every number is computed by schedule.py.
    """
    tasks = _fetch(limit=limit)
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


def analyze_capacity(today: str = "", limit: int = 200) -> dict:
    """The achievable finish, with owner capacity applied, next to the dependency-only forecast.
    One person cannot run several tasks at once, so this is usually later — and that is reality."""
    tasks = _fetch(limit=limit)
    if not tasks:
        return {"error": "no tasks."}
    try:
        return capacity.summary(tasks, _today(today), availability=_availability())
    except schedule.CycleError as e:
        return {"error": str(e)}


def suggest_rebalance(today: str = "", max_moves: int = 3) -> dict:
    """Work out who a bottleneck owner's task could move to, and how many days that saves.

    A proposal only; nothing is applied.
    """
    tasks = _fetch()
    if not tasks:
        return {"error": "no tasks."}
    try:
        return schedule.iso(capacity.rebalance(tasks, _today(today), max_moves=int(max_moves)))
    except schedule.CycleError as e:
        return {"error": str(e)}


def _link_assist():
    """Turn on model assistance only when LINK_ASSIST=on.

    Off by default — a model call costs money and latency, and is less precise than the rules.
    Whether to turn it on is the caller's decision.
    """
    if env("LINK_ASSIST", "off").strip().lower() not in ("on", "true", "1", "yes"):
        return None
    from pmo_agent import link_assist

    return link_assist.assistant()


def analyze_signals(today: str = "", days: int = 14) -> dict:
    """Line the board status up against real code activity and find where they disagree.
    "Ticket in progress with no commits", "done with an open PR", "PR waiting on review", and so on.
    None of it is visible from the board alone, so use it when progress looks doubtful."""
    tasks = _fetch()
    if not tasks:
        return {"error": "no tasks."}
    try:
        return signals.summary(
            tasks, repo().snapshot(100), _today(today), days=int(days), assist=_link_assist()
        )
    except Exception as e:
        return {
            "error": f"could not read the repository: {str(e)[:200]}",
            "hint": (
                "Check GITHUB_REPO and the gh login, or use REPO_BACKEND=memory for the local repo."
            ),
        }


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
