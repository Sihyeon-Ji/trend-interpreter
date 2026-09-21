"""The Echo PMO web service — the FastAPI app that goes on Cloud Run.

It opens the agent's capabilities over HTTP. All the calculation and judgement stays in the
package; this file only handles input and output — web or CLI, the same code gives the same numbers.

The safety rules are the CLI's rules:
  · read endpoints change nothing
  · /api/ingest only ever produces proposals (applied=false)
  · /api/approve applies nothing without the indices a user picked and confirm=true
    (this is not somewhere a model can reach — only a person's click in the UI arrives here)

Run:
  local      PMO_BACKEND=memory uvicorn pmo_agent.api:app --reload --port 8080
  container  docker build -t echo-pmo . && docker run -p 8080:8080 --env-file .env echo-pmo
"""

from __future__ import annotations

import datetime as dt
import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from pmo_agent import approve as approve_mod  # noqa: E402
from pmo_agent import capacity, i18n, ingest, projects, report, schedule, signals, tools
from pmo_agent.llm import LLMError  # noqa: E402

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_UPLOAD = 15 * 1024 * 1024
UPLOAD = File(None)  # kept at module level so it is not called in a default argument

app = FastAPI(
    title="Echo PMO",
    version="0.1.0",
    description="Code computes the schedule, Gemini explains it, writes wait for a person.",
)


def _tasks(project: str = ""):
    try:
        t = tools._fetch(project=project)
    except KeyError as e:  # a project key nobody watches; say so rather than answer about another
        raise HTTPException(404, str(e)) from None
    if not t:
        raise HTTPException(503, "no tasks on the board. Generate the seed first (seeds/).")
    return t


def _today(v: str = "") -> dt.date:
    try:
        return schedule.parse_date(v) or dt.date.today()
    except ValueError:
        raise HTTPException(400, f"bad date format: {v} (YYYY-MM-DD)") from None


# ---------- reads ----------
@app.get("/health")
def health():
    """The Cloud Run health check. It does not test the backends — that would block startup."""
    return {"ok": True, "backend": os.environ.get("PMO_BACKEND", "jira"), "version": app.version}


@app.get("/api/board")
def board():
    """Which backend is connected. For showing "this really is Jira" in the demo."""
    j = tools.jira()
    out = {
        "site": getattr(j, "site", "?"),
        "project": getattr(j, "project", "?"),
        "kind": type(j).__name__,
    }
    try:
        out["repo"] = tools.repo().repo
    except Exception:
        out["repo"] = None
    return out


LIVE = {"Jira", "GitHub", "MSCalendar", "NotionNotes"}

# What each tool is *for*. The point of the product is that no one row can answer the
# question on its own, so the dashboard shows the four together and says who writes.
SOURCES = (
    ("board", "Jira", "status, dependencies, due dates", True),
    ("repo", "GitHub", "commits, pull requests, changed paths", False),
    ("calendar", "Outlook", "meeting hours per person", False),
    ("notes", "Notion", "what was decided, in words", False),
)


@app.get("/api/projects")
def api_projects():
    """Every project this agent watches, and what kind of work each one is.

    The kind is not decoration. A delivery project is asked "when does it finish"; work
    that runs has no finish and the question is whether it is healthy, so the same
    calculation underneath has to surface different numbers.
    """
    return {"projects": projects.summary(), "default": projects.default().key}


@app.get("/api/queue")
def api_queue(today: str = "", project: str = "", limit: int = 8, lang: str = ""):
    """What is waiting for a person today. The front door.

    Not a status panel. The research this was built from says the problem is coordination
    labour rather than a shortage of information — knowledge workers lose 352 hours a year
    to *talking about* work — so this is the small decisions and messages nobody has got
    round to, already prepared, each needing only a yes or a no.
    """
    try:
        found = tools.todays_queue(today=today, project=project, limit=limit)
        return i18n.apply(found, "queue", lang)
    except KeyError as e:
        raise HTTPException(404, str(e)) from None


