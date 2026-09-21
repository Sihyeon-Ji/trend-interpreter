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
from pmo_agent import capacity, ingest, report, schedule, signals, tools
from pmo_agent.llm import LLMError  # noqa: E402

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_UPLOAD = 15 * 1024 * 1024
UPLOAD = File(None)  # kept at module level so it is not called in a default argument

app = FastAPI(
    title="Echo PMO",
    version="0.1.0",
    description="Code computes the schedule, Gemini explains it, writes wait for a person.",
)


def _tasks():
    t = tools._fetch()
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


@app.get("/api/schedule")
def api_schedule(today: str = ""):
    """The dependency-only schedule — critical path, tasks at risk, and the evidence."""
    return schedule.summary(_tasks(), _today(today))


@app.get("/api/capacity")
def api_capacity(today: str = ""):
    """The achievable schedule with capacity applied: the bottleneck and who is waiting."""
    return capacity.summary(_tasks(), _today(today), availability=tools._availability())


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
def api_signals(today: str = "", days: int = 14):
    """The board against real code activity — the divergence neither side shows alone."""
    try:
        return signals.summary(_tasks(), tools.repo().snapshot(100), _today(today), days=days)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"could not read the repository: {str(e)[:200]}") from e


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
        code = signals.summary(_tasks(), tools.repo().snapshot(100), _today(today))
    except Exception:
        pass
    return report.weekly(
        _tasks(),
        _today(today),
        project=getattr(j, "project", "ECHO"),
        rebalance=rebalance,
        done_recent=done_recent,
        code=code,
    )


# ---------- notes and photos → proposals ----------
@app.post("/api/ingest")
async def api_ingest(
    text: str = Form(""), today: str = Form(""), image: UploadFile | None = UPLOAD
):
    """Read note text and photos and build proposals. Nothing is applied (applied=false)."""
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
