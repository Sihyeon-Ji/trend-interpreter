"""API 응답 뷰 모델 — 프론트 `apps/trend-web/lib/types.ts` 와 1:1. 화면은 이 모양만 안다."""
from __future__ import annotations

import hashlib

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

from ..collectors.community import is_community_post
from ..lifecycle import recheck_interval_days
from ..schemas import (CampaignTone, Diffusion, Evidence, EvidenceBrief, Feeling, Lifecycle, Meaning, MeaningDraft, MeaningText, ProductBrief,
                       RiskLevel, Segment, ShortScript, SocialCopy, Term, Text2, ThumbnailPlan)
from ..storage import dictionary_store as ds
from .match import evidence_mentions
from ..storage.db import Connection

CATEGORY_MAP = {"slang": "slang", "meme": "meme", "song": "song", "drama": "other", "dance": "other", "news": "other", "geopolitics": "other", "product": "other", "other": "other"}


class TermUsage(BaseModel):
    segment: Segment
    first_seen: str
    share: float
    source: str = "model"


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


Maker = Literal["gemma", "gemini", "person", "unknown"]


class Provenance(BaseModel):
    """사전 항목 화면의 '이렇게 만들었어요' — 이 뜻을 누가(어느 모델·사람이) 쓰고 무엇으로 확인했나. 기록에 있는 것만 보인다.
    배포된 화면에서 수집 쪽 AI 가 하는 일이 보이지 않았다(공개 저장소 비교, 10-05). 검수자 이름은 넣지 않는다."""
    evidences: int                         # 이 말의 근거 수(화면에 보이는 것)
    drafted_by: Maker | None = None        # 현재 뜻의 초안
    drafted_at: datetime | None = None
    reference: str | None = None           # 참고 문서 도메인(verification.reference_doc) — 자동 확인의 근거
    checked: Literal["person", "rules", "pending"] = "pending"
    checked_at: datetime | None = None     # 사람이 확인한 때(검수 결정 시각)
    audit: Literal["ok", "fix"] | None = None   # 감사관이 출처와 다시 대조한 결과
    rewritten: bool = False                # 감사관이 출처에 맞게 고쳐 쓴 판(created_by 'audit')
    audit_by: Maker | None = None
    risk_sentences: int = 0                # 리스크를 정하려고 분류한 쓰인 문장 수
    risk_by: Maker | None = None
    translated_by: Maker | None = None     # 영어판


class SentenceLabel(BaseModel):
    """근거 문장 하나에 모델이 붙인 분류(Plan 14 0단계). 인용할 수 있는 근거(기사·쇼츠·문서)만 문장을 싣는다."""
    evidence_id: str
    text: str
    url: str = ""
    source_domain: str = ""
    kind: str = ""
    observed_at: datetime | None = None
    on_topic: bool                         # False 면 글자만 같은 딴 이야기 — 판정에서 뺀다
    polarity: Literal["positive", "neutral", "negative"] | None = None
    risk: str = "none"                     # hate·mockery·gender·politics·sexual·none
    by: Maker | None = None
    labeled_at: datetime | None = None


class RiskBreakdown(BaseModel):
    """리스크 판정에 쓴 근거 문장 분류 — 문장별 결과와 규칙이 센 수. 커뮤니티·SNS 글은 문장 없이 건수만(ADR 0003)."""
    sentences: list[SentenceLabel] = []
    community: int = 0                     # 분류했지만 문장을 보이지 않는 커뮤니티·SNS 글 수
    counted: int = 0                       # 그 뜻으로 쓰여 판정에 센 문장(커뮤니티 포함)
    offtopic: int = 0
    risky: int = 0
    negative: int = 0
    min_labeled: int = 5                   # 규칙의 문턱(pipeline/risk.py) — 화면이 '왜 이 수준인지' 를 설명할 때 쓴다
    caution_risky: int = 2
    caution_negative: float = 0.3
    avoid_risky: int = 3


class GemmaStage(BaseModel):
    """'/about/gemma' 의 한 줄 — 파이프라인 단계 하나에서 모델이 남긴 결과 수."""
    stage: Literal["risk", "translate", "fit", "audit", "crosscheck", "research"]
    gemma: int = 0
    gemini: int = 0
    other: int = 0
    terms: int = 0                         # Gemma 결과가 있는 용어 수
    models: list[str] = []                 # Gemma 모델 이름(예: gemma4:12b)
    last_at: datetime | None = None


class ModelCalls(BaseModel):
    """실행 기록의 한 단계·한 모델 — 최근 24시간에 성공한 호출 수와 걸린 시간."""
    stage: str
    label: str
    model: str                             # 화면에 보일 이름(예: gemma4:12b, gemini-3.5-flash)
    maker: Literal["gemma", "gemini", "unknown"]
    calls: int
    seconds: float


class GemmaUsage(BaseModel):
    """배포본에서 Gemma 가 무엇을 만들었는지(Plan 14 0단계). 이미 저장된 기록만 센다 — 모델을 부르지 않는다."""
    stages: list[GemmaStage]
    calls_24h: list[ModelCalls] = []       # 파이프라인 단계별 모델 호출 수·시간(실행 기록 pipeline_runs.model_calls)
    samples: list[dict[str, str]] = []     # Gemma 가 문장을 분류한 대표 항목 {term_id, canonical, lang}
    generated_at: datetime


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
    # 위키 분류가 말하는 유행 시기(연도·연대). 생애주기와 따로 둔다 – 생애주기는 최근 쓰임으로만 정하고, 오래된 밈은 이 값으로 '언제 유행했나' 를 보인다
    popular_year: int | None = None
    popular_decade: int | None = None
    provenance: Provenance | None = None   # 항목 하나를 볼 때만(GET /terms/{id}) 채운다 — 사전 색인에는 없다
    risk_labels: RiskBreakdown | None = None   # 항목 하나를 볼 때만 — 리스크 판정에 쓴 근거 문장별 분류
    regions: list[str] = []   # 보여 줄 지역 — 대시보드와 같은 규칙(dashboard.regions_for: 쓰는 나라 + 그 나라 매체 3곳 이상이 쓴 목표 지역)


