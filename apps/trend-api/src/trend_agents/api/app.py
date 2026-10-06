"""FastAPI — 프론트(apps/trend-web/lib/data.ts api 모드)가 부르는 엔드포인트. 읽기는 PostgreSQL, 쓰기는 검수 결정만."""
from __future__ import annotations

import base64
import json
import logging
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from queue import Queue
import threading
import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.formparsers import MultiPartParser
from pydantic import BaseModel, Field

from ..config import REGIONS_FOCUS, WEB_ORIGINS
from ..pipeline import ask as ask_stage, board as board_stage
from ..pipeline import content_agent
from ..pipeline import explain as explain_stage
from ..pipeline import dashboard, generate as generate_stage, recommend as recommend_stage, risk, views
from ..pipeline import briefing as briefing_stage, copycheck, poster as poster_stage
from ..schemas import CampaignTone, ProductBrief, RiskLevel, Topic, TrendBoard
from ..auth import check_account, frontend_token_ok
from ..logging_setup import configure as configure_logging
from ..storage import db
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from ..verification import is_public_entry
from ..pipeline.match import term_pattern, text_pattern

configure_logging()


def _warm() -> None:
    """새로 뜬 인스턴스의 첫 요청이 떠안던 준비를 미리 한다 — 대시보드(8.9MB)·지도 보드 캐시 해석과 표기 1만여 개의 정규식 컴파일.
    운영 첫 요청이 사전 10.7초·메시지 해석 13.7초였다(10-05 익명 점검). 실패해도 요청 때 하던 대로 하므로 기록만 남긴다(사용자 문장 없음)."""
    try:
        with db.session() as con:
            dashboard._load(con)
            board_stage.cached(con)
            views.term_index_json(con)
            for t in ds.list_terms(con, ("verified", "needs_review")):
                for name in (t.canonical, *t.aliases):
                    if name and name.strip():
                        term_pattern(name)
                        text_pattern(name)
    except Exception as e:
        logging.getLogger(__name__).warning("cache warm-up skipped: %s", type(e).__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    threading.Thread(target=_warm, name="warm-caches", daemon=True).start()   # 상태 점검을 막지 않게 뒤에서
    yield


app = FastAPI(title="trend-agents api", version="0.1", lifespan=_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=WEB_ORIGINS or ["*"], allow_methods=["*"], allow_headers=["*"])
# Cloud Run 은 스트리밍이 아닌 응답을 32MiB 까지만 보낸다. 실데이터의 사전 전체 /terms 가 29MB, status=all 은 그 이상이었다(staging 10-03).
# gzip 으로 약 1/4 이 된다. text/event-stream(질문 스트리밍)은 Starlette 기본값으로 압축하지 않는다.
app.add_middleware(GZipMiddleware, minimum_size=1024)


class _Borrowed:
    """요청 하나가 빌린 연결. 처음 DB 를 쓸 때 작업 스레드에서 빌리고, 요청이 끝나면 미들웨어가 돌려준다."""

    def __init__(self) -> None:
        self.raw = None
        self.con: Connection | None = None


_request_slot: ContextVar[_Borrowed | None] = ContextVar("request_slot", default=None)


class _RequestConnection:
    """요청마다 풀에서 빌린 연결을 쓴다. 엔드포인트는 그대로 `_con` 을 넘기면 된다.

    FastAPI 는 동기 엔드포인트를 스레드풀에서 동시에 돌리므로 연결 하나를 나눠 쓰면 안 된다(SQLite 시절 2026-09-26 실측).
    연결은 이벤트 루프가 아니라 엔드포인트를 실행하는 작업 스레드에서 빌린다. 루프에서 빌리면 풀이 찼을 때 루프가 멈춰
    앞선 요청도 끝나지 못한다. 풀 크기(DB_POOL_SIZE)가 인스턴스당 동시 DB 사용 수의 상한이다.
    응답 뒤에도 일하는 스트리밍 작업은 db.session() 으로 따로 빌린다.
    """

    def __getattr__(self, name: str):
        slot = _request_slot.get()
        if slot is None:
            raise RuntimeError("요청 밖에서 _con 을 썼습니다. db.session() 으로 연결을 빌리세요.")
        if slot.con is None:
            slot.raw = db.pool().getconn()
            slot.con = Connection(slot.raw)
        return getattr(slot.con, name)


_con = _RequestConnection()


@app.middleware("http")
async def _database_session(request, call_next):
    slot = _Borrowed()
    token = _request_slot.set(slot)
    try:
        return await call_next(request)
    finally:
        _request_slot.reset(token)
        if slot.raw is not None:
            db.pool().putconn(slot.raw)  # 열린 트랜잭션은 풀이 롤백한다


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
    meaning_id: str | None = None  # 검수자가 본 뜻. 그사이 조사가 새 판을 만들었으면 409 — 보지 않은 뜻을 싣지 않는다
    # 검수자가 본 제안의 종류(Plan 12). 서버에 대기 중인 제안과 다르면 409 — '승인' 의 뜻이 종류마다 달라서(retire 의 승인은 제외다)
    # 새 말(new) 밖의 제안에는 반드시 적는다. 적지 않으면 new 로 본다(예전 화면).
    kind: str | None = None
    # 검수자가 본 제안의 표(ReviewItem.token). 대기 중인 제안과 다르면 409 — 그사이 같은 종류의 다른 제안이 올라왔을 때 보지 않은 안을 싣지 않게.
    # 새 말 밖의 제안에는 반드시 적는다.
    token: str | None = None
    # 위키끼리 다름(conflict)을 승인할 때 고른 문서의 주소(docs[].url), 또는 "keep"(지금 뜻 그대로). 번호로 고르지 않는다 —
    # 화면은 모양이 틀린 문서를 빼고 보이므로 번호가 밀린다.
    choice: str | None = None


@app.get("/graph/contents")
def graph_contents():
    """밈을 조사해 둔 작품들."""
    return content_agent.contents(_con)


@app.get("/graph/content/{key}")
def graph_content(key: str):
    """작품 하나에서 나라마다 파생된 밈 — 같은 밈의 나라별 이름을 한 줄로 묶어서."""
    v = content_agent.view(_con, key)
    if not v:
        raise HTTPException(404, "조사하지 않은 콘텐츠")
    return v


@app.get("/health")
def health():
    # 용어 JSON 을 읽지 않고 센다 — 3초마다 부르는 상태 점검이 용어 11,000개를 해석해 API·DB 가 늘 바빴다(모든 요청이 2~3초, 10-04)
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat(), "terms": ds.count_terms(_con)}



