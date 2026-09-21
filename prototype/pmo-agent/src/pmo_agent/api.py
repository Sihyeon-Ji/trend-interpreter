"""Echo PMO 웹 서비스 — Cloud Run 에 올릴 FastAPI 앱.

에이전트의 기능을 HTTP 로 연다. 계산·판정 로직은 전부 agent/ 에 그대로 있고,
여기서는 입출력만 다룬다 — 웹이든 CLI 든 같은 코드가 같은 숫자를 낸다.

안전 규칙은 CLI 와 동일하다:
  · 읽기 엔드포인트는 아무것도 바꾸지 않는다
  · /api/ingest 는 '제안'까지만 만든다 (applied=false)
  · /api/approve 는 사용자가 고른 번호 + confirm=true 없이는 아무것도 반영하지 않는다
    (모델이 부를 수 있는 자리가 아니다 — 사람이 UI 에서 누른 것만 여기로 온다)

실행:
  로컬   PMO_BACKEND=memory uvicorn app.main:app --reload --port 8080
  컨테이너 docker build -t echo-pmo . && docker run -p 8080:8080 --env-file .env echo-pmo
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
UPLOAD = File(None)  # 기본 인자에서 호출하지 않도록 모듈 수준에 둔다

app = FastAPI(
    title="Echo PMO",
    version="0.1.0",
    description="일정 계산은 코드가, 판단과 설명은 Gemini 가. 쓰기는 사람 승인 뒤에만.",
)


def _tasks():
    t = tools._fetch()
    if not t:
        raise HTTPException(503, "보드에 태스크가 없다. 시드를 먼저 생성하라 (data/seed_jira.py).")
    return t


def _today(v: str = "") -> dt.date:
    try:
        return schedule.parse_date(v) or dt.date.today()
    except ValueError:
        raise HTTPException(400, f"날짜 형식이 잘못됐다: {v} (YYYY-MM-DD)") from None


# ---------- 읽기 ----------
@app.get("/health")
def health():
    """Cloud Run 헬스체크. 백엔드 연결까지는 확인하지 않는다 (기동을 막지 않기 위해)."""
    return {"ok": True, "backend": os.environ.get("PMO_BACKEND", "jira"), "version": app.version}


@app.get("/api/board")
def board():
    """어떤 백엔드에 붙어 있는지. 데모에서 '실제 Jira 입니다'를 보여주는 용도."""
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
    """의존관계 기준 일정 — 임계경로, 지연 위험과 그 근거."""
    return schedule.summary(_tasks(), _today(today))


@app.get("/api/capacity")
def api_capacity(today: str = ""):
    """사람 용량까지 반영한 실현 가능한 일정, 병목, 대기 중인 태스크."""
    return capacity.summary(_tasks(), _today(today), availability=tools._availability())


@app.get("/api/rebalance")
def api_rebalance(today: str = "", max_moves: int = 3):
    """병목을 풀 재배치 제안. 계산만 하고 아무것도 바꾸지 않는다."""
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
    """담당자별 회의 부담 — 앞으로 N영업일 중 실제로 쓸 수 있는 날이 얼마인지."""
    from pmo_agent import availability as avail_mod

    avail = tools._availability()
    if not avail:
        raise HTTPException(503, "캘린더가 연결되지 않았다 (CALENDAR_BACKEND 확인).")
    people = sorted({t.assignee for t in _tasks().values() if t.assignee})
    return {
        "source": getattr(tools.calendar(), "source", "?"),
        "window_days": days,
        "load": [avail_mod.meeting_load(avail, p, _today(), days) for p in people],
    }


@app.get("/api/signals")
def api_signals(today: str = "", days: int = 14):
    """보드 상태와 실제 코드 활동의 대조. 한쪽만으로는 보이지 않는 어긋남."""
    try:
        return signals.summary(_tasks(), tools.repo().snapshot(100), _today(today), days=days)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"저장소를 읽지 못했다: {str(e)[:200]}") from e


@app.get("/api/report", response_class=PlainTextResponse)
def api_report(today: str = "", rebalance: bool = True):
    """주간 리포트 (마크다운)."""
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


# ---------- 메모/사진 → 제안 ----------
@app.post("/api/ingest")
async def api_ingest(
    text: str = Form(""), today: str = Form(""), image: UploadFile | None = UPLOAD
):
    """메모 텍스트와 사진을 읽어 '제안'을 만든다. 아무것도 반영하지 않는다 (applied=false)."""
    paths, tmp = [], None
    if image is not None and image.filename:
        raw = await image.read()
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, f"파일이 너무 크다 ({len(raw) / 1048576:.1f}MB > 15MB)")
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ingest.MIME:
            raise HTTPException(415, f"지원하지 않는 형식: {ext}")
        fd, tmp = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        paths = [tmp]
    if not text.strip() and not paths:
        raise HTTPException(400, "메모 텍스트나 이미지 중 하나는 있어야 한다.")
    try:
        return ingest.ingest(text, paths, tasks=_tasks(), today=_today(today))
    except LLMError as e:
        raise HTTPException(502, f"모델 호출 실패: {e}") from e
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


# ---------- 승인 (유일한 쓰기 경로) ----------
class ApproveBody(BaseModel):
    proposals: list  # /api/ingest 가 돌려준 proposals 를 그대로
    indices: list[int] = []  # 사용자가 고른 번호 (1부터)
    confirm: bool = False  # 최종 확인 — 없으면 아무것도 하지 않는다
    source: str = "web"


@app.post("/api/approve")
def api_approve(body: ApproveBody):
    """고른 제안만 실제로 반영한다. CLI 의 승인 게이트와 같은 규칙을 강제한다."""
    items = approve_mod.appliable(body.proposals)
    if not body.confirm:
        return {
            "applied": 0,
            "skipped": len(items),
            "results": [],
            "message": "confirm=true 없이는 반영하지 않는다.",
        }
    if not body.indices:
        return {"applied": 0, "skipped": len(items), "results": [], "message": "고른 번호가 없다."}
    bad = [i for i in body.indices if not 1 <= i <= len(items)]
    if bad:
        raise HTTPException(400, f"범위를 벗어난 번호: {bad} (1~{len(items)})")
    out = approve_mod.apply(body.proposals, [i - 1 for i in body.indices], source=body.source)
    return out


@app.get("/api/approvals")
def api_approvals(days: int = 7):
    """최근 반영 내역 (감사 로그). 무엇이 언제 실제로 바뀌었는지."""
    since = schedule.add_workdays(dt.date.today(), -abs(days))
    return {"since": since.isoformat(), "rows": report.recent_approvals(since)}


# ---------- 데모 UI ----------
@app.get("/")
def index():
    # 캐시를 막는다 — UI 를 고치고 새로고침했는데 옛 화면이 나오면 시연 중에 원인을 찾기 어렵다
    return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