class PipelineStage(BaseModel):
    key: str
    label: str
    count_24h: int
    status: Literal["ok", "warn", "zero"]
    note: str | None = None
    # 관리 화면 '수집 현황' — 마지막 실행의 상태를 나눠 보낸다(실패·건너뜀·처리 없음이 한 모양이던 '주의'를 가른다).
    # None 이면 24시간 안에 실행 기록이 없다. 시각은 24시간 창과 상관없이 그 단계의 마지막 실행.
    run_status: Literal["ok", "idle", "skipped", "error"] | None = None
    last_started_at: str | None = None
    last_finished_at: str | None = None


ReviewKind = Literal["new", "correction", "conflict", "retire"]


class ReviewDoc(BaseModel):
    """제안의 근거가 된 참고 문서 한 쪽(Plan 12). 위키끼리 다를 때(conflict)는 사람이 고르는 설명이다 — proposal 이 있는 것만 고를 수 있고,
    고르면 고칠 안과 같은 길(새 판)로 간다. summary 는 짧은 발췌나 요약뿐, 문서 본문은 두지 않는다."""

    wiki: str
    url: str
    summary: str = ""
    proposal: MeaningDraft | None = None


class ReviewItem(BaseModel):
    """검수 한 건. kind 마다 보이는 것이 다르다(Plan 12 §3).
    new         조사 결과 — proposed 가 확인 전인 지금 판, current 는 그 앞의 확인된 판(없으면 새 말)
    correction  고칠 안 — current 가 공개 중인 지금 뜻, draft 가 고칠 안(승인하면 새 판)
    conflict    위키끼리 다름 — current 와 docs(문서마다의 설명)
    retire      사전에서 뺄지 — current 와 사유·docs
    meaning_id 는 결정과 함께 되돌려 보낼 뜻(new 는 proposed, 나머지는 current), token 은 이 제안의 표(올린 때·내용) —
    둘 가운데 하나라도 그사이 바뀌었으면 서버가 409 로 막는다. 새 말 밖의 제안은 둘 다 보내야 한다."""

    term_id: str
    canonical: str
    kind: ReviewKind = "new"
    meaning_id: str | None = None
    token: str = ""
    proposed: Meaning | None = None
    draft: MeaningDraft | None = None
    reasons: list[str]
    evidence_count: int
    queued_at: str
    # 검수자가 근거를 보고 결정하도록(관리 화면 개편): 표제어 말, 지금 사전에 실린 뜻, 표제어가 든 근거 상위 5건, 최근 12주 언급
    lang: str | None = None
    current: Meaning | None = None
    evidences: list[Evidence] = []
    weekly: list[WeeklyPoint] = []
    docs: list[ReviewDoc] = []


STAGE_LABELS = {
    "collect.youtube": "영상 수집", "collect.news": "뉴스 수집", "collect.trends_rss": "검색 트렌드(지금)", "collect.trends_bq": "검색 트렌드(일별)",
    "collect.wikipedia": "위키 조회 상위", "collect.mentions": "용어 언급 추적", "collect.retention": "30일 보존 정리", "classify": "검색어 분류", "spikes": "급증 원인 조사", "candidates": "후보 추출", "spot": "새 표현 발굴", "namu": "나무위키 발굴·재조사", "hunt": "못 답한 질문 조사",
    "interpret": "쇼츠 해석", "research": "조사·확인", "crosscheck": "문서 대조", "track": "추세 갱신", "risk": "쓸 때 주의 판정", "naver": "한국 세대 신호(네이버)", "translate": "언어판", "topics": "나라별 차이 서술", "board": "보드 생성", "dashboard": "키워드 대시보드", "fit": "추천용 쓰임 낱말",
}


def shown_evidences(con: Connection, t: Term) -> list[Evidence]:
    """사전 화면·질문 답·검수 화면에 낼 근거 — 표제어가 든 것만(검색 지수 datalab 은 문장이 아니라 그대로 둔다). 검색이 끌어온 딴 글
    ('오살힘' 에 2022년 '오살 의식' 기사)이 인용으로 나갔다(2026-09-29 원작자 서버 근거 9,738건 중 1,882건, match.evidence_mentions).
    커뮤니티·SNS 글은 내지 않는다 — 쓰임 지표로만 센다(ADR 0003)."""
    return [e for e in ds.list_evidences(con, t.term_id)
            if not is_community_post(e) and (e.kind == "datalab" or evidence_mentions(e, t.canonical, t.aliases))]


