"""키워드 대시보드 (Plan 04). 용어 하나를 마케터가 볼 신호로 모은다 — 퍼진 정도·리스크·언급 추이·검색 순위·출몰 커뮤니티·뉘앙스·최근 근거.

지역 판정과 목록 나누기(지금 뜨는 밈·식어 가는 밈·주의가 필요한 밈)는 규칙이다. 모델은 부르지 않는다.
단계(run)가 모든 카드를 만들어 board_cache 의 'dashboard' 에 두고, API(board)는 고른 지역으로 거르기만 한다.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from ..config import LANG_REGION, REGIONS_FOCUS
from ..schemas import Evidence, EvidenceBrief, Term
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from .match import mentions
from .runs import stage
from .views import CATEGORY_MAP, KeywordBoard, KeywordCard, SearchHit, SourceCount, Tone, WeeklyPoint

GLOBAL = "GLOBAL"
CACHE_KEY = "dashboard"
LIST_MAX = 30
SEARCH_DAYS = 14
DIFFUSION_ORDER = {"spreading": 0, "underground": 1, "mainstream": 2}
LIFECYCLE_ORDER = {"emerging": 0, "rising": 0, "peak": 1, "steady": 2}


def term_regions(term: Term, usage_regions: set[str]) -> list[str]:
    """이 용어를 보여 줄 지역. 조사가 정한 쓰는 나라(usage) 가운데 목표 지역, 비었으면 표제어 언어의 나라.
    목표 지역 밖(미국 등)에서만 쓰인다고 한 영어 표현과 GLOBAL 은 '전 세계' 로 묶는다 — 나라 목록에 섞지 않는다."""
    regions = [r for r in REGIONS_FOCUS if r in usage_regions]
    if not regions and LANG_REGION.get(term.lang) in REGIONS_FOCUS:
        regions = [LANG_REGION[term.lang]]
    if GLOBAL in usage_regions or (not regions and term.lang == "en"):
        regions.append(GLOBAL)
    return regions


def _is_fading(c: KeywordCard) -> bool:
    return c.diffusion == "fading" or c.lifecycle in ("declining", "dormant")


def split(cards: list[KeywordCard]) -> tuple[list[KeywordCard], list[KeywordCard], list[KeywordCard]]:
    """(지금 뜨는 밈, 식어 가는 밈, 주의가 필요한 밈). 사용 자제는 뜨는·식는 목록에 넣지 않고 주의 목록에만 둔다."""
    rising = sorted((c for c in cards if not _is_fading(c) and c.risk_level != "avoid"),
                    key=lambda c: (DIFFUSION_ORDER.get(c.diffusion or "", 3), LIFECYCLE_ORDER.get(c.lifecycle, 3), -c.mentions_4w))
    fading = sorted((c for c in cards if _is_fading(c) and c.risk_level != "avoid"),
                    key=lambda c: -(c.last_seen.timestamp() if c.last_seen else 0))
    caution = sorted((c for c in cards if c.risk_level in ("caution", "avoid")),
                     key=lambda c: (c.risk_level != "avoid", -c.mentions_4w))
    return rising[:LIST_MAX], fading[:LIST_MAX], caution[:LIST_MAX]


def _recent_queries(con: Connection) -> list[tuple]:
    since = (date.today() - timedelta(days=SEARCH_DAYS)).isoformat()
    marks = ",".join("?" * len(REGIONS_FOCUS))
    rows = con.execute(f"SELECT term, region, rank, source, date, approx_traffic FROM trend_queries WHERE date >= ? AND region IN ({marks})",
                       (since, *REGIONS_FOCUS)).fetchall()
    return [(ds.norm(q), q, reg, rank, src, str(d), traffic) for q, reg, rank, src, d, traffic in rows if q]


def search_hits(term: Term, queries: list[tuple]) -> list[SearchHit]:
    """나라마다 이 표현이 든 인기 검색어 하나 — 가장 최근, 같은 날이면 순위가 높은 것. 들어 있는지는 mentions() 로만 본다.
    공백을 뺀 글자열 포함은 mentions() 가 참이 되기 위한 필요조건이라, 먼저 그것으로 거른다(빠르다)."""
    keys = [k for k in (ds.norm(n) for n in (term.canonical, *term.aliases)) if k]
    best: dict[str, SearchHit] = {}
    for norm, q, reg, rank, src, d, traffic in queries:
        if not any(k in norm for k in keys) or not mentions(q, term.canonical, term.aliases):
            continue
        cur = best.get(reg)
        if cur is None or (d, -(rank or 999)) > (cur.date, -(cur.rank or 999)):
            best[reg] = SearchHit(region=reg, query=q, source=src, date=d, rank=rank, traffic=traffic)
    return sorted(best.values(), key=lambda h: REGIONS_FOCUS.index(h.region))


def _usage_examples(evs: list[Evidence], n: int = 5, per_domain: int = 2) -> list[Evidence]:
    """최근 쓰임 근거. 검색 추이(datalab)는 쓰임이 아니라 따로 보이고, 한 곳에 몰리지 않게 출처마다 두 건까지."""
    out: list[Evidence] = []
    seen: Counter = Counter()
    for e in evs:
        if e.kind == "datalab" or seen[e.source_domain] >= per_domain:
            continue
        seen[e.source_domain] += 1
        out.append(e)
        if len(out) == n:
            break
    return out


def build_card(con: Connection, t: Term, queries: list[tuple], *, outside: bool = False) -> KeywordCard | None:
    """카드 하나. 목표 지역 밖 용어는 대시보드에 없으므로 None — outside 면 지역을 비운 채 만든다(사전 화면용)."""
    regions = term_regions(t, {u["region"] for u in ds.get_usage(con, t.term_id)})
    if not regions and not outside:
        return None
    m = ds.current_meaning(con, t.term_id)
    ko, en = ds.get_translation(con, t.term_id, "ko"), ds.get_translation(con, t.term_id, "en")
    base = m.definition if m else ""
    weekly = [WeeklyPoint(week_start=w, count=c) for w, c in ds.get_weekly(con, t.term_id, 12)]
    evs = ds.list_evidences(con, t.term_id)                        # 최근 것부터
    trend = next((e for e in evs if e.source_domain == "datalab.naver.com"), None)
    tone = Counter(p for p, _ in ds.evidence_labels(con, t.term_id).values() if p != "offtopic")
    return KeywordCard(
        term_id=t.term_id, canonical=t.canonical, lang=t.lang, category=CATEGORY_MAP.get(t.category, "other"),
        gloss_ko=ko.definition if ko else base, gloss_en=en.definition if en else base, regions=regions,
        lifecycle=t.lifecycle, diffusion=t.diffusion, risk_level=t.risk_level, risk_reasons=t.risk_reasons,
        weekly=weekly, mentions_4w=sum(p.count for p in weekly[-4:]), search=search_hits(t, queries),
        search_trend=(trend.excerpt or None) if trend else None,
        communities=[SourceCount(domain=d, count=n) for d, n in Counter(e.source_domain for e in evs if e.kind == "community").most_common(5)],
        tone=Tone(positive=tone["positive"], neutral=tone["neutral"], negative=tone["negative"]),
        evidences=[EvidenceBrief(kind=e.kind, source_domain=e.source_domain, title=(e.title or e.excerpt)[:160], url=e.url, observed_at=e.observed_at)
                   for e in _usage_examples(evs)],
        last_seen=t.last_seen)


def build(con: Connection) -> list[KeywordCard]:
    queries = _recent_queries(con)
    return [c for t in ds.list_terms(con, ("verified",)) if (c := build_card(con, t, queries))]


def _save(con: Connection, cards: list[KeywordCard]) -> None:
    ds.cache_set(con, CACHE_KEY, "[" + ",".join(c.model_dump_json() for c in cards) + "]")


def _load(con: Connection) -> tuple[list[KeywordCard], datetime] | None:
    import json

    cached = ds.cache_get(con, CACHE_KEY)
    return ([KeywordCard.model_validate(x) for x in json.loads(cached[0])], datetime.fromisoformat(cached[1])) if cached else None


def refresh_card(con: Connection, term_id: str) -> None:
    """검수자가 수준을 바꾸거나 뜻을 승인·제외했을 때 그 카드만 다시 만든다 — 다음 파이프라인까지 기다리지 않게."""
    loaded = _load(con)
    if loaded is None:
        return
    cards = [c for c in loaded[0] if c.term_id != term_id]
    t = ds.get_term(con, term_id)
    if t and t.status == "verified" and (c := build_card(con, t, _recent_queries(con))):
        cards.append(c)
    _save(con, cards)


def board(con: Connection, regions: list[str] | None = None) -> KeywordBoard:
    """고른 지역의 대시보드. regions 가 없으면 목표 지역 전체(전 세계 묶음은 빼고)."""
    loaded = _load(con)
    if loaded is None:                # 첫 실행 전 — 바로 만들어 둔다
        _save(con, build(con))
        loaded = _load(con)
    cards, generated_at = loaded
    known = [*REGIONS_FOCUS, GLOBAL]
    chosen = [r for r in known if r in (regions or [])] or list(REGIONS_FOCUS)
    picked = [c.model_copy(update={"search": [h for h in c.search if h.region in chosen]})
              for c in cards if set(c.regions) & set(chosen)]
    rising, fading, caution = split(picked)
    return KeywordBoard(generated_at=generated_at, regions=chosen,
                        counts={r: sum(1 for c in cards if r in c.regions) for r in known},
                        rising=rising, fading=fading, caution=caution)


def card(con: Connection, term_id: str) -> KeywordCard | None:
    """용어 하나의 신호 (사전 화면의 '쓰임 신호'). 목표 지역 밖이라 대시보드에 없는 용어도 만들어 준다."""
    for c in (_load(con) or ([], None))[0]:
        if c.term_id == term_id:
            return c
    t = ds.get_term(con, term_id)
    if not t or t.status != "verified":
        return None
    return build_card(con, t, _recent_queries(con), outside=True)


def run(con: Connection) -> dict:
    with stage(con, "dashboard") as r:
        cards = build(con)
        _save(con, cards)
        r.count = len(cards)
        r.detail = {k: sum(1 for c in cards if k in c.regions) for k in (*REGIONS_FOCUS, GLOBAL)}
    return {"dashboard": r}