def _review_access(response: Response, x_frontend_token: str = Header(default="")) -> None:
    # The web server checks the signed reviewer session before attaching this token.
    if not frontend_token_ok(x_frontend_token):
        raise HTTPException(401, "검수 권한이 필요합니다")
    response.headers["Cache-Control"] = "private, no-store"


def _public_term(term_id: str):
    t = ds.get_term(_con, term_id)
    if not is_public_entry(t, ds.current_meaning(_con, term_id) if t else None):
        raise HTTPException(404, "not found")
    return t


@app.get("/terms", response_model=list[views.TermRecord])
def terms(status: Literal["verified"] = "verified", slim: bool = False):
    """Public entries only. Review drafts are available under /review/terms."""
    if slim:
        return Response(content=views.term_index_json(_con), media_type="application/json")
    return views.term_records(_con, public=True)


@app.get("/terms/{term_id}", response_model=views.TermRecord | None)
def term(term_id: str):
    t = _public_term(term_id)
    r = views.term_record(_con, t, public=True)
    return r.model_copy(update={"provenance": views.provenance(_con, t, r.meanings, r.evidences), "risk_labels": views.risk_breakdown(_con, t)})


@app.get("/review/terms", response_model=list[views.TermRecord], dependencies=[Depends(_review_access)])
def review_terms(status: Literal["verified", "all"] = "all", slim: bool = False):
    statuses = ("verified", "needs_review") if status == "all" else ("verified",)
    return views.term_records(_con, statuses, slim=slim)


@app.get("/review/terms/{term_id}", response_model=views.TermRecord, dependencies=[Depends(_review_access)])
def review_term(term_id: str):
    t = ds.get_term(_con, term_id)
    if not t or t.status not in ("verified", "needs_review"):
        raise HTTPException(404, "not found")
    return views.term_record(_con, t)