@app.get("/api/rollup")
def api_rollup(today: str = "", lang: str = ""):
    """Every project on one line, worst first. The screen for somebody who will not open five.

    No new calculation — the same answers the per-project views give, arranged. The
    unexplained part rides along on each row rather than being folded away: a tidy number
    is what gets asked for at this altitude, and it is exactly what would make the rest
    look surer than it is.
    """
    return i18n.apply(tools.rollup_projects(today=today), "rollup", lang)


@app.get("/api/health")
def api_health(today: str = "", project: str = "", days: int = 0, lang: str = ""):
    """How an operations project is doing. No finish date, because a queue does not finish."""
    try:
        found = tools.project_health(today=today, project=project, days=days)
        return i18n.apply(found, "health", lang)
    except KeyError as e:
        raise HTTPException(404, str(e)) from None


@app.get("/api/sources")
def api_sources(lang: str = "", project: str = ""):
    """The four tools behind every answer: which is connected, and which one can write.

    No network calls. Asking each service to prove itself would make the page slow and
    could make it fail, and the panels below already show whether the data arrived — this
    says what is *configured*, which is a different and honestly smaller claim.
    """
    build = {
        "board": lambda: tools.jira(project),
        "repo": lambda: tools.repo(project),
        "calendar": lambda: tools.calendar(),
        "notes": lambda: tools.notes(project),
    }
    out = []
    for role, label, supplies, writes in SOURCES:
        row = {"role": role, "tool": label, "supplies": supplies, "writes": writes}
        try:
            adapter = build[role]()
        except Exception as e:  # a missing key is a state to show, not a page that fails
            out.append({**row, "kind": "", "live": False, "identity": "", "error": str(e)[:120]})
            continue
        kind = type(adapter).__name__
        row["kind"] = kind
        row["live"] = kind in LIVE
        row["identity"] = _identity(adapter, role)
        out.append(row)
    return i18n.apply(
        {
            "sources": out,
            # The agent's own job, in the words the README uses, so the page states it too
            "agent": {
                "joins": "commits to tasks with no ticket key — author, timing, vocabulary, path",
                "computes": "every date and every day-count, in schedule.py and capacity.py",
                "asks": "the model reads prose and pictures; it never produces a number",
                "waits": "nothing reaches the board until a person picks it",
            },
        },
        "sources",
        lang,
    )


def _identity(adapter, role: str) -> str:
    """What this adapter is pointed at, from what it already knows. Never a network call."""
    if role == "board":
        site = str(getattr(adapter, "site", "") or "local board").replace("https://", "")
        return f"{site.rstrip('/')} / {getattr(adapter, 'project', '?')}"
    if role == "repo":
        return str(getattr(adapter, "repo", "") or "local repository")
    if role == "notes":
        return str(getattr(adapter, "source", "") or "local archive")
    return str(getattr(adapter, "source", "") or "local calendar")


@app.get("/api/schedule")
def api_schedule(today: str = "", lang: str = "", project: str = ""):
    """The dependency-only schedule — critical path, tasks at risk, and the evidence."""
    return i18n.apply(schedule.summary(_tasks(project), _today(today)), "schedule", lang)


@app.get("/api/capacity")
def api_capacity(today: str = "", project: str = ""):
    """The achievable schedule with capacity applied: the bottleneck and who is waiting."""
    return capacity.summary(_tasks(project), _today(today), availability=tools._availability())


@app.get("/api/rebalance")
def api_rebalance(today: str = "", max_moves: int = 3):
    """A rebalancing proposal to clear the bottleneck. It calculates; it changes nothing."""
    return schedule.iso(
        capacity.rebalance(
            _tasks(),
            _today(today),
            max_moves=max(1, min(max_moves, 5)),
            availability=tools._availability(),
        )
    )


@app.get("/api/calendar")
def api_calendar(days: int = 10):
    """Meeting load per owner — how many of the next N business days are actually usable."""
    from pmo_agent import availability as avail_mod

    avail = tools._availability()
    if not avail:
        raise HTTPException(503, "no calendar is connected (check CALENDAR_BACKEND).")
    people = sorted({t.assignee for t in _tasks().values() if t.assignee})
    return {
        "source": getattr(tools.calendar(), "source", "?"),
        "window_days": days,
        "load": [avail_mod.meeting_load(avail, p, _today(), days) for p in people],
    }


