"""사전 항목의 '지금 다시 분류해 보기' – 배포본에서 Gemma 가 도는 모습(ejchoi 계획 1단계, Plan 14 설계).

검수자만 누른다(10-10 결정). 최신 기사 제목을 모아 표제어가 든 문장만 남기고, 배치 리스크 단계(pipeline/risk.py)와 같은 지시문·출력
형식으로 GPU gateway 의 Gemma 에 분류시킨 뒤, 같은 규칙(risk.judge_labeled)으로 수준을 매긴다. 결과는 배치 판정과 나란히 보일 뿐
공개 사전·근거 표에 쓰지 않는다. GPU 가 꺼져 있거나 적재 중이면 기다리지 않고 '준비 안 됨' 으로 돌려준다(GPU 는 데모·녹화 때만 켠다).
실행 기록(live_risk_runs)에는 시각·용어·상태·문장 수·걸린 시간·수준·모델만 남긴다 – 문장·모델 출력 원문은 남기지 않는다.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

from .. import config
from ..collectors import news_rss
from ..interpreters import gpu_gateway, local_chat
from ..schemas import Evidence, EvidenceLabel
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from . import risk
from .collect import home_edition
from .match import mentions

READY_WAIT_S = 3          # GPU readiness 확인 – 모델 적재 중이면 30초씩 기다리지 않는다
NEWS_WAIT_S = 8
CACHE_S = 600             # 같은 용어는 10분 안에 다시 부르지 않는다(Plan 14)
_cache: dict[str, tuple[float, "LiveRisk"]] = {}
_cache_lock = threading.Lock()
_run_lock = threading.Lock()   # GPU 한 장 – 한 번에 하나만. 돌고 있으면 기다리지 않고 busy

Status = Literal["ok", "not_ready", "busy", "too_few", "source_unavailable", "failed"]


class LiveSentence(BaseModel):
    title: str
    source: str
    url: str
    published_at: datetime | None = None
    polarity: str            # positive · neutral · negative · offtopic
    risk: str


class LiveRisk(BaseModel):
    status: Status
    term_id: str
    level: str | None = None              # 실시간 분류의 규칙 판정
    reasons: list[str] = []
    batch_level: str | None = None        # 배치(공개 사전)의 규칙 판정
    batch_reasons: list[str] = []
    same_as_batch: bool | None = None
    sentences: list[LiveSentence] = []
    found: int = 0                        # 표제어가 든 기사 제목 수
    model: str | None = None
    seconds: float | None = None
    checked_at: datetime | None = None
    cached: bool = False


def _log(con: Connection, out: "LiveRisk | RiskRerun", kind: str = "live") -> None:
    level = out.level if isinstance(out, LiveRisk) else out.after_level
    con.execute("INSERT OR IGNORE INTO live_risk_runs (run_at, term_id, status, sentences, seconds, level, model, kind) VALUES (?,?,?,?,?,?,?,?)",
                ((out.checked_at or datetime.now(timezone.utc)).isoformat(), out.term_id, out.status, len(out.sentences),
                 out.seconds, level, out.model, kind))
    con.commit()


def _evidence(i: int, n) -> Evidence:
    return Evidence(evidence_id=f"live:{i}", kind="news", url=n.link, title=n.title,
                    source_domain=n.source or urlsplit(n.link).hostname or "news",
                    observed_at=n.published_at or datetime.now(timezone.utc))


def run(con: Connection, term) -> LiveRisk:
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(term.term_id)
    if hit and now - hit[0] < CACHE_S:
        return hit[1].model_copy(update={"cached": True})
    if not _run_lock.acquire(blocking=False):
        return LiveRisk(status="busy", term_id=term.term_id)
    try:
        out = _run(con, term)
    finally:
        _run_lock.release()
    if out.status == "ok":
        with _cache_lock:
            _cache[term.term_id] = (time.monotonic(), out)
    return out


def _run(con: Connection, term) -> LiveRisk:
    started = time.monotonic()
    model = config.GPU_GATEWAY_MODEL or None
    base = LiveRisk(status="not_ready", term_id=term.term_id, batch_level=term.risk_level, batch_reasons=list(term.risk_reasons or []),
                    model=model, checked_at=datetime.now(timezone.utc))
    if not gpu_gateway.configured() or not model or not gpu_gateway.available(model, timeout=READY_WAIT_S):
        return base                                   # 기다리지 않는다 – 화면이 '준비 안 됨' 을 보인다(기록도 남기지 않는다)
    try:
        items = news_rss.fetch_news(home_edition(term), query=term.canonical, limit=30, timeout=NEWS_WAIT_S)
    except Exception:
        out = base.model_copy(update={"status": "source_unavailable", "seconds": round(time.monotonic() - started, 1)})
        _log(con, out)
        return out
    seen, keep = set(), []
    for n in items:                                   # 표제어가 실제로 든 제목만 – 배치(risk._usage)와 같은 거르기
        if n.title not in seen and mentions(n.title, term.canonical, term.aliases):
            seen.add(n.title)
            keep.append(n)
    keep = keep[:risk.PER_TERM]
    if len(keep) < risk.MIN_LABELED:                  # 5개 미만이면 모델을 부르지 않는다
        out = base.model_copy(update={"status": "too_few", "found": len(keep), "seconds": round(time.monotonic() - started, 1)})
        _log(con, out)
        return out
    evs = [_evidence(i, n) for i, n in enumerate(keep)]
    m = ds.current_meaning(con, term.term_id)
    prompt = risk.PROMPT.format(term=term.canonical, definition=(m.definition if m else "")[:160],
                                items="\n".join(f"{i}. {e.title[:220]}" for i, e in enumerate(evs)))
    try:
        parsed = local_chat.structured(prompt, list[EvidenceLabel], model=model)
    except Exception:                                 # 장애·형식 실패 – 원문은 남기지 않는다
        out = base.model_copy(update={"status": "failed", "found": len(keep), "seconds": round(time.monotonic() - started, 1)})
        _log(con, out)
        return out
    labels = {p.i: p for p in (parsed or []) if 0 <= p.i < len(evs)}
    sentences, labeled, offtopic = [], [], 0
    for i, (e, n) in enumerate(zip(evs, keep)):
        p = labels.get(i)
        polarity = "neutral" if p is None else (p.polarity if p.on_topic else "offtopic")
        kind = "none" if p is None or not p.on_topic else p.risk
        sentences.append(LiveSentence(title=e.title, source=e.source_domain, url=e.url, published_at=n.published_at, polarity=polarity, risk=kind))
        if polarity == "offtopic":
            offtopic += 1
        elif p is not None:
            labeled.append((e, polarity, kind))
    level, reasons = risk.judge_labeled(con, term, labeled, offtopic)
    out = base.model_copy(update={"status": "ok", "level": level, "reasons": reasons, "same_as_batch": level == term.risk_level,
                                  "sentences": sentences, "found": len(keep), "seconds": round(time.monotonic() - started, 1)})
    _log(con, out)
    return out


# ── 2단계: 관리자 수동 실행(/admin/status) ─────────────────────────────────────────────
# 배치 리스크 단계(risk.classify)를 고른 용어 하나에 지금 GPU 에서 다시 돌려 본다. 대상은 운영 DB 에 이미 있는 쓰임 문장(risk._usage)이라
# 수집 키가 필요 없다. 첫 판은 미리보기(10-10 결정) – 이전 분류·판정과 새 분류·판정의 차이를 화면에만 보이고 저장하지 않는다.


class RerunSentence(BaseModel):
    text: str | None = None               # 인용할 수 있는 근거(기사·쇼츠·문서)만. 커뮤니티·SNS 글은 비운다(ADR 0003)
    source: str | None = None
    kind: str
    before_polarity: str | None = None    # 배치가 붙인 분류. 아직 분류 전이면 None
    before_risk: str | None = None
    polarity: str                         # 지금 분류 – positive · neutral · negative · offtopic
    risk: str
    changed: bool


class RiskRerun(BaseModel):
    status: Literal["ok", "not_ready", "busy", "too_few", "failed"]
    term_id: str
    stage: Literal["risk"] = "risk"
    public_level: str | None = None       # 공개 사전의 수준(검수자 결정이 있으면 그것)
    before_level: str | None = None       # 저장된 분류로 매긴 규칙 판정
    before_reasons: list[str] = []
    after_level: str | None = None        # 지금 분류로 매긴 규칙 판정
    after_reasons: list[str] = []
    changed: int = 0                      # 분류가 달라진 문장 수
    sentences: list[RerunSentence] = []
    model: str | None = None
    seconds: float | None = None
    checked_at: datetime | None = None


def rerun(con: Connection, term) -> RiskRerun:
    if not _run_lock.acquire(blocking=False):          # 실시간 분류와 같은 GPU – 한 번에 하나
        return RiskRerun(status="busy", term_id=term.term_id)
    try:
        return _rerun(con, term)
    finally:
        _run_lock.release()


def _rerun(con: Connection, term) -> RiskRerun:
    started = time.monotonic()
    model = config.GPU_GATEWAY_MODEL or None
    before_level, before_reasons = risk.judge(con, term)
    base = RiskRerun(status="not_ready", term_id=term.term_id, public_level=term.risk_level, before_level=before_level,
                     before_reasons=before_reasons, model=model, checked_at=datetime.now(timezone.utc))
    if not gpu_gateway.configured() or not model or not gpu_gateway.available(model, timeout=READY_WAIT_S):
        return base
    evs = risk._usage(con, term)
    if not evs:
        out = base.model_copy(update={"status": "too_few", "seconds": round(time.monotonic() - started, 1)})
        _log(con, out, "rerun")
        return out
    m = ds.current_meaning(con, term.term_id)
    prompt = risk.PROMPT.format(term=term.canonical, definition=(m.definition if m else "")[:160],
                                items="\n".join(f"{i}. {(e.excerpt or e.title)[:220]}" for i, e in enumerate(evs)))
    try:
        parsed = local_chat.structured(prompt, list[EvidenceLabel], model=model)
    except Exception:                                 # 장애·형식 실패 – 원문은 남기지 않는다
        out = base.model_copy(update={"status": "failed", "seconds": round(time.monotonic() - started, 1)})
        _log(con, out, "rerun")
        return out
    labels = {p.i: p for p in (parsed or []) if 0 <= p.i < len(evs)}
    stored = ds.evidence_labels(con, term.term_id)
    sentences, labeled, offtopic = [], [], 0
    for i, e in enumerate(evs):
        p = labels.get(i)
        polarity = "neutral" if p is None else (p.polarity if p.on_topic else "offtopic")
        kind = "none" if p is None or not p.on_topic else p.risk
        bp, br = stored.get(e.evidence_id, (None, None))
        quotable = risk._quotable(e)
        sentences.append(RerunSentence(text=(e.excerpt or e.title).strip()[:220] if quotable else None,
                                       source=e.source_domain if quotable else None, kind=e.kind,
                                       before_polarity=bp, before_risk=br, polarity=polarity, risk=kind,
                                       changed=bp is not None and (bp, br) != (polarity, kind)))
        if polarity == "offtopic":
            offtopic += 1
        elif p is not None:
            labeled.append((e, polarity, kind))
    level, reasons = risk.judge_labeled(con, term, labeled, offtopic)
    out = base.model_copy(update={"status": "ok", "after_level": level, "after_reasons": reasons, "sentences": sentences,
                                  "changed": sum(s.changed for s in sentences), "seconds": round(time.monotonic() - started, 1)})
    _log(con, out, "rerun")
    return out