@app.get("/model-usage", response_model=views.GemmaUsage, dependencies=[Depends(_review_access)])
def model_usage():
    """단계별로 모델이 남긴 결과의 수(Plan 14 0단계) — 관리 화면 '모델 기록'. 저장된 기록만 센다."""
    return views.gemma_usage(_con)


@app.get("/pipeline/stages", response_model=list[views.PipelineStage], dependencies=[Depends(_review_access)])
def stages():
    return views.pipeline_stages(_con)


@app.get("/review/queue", response_model=list[views.ReviewItem], dependencies=[Depends(_review_access)])
def queue():
    return views.review_items(_con)


@app.get("/review/stats", response_model=views.ReviewStats, dependencies=[Depends(_review_access)])
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
    q = ds.pending_review(_con, term_id)
    kind = q["kind"] if q else "new"
    if not t or (not m and kind != "retire"):
        raise HTTPException(404, "not found")
    if body.decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve|reject")
    if kind != "new" and ((m is not None and not body.meaning_id) or not body.token):
        raise HTTPException(400, "문서 대조의 제안은 본 뜻(meaning_id)과 제안의 표(token)를 함께 보내야 합니다")
    if (body.kind or "new") != kind:
        raise HTTPException(409, "그사이 제안이 바뀌었습니다")
    if body.meaning_id and body.meaning_id != (m.meaning_id if m else None):
        raise HTTPException(409, "그사이 제안이 바뀌었습니다")
    if body.token and (q is None or body.token != q["token"]):
        raise HTTPException(409, "그사이 제안이 바뀌었습니다")
    if kind != "new":
        return _decide_proposal(t, m, q, body)
    if body.decision == "approve":
        ds.set_verification(_con, m.meaning_id, "verified_human", body.by)
        t.status = "verified"
    else:
        ds.set_verification(_con, m.meaning_id, "rejected", body.by)
        t.status = "retired"
    ds.upsert_term(_con, t, human=True)     # 사람의 결정 — 제외를 되돌리는 승인도 여기서만 한다
    ds.decide_review(_con, term_id, body.decision, body.by)
    if t.status == "verified":
        risk.apply(_con, t)                 # 승인한 말도 리스크 규칙을 거친 뒤에 대시보드에 오른다(표제어 욕설 등)
    dashboard.refresh_card(_con, term_id)   # 승인한 말은 대시보드에 바로 오르고, 제외한 말은 바로 빠진다
    return {"ok": True, "term_id": term_id, "status": t.status}


