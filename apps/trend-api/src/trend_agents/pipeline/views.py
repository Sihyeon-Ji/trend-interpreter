"""API 응답 뷰 모델 — 프론트 `apps/trend-web/lib/types.ts` 와 1:1. 화면은 이 모양만 안다."""
from __future__ import annotations

import sqlite3
from typing import Literal

from pydantic import BaseModel

from ..lifecycle import recheck_interval_days
from ..schemas import Evidence, EvidenceBrief, Meaning, MeaningText, Segment, Term
from ..storage import dictionary_store as ds

CATEGORY_MAP = {"slang": "slang", "meme": "meme", "song": "song", "drama": "other", "dance": "other", "news": "other", "geopolitics": "other", "product": "other", "other": "other"}


class TermUsage(BaseModel):
    segment: Segment
    first_seen: str
    share: float


class WeeklyPoint(BaseModel):
    week_start: str
    count: int


class TermMedia(BaseModel):
    """대표 그림·영상. 파일을 받아 두지 않고 주소만 둔다 — 그림은 위키미디어 공용의 자유 라이선스,
    영상은 유튜브 주소(화면에서 공식 플레이어로 끼운다). license·attribution 을 함께 보여 준다."""

    kind: Literal["image", "video"]
    url: str
    page_url: str = ""
    title: str = ""
    license: str = ""
    attribution: str = ""


class TermRecord(BaseModel):
    term: Term
    category: Literal["slang", "meme", "song", "other"]
    plain: str
    ko: MeaningText | None = None   # 한국어 화면이 쓸 뜻. 없으면 저장된 원문을 그대로 보여 준다
    en: MeaningText | None = None
    meanings: list[Meaning]
    evidences: list[Evidence]
    usage: list[TermUsage]
    weekly: list[WeeklyPoint]
    recheck_days: int
    media: list[TermMedia] = []
    gate_reasons: list[str] | None = None


class PipelineStage(BaseModel):
    key: str
    label: str
    count_24h: int
    status: Literal["ok", "warn", "zero"]
    note: str | None = None


class ReviewItem(BaseModel):
    term_id: str
    canonical: str
    proposed: Meaning
    reasons: list[str]
    evidence_count: int
    queued_at: str


STAGE_LABELS = {
    "collect.youtube": "영상 수집", "collect.news": "뉴스 수집", "collect.trends_rss": "검색 트렌드(지금)", "collect.trends_bq": "검색 트렌드(일별)",
    "collect.wikipedia": "위키 조회 상위", "collect.mentions": "용어 언급 추적", "collect.retention": "30일 보존 정리", "classify": "검색어 분류", "spikes": "급증 원인 조사", "candidates": "후보 추출",
    "interpret": "쇼츠 해석", "research": "조사·확인", "track": "추세 갱신", "naver": "한국 세대 신호(네이버)", "translate": "언어판", "topics": "나라별 차이 서술", "board": "보드 생성",
}


def term_record(con: sqlite3.Connection, t: Term) -> TermRecord:
    meanings = ds.list_meanings(con, t.term_id)
    ko = ds.get_translation(con, t.term_id, "ko")
    en = ds.get_translation(con, t.term_id, "en")
    usage = [TermUsage(segment=Segment(segment_id=u["segment_id"], generation=u["generation"], region=u["region"]), first_seen=u["first_seen"], share=u["share"])
             for u in ds.get_usage(con, t.term_id)]
    weekly = [WeeklyPoint(week_start=w, count=c) for w, c in ds.get_weekly(con, t.term_id)]
    reasons = ds.gate_reasons(con, t.term_id) if t.status == "needs_review" else None
    return TermRecord(term=t, category=CATEGORY_MAP.get(t.category, "other"), plain=(ko.plain if ko and ko.plain else ""), ko=ko, en=en,
                      meanings=meanings, evidences=ds.list_evidences(con, t.term_id), usage=usage, weekly=weekly,
                      recheck_days=recheck_interval_days(t.lifecycle),
                      media=[TermMedia(**m) for m in ds.get_media(con, t.term_id) if m["kind"] in ("image", "video")],
                      gate_reasons=reasons or None)


def term_records(con: sqlite3.Connection, statuses: tuple[str, ...] = ("verified",)) -> list[TermRecord]:
    return [term_record(con, t) for t in ds.list_terms(con, statuses)]


def pipeline_stages(con: sqlite3.Connection) -> list[PipelineStage]:
    counts = ds.stage_counts_24h(con)
    out = []
    for key, label in STAGE_LABELS.items():
        cnt, status, note = counts.get(key, (0, "", ""))
        st: Literal["ok", "warn", "zero"] = "warn" if status in ("error", "skipped") else ("ok" if (cnt > 0 or key == "collect.retention") else "zero")
        out.append(PipelineStage(key=key, label=label, count_24h=cnt, status=st, note=note or None))
    return out


