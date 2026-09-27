"""FastAPI — 프론트(web/lib/data.ts api 모드)가 부르는 엔드포인트. 읽기는 SQLite, 쓰기는 검수 결정만."""
from __future__ import annotations

import json
from queue import Queue
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import WEB_ORIGINS
from ..pipeline import ask as ask_stage, board as board_stage
from ..pipeline import explain as explain_stage
from ..pipeline import views
from ..schemas import TrendBoard
from ..auth import check_account, frontend_token_ok
from ..storage import dictionary_store as ds
from ..storage import sqlite_store as db

app = FastAPI(title="trend-agents api", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=WEB_ORIGINS or ["*"], allow_methods=["*"], allow_headers=["*"])


class _PerThreadConnection:
    """스레드마다 자기 SQLite 연결을 쓴다. 엔드포인트는 그대로 `_con` 을 넘기면 된다.

    전에는 연결 하나를 모든 요청이 나눠 썼다. check_same_thread=False 는 스레드 간 공유를 허용할 뿐 동시 사용을 안전하게 하지
    않는다 — FastAPI 는 동기 엔드포인트를 스레드풀에서 동시에 돌리므로, 화면이 보드·메타·업데이트를 한꺼번에 부르면
    sqlite3.InterfaceError('bad parameter or other API misuse') 가 났다(2026-09-26 실측). 보드가 500 을 받으면 프론트는
    예시 데이터로 물러서서, 실데이터가 아닌 화면이 오류 없이 보였다.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def _get(self):
        con = getattr(self._local, "con", None)
        if con is None:
            con = self._local.con = db.connect()
        return con

    def __getattr__(self, name: str):
        return getattr(self._get(), name)


_con = _PerThreadConnection()


class ReaderIn(BaseModel):
    gen: str | None = None
    region: str | None = None


class ExplainIn(BaseModel):
    text: str
    lang: str = "ko"
    reader: ReaderIn | None = None  # 읽는 사람의 세대·나라 (저장하지 않음)


class ExplainOut(BaseModel):
    term_ids: list[str]
    plain: str | None


class ReviewIn(BaseModel):
    decision: str  # approve | reject
    by: str = "reviewer"


@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat(), "terms": len(ds.list_terms(_con))}


@app.get("/terms", response_model=list[views.TermRecord])
def terms(status: str = "verified"):
    """공개 사전은 확인된 것만. status=all 이면 확인 중인 것까지 (관리자·내보내기용)."""
    statuses = ("verified", "needs_review") if status == "all" else ("verified",)
    return views.term_records(_con, statuses)


@app.get("/terms/{term_id}", response_model=views.TermRecord | None)
def term(term_id: str):
    t = ds.get_term(_con, term_id)
    if not t or t.status == "retired":  # 사전에서 제외된 항목은 공개 화면에 없다
        raise HTTPException(404, "not found")
    return views.term_record(_con, t)


@app.get("/pipeline/stages", response_model=list[views.PipelineStage])
def stages():
    return views.pipeline_stages(_con)


@app.get("/review/queue", response_model=list[views.ReviewItem])
def queue():
    return views.review_items(_con)


@app.get("/review/stats", response_model=views.ReviewStats)
def review_stats():
    return views.review_stats(_con)


class LoginIn(BaseModel):
    user: str
    password: str


@app.post("/auth/login")
def login(body: LoginIn):
    """검수자 자격 확인만 한다. 브라우저 세션은 프론트(Next)가 갖는다 — 쿠키가 화면과 같은 출처에 있어야 하기 때문.
    나중에 Firebase Auth 로 바꿀 때 이 함수만 ID 토큰 검증으로 갈아 끼우면 된다."""
    acct = check_account(body.user, body.password)
    if not acct:
        raise HTTPException(401, "아이디 또는 비밀번호가 맞지 않습니다")
    return {"ok": True, "name": acct.user, "reviewer": acct.reviewer}


class PrefsIn(BaseModel):
    prefs: dict


@app.get("/prefs/{user}")
def read_prefs(user: str, x_frontend_token: str = Header(default="")):
    """로그인한 사람의 설정. 세션 확인은 프론트가 하고, 이 API 는 프론트 서버만 부를 수 있다."""
    if not frontend_token_ok(x_frontend_token):
        raise HTTPException(401, "로그인이 필요합니다")
    return ds.get_prefs(_con, user)


@app.put("/prefs/{user}")
def write_prefs(user: str, body: PrefsIn, x_frontend_token: str = Header(default="")):
    if not frontend_token_ok(x_frontend_token):
        raise HTTPException(401, "로그인이 필요합니다")
    ds.set_prefs(_con, user, body.prefs)
    return {"ok": True}


@app.post("/review/{term_id}")
def decide(term_id: str, body: ReviewIn, x_frontend_token: str = Header(default="")):
    # 사전의 승인·제외는 프론트의 로그인한 검수자만 거쳐 온다. 토큰이 설정돼 있지 않으면 쓰기 자체가 잠긴다.
    if not frontend_token_ok(x_frontend_token):
        raise HTTPException(401, "검수 권한이 필요합니다")
    t = ds.get_term(_con, term_id)
    m = ds.current_meaning(_con, term_id)
    if not t or not m:
        raise HTTPException(404, "not found")
    if body.decision == "approve":
        ds.set_verification(_con, m.meaning_id, "verified_human", body.by)
        t.status = "verified"
    elif body.decision == "reject":
        ds.set_verification(_con, m.meaning_id, "rejected", body.by)
        t.status = "retired"
    else:
        raise HTTPException(400, "decision must be approve|reject")
    ds.upsert_term(_con, t)
    ds.decide_review(_con, term_id, body.decision, body.by)
    return {"ok": True, "term_id": term_id, "status": t.status}


class AskIn(BaseModel):
    question: str
    lang: str = "ko"
    history: list[dict] = []   # [{role, content}] 최근 대화 — 앞을 받는 말("비슷한 것도 없어?")을 알아듣게
    log_miss: bool = True      # False 면 '못 답한 질문' 으로 쌓지 않는다 (평가·시험용 호출)


class AskOut(BaseModel):
    answer: str
    cards: list[dict] = []      # 화면이 그리는 조각: 표제어 카드·목록·세대 비중
    term_ids: list[str] = []
    tools: list[str] = []
    turns: int = 0
    seconds: float = 0
    fallback: str | None = None


@app.post("/ask/stream")
def ask_stream(body: AskIn):
    """진행 상황을 흘려보내며 답한다(SSE). 오래 걸려도 무엇을 하는 중인지 보이면 기다릴 만하다.

    event: progress  {step, label}   — 사전을 보는 중, 위키백과에서 찾는 중 …
    event: result    AskOut          — 마지막에 한 번
    """
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "question 이 비었습니다")

    events: "Queue[tuple[str, dict] | None]" = Queue()   # queue 라는 이름은 아래 검수 큐 함수가 쓴다

    def work() -> None:
        try:
            a = ask_stage.run(_con, q[:500], body.lang, body.history[-6:],
                              progress=lambda step, label: events.put(("progress", {"step": step, "label": label})),
                              log_miss=body.log_miss)
            events.put(("result", AskOut(answer=a.text, cards=a.cards, term_ids=a.term_ids, tools=a.used,
                                         turns=a.turns, seconds=round(a.seconds, 1), fallback=a.fallback).model_dump()))
        except Exception as e:
            events.put(("error", {"message": f"{type(e).__name__}"}))
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while True:
            item = events.get()
            if item is None:
                break
            name, data = item
            yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/ask", response_model=AskOut)
def ask_dictionary(body: AskIn):
    """사전에 묻는다. 모델은 검증된 사전·그래프를 도구로만 읽고 그 밖의 이야기는 하지 않는다 (pipeline/ask.py).
    답을 못 하면 fallback 에 이유가 담기고, 화면은 규칙 기반 메시지 해석으로 물러선다."""
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "질문이 비었습니다")
    a = ask_stage.run(_con, q[:500], body.lang, body.history[-6:], log_miss=body.log_miss)
    return AskOut(answer=a.text, cards=a.cards, term_ids=a.term_ids, tools=a.used, turns=a.turns,
                  seconds=round(a.seconds, 1), fallback=a.fallback)


@app.post("/explain", response_model=ExplainOut)
def explain(body: ExplainIn):
    ids, plain = explain_stage.explain(_con, body.text, body.lang, body.reader.model_dump() if body.reader else None)
    return ExplainOut(term_ids=ids, plain=plain)


@app.get("/trends/board", response_model=TrendBoard)
def trends_board():
    cached = ds.cache_get(_con, "board")
    if cached:
        return TrendBoard.model_validate_json(cached[0])
    return board_stage.build(_con)


@app.get("/candidates")
def candidates():
    return [c.model_dump() for c in ds.candidates(_con, "new", 100)]


@app.get("/trends/why")
def trends_why(region: str | None = None):
    """급증 원인 설명 목록 (근거 id·관련 인물 포함)."""
    out = [x.model_dump(mode="json") for x in ds.explanations_by_region(_con).values()]
    return [x for x in out if not region or x["region"] == region]


@app.get("/meta")
def meta():
    """갱신 시각: 마지막 파이프라인 종료, 보드 생성 시각, 용어 수."""
    cached = ds.cache_get(_con, "board")
    return {"last_run": ds.last_finished(_con), "board_generated_at": cached[1] if cached else None, "terms": len(ds.list_terms(_con, ("verified", "needs_review"))),
            "explanations": len(ds.explanations_by_region(_con))}


@app.get("/updates")
def updates(hours: int = 48):
    """최근 변화 피드 (새 용어·확인·뜻 변경·급증 설명·재조사·검수 결정)."""
    return ds.recent_updates(_con, hours=hours)


@app.get("/countries/{region}", response_model=views.CountryPage)
def country(region: str):
    return views.country_page(_con, region.upper())


@app.get("/graph/shared", response_model=list[views.SharedNode])
def graph_shared(min: int = 2):
    """여러 급증 검색어에 함께 걸린 인물·위키 (나라 수 많은 것부터). 지도의 '같은 사건이 여러 나라에서' 연결 재료."""
    return views.shared_nodes(_con, min_queries=max(2, min))


@app.get("/graph/query/{key:path}", response_model=views.QueryGraph | None)
def graph_query(key: str):
    """급증 검색어(norm(term)|region)의 그래프 이웃: 인물·위키·근거·사전 용어."""
    return views.query_graph(_con, key)


@app.get("/terms/{term_id}/graph", response_model=list[views.TermGraphQuery])
def term_graph(term_id: str):
    """이 용어로 판정된 급증 검색어들 (IS_TERM)."""
    return views.term_graph(_con, term_id)


@app.get("/terms/{term_id}/generations")
def generations(term_id: str):
    """네이버 데이터랩 세대별 검색 곡선 (한국어 용어만 있음)."""
    curves = ds.get_gen_curves(_con, term_id)
    out = []
    for g, pts in curves.items():
        peak = max(pts, key=lambda p: p[1]) if pts else None
        out.append({"generation": g, "points": pts, "peak_date": peak[0] if peak else None})
    return out