def popular_era(con: Connection, term_id: str) -> tuple[int | None, int | None]:
    """위키 문서마다 분류에서 읽은 연도·연대 가운데 가장 이른 것. 위키마다 처음 퍼진 해를 달리 적으면 먼저 퍼진 쪽이 유행 시작이다."""
    from .catalog import meta

    found = [meta(cats) for cats in ds.catalog_categories(con, term_id)]
    years = [f["year"] for f in found if f["year"]]
    decades = [f["decade"] for f in found if f["decade"]]
    year = min(years, default=None)
    return year, (year // 10 * 10 if year else min(decades, default=None))


def term_record(con: Connection, t: Term, *, public: bool = False) -> TermRecord:
    from .dashboard import regions_for   # dashboard 가 이 모듈의 뷰 모델을 쓴다 — 순환을 피해 여기서

    meanings = ds.list_meanings(con, t.term_id)
    if public:
        from ..verification import PUBLIC_VERIFICATIONS

        meanings = [m for m in meanings if m.verification in PUBLIC_VERIFICATIONS]
    ko = ds.get_translation(con, t.term_id, "ko")
    en = ds.get_translation(con, t.term_id, "en")
    usage = [TermUsage(segment=Segment(segment_id=u["segment_id"], generation=u["generation"], region=u["region"]), first_seen=u["first_seen"], share=u["share"], source=u["source"])
             for u in ds.get_usage(con, t.term_id)]
    weekly = [WeeklyPoint(week_start=w, count=c) for w, c in ds.get_weekly(con, t.term_id)]
    reasons = ds.gate_reasons(con, t.term_id) if t.status == "needs_review" else None
    year, decade = popular_era(con, t.term_id)
    return TermRecord(term=t, category=CATEGORY_MAP.get(t.category, "other"), plain=(ko.plain if ko and ko.plain else ""), ko=ko, en=en,
                      meanings=meanings, evidences=shown_evidences(con, t), usage=usage, weekly=weekly,
                      recheck_days=recheck_interval_days(t.lifecycle),
                      media=[TermMedia(**m) for m in ds.get_media(con, t.term_id) if m["kind"] in ("image", "video")],
                      gate_reasons=reasons or None, regions=regions_for(con, t),
                      popular_year=year, popular_decade=decade)


def _maker(model: str | None) -> Maker | None:
    """기록된 모델 ID → 화면 말. 'offline:local'·'local:gemma4:e4b' 는 로컬 Gemma, 'gemini-…' 는 Gemini, 사람 계정은 사람."""
    m = (model or "").lower()
    if not m:
        return None
    if "gemini" in m:
        return "gemini"
    if "gemma" in m or "local" in m:
        return "gemma"
    if m in ("team", "reviewer", "human") or not any(ch in m for ch in ":-_."):
        return "person"
    return "unknown"


_AUTOMATIC = ("research_agent", "gate", "crosscheck_auto", "cleanup", "audit")


def provenance(con: Connection, t: Term, meanings: list[Meaning], evidences: list[Evidence]) -> Provenance:
    """현재 뜻이 어떻게 만들어졌나(기록만). 초안 모델은 그 판 직후 5분 안의 조사 기록에서, 확인은 판의 검증 상태와 검수 결정에서 읽는다."""
    from datetime import timedelta

    from ..verification import reference_doc

    open_ = [m for m in meanings if not m.valid_to]
    m = (open_ or meanings)[-1] if meanings else None
    out = Provenance(evidences=len(evidences))
    if not m:
        return out
    if m.created_by not in _AUTOMATIC:
        out.drafted_by, out.drafted_at = "person", m.valid_from
    elif m.created_by == "audit":
        row = con.execute("SELECT model FROM audit_log WHERE term_id=? AND action='rewritten' ORDER BY checked_at DESC LIMIT 1",
                          (t.term_id,)).fetchone()
        out.drafted_by, out.drafted_at, out.rewritten = _maker(row[0] if row else None) or "unknown", m.valid_from, True
    else:
        start = m.valid_from
        for at, model in con.execute("SELECT researched_at, model FROM research_log WHERE term_id=? ORDER BY researched_at", (t.term_id,)).fetchall():
            when = datetime.fromisoformat(at) if isinstance(at, str) else at
            if start <= when <= start + timedelta(minutes=5):
                out.drafted_by, out.drafted_at = _maker(model) or "unknown", start
                break
    ref = next((e for e in evidences if reference_doc(e)), None)
    out.reference = ref.source_domain if ref else None
    if m.verification == "verified_human":
        out.checked = "person"
        decided = [r["decided_at"] for r in ds.review_history(con, t.term_id) if r.get("decision") == "approve"]
        out.checked_at = datetime.fromisoformat(decided[-1]) if decided and isinstance(decided[-1], str) else (decided[-1] if decided else None)
    elif m.verification == "verified_auto":
        out.checked = "rules"
    row = con.execute("SELECT verdict, model FROM audit_log WHERE term_id=? AND meaning_id=? ORDER BY checked_at DESC LIMIT 1",
                      (t.term_id, m.meaning_id)).fetchone()
    if row and row[0] in ("ok", "fix"):
        out.audit, out.audit_by = row[0], _maker(row[1])
    labels = con.execute("SELECT model, count(*) FROM evidence_labels WHERE term_id=? AND polarity <> 'offtopic' GROUP BY model ORDER BY 2 DESC",
                         (t.term_id,)).fetchall()
    out.risk_sentences = sum(n for _, n in labels)
    out.risk_by = _maker(labels[0][0]) if labels else None
    tr = con.execute("SELECT model FROM translations WHERE term_id=? AND lang='en'", (t.term_id,)).fetchone()
    out.translated_by = _maker(tr[0]) if tr else None
    return out


def _when(v) -> datetime | None:
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(v) if v else None
    except ValueError:
        return None


def risk_breakdown(con: Connection, t: Term) -> RiskBreakdown | None:
    """리스크 판정이 본 쓰임 문장과 모델이 붙인 분류(pipeline/risk.judge 와 같은 문장·같은 규칙). 분류한 문장이 없으면 None."""
    from . import risk

    rows = ds.evidence_label_rows(con, t.term_id)
    if not rows:
        return None
    out = RiskBreakdown(min_labeled=risk.MIN_LABELED, caution_risky=risk.CAUTION_RISKY, caution_negative=risk.CAUTION_NEGATIVE,
                        avoid_risky=risk.AVOID_RISKY)
    for e in risk._usage(con, t):
        if e.evidence_id not in rows:
            continue
        polarity, kind, model, at = rows[e.evidence_id]
        on_topic = polarity != "offtopic"
        if on_topic:
            out.counted += 1
            out.risky += kind != "none"
            out.negative += polarity == "negative"
        else:
            out.offtopic += 1
        if not risk._quotable(e):
            out.community += 1
            continue
        out.sentences.append(SentenceLabel(
            evidence_id=e.evidence_id, text=(e.excerpt or e.title).strip()[:220], url=e.url, source_domain=e.source_domain, kind=e.kind,
            observed_at=e.observed_at, on_topic=on_topic, polarity=polarity if on_topic and polarity in ("positive", "neutral", "negative") else None,
            risk=kind if on_topic else "none", by=_maker(model), labeled_at=_when(at)))
    return out if out.counted or out.offtopic else None


# 단계 → (표, 모델 열, 시각 열). 표가 없거나 비면 0 으로 센다
_GEMMA_TABLES = {"risk": ("evidence_labels", "model", "labeled_at"), "translate": ("translations", "model", "updated_at"),
                 "fit": ("term_fit", "model", "labeled_at"), "audit": ("audit_log", "model", "checked_at"),
                 "crosscheck": ("crosscheck_log", "model", "checked_at"), "research": ("research_log", "model", "researched_at")}


def _model_name(model: str) -> str:
    """'local:gemma4:12b'·'offline:local' → 화면에 보일 이름. 경로·호스트는 버린다."""
    m = model.split("local:", 1)[-1] if "local:" in model else model
    return m.rsplit("/", 1)[-1][:40]


def gemma_usage(con: Connection) -> GemmaUsage:
    """단계별로 Gemma·Gemini 가 남긴 결과 수(공개 사전의 확인된 항목만)와 대표 항목. 문장·출력 원문은 내지 않는다."""
    verified = {tid for (tid,) in con.execute("SELECT term_id FROM terms WHERE status='verified'").fetchall()}
    stages = []
    for stage, (table, col, at_col) in _GEMMA_TABLES.items():
        st = GemmaStage(stage=stage)
        gemma_terms: set[str] = set()
        models: set[str] = set()
        last: datetime | None = None
        for tid, model, n, at in con.execute(f"SELECT term_id, {col}, count(*), max({at_col}) FROM {table} GROUP BY term_id, {col}").fetchall():
            if tid not in verified:
                continue
            who = _maker(model)
            if who == "gemma":
                st.gemma += n
                gemma_terms.add(tid)
                models.add(_model_name(model or ""))
                w = _when(at)
                last = max(last, w) if last and w else (w or last)
            elif who == "gemini":
                st.gemini += n
            else:
                st.other += n
        st.terms, st.models, st.last_at = len(gemma_terms), sorted(m for m in models if m and m != "offline"), last
        stages.append(st)
    picks = con.execute("SELECT el.term_id, el.model, count(*) FROM evidence_labels el JOIN terms t ON t.term_id=el.term_id "
                        "WHERE t.status='verified' AND el.polarity <> 'offtopic' GROUP BY el.term_id, el.model ORDER BY 3 DESC, 1 LIMIT 40").fetchall()
    samples: list[dict[str, str]] = []
    for tid, model, _ in picks:
        if _maker(model) != "gemma" or any(x["term_id"] == tid for x in samples):
            continue
        t = ds.get_term(con, tid)
        if t:
            samples.append({"term_id": tid, "canonical": t.canonical, "lang": t.lang})
        if len(samples) >= 4:
            break
    calls: list[ModelCalls] = []
    for stage_key, models in ds.model_calls_24h(con).items():
        for model, (n, secs) in sorted(models.items(), key=lambda kv: -kv[1][0]):
            who = _maker(model)
            calls.append(ModelCalls(stage=stage_key, label=STAGE_LABELS.get(stage_key, stage_key), model=_model_name(model),
                                    maker=who if who in ("gemma", "gemini") else "unknown", calls=int(n), seconds=round(secs, 1)))
    order = list(STAGE_LABELS)
    calls.sort(key=lambda c: (order.index(c.stage) if c.stage in order else len(order), -c.calls))
    return GemmaUsage(stages=stages, samples=samples, calls_24h=calls, generated_at=datetime.now().astimezone())


def term_records(con: Connection, statuses: tuple[str, ...] = ("verified",), *, slim: bool = False, public: bool = False) -> list[TermRecord]:
    terms = ds.list_terms(con, statuses)
    with ds.batched(con, [t.term_id for t in terms]):
        from ..verification import is_public_entry

        records = [term_record(con, t, public=public) for t in terms
                   if not public or is_public_entry(t, ds.current_meaning(con, t.term_id))]
    return [_slim(r) for r in records] if slim else records


_USED_KINDS = ("community", "news", "short")

# 사전 색인(slim)은 용어 7,600개를 조립하느라 한 번에 5~7초 걸렸다(10-05). 만든 JSON 을 두고, 용어·뜻·번역·근거 수가 바뀌거나
# INDEX_TTL 이 지나면 다시 만든다. 검수자가 리스크만 바꾼 것은 색인에 INDEX_TTL 안에 반영된다(사전 항목·대시보드는 바로).
INDEX_KEY = "term_index"
_INDEX: dict[str, tuple[str, bytes]] = {}


def _index_stamp(con: Connection) -> str:
    """사전 색인을 다시 만들어야 하나 — 확인된 용어 JSON(상태·별칭·리스크), 뜻 판, 번역, 근거 가운데 무엇이든 바뀌면 달라진다(40ms 남짓)."""
    row = con.execute(
        "SELECT (SELECT md5(string_agg(md5(json), '' ORDER BY term_id)) FROM terms WHERE status='verified'), "
        "(SELECT md5(string_agg(md5(json), '' ORDER BY meaning_id)) FROM meanings WHERE valid_to IS NULL), "
        "(SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM translations), "
        "(SELECT count(*) FROM evidences)").fetchone()
    return hashlib.md5(("public-v2|" + "|".join(str(v) for v in row)).encode()).hexdigest()   # v2: 욕설·성적 표제어를 공개에서 뺀 뒤(10-09)


def save_term_index(con: Connection) -> bytes:
    """사전 색인(slim)을 만들어 board_cache 에 둔다 — dashboard 단계가 부른다. 요청 기반 CPU 과금에서는 API 의 시작 예열이 CPU 를 못 받아
    운영 사전 첫 요청이 21초였다(10-05, 로컬에서도 만드는 데 10.7초). 열쇠에 상태값을 넣어, 자료가 바뀐 뒤의 옛 색인은 읽지 않는다."""
    stamp = _index_stamp(con)
    body = ("[" + ",".join(r.model_dump_json() for r in term_records(con, slim=True, public=True)) + "]").encode()
    con.execute("DELETE FROM board_cache WHERE key LIKE ?", (f"{INDEX_KEY}:%",))
    ds.cache_set(con, f"{INDEX_KEY}:{stamp}", body.decode())
    _INDEX["slim"] = (stamp, body)
    return body


def term_index_json(con: Connection) -> bytes:
    """사전 색인 JSON. 프로세스 메모 → board_cache(파이프라인이 만들어 둔 것) → 새로 만들어 저장, 순서로 찾는다."""
    stamp = _index_stamp(con)
    hit = _INDEX.get("slim")
    if hit and hit[0] == stamp:
        return hit[1]
    row = ds.cache_get(con, f"{INDEX_KEY}:{stamp}")
    if row:
        body = row[0].encode()
        _INDEX["slim"] = (stamp, body)
        return body
    return save_term_index(con)


def _slim(r: TermRecord) -> TermRecord:
    """사전 색인 한 줄에 필요한 것만 — 현재 뜻, 마지막 쓰임을 셀 근거 하나. 뜻 이력·근거 전부·주간 수·매체는 뺀다.
    전체 기록은 용어 7,600개에 29.6MB(7.8초)라 사전 첫 화면이 18초 걸렸다(10-04). 웹의 lastUsedOf·currentMeaning 이 같은 답을 낸다."""
    open_ = [m for m in r.meanings if not m.valid_to]
    current = (open_ or r.meanings)[-1:]
    used = [e for e in r.evidences if e.kind in _USED_KINDS and urlsplit(e.url or "").path not in ("", "/")]
    latest = max(used, key=lambda e: e.observed_at, default=None)
    return r.model_copy(update={"meanings": current, "evidences": [latest] if latest else [], "usage": [], "weekly": [], "media": []})


def pipeline_stages(con: Connection) -> list[PipelineStage]:
    counts = ds.stage_counts_24h(con)
    last = ds.stage_last_runs(con)
    out = []
    for key, label in STAGE_LABELS.items():
        cnt, status, note = counts.get(key, (0, "", ""))
        st: Literal["ok", "warn", "zero"] = "warn" if status in ("error", "skipped") else ("ok" if (cnt > 0 or key == "collect.retention") else "zero")
        # 0건이 정상인 단계(정리·못 답한 질문 조사 등)도 있으니 '처리 없음' 은 실패가 아니다 — 화면이 배지로만 알린다
        run: Literal["ok", "idle", "skipped", "error"] | None = (
            None if not status else "error" if status == "error" else "skipped" if status == "skipped" else "ok" if st == "ok" else "idle")
        started, finished = last.get(key, (None, None))
        out.append(PipelineStage(key=key, label=label, count_24h=cnt, status=st, note=note or None, run_status=run,
                                 last_started_at=started, last_finished_at=finished))
    return out


def review_items(con: Connection) -> list[ReviewItem]:
    queue = ds.review_queue(con)
    with ds.batched(con, [q["term_id"] for q in queue]):
        return _review_items(con, queue)


def _review_items(con: Connection, queue: list[dict]) -> list[ReviewItem]:
    out = []
    for q in queue:
        t = ds.get_term(con, q["term_id"])
        m = ds.current_meaning(con, q["term_id"])
        kind = q["kind"] if q["kind"] in ds.REVIEW_KINDS else "new"
        if not t or (not m and kind != "retire"):
            continue
        evs = [e for e in shown_evidences(con, t) if e.kind != "datalab"][:5]
        weekly = [WeeklyPoint(week_start=w, count=c) for w, c in ds.get_weekly(con, t.term_id)]
        base = dict(term_id=t.term_id, canonical=t.canonical, kind=kind, token=q["token"], reasons=q["reasons"], evidence_count=q["evidence_count"],
                    queued_at=q["queued_at"], lang=t.lang, evidences=evs, weekly=weekly)
        if kind == "new":
            # 지금 실린 뜻: 제안보다 앞 판 가운데 확인된 마지막 것. 없으면 새 뜻이다
            cur = [x for x in ds.list_meanings(con, t.term_id) if x.version < m.version and x.verification in ("verified_auto", "verified_human")]
            out.append(ReviewItem(**base, meaning_id=m.meaning_id, proposed=m, current=cur[-1] if cur else None))
            continue
        # 문서 대조의 제안(Plan 12 §3): 지금 뜻은 닫지 않고 공개된 그대로다 — 지금 뜻을 current 로, 고칠 안(또는 문서들의 설명)을 제안으로 보인다.
        # 예전에는 지금 뜻을 제안처럼 보여 주었고, 그러려면 제안을 올리는 순간 항목이 공개 사전에서 빠져야 했다.
        docs = []
        for d in q["docs"]:
            try:
                docs.append(ReviewDoc.model_validate(d))
            except ValueError:
                continue
        out.append(ReviewItem(**base, meaning_id=m.meaning_id if m else None, current=m,
                              draft=q["draft"] if kind == "correction" else None, docs=docs))
    return out


class ReviewStats(BaseModel):
    verified_auto: int
    verified_human: int
    needs_review: int          # 새 말(조사 결과) 검수 대기 — 자동으로 실린 비율의 분모에 든다
    rejected: int
    proposals: int = 0         # 문서 대조의 제안(고칠 안·위키끼리 다름·사전에서 뺄지). 이미 실린 말이라 비율에 넣지 않는다(두 번 세지 않게)


def review_stats(con: Connection) -> ReviewStats:
    rows = dict(con.execute("SELECT verification, COUNT(*) FROM meanings WHERE valid_to IS NULL GROUP BY verification").fetchall())
    pending = ds.pending_counts(con)
    return ReviewStats(verified_auto=rows.get("verified_auto", 0), verified_human=rows.get("verified_human", 0),
                       needs_review=pending.get("new", 0), rejected=rows.get("rejected", 0),
                       proposals=sum(n for k, n in pending.items() if k != "new"))


class CountryPage(BaseModel):
    region: str
    items: list  # TrendItem
    why: list  # TrendWhy
    terms: list[TermRecord]
    generation_share: dict[str, float]
    updated_at: str | None


def country_page(con: Connection, region: str) -> CountryPage:
    from ..schemas import TrendBoard
    from ..storage import dictionary_store as ds2

    cached = ds2.cache_get(con, "board")
    board = TrendBoard.model_validate_json(cached[0]) if cached else None
    items = [i for i in board.items if i.region == region] if board else []
    why = [w for w in board.why if w.region == region] if board else []
    from .match import unsafe

    # 둘러보는 목록이다 — 표제어 자체가 욕설·성적 표현인 것은 내지 않는다(검수자가 '문제 없음' 으로 푼 것은 낸다, 대시보드와 같은 규칙)
    # 확인된 것만 — 공개 사전(/terms)과 같은 규칙. 확인 전 표현이 '확인된 표현' 으로 섞여 나왔다(화면 개편 2차 검토)
    from ..verification import is_public_entry

    recs = [term_record(con, t, public=True) for t in ds2.list_terms(con, ("verified",))
            if is_public_entry(t, ds2.current_meaning(con, t.term_id)) and any(u["region"] == region for u in ds2.get_usage(con, t.term_id)) and (not unsafe(t.canonical) or t.risk_level == "none")]
    share: dict[str, float] = {}
    for r in recs:
        for u in r.usage:
            if u.segment.region == region and u.source == "datalab":
                share[u.segment.generation] = share.get(u.segment.generation, 0) + u.share
    total = sum(share.values()) or 1
    return CountryPage(region=region, items=items, why=why, terms=recs, generation_share={k: round(v / total, 3) for k, v in share.items()},
                       updated_at=ds2.last_collected(con) or (board.generated_at.isoformat() if board else None))   # 화면의 '자료 수집'


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


def query_graph(con: Connection, key: str, limit_evidence: int = 12) -> QueryGraph | None:
    g = ds.graph_query(con, key)
    if not g:
        return None
    evs = [e for e in ds.list_evidences(con, f"q|{key}") if not is_community_post(e)]   # 커뮤니티·SNS 글은 내지 않는다(ADR 0003)
    return QueryGraph(key=g["key"], term=g["term"], region=g["region"], explained=g["explained"], actors=g["actors"], wiki=g["wiki"], term_id=g["term_id"],
                      evidence=[EvidenceBrief(kind=e.kind, source_domain=e.source_domain, title=e.title or e.excerpt, url=e.url, observed_at=e.observed_at) for e in evs[:limit_evidence]])


def shared_nodes(con: Connection, min_queries: int = 2) -> list[SharedNode]:
    return [SharedNode(type=n["type"], id=n["id"], label=_label(n["type"], n["id"]), queries=n["queries"], regions=n["regions"])
            for n in ds.graph_shared_nodes(con, min_queries) if n["type"] in ("actor", "wiki")]


def term_graph(con: Connection, term_id: str) -> list[TermGraphQuery]:
    return [TermGraphQuery(**q) for q in ds.graph_term_queries(con, term_id)]


# ---------- 키워드 대시보드 (Plan 04) — 값은 pipeline/dashboard.py 가 규칙으로 채운다 ----------

class SearchHit(BaseModel):
    """이 표현이 든 검색어가 그 나라 인기 검색어에 오른 기록 (Google Trends·나무위키 실시간 검색어)."""

    region: str
    query: str
    source: str
    date: str
    rank: int | None = None
    traffic: str | None = None


class GenPeak(BaseModel):
    """연령대별 검색 곡선의 정점 (네이버 데이터랩, 한국어 표제어만)."""

    generation: str
    date: str


class SourceCount(BaseModel):
    domain: str
    count: int


class Tone(BaseModel):
    """근거 문장의 뉘앙스 수 (Plan 03 분류, 글자만 같은 딴 이야기는 뺐다)."""

    positive: int = 0
    neutral: int = 0
    negative: int = 0


class KeywordCard(BaseModel):
    term_id: str
    canonical: str
    lang: str
    category: str
    gloss_ko: str
    gloss_en: str
    regions: list[str]                 # 목표 지역 코드, 목표 지역 밖에서 널리 쓰이면 GLOBAL
    lifecycle: Lifecycle
    diffusion: Diffusion | None = None
    risk_level: RiskLevel | None = None
    risk_reasons: list[str] = []
    risk_checked_at: datetime | None = None   # 리스크 규칙을 돌린 때. None 이면 아직 검사 전 — 화면이 '근거 부족' 과 가른다
    weekly: list[WeeklyPoint]          # 최근 12주
    mentions_4w: int
    search: list[SearchHit]            # 나라마다 가장 최근·높은 순위 하나
    gen_peaks: list[GenPeak] = []      # 연령대별 검색 정점 (네이버 데이터랩, 한국어 표제어만. 눈에 띄는 정점만)
    communities: list[SourceCount] = []   # 늘 빈 목록 — 커뮤니티 사이트 이름은 이용자에게 내지 않는다(ADR 0003). 예전 화면이 읽는 칸이라 남긴다
    tone: Tone
    evidences: list[EvidenceBrief]     # 최근 근거 5건 (커뮤니티·SNS 글은 빼고)
    last_seen: datetime | None = None
    last_used: datetime | None = None  # 고른 지역에서 가장 최근에 쓰인 글(커뮤니티·뉴스·쇼츠)의 때 — 원본 언급이 0 인 말의 순서와 표시
    use_confirmed: bool = True         # 그 뜻으로 쓰인 글이 확인됐다. 위키 밈 분류에서만 들어와 아직 확인 전이면 False — 목록 뒤로(dashboard.meme_use)
    mentions_mixed: bool = False       # 분류된 글 가운데 글자만 같은 딴 이야기가 더 많다 — 언급 수를 순서에 쓰지 않는다
    dated: bool = False                # 뜻풀이(뉘앙스)가 유행이 지났다고 적었다 — '식어 가는 밈' 으로(dashboard.DATED)
    en_pending: bool = False           # 영어 뜻풀이가 아직 없다 — gloss_en 은 한국어 원문이다. 영어 화면은 원문 대신 '번역 전' 으로 보인다
    ko_pending: bool = False           # 한국어 뜻풀이가 없고 gloss_ko 가 일본어·영어 원문이다. 한국어 화면은 원문 대신 '준비 중' 으로 보인다


class RegionTop(BaseModel):
    term_id: str
    canonical: str
    lang: str


class RegionSummary(BaseModel):
    """세계 지도의 지역 한 곳 — 쪽과 상관없이 그 지역 전체에서 센다(대시보드와 같은 목록 규칙)."""
    caution: int = 0                   # 주의가 필요한 밈(주의·사용 자제) 수
    top: RegionTop | None = None       # 지금 쓰이는 밈 1위, 없으면 식어 가는 밈 1위


class KeywordBoard(BaseModel):
    generated_at: datetime
    collected_at: datetime | None = None   # 자료를 마지막으로 모은 때(ds.last_collected) — 화면의 '자료 수집'. generated_at 은 캐시를 만든 때
    regions: list[str]                 # 고른 지역
    counts: dict[str, int]             # 지역마다 카드 수 (지역 고르기 버튼에 쓴다). 'ALL' 은 목표 지역 어디든(전 세계만인 것은 빼고)
    totals: dict[str, int] = {}        # 목록마다 전체 건수 {rising, fading, caution}. 주의 밈은 쓰이는·식는 목록에도 있다(Plan 04)
    page: int = 1                      # 아래 세 목록에 실린 쪽 (1부터)
    page_size: int = 30
    rising: list[KeywordCard]          # 지금 쓰이는 밈 (그 쪽만)
    fading: list[KeywordCard]          # 식어 가는 밈 (그 쪽만)
    caution: list[KeywordCard]         # 주의가 필요한 밈 (그 쪽만)
    summary: dict[str, RegionSummary] = {}   # summary=1 로 물을 때만 — 지역마다(세계 지도). 첫 쪽만 보고 세면 작은 지역의 대표 밈이 빠진다


# ---------- 밈 추천 (Plan 07) — 값은 pipeline/recommend.py 규칙이 채운다 ----------

class RecommendItem(BaseModel):
    term_id: str
    canonical: str
    lang: str = ""                     # 표제어의 말(KeywordCard.lang) — 화면이 원문에 lang 을 붙인다
    gloss_ko: str
    gloss_en: str
    en_pending: bool = False
    ko_pending: bool = False
    regions: list[str]
    diffusion: Diffusion | None = None
    lifecycle: Lifecycle
    risk_level: RiskLevel | None = None
    risk_reasons: list[str] = []
    risk_checked_at: datetime | None = None   # 리스크 규칙을 돌린 때 — 화면이 '근거 부족' 을 보일지 가른다
    matched_category: bool             # 제품 분야가 이 밈이 어울리는 분야에 있다
    any_category: bool                 # 분야를 가리지 않는 반응·감탄 표현
    matched_feelings: list[Feeling]
    # 고른 나라에서의 쓰임 — 파이프라인이 근거로 미리 써 둔 국가별 해석(확신 0.5 이상). 이유는 화면이 사전 뜻·겹친 낱말·이것으로 구성한다
    local_region: str | None = None
    local_note: Text2 | None = None
    write_regions: list[str] = []      # 고른 지역 가운데 이 밈으로 결과물을 쓸 수 있는 곳(generate.writable) — 화면의 '결과물 지역' 선택지
    score: float
    evidences: list[EvidenceBrief] = []
    pinned: bool = False               # 사전 항목의 '이 밈으로 만들기' 로 사람이 먼저 고른 밈 — 순위 밖이어도 목록 끝에 넣는다


class ExcludedItem(BaseModel):
    """제품과 이어지는데 규칙이 뺀 후보(Plan 20 만들기의 '뺀 말'). code 는 recommend.blocked 의 이유."""
    term_id: str
    canonical: str
    lang: str
    regions: list[str]
    code: Literal["avoid", "crude", "tone", "fading", "sensitive"]


class RecommendResult(BaseModel):
    brief: ProductBrief | None = None                    # 고른 지역에 비교할 후보가 없으면 사진·문구를 읽지 않는다(None)
    brief_source: Literal["gemini", "local", "sample", "none"]   # sample 이면 화면이 '예시 설명', none 이면 '아직 준비 안 됨' 이라고 알린다
    regions: list[str]
    tone: CampaignTone
    items: list[RecommendItem]
    considered: int                    # 지역·말투·리스크를 통과해 점수를 받은 후보 수
    untagged: int                      # 아직 쓰임 낱말이 없어 비교하지 못한 표제어 수
    excluded: list[ExcludedItem] = []  # 제품과 이어지는데 규칙이 뺀 후보 — 시장마다 몇 개(언급 많은 순)
    pool: dict[str, int] = {}          # 시장마다 사전에서 확인된 후보 수 (대시보드 카드)
    considered_by_region: dict[str, int] = {}   # 시장마다 규칙을 통과해 점수를 받은 후보 수


# ---------- 콘텐츠 생성 (Plan 08) — 값은 pipeline/generate.py 가 채운다. 저장하지 않는다 ----------

class Dropped(BaseModel):
    id: str                            # copy0…copy3·script·thumbnail
    code: Literal["unsafe", "no_meme", "x_too_long", "avoid_word"]   # 걸린 규칙 — 화면이 언어별 문구로 보인다
    reason: str                        # 같은 문제의 한국어 설명 (운영 기록용)


class GenerationResult(BaseModel):
    region: str
    language: str                      # 결과물의 말 (목표 지역)
    tone: CampaignTone
    memes: list[str]                   # 쓴 밈 이름
    copies: list[SocialCopy]           # 검사를 통과한 안만
    script: ShortScript | None = None
    thumbnail: ThumbnailPlan | None = None
    dropped: list[Dropped] = []        # 두 번 다 검사에 걸려 뺀 안과 이유
    model_calls: int                   # 모델 호출 수 — 생성 1, 다시 만들면 2 (검사는 규칙이라 세지 않는다)
    source: Literal["gemini", "local", "sample"]


# ---------- 시장별 포스터 시안 — 구성안은 pipeline/poster.py 의 규칙이 만든다. 이미지에는 글자를 넣지 않고, 검사한 문구는 화면이 얹는다 ----------

class PosterPlan(BaseModel):
    market: str                        # 목표 지역 코드(poster.MARKETS)
    product: str                       # 제품 설명 (밈·사람 이름을 지운 것)
    scene: str
    mood: list[str]                    # 고른 밈의 느낌·말투에서 옮긴 분위기 낱말 (닫힌 낱말만)
    colors: list[str]
    aspect_ratio: str
    prompt: str                        # 이미지 모델에 보내는 지시문 — 밈 이름·사람 이름이 들어가지 않는다


class PosterResult(BaseModel):
    enabled: bool                      # 이미지 생성이 켜져 있나. 꺼져 있으면 구성안만 오고 화면이 자리 표시를 보인다
    plan: PosterPlan
    images: list[str] = []             # data URL(data:image/png;base64,…). 저장하지 않는다



# ---------- 트렌드 브리핑 — 값은 pipeline/briefing.py 가 대시보드 규칙(dashboard.split)으로 채운다. 요약 문장만 모델 ----------

class BriefingCounts(BaseModel):
    rising: int                        # 지금 쓰이는 밈 (주의 포함, 사용 자제 제외 — 대시보드와 같다)
    use_now: int                       # 그중 리스크 '없음'
    careful: int                       # 그중 '주의'
    undecided: int                     # 그중 리스크 판단 보류(근거 부족·검사 전)
    avoid: int                         # 사용 자제
    fading: int                        # 식어 가는 밈


class Briefing(BaseModel):
    generated_at: datetime             # 대시보드 캐시를 만든 때
    collected_at: datetime | None = None   # 자료를 마지막으로 모은 때 — 보고서의 기준 시각
    regions: list[str]
    counts: BriefingCounts
    use_now: list[KeywordCard]         # 지금 써도 되는 밈 (위에서부터 BRIEF_TOP 개)
    careful: list[KeywordCard]         # 조심해서 쓸 밈
    avoid: list[KeywordCard]           # 쓰지 말 밈
    fading: list[KeywordCard]          # 식어 가는 밈
    summary: str | None = None         # 모델이 위 목록·건수만 보고 쓴 요약. None 이면 화면이 규칙 문장을 쓴다
    summary_source: Literal["gemini", "local", "none"] = "none"


# ---------- 카피 검사 — 판정은 pipeline/copycheck.py 규칙, '뜻에 맞게 썼나' 만 모델 의견. 입력 문장은 저장·기록하지 않는다 ----------

class CopyIssue(BaseModel):
    code: Literal["avoid", "caution", "undecided", "fading", "not_in_region", "no_script"]
    note: str = ""                     # caution 일 때 '쓸 때 조심' 안내(generate.caution_note, 한국어). 근거 글은 인용하지 않는다


class CopyMeme(BaseModel):
    term_id: str
    canonical: str
    lang: str = ""
    matched: str                       # 문구에서 찾은 그대로의 표기
    gloss_ko: str
    gloss_en: str
    en_pending: bool = False
    ko_pending: bool = False
    regions: list[str]
    lifecycle: Lifecycle
    diffusion: Diffusion | None = None
    risk_level: RiskLevel | None = None
    risk_checked_at: datetime | None = None
    issues: list[CopyIssue] = []
    fit: Literal["ok", "off", "unsure"] | None = None   # 모델 의견: 사전 뜻에 맞게 썼나. None 이면 보지 않았다
    fit_note: str | None = None        # 모델이 쓴 짧은 이유 (화면 언어)


class CopyCheck(BaseModel):
    region: str
    memes: list[CopyMeme]              # 문구에 나온 순서
    unsafe: bool                       # 문구에 욕설·선정 표현이 있다(match.unsafe)
    x_length: int                      # X 가 세는 글자 수 (280 까지)
    fit_source: Literal["gemini", "local", "none", "busy", "failed"]   # none: 모델 없음, busy: 자리 없음, failed: 모델 실패