def _decide_proposal(t, m, q: dict, body: ReviewIn) -> dict:
    """문서 대조의 제안(Plan 12 §3). 제안이 올라와 있는 동안 지금 뜻은 공개된 그대로이고, 사람의 결정으로만 바뀐다.
    correction 승인 → 고칠 안을 새 판(verified_human)으로, 이전 판은 valid_to 를 닫는다. 거절 → 제안만 닫는다.
    conflict   승인 → 고른 문서(choice = 문서 주소)의 고칠 안을 correction 과 같은 길로. choice="keep" 이면 지금 뜻 그대로 두고 닫는다. 거절 → 제안만 닫는다.
    retire     승인 → 사람이 사전에서 뺀다(retired, 뜻은 rejected — 새 말의 '제외' 와 같다). 거절 → 아무것도 바꾸지 않는다.
    결정은 검수자가 본 그 제안(올린 때가 같은 대기 줄)을 먼저 붙잡은 뒤에만 적용한다 — 동시에 두 결정이 오면 하나만 된다(409)."""
    from ..verification import normalize_url

    term_id, kind, when = t.term_id, q["kind"], q["queued_at"]

    def claim(decision: str, *, commit: bool = True) -> None:
        if not ds.claim_review(_con, term_id, when, decision, body.by, commit=commit):
            raise HTTPException(409, "그사이 제안이 바뀌었습니다")

    if body.decision == "reject":
        claim("reject")
        return {"ok": True, "term_id": term_id, "status": t.status, "kind": kind}
    if kind == "retire":
        claim("approve", commit=False)
        if m:
            ds.set_verification(_con, m.meaning_id, "rejected", body.by)
        t.status = "retired"
        ds.upsert_term(_con, t, human=True)          # 제외는 사람만 한다
        dashboard.refresh_card(_con, term_id)
        return {"ok": True, "term_id": term_id, "status": t.status, "kind": kind}
    docs = q["docs"]
    if kind == "conflict":
        if body.choice == "keep":
            claim("keep")
            return {"ok": True, "term_id": term_id, "status": t.status, "kind": kind}
        picked = next((d for d in docs if body.choice and normalize_url(d.get("url", "")) == normalize_url(body.choice)), None)
        if picked is None:
            raise HTTPException(400, "고른 설명이 없습니다 (choice: 문서 주소 또는 keep)")
        if not picked.get("proposal"):
            raise HTTPException(400, "이 문서에는 고칠 안이 없어 고를 수 없습니다")
        draft, cites = views.ReviewDoc.model_validate(picked).proposal, [picked.get("url", "")]
    else:
        draft, cites = q["draft"], [d.get("url", "") for d in docs]
    if draft is None:
        raise HTTPException(400, "고칠 안이 없습니다")
    claim("approve", commit=False)                    # 새 판 싣기와 한 트랜잭션 — 싣다가 실패하면 붙잡은 것도 풀린다
    new = ds.publish_fix(_con, term_id, draft, body.by, [c for c in cites if c])
    t.status = "verified"
    ds.upsert_term(_con, t, human=True)
    risk.apply(_con, t)                              # 뜻이 바뀌었으니 뜻풀이의 주의점으로 리스크를 다시 본다
    dashboard.refresh_card(_con, term_id)            # 대시보드 카드의 뜻도 바로 바뀐다
    return {"ok": True, "term_id": term_id, "status": t.status, "kind": kind, "meaning_id": new.meaning_id, "version": new.version}


class RiskIn(BaseModel):
    level: RiskLevel | None  # None 이면 사람의 결정을 지우고 규칙 판정으로 돌아간다
    by: str = "reviewer"     # 결정한 사람 — 프론트가 세션의 계정 이름을 넣는다