@app.get("/api/signals")
def api_signals(today: str = "", days: int = 14, lang: str = "", project: str = ""):
    """The board against real code activity — the divergence neither side shows alone."""
    try:
        found = signals.summary(
            _tasks(project), tools._snapshot(100, project=project), _today(today), days=days
        )
        return i18n.apply(found, "signals", lang)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"could not read the repository: {str(e)[:200]}") from e


@app.get("/api/cause")
def api_cause(key: str = "", today: str = "", lang: str = "", project: str = ""):
    """Why a task stopped. Empty key returns whatever has been silent longest.

    This is the only endpoint that needs all three tools at once, which is the point:
    the board knows the status, the repository knows the silence, and only the calendar
    knows where that time went.
    """
    out = tools.explain_stall(key=key, today=today, project=project)
    if "error" in out:
        raise HTTPException(502 if "repository" in out["error"] else 404, out["error"])
    return i18n.apply(out, "cause", lang)


@app.get("/api/report", response_class=PlainTextResponse)
def api_report(today: str = "", rebalance: bool = True):
    """The weekly report, as Markdown."""
    j = tools.jira()
    done_recent = None
    try:
        done_recent = list(schedule.from_jira_issues(j.done_since(7)).values())
    except Exception:
        pass
    code = None
    try:
        code = signals.summary(_tasks(), tools._snapshot(100), _today(today))
    except Exception:
        pass
    stalls = tools.explain_stall(today=today) or {}
    return report.weekly(
        _tasks(),
        _today(today),
        project=getattr(j, "project", "ECHO"),
        rebalance=rebalance,
        done_recent=done_recent,
        code=code,
        stalls=stalls.get("worst"),
        stalls_note=stalls.get("notes_note", ""),
        can_take=tools._handover_check(_tasks())[0],
    )


# ---------- notes and photos → proposals ----------
@app.post("/api/ingest")
async def api_ingest(
    text: str = Form(""), today: str = Form(""), image: UploadFile | None = UPLOAD
):
    """Read note text, photos and recordings, and build proposals. Nothing is applied."""
    paths, tmp = [], None
    if image is not None and image.filename:
        raw = await image.read()
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, f"file too large ({len(raw) / 1048576:.1f}MB > 15MB)")
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ingest.MIME:
            raise HTTPException(415, f"unsupported format: {ext}")
        fd, tmp = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        paths = [tmp]
    if not text.strip() and not paths:
        raise HTTPException(400, "there has to be either note text or an image.")
    try:
        return ingest.ingest(text, paths, tasks=_tasks(), today=_today(today))
    except LLMError as e:
        raise HTTPException(502, f"the model call failed: {e}") from e
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


# ---------- approval (the only write path) ----------
class ApproveBody(BaseModel):
    proposals: list  # exactly what /api/ingest returned
    indices: list[int] = []  # the numbers the user picked (1-based)
    confirm: bool = False  # final confirmation — without it, nothing happens
    source: str = "web"


@app.post("/api/approve")
def api_approve(body: ApproveBody):
    """Apply only the chosen proposals. The same rules the CLI approval gate enforces."""
    items = approve_mod.appliable(body.proposals)
    if not body.confirm:
        return {
            "applied": 0,
            "skipped": len(items),
            "results": [],
            "message": "nothing is applied without confirm=true.",
        }
    if not body.indices:
        return {"applied": 0, "skipped": len(items), "results": [], "message": "no numbers chosen."}
    bad = [i for i in body.indices if not 1 <= i <= len(items)]
    if bad:
        raise HTTPException(400, f"number out of range: {bad} (1-{len(items)})")
    out = approve_mod.apply(body.proposals, [i - 1 for i in body.indices], source=body.source)
    return out


@app.get("/api/approvals")
def api_approvals(days: int = 7):
    """What was applied recently (the audit log). What really changed, and when."""
    since = schedule.add_workdays(dt.date.today(), -abs(days))
    return {"since": since.isoformat(), "rows": report.recent_approvals(since)}


# ---------- the demo UI ----------
@app.get("/")
def index():
    # No caching — editing the UI, refreshing and getting the old screen wastes demo time
    return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
