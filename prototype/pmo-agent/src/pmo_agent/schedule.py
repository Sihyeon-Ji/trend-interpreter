"""The schedule engine — CPM critical path, delay propagation, finish forecast. Pure Python.

Design rule (SETUP.md): every number and date is computed here. Gemini only quotes the result.
This module never imports Jira — it takes lists of dicts, so it unit-tests without credentials.
To feed it a Jira response, convert with from_jira_issues().

Terms: ES/EF earliest start/finish, LS/LF latest start/finish, slack spare days (0 = critical path).
All durations are in business days (weekends excluded), and EF means end of business that day.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

DONE = {"done", "완료", "closed", "resolved", "종료"}

# Status names that mean the same thing. A Jira site reports them in its own language
# while a model tends to answer in English, so the adapters bridge through this table.
# Each group is one meaning; add a language by adding its words to the right group.
STATUS_ALIASES = [
    {"done", "완료", "종료", "closed", "resolved"},
    {"in progress", "진행 중", "진행중", "doing", "wip"},
    {"to do", "todo", "할 일", "할일", "backlog", "open"},
    {"in review", "리뷰 중", "검토", "review", "code review"},
]


def status_alike(a: str, b: str) -> bool:
    """Do two status names mean the same thing? Absorbs case, spacing and language."""
    na, nb = (a or "").strip().lower(), (b or "").strip().lower()
    if na == nb:
        return True

    def squish(value: str) -> str:
        return value.replace(" ", "")

    if squish(na) == squish(nb):
        return True
    return any(na in g and nb in g for g in STATUS_ALIASES)


DAYS_PER_POINT = 1.0  # 1 story point = 1 business day
DEFAULT_DURATION = 2.0  # duration assumed when there are no points (business days)


class CycleError(ValueError):
    """The dependencies have a cycle, so no schedule can be computed."""


# ---------- business-day arithmetic ----------
def is_workday(d: _dt.date, holidays=()) -> bool:
    return d.weekday() < 5 and d not in set(holidays)


def add_workdays(start: _dt.date, days: float, holidays=()) -> _dt.date:
    """The date `days` business days after `start`; negative counts backwards.
    days=0 gives start itself (nudged to the next business day if it is a weekend)."""
    d, n = start, int(round(days))
    step = _dt.timedelta(days=-1 if n < 0 else 1)
    while not is_workday(d, holidays):
        d += step
    for _ in range(abs(n)):
        d += step
        while not is_workday(d, holidays):
            d += step
    return d


def workdays_between(a: _dt.date, b: _dt.date, holidays=()) -> int:
    """Business days from a to b. Negative when b is before a."""
    if b < a:
        return -workdays_between(b, a, holidays)
    n, d = 0, a
    while d < b:
        d += _dt.timedelta(days=1)
        if is_workday(d, holidays):
            n += 1
    return n


def parse_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, _dt.date):
        return v
    return _dt.date.fromisoformat(str(v)[:10])


# ---------- tasks ----------
@dataclass
class Task:
    key: str
    summary: str = ""
    status: str = ""
    assignee: str = ""
    duedate: _dt.date | None = None
    points: float | None = None
    deps: list = field(default_factory=list)  # keys that must finish before this can start
    progress: float = 0.0  # 0.0-1.0, how far an in-progress task has got

    @property
    def duration(self) -> float:
        return (self.points * DAYS_PER_POINT) if self.points else DEFAULT_DURATION

    @property
    def is_done(self) -> bool:
        return (self.status or "").strip().lower() in DONE

    @property
    def remaining(self) -> float:
        """Business days left. Zero when done; in progress accounts for progress."""
        if self.is_done:
            return 0.0
        return self.duration * (1.0 - min(max(self.progress, 0.0), 1.0))


def to_tasks(rows) -> dict:
    """List of dicts (or Tasks) → {key: Task}. deps pointing at unknown keys are dropped."""
    out = {}
    for r in rows:
        if isinstance(r, Task):
            out[r.key] = r
            continue
        out[r["key"]] = Task(
            key=r["key"],
            summary=r.get("summary", "") or "",
            status=r.get("status", "") or "",
            assignee=r.get("assignee", "") or "",
            duedate=parse_date(r.get("duedate")),
            points=r.get("points"),
            deps=list(r.get("deps") or []),
            progress=float(r.get("progress") or 0.0),
        )
    for t in out.values():
        t.deps = [d for d in t.deps if d in out and d != t.key]
    return out


OWNER_PREFIX = "owner-"


def owner_tag(name: str) -> str:
    """A name → the label that carries it. Jira labels cannot contain spaces, so they
    become underscores; owner_label() puts them back."""
    return f"{OWNER_PREFIX}{(name or '').strip().replace(' ', '_')}"


def owner_label(fields: dict) -> str:
    """Carry fictional assignees with no Jira account on a label (owner-<name>).
    The sandbox has exactly one real account, so showing per-owner load needs this fallback."""
    for label in fields.get("labels") or []:
        if label.startswith(OWNER_PREFIX):
            return label[len(OWNER_PREFIX) :].replace("_", " ")
    return ""


def from_jira_issues(issues) -> dict:
    """Jira search() response → {key: Task}.

    Reading Blocks links: an inwardIssue means "blocked by" (that issue comes first),
    an outwardIssue means "blocks" (this issue comes first).
    """
    rows, blocks = {}, []
    for i in issues:
        f = i.get("fields", {})
        rows[i["key"]] = {
            "key": i["key"],
            "summary": f.get("summary", ""),
            "status": ((f.get("status") or {}).get("name") or ""),
            "assignee": ((f.get("assignee") or {}) or {}).get("displayName") or owner_label(f),
            "duedate": f.get("duedate"),
            "points": f.get("customfield_10016"),
            "deps": [],
        }
        for link in f.get("issuelinks") or []:
            if "block" not in ((link.get("type") or {}).get("name", "")).lower():
                continue
            if link.get("inwardIssue"):
                blocks.append((link["inwardIssue"]["key"], i["key"]))
            if link.get("outwardIssue"):
                blocks.append((i["key"], link["outwardIssue"]["key"]))
    for pred, succ in blocks:
        if succ in rows and pred not in rows[succ]["deps"]:
            rows[succ]["deps"].append(pred)
    return to_tasks(rows.values())


# ---------- graph ----------
def successors(tasks: dict) -> dict:
    succ: dict[str, list[str]] = {k: [] for k in tasks}
    for k, t in tasks.items():
        for d in t.deps:
            succ[d].append(k)
    return succ


def topo_order(tasks: dict) -> list:
    indeg = {k: len(t.deps) for k, t in tasks.items()}
    succ = successors(tasks)
    queue = sorted(k for k, n in indeg.items() if n == 0)
    order = []
    while queue:
        k = queue.pop(0)
        order.append(k)
        for s in sorted(succ[k]):
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    if len(order) != len(tasks):
        raise CycleError("dependency cycle: " + ", ".join(sorted(set(tasks) - set(order))))
    return order


# ---------- CPM ----------
def cpm(tasks: dict, start: _dt.date, holidays=()) -> dict:
    """Critical path. Returns {tasks: {key: {...}}, finish, duration_days, critical_path}"""
    order, succ = topo_order(tasks), successors(tasks)
    es: dict[str, float] = {}
    ef: dict[str, float] = {}
    for k in order:
        es[k] = max([ef[d] for d in tasks[k].deps], default=0.0)
        ef[k] = es[k] + tasks[k].duration
    total = max(ef.values(), default=0.0)
    ls: dict[str, float] = {}
    lf: dict[str, float] = {}
    for k in reversed(order):
        lf[k] = min([ls[s] for s in succ[k]], default=total)
        ls[k] = lf[k] - tasks[k].duration
    rows = {}
    for k in order:
        slack = round(ls[k] - es[k], 3)
        rows[k] = {
            "key": k,
            "summary": tasks[k].summary,
            "assignee": tasks[k].assignee,
            "status": tasks[k].status,
            "duration_days": tasks[k].duration,
            "es": add_workdays(start, es[k], holidays),
            "ef": add_workdays(start, ef[k], holidays),
            "ls": add_workdays(start, ls[k], holidays),
            "lf": add_workdays(start, lf[k], holidays),
            "slack_days": slack,
            "critical": slack <= 0.0001,
            "duedate": tasks[k].duedate,
            "deps": list(tasks[k].deps),
        }
    return {
        "tasks": rows,
        "finish": add_workdays(start, total, holidays),
        "duration_days": int(round(total)),
        "critical_path": [k for k in order if rows[k]["critical"]],
    }


# ---------- finish forecast ----------
def forecast(tasks: dict, today: _dt.date, holidays=()) -> dict:
    """Forecast from the work left. Done tasks count as 0 days and it replays from today."""
    order = topo_order(tasks)
    out: dict[str, dict] = {}
    ef: dict[str, float] = {}
    for k in order:
        t = tasks[k]
        ef[k] = max([ef[d] for d in t.deps], default=0.0) + t.remaining
        pred = add_workdays(today, ef[k], holidays)
        delay = workdays_between(t.duedate, pred, holidays) if t.duedate else 0
        out[k] = {
            "key": k,
            "summary": t.summary,
            "assignee": t.assignee,
            "status": t.status,
            "remaining_days": round(t.remaining, 2),
            "predicted_finish": pred,
            "duedate": t.duedate,
            "delay_days": max(0, delay) if t.duedate else None,
            "late": bool(t.duedate and delay > 0),
        }
    return {
        "tasks": out,
        "project_finish": add_workdays(today, max(ef.values(), default=0.0), holidays),
    }


def propagate(tasks: dict, key: str, slip_days: float, today: _dt.date, holidays=()) -> dict:
    """If one task slips by slip_days, how many days does each downstream task move?

    Slack absorbs part of it; only what is left over propagates.
    """
    if key not in tasks:
        return {"error": f"unknown task: {key}"}
    base = forecast(tasks, today, holidays)
    bumped = {k: Task(**dict(t.__dict__)) for k, t in tasks.items()}
    hit = bumped[key]
    hit.points = (tasks[key].remaining + slip_days) / DAYS_PER_POINT
    hit.progress, hit.status = 0.0, ""  # treat the slip as work still outstanding
    after = forecast(bumped, today, holidays)
    moved = []
    for k in after["tasks"]:
        d = workdays_between(
            base["tasks"][k]["predicted_finish"], after["tasks"][k]["predicted_finish"], holidays
        )
        if d <= 0:
            continue
        new_finish = after["tasks"][k]["predicted_finish"]
        moved.append(
            {
                "key": k,
                "summary": tasks[k].summary,
                "assignee": tasks[k].assignee,
                "slip_days": d,
                "new_finish": new_finish,
                "duedate": tasks[k].duedate,
                "breaks_duedate": bool(tasks[k].duedate and new_finish > tasks[k].duedate),
            }
        )
    moved.sort(key=lambda r: (-r["slip_days"], r["key"]))
    return {
        "trigger": key,
        "slip_days": slip_days,
        "affected": moved,
        "project_finish_before": base["project_finish"],
        "project_finish_after": after["project_finish"],
    }


def risks(
    tasks: dict,
    today: _dt.date,
    start: _dt.date | None = None,
    slack_threshold: float = 1.0,
    holidays=(),
) -> list:
    """Tasks at risk, sorted, with their evidence — in a shape Gemini can quote verbatim."""
    fc = forecast(tasks, today, holidays)["tasks"]
    cp = cpm(tasks, start or today, holidays)["tasks"]
    succ, out = successors(tasks), []
    for k, t in tasks.items():
        if t.is_done:
            continue
        why = []
        if fc[k]["late"]:
            why.append(
                f"forecast finish {fc[k]['predicted_finish']} > due {t.duedate} "
                f"({fc[k]['delay_days']} days over)"
            )
        if cp[k]["critical"]:
            why.append("on the critical path (zero slack)")
        elif cp[k]["slack_days"] <= slack_threshold:
            why.append(f"only {cp[k]['slack_days']} days of slack")
        if t.duedate and t.duedate < today:
            why.append(f"past its due date of {t.duedate}")
        if not why:
            continue
        out.append(
            {
                "key": k,
                "summary": t.summary,
                "assignee": t.assignee,
                "status": t.status,
                "duedate": t.duedate,
                "predicted_finish": fc[k]["predicted_finish"],
                "delay_days": fc[k]["delay_days"] or 0,
                "slack_days": cp[k]["slack_days"],
                "critical": cp[k]["critical"],
                "reasons": why,
                "blocks": sorted(succ[k]),
            }
        )
    out.sort(key=lambda r: (-r["delay_days"], r["slack_days"], r["key"]))
    return out


def summary(tasks: dict, today: _dt.date, start: _dt.date | None = None, holidays=()) -> dict:
    """One bundle for the report. Dates serialize to ISO strings so it drops into JSON."""
    start = start or today
    c, f = cpm(tasks, start, holidays), forecast(tasks, today, holidays)
    return iso(
        {
            "today": today,
            "planned_finish": c["finish"],
            "predicted_finish": f["project_finish"],
            "slip_days": workdays_between(c["finish"], f["project_finish"], holidays),
            "total": len(tasks),
            "done": sum(1 for t in tasks.values() if t.is_done),
            "critical_path": c["critical_path"],
            "risks": risks(tasks, today, start, holidays=holidays),
        }
    )


def iso(o):
    """A copy with dates turned into ISO strings, for JSON."""
    if isinstance(o, _dt.date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: iso(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [iso(v) for v in o]
    return o