def review_items(con: sqlite3.Connection) -> list[ReviewItem]:
    out = []
    for q in ds.review_queue(con):
        t = ds.get_term(con, q["term_id"])
        m = ds.current_meaning(con, q["term_id"])
        if not t or not m:
            continue
        out.append(ReviewItem(term_id=t.term_id, canonical=t.canonical, proposed=m, reasons=q["reasons"], evidence_count=q["evidence_count"], queued_at=q["queued_at"]))
    return out


class ReviewStats(BaseModel):
    verified_auto: int
    verified_human: int
    needs_review: int
    rejected: int


def review_stats(con: sqlite3.Connection) -> ReviewStats:
    rows = dict(con.execute("SELECT verification, COUNT(*) FROM meanings WHERE valid_to IS NULL GROUP BY verification").fetchall())
    return ReviewStats(verified_auto=rows.get("verified_auto", 0), verified_human=rows.get("verified_human", 0),
                       needs_review=len(ds.review_queue(con)), rejected=rows.get("rejected", 0))


class CountryPage(BaseModel):
    region: str
    items: list  # TrendItem
    why: list  # TrendWhy
    terms: list[TermRecord]
    generation_share: dict[str, float]
    updated_at: str | None


def country_page(con: sqlite3.Connection, region: str) -> CountryPage:
    from ..schemas import TrendBoard
    from ..storage import dictionary_store as ds2

    cached = ds2.cache_get(con, "board")
    board = TrendBoard.model_validate_json(cached[0]) if cached else None
    items = [i for i in board.items if i.region == region] if board else []
    why = [w for w in board.why if w.region == region] if board else []
    recs = [term_record(con, t) for t in ds2.list_terms(con, ("verified", "needs_review")) if any(u["region"] == region for u in ds2.get_usage(con, t.term_id))]
    share: dict[str, float] = {}
    for r in recs:
        for u in r.usage:
            if u.segment.region == region:
                share[u.segment.generation] = share.get(u.segment.generation, 0) + u.share
    total = sum(share.values()) or 1
    return CountryPage(region=region, items=items, why=why, terms=recs, generation_share={k: round(v / total, 3) for k, v in share.items()},
                       updated_at=board.generated_at.isoformat() if board else None)


# ---------- 지식그래프 (급증 검색어 ↔ 인물·위키·근거·사전 용어) ----------

class QueryGraph(BaseModel):
    """급증 검색어 하나의 이웃. 인물·위키는 spikes 가 근거 원문에서 앵커한 것만 — LLM 이 지어낸 이름은 여기 없다."""

    key: str
    term: str
    region: str
    explained: bool
    actors: list[str]
    wiki: list[str]
    term_id: str | None
    evidence: list[EvidenceBrief]


class SharedNode(BaseModel):
    """여러 급증 검색어에 함께 걸린 인물·위키. regions 가 2개 이상이면 나라를 건너 같은 인물·사건이 뜨는 것."""

    type: Literal["actor", "wiki"]
    id: str
    label: str
    queries: list[str]
    regions: list[str]


class TermGraphQuery(BaseModel):
    key: str
    term: str
    region: str
    date: str | None


def _label(node_type: str, node_id: str) -> str:
    return node_id.split(":", 1)[1] if node_type == "wiki" and ":" in node_id else node_id


def query_graph(con: sqlite3.Connection, key: str, limit_evidence: int = 12) -> QueryGraph | None:
    g = ds.graph_query(con, key)
    if not g:
        return None
    evs = ds.list_evidences(con, f"q|{key}")
    return QueryGraph(key=g["key"], term=g["term"], region=g["region"], explained=g["explained"], actors=g["actors"], wiki=g["wiki"], term_id=g["term_id"],
                      evidence=[EvidenceBrief(kind=e.kind, source_domain=e.source_domain, title=e.title or e.excerpt, url=e.url, observed_at=e.observed_at) for e in evs[:limit_evidence]])


def shared_nodes(con: sqlite3.Connection, min_queries: int = 2) -> list[SharedNode]:
    return [SharedNode(type=n["type"], id=n["id"], label=_label(n["type"], n["id"]), queries=n["queries"], regions=n["regions"])
            for n in ds.graph_shared_nodes(con, min_queries) if n["type"] in ("actor", "wiki")]


def term_graph(con: sqlite3.Connection, term_id: str) -> list[TermGraphQuery]:
    return [TermGraphQuery(**q) for q in ds.graph_term_queries(con, term_id)]
