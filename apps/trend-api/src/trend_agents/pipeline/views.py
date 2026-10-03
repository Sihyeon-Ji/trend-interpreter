"""API 응답 뷰 모델 — 프론트 `apps/trend-web/lib/types.ts` 와 1:1. 화면은 이 모양만 안다."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

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


def term_record(con: Connection, t: Term) -> TermRecord:
    from .dashboard import regions_for   # dashboard 가 이 모듈의 뷰 모델을 쓴다 — 순환을 피해 여기서

    meanings = ds.list_meanings(con, t.term_id)
    ko = ds.get_translation(con, t.term_id, "ko")
    en = ds.get_translation(con, t.term_id, "en")
    usage = [TermUsage(segment=Segment(segment_id=u["segment_id"], generation=u["generation"], region=u["region"]), first_seen=u["first_seen"], share=u["share"])
             for u in ds.get_usage(con, t.term_id)]
    weekly = [WeeklyPoint(week_start=w, count=c) for w, c in ds.get_weekly(con, t.term_id)]
    reasons = ds.gate_reasons(con, t.term_id) if t.status == "needs_review" else None
    return TermRecord(term=t, category=CATEGORY_MAP.get(t.category, "other"), plain=(ko.plain if ko and ko.plain else ""), ko=ko, en=en,
                      meanings=meanings, evidences=shown_evidences(con, t), usage=usage, weekly=weekly,
                      recheck_days=recheck_interval_days(t.lifecycle),
                      media=[TermMedia(**m) for m in ds.get_media(con, t.term_id) if m["kind"] in ("image", "video")],
                      gate_reasons=reasons or None, regions=regions_for(con, t))


def term_records(con: Connection, statuses: tuple[str, ...] = ("verified",)) -> list[TermRecord]:
    terms = ds.list_terms(con, statuses)
    with ds.batched(con, [t.term_id for t in terms]):
        return [term_record(con, t) for t in terms]


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
    recs = [term_record(con, t) for t in ds2.list_terms(con, ("verified",))
            if any(u["region"] == region for u in ds2.get_usage(con, t.term_id)) and (not unsafe(t.canonical) or t.risk_level == "none")]
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


class RecommendResult(BaseModel):
    brief: ProductBrief | None = None                    # 고른 지역에 비교할 후보가 없으면 사진·문구를 읽지 않는다(None)
    brief_source: Literal["gemini", "local", "sample", "none"]   # sample 이면 화면이 '예시 설명', none 이면 '아직 준비 안 됨' 이라고 알린다
    regions: list[str]
    tone: CampaignTone
    items: list[RecommendItem]
    considered: int                    # 지역·말투·리스크를 통과해 점수를 받은 후보 수
    untagged: int                      # 아직 쓰임 낱말이 없어 비교하지 못한 표제어 수


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



# ---------- 트렌드 브리핑 — 값은 pipeline/briefing.py 가 대시보드 규칙(dashboard.split)으로 채운다. 요약 문장만 모델 ----------

class BriefingCounts(BaseModel):
    rising: int                        # 지금 쓰이는 밈 (주의 포함, 사용 자제 제외 — 대시보드와 같다)
    use_now: int                       # 그중 리스크 '없음'
    careful: int                       # 그중 '주의'
    undecided: int                     # 그중 리스크 판단 보류(근거 부족·검사 전)
    avoid: int                         # 사용 자제
    fading: int                        # 식어 가는 밈


class Briefing(BaseModel):
    generated_at: datetime             # 대시보드 갱신 시각 — 보고서의 기준 시각
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