@app.post("/review/{term_id}/risk")
def decide_risk(term_id: str, body: RiskIn, x_frontend_token: str = Header(default="")):
    # 리스크 수준도 검수자가 덮어쓸 수 있다(Plan 03). 사람의 결정이 규칙보다 우선한다.
    if not frontend_token_ok(x_frontend_token):
        raise HTTPException(401, "검수 권한이 필요합니다")
    t = ds.get_term(_con, term_id)
    if not t:
        raise HTTPException(404, "not found")
    t.risk_human = body.level
    t.risk_decided_by, t.risk_decided_at = body.by, datetime.now(timezone.utc)   # 지운 것도 누가 언제 지웠는지 남긴다
    risk.apply(_con, t, human=True)
    dashboard.refresh_card(_con, term_id)
    return {"ok": True, "term_id": term_id, "risk_level": t.risk_level, "risk_rule_level": t.risk_rule_level,
            "risk_decided_by": t.risk_decided_by}


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
            with db.session() as con:  # 응답 헤더가 나간 뒤에도 돌므로 요청 연결과 별도로 빌린다
                a = ask_stage.run(con, q[:500], body.lang, body.history[-6:],
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
    return board_stage.cached(_con) or board_stage.build(_con)


@app.get("/terms/{term_id}/topic", response_model=Topic | None)
def term_topic(term_id: str):
    """용어가 든 주제 하나 — 사전 항목이 관련 표현을 찾으려고 보드 전체(1.5MB)를 받지 않게. 없으면 null."""
    t = _public_term(term_id)
    b = board_stage.cached(_con)
    return board_stage.topic_of(b, term_id, t.canonical) if t and b else None


@app.get("/candidates", dependencies=[Depends(_review_access)])
def candidates():
    return [c.model_dump() for c in ds.candidates(_con, "new", 100)]


@app.get("/trends/why")
def trends_why(region: str | None = None):
    """급증 원인 설명 목록 (근거 id·관련 인물 포함)."""
    out = [x.model_dump(mode="json") for x in ds.explanations_by_region(_con).values()]
    return [x for x in out if not region or x["region"] == region]


@app.get("/meta")
def meta():
    """갱신 시각: 마지막 정상 게시(last_run, 지도·대시보드 게시가 모두 성공한 때)와 그게 STALE_AFTER_HOURS(12시간)보다 오래됐는지(stale),
    보드 생성 시각, 용어 수. last_run 은 이름만 예전 그대로다 — 어느 단계든 끝난 때를 쓰면 수집만 돌아도 새 자료로 보였다.
    stale 은 게시가 멈춘 것이지 수집원이 멈춘 것이 아니다 — 수집원이 모두 실패해도 저장된 행으로 게시는 성공한다(ds.PUBLISH_STAGES)."""
    stamp = ds.cache_stamp(_con, "board")              # 보드 본문(1.3MB)·용어 11,000개를 읽지 않는다 — 150바이트 응답이 2.6초였다(10-04)
    published = ds.last_published(_con)
    active = _con.execute("SELECT publication_id FROM publication_state WHERE singleton=1").fetchone()
    return {"publication_id": active[0] if active else None, "last_run": published, "stale": ds.is_stale(published), "board_generated_at": stamp[0] if stamp else None,
            "collected_at": ds.last_collected(_con),
            "terms": ds.count_terms(_con, ("verified", "needs_review")), "explanations": len(ds.explanations_by_region(_con))}


@app.get("/updates")
def updates(hours: int = 48, kinds: str | None = None, limit: int = 100):
    """최근 변화 피드 {items, counts, total}. 기본은 이용자에게 보일 종류(새로 확인·뜻 바뀜·검색 급증)만.
    kinds=all 이면 작업 기록(새로 포착·재조사·뜻 제안·검수 결정)까지, 쉼표로 골라 받을 수도 있다 — 관리 화면용."""
    if kinds == "all":
        wanted = ds.UPDATE_KINDS
    elif kinds:
        wanted = tuple(k for k in ds.UPDATE_KINDS if k in kinds.split(","))
    else:
        wanted = ds.USER_UPDATE_KINDS
    return ds.update_feed(_con, hours=max(1, min(hours, 168)), kinds=wanted, limit=max(1, min(limit, 300)))


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
    _public_term(term_id)
    return views.term_graph(_con, term_id)


_recommend_limit = recommend_stage.RateLimit()
# 사진은 메모리에서만(ADR 0002 §4). Starlette 는 1MB 넘는 업로드를 임시 파일(디스크)로 넘기므로 한도까지는 메모리에 두게 올리고,
# 그보다 큰 요청은 폼을 읽기 전에 Content-Length 로 막는다.
MultiPartParser.spool_max_size = recommend_stage.MAX_IMAGE + 1024 * 1024


# 몸통 크기 한도 — 폼·JSON 을 읽기 전에 Content-Length 로 막는다. 만들기는 제품 설명(수백 자)과 밈 id 몇 개뿐이다(검토 3차: 수백 KB 설명이 프롬프트로 갔다)
_BODY_CAP = {"/recommend": recommend_stage.MAX_IMAGE + 64 * 1024, "/campaign/poster": recommend_stage.MAX_IMAGE + 64 * 1024,
             "/generate": 16 * 1024, "/copy-check": 16 * 1024}


@app.middleware("http")
async def _upload_cap(request, call_next):
    cap = _BODY_CAP.get(request.url.path) if request.method == "POST" else None
    if cap:
        length = request.headers.get("content-length")
        if length is None:          # 길이를 밝히지 않는 조각 전송(chunked)은 크기를 미리 막을 수 없다 — 받지 않는다(검토 2차)
            return JSONResponse({"detail": "요청 길이가 필요합니다"}, status_code=411)
        if not length.isdigit() or int(length) > cap:
            return JSONResponse({"detail": "사진은 5MB까지입니다" if request.url.path in ("/recommend", "/campaign/poster") else "요청이 너무 큽니다"}, status_code=413)
    return await call_next(request)


# 모델을 부르는 요청은 한 인스턴스에 동시에 둘까지 — 분당 한도만으로는 느린 요청(생성 10~85초)이 쌓여 작업 스레드·DB 연결을 다 차지해
# 사전·대시보드 읽기까지 멈출 수 있었다(검토 3차). 자리가 없으면 기다리지 않고 429.
MODEL_SLOTS = 2
_model_slots = threading.BoundedSemaphore(MODEL_SLOTS)


@contextmanager
def _model_slot():
    if not _model_slots.acquire(blocking=False):
        raise HTTPException(429, "지금은 요청이 많습니다. 잠시 뒤에 다시 시도해 주세요")
    try:
        yield
    finally:
        _model_slots.release()


@app.post("/recommend", response_model=views.RecommendResult)
def recommend(text: str = Form(""), regions: str = Form(""), tone: str = Form("friendly"), lang: str = Form("ko"),
              image: UploadFile | None = File(None), term: str = Form("")):
    """사진 한 장이나 홍보 문구(또는 둘 다)로 밈 추천 (Plan 07). 사진은 메모리에서만 읽고 저장·기록하지 않는다.
    모델 호출이 막히는 작업이라 동기 함수로 둔다(작업 스레드에서 돈다)."""
    if tone not in recommend_stage.TONES:
        raise HTTPException(400, "tone 은 friendly·witty·premium 가운데 하나입니다")
    text = text.strip()
    if len(text) > 500:
        raise HTTPException(400, "홍보 문구는 500자까지입니다")
    picture: tuple[bytes, str] | None = None
    if image is not None:
        data = image.file.read(recommend_stage.MAX_IMAGE + 1)
        if len(data) > recommend_stage.MAX_IMAGE:
            raise HTTPException(413, "사진은 5MB까지입니다")
        mime = recommend_stage.sniff_image(data)
        if data and not mime:
            raise HTTPException(415, "JPEG·PNG·WebP 사진만 받습니다")
        picture = (data, mime) if data else None
    if not text and not picture:
        raise HTTPException(400, "사진이나 홍보 문구 가운데 하나는 넣어 주세요")
    if not _recommend_limit.allow(time.monotonic()):
        raise HTTPException(429, "잠시 뒤에 다시 시도해 주세요")
    wanted = [r.strip().upper() for r in regions.split(",") if r.strip()]
    ui = "en" if lang == "en" else "ko"
    if not recommend_stage.ready(_con, wanted):      # 비교할 후보가 없는 지역 — 모델을 부르지 않고 알린다
        return views.RecommendResult(brief=None, brief_source="none", regions=dashboard.chosen_regions(wanted), tone=tone,  # type: ignore[arg-type]
                                     items=[], considered=0, untagged=len(dashboard.cards(_con, wanted)))
    with _model_slot():
        try:
            brief, source = recommend_stage.understand(_con, text, picture, ui)
        except recommend_stage.Unavailable as e:
            raise HTTPException(503, str(e)) from None
    # term: 사전 항목의 '이 밈으로 만들기' 에서 먼저 고른 밈 id — 순위 밖이어도 목록에 넣는다(규칙 문턱만 건너뛴다)
    return recommend_stage.recommend(_con, brief, source, wanted, tone, term.strip()[:64] or None)


class GenerateIn(BaseModel):
    term_ids: list[str] = Field(min_length=1, max_length=3)   # 추천에서 고른 밈
    brief: ProductBrief                                     # 추천이 읽어 낸 제품 설명 (다시 읽지 않는다 — 모델 호출을 아낀다)
    region: str                                             # 결과물을 쓸 목표 지역 하나 — 그 나라 말로 만든다
    tone: CampaignTone = "friendly"
    lang: str = "ko"                                        # 화면 언어 — 설명 칸을 그 말로


_generate_limit = recommend_stage.RateLimit(per_minute=10)


@app.post("/generate", response_model=views.GenerationResult)
def generate(body: GenerateIn):
    """SNS 카피·숏폼 대본·썸네일 구성안 (Plan 08). 모델은 생성 한 번, 다시 만들어도 두 번(검사는 규칙). 결과는 저장하지 않는다."""
    region = body.region.strip().upper()
    if region not in REGIONS_FOCUS:
        raise HTTPException(400, "목표 지역 가운데 하나를 골라 주세요")
    if not _generate_limit.allow(time.monotonic()):
        raise HTTPException(429, "잠시 뒤에 다시 시도해 주세요")
    try:
        with _model_slot():
            return generate_stage.run(_con, body.term_ids, body.brief, region, body.tone, "en" if body.lang == "en" else "ko")
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    except generate_stage.Unavailable as e:
        raise HTTPException(503, str(e)) from None


_poster_limit = recommend_stage.RateLimit(per_minute=5)


@app.post("/campaign/poster", response_model=views.PosterResult)
def campaign_poster(market: str = Form(...), brief: str = Form(""), text: str = Form(""), term_ids: str = Form(""),
                    image: UploadFile | None = File(None)):
    """시장별 포스터 시안. 구성안(지시문)은 규칙이 만들고, 이미지 생성이 켜져 있으면(IMAGE_BACKEND) 모델 한 번으로 그린다.
    꺼져 있으면 enabled=false 와 구성안만 200 으로 — 화면이 자리 표시를 보인다. 그림에는 글자가 없고 검사한 문구는 화면이 얹는다.
    brief 는 추천이 읽어 낸 제품 설명(JSON, 다시 읽지 않는다), 없으면 text 를 제품 설명으로 쓴다. 사진·결과는 저장하지 않는다."""
    market = market.strip().upper()
    if market not in poster_stage.MARKETS:
        raise HTTPException(400, "시장은 KR·JP·US 가운데 하나입니다")
    if len(brief) > 8 * 1024 or len(text) > 500:
        raise HTTPException(400, "제품 설명이 너무 깁니다")
    try:
        product = ProductBrief.model_validate_json(brief) if brief.strip() else \
            ProductBrief(product=text.strip(), category="lifestyle", feelings=[]) if text.strip() else None
    except ValueError:
        raise HTTPException(400, "제품 설명 형식이 맞지 않습니다") from None
    if product is None:
        raise HTTPException(400, "제품 설명이나 문구 가운데 하나는 넣어 주세요")
    ids = [t.strip()[:64] for t in term_ids.split(",") if t.strip()]
    if len(ids) > 3:
        raise HTTPException(400, "밈은 셋까지 고를 수 있습니다")
    photo: bytes | None = None
    if image is not None:
        data = image.file.read(recommend_stage.MAX_IMAGE + 1)
        if len(data) > recommend_stage.MAX_IMAGE:
            raise HTTPException(413, "사진은 5MB까지입니다")
        if data and not recommend_stage.sniff_image(data):
            raise HTTPException(415, "JPEG·PNG·WebP 사진만 받습니다")
        photo = data or None
    fits = ds.all_fits(_con) if ids else {}
    memes = [([t.canonical, *t.aliases], fits[i][1] if i in fits else None) for i in ids if (t := ds.get_term(_con, i))]
    plan = poster_stage.plan(product, market, memes)
    if not poster_stage.enabled():
        return views.PosterResult(enabled=False, plan=plan)
    if not _poster_limit.allow(time.monotonic()):
        raise HTTPException(429, "잠시 뒤에 다시 시도해 주세요")
    try:
        with _model_slot():
            images = poster_stage.generate(_con, plan, photo)
    except poster_stage.NotConfigured:
        return views.PosterResult(enabled=False, plan=plan)
    except poster_stage.Unavailable as e:
        raise HTTPException(503, str(e)) from None
    return views.PosterResult(enabled=True, plan=plan, images=[f"data:{poster_stage.sniff_image(b)};base64,{base64.b64encode(b).decode('ascii')}" for b in images])


_briefing_limit = recommend_stage.RateLimit(per_minute=30)


@app.get("/briefing", response_model=views.Briefing)
def trend_briefing(regions: str = "", lang: str = "ko", summary: bool = True):
    """트렌드 브리핑 — 고른 지역의 대시보드를 한 장으로. 목록·건수는 대시보드 규칙, 요약 문장만 모델(갱신 시각·지역·언어마다 한 번).
    모델이 없거나 자리·한도가 없거나 실패하면 summary 를 비워 두고 화면이 규칙 문장을 쓴다 — 보고서는 늘 열린다.
    summary=false 면 모델을 부르지 않는다(이미 만든 요약은 준다) — 대시보드의 '한눈에 보기' 가 열 때마다 모델을 부르지 않게."""
    ui = "en" if lang == "en" else "ko"
    b = briefing_stage.build(_con, [r.strip().upper() for r in regions.split(",") if r.strip()])
    hit = briefing_stage.cached(b, ui)
    if hit:
        b.summary, b.summary_source = hit  # type: ignore[assignment]
    elif summary and briefing_stage.model_ready() and _briefing_limit.allow(time.monotonic()) and _model_slots.acquire(blocking=False):
        try:
            b.summary, b.summary_source = briefing_stage.summarize(_con, b, ui)  # type: ignore[assignment]
        except Exception:      # 예산·장애·형식 — 규칙 문장으로 대신한다
            b.summary, b.summary_source = None, "none"
        finally:
            _model_slots.release()
    return b


class CopyCheckIn(BaseModel):
    text: str = Field(max_length=copycheck.MAX_TEXT)
    region: str
    lang: str = "ko"


_copy_limit = recommend_stage.RateLimit(per_minute=20)


@app.post("/copy-check", response_model=views.CopyCheck)
def copy_check(body: CopyCheckIn):
    """카피 검사 — 문구에 든 밈을 사전으로 찾고, 고른 시장에서 써도 되는지는 규칙으로, 뜻에 맞게 썼는지는 모델 의견으로.
    문구는 저장하지 않고 기록에도 남기지 않는다. 모델 자리가 없거나 실패해도 규칙 결과는 돌려준다(fit_source 로 알린다)."""
    region = body.region.strip().upper()
    if region not in REGIONS_FOCUS:
        raise HTTPException(400, "목표 지역 가운데 하나를 골라 주세요")
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "검사할 문구를 넣어 주세요")
    if not _copy_limit.allow(time.monotonic()):
        raise HTTPException(429, "잠시 뒤에 다시 시도해 주세요")
    result, terms = copycheck.check(_con, text, region)
    if not terms or not copycheck.model_ready():
        return result
    if not _model_slots.acquire(blocking=False):
        result.fit_source = "busy"
        return result
    try:
        return copycheck.fit(_con, text, result, terms, "en" if body.lang == "en" else "ko")
    except Exception:
        result.fit_source = "failed"
        return result
    finally:
        _model_slots.release()


@app.get("/dashboard", response_model=views.KeywordBoard)
def keyword_dashboard(regions: str = "", page: int = Query(1, ge=1, le=10_000), summary: bool = False):
    """키워드 대시보드 (Plan 04). regions 는 쉼표로 (KR,JP,GLOBAL). 없거나 모르는 값뿐이면 목표 지역 전체.
    page 는 목록마다 몇째 쪽(30개씩)인지 — 건수는 totals 에 있다. summary=1 이면 지역마다 주의 수·대표 밈(세계 지도)."""
    return dashboard.board(_con, [r.strip().upper() for r in regions.split(",") if r.strip()], page, summary)


@app.get("/dashboard/cards", response_model=list[views.KeywordCard])
def keyword_cards(ids: str = Query("", max_length=8_000)):
    """용어 id(쉼표, 200개까지)의 대시보드 카드 — 최근 변화 행에 단계·쓸 때 조심을 붙인다. 둘러보는 목록에 없는 말은 빠진다."""
    want = [i.strip() for i in ids.split(",") if i.strip()][:200]
    return dashboard.cards_by_id(_con, want) if want else []


@app.get("/terms/{term_id}/signals", response_model=views.KeywordCard | None)
def term_signals(term_id: str, regions: str = ""):
    """용어 하나의 쓰임 신호 — 검색 순위·출몰 커뮤니티·뉘앙스·최근 근거 (사전 화면).
    regions 는 대시보드와 같은 쉼표 목록(KR,JP). 없으면 모든 지역 합계."""
    _public_term(term_id)
    c = dashboard.card(_con, term_id, [r.strip().upper() for r in regions.split(",") if r.strip()] or None)
    if not c:
        raise HTTPException(404, "not found")
    return c


@app.get("/terms/{term_id}/generations")
def generations(term_id: str):
    """네이버 데이터랩 세대별 검색 곡선 (한국어 용어만 있음)."""
    _public_term(term_id)
    curves = ds.get_gen_curves(_con, term_id)
    out = []
    for g, pts in curves.items():
        peak = max(pts, key=lambda p: p[1]) if pts else None
        out.append({"generation": g, "points": pts, "peak_date": peak[0] if peak else None})
    return out
