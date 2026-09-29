"""키워드 대시보드 (Plan 04). 용어 하나를 마케터가 볼 신호로 모은다 — 퍼진 정도·리스크·언급 추이·검색 순위·연령대 정점·뉘앙스·최근 근거.

지역 판정과 목록 나누기(지금 쓰이는 밈·식어 가는 밈·주의가 필요한 밈)는 규칙이다. 모델은 부르지 않는다.
단계(run)가 용어마다 **나라별 재료**(원본 언급·뉘앙스·근거·마지막 쓰임)를 만들어 board_cache 의 'dashboard' 에 두고,
API(board)는 고른 지역의 재료만 더해 카드를 만든다 — 지역을 바꾸면 목록뿐 아니라 수치도 그 지역 것으로 바뀐다(Plan 04 완료 기준).
커뮤니티·SNS 글은 마지막 쓰임·뉘앙스로만 센다. 근거 예시·'많이 보인 곳' 으로 내지 않는다(ADR 0003).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from pydantic import BaseModel

from ..collectors.community import COMMUNITY_SITES, is_community_post
from ..config import LANG_REGION, REGIONS_FOCUS
from ..schemas import Evidence, EvidenceBrief, Term
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from .match import mentions, unsafe
from .runs import stage
from .views import CATEGORY_MAP, GenPeak, KeywordBoard, KeywordCard, RegionSummary, RegionTop, SearchHit, Tone, WeeklyPoint

GLOBAL = "GLOBAL"
CACHE_KEY = "dashboard"
LIST_MAX = 30          # 한 쪽에 보이는 수 — 목록은 자르지 않고 쪽으로 나눈다(totals 가 전체 건수)
STALE_DAYS = 90        # 12주 언급이 0 이고 마지막 쓰임이 이보다 오래되면 '지금 쓰이는' 이 아니라 '식어 가는'
SEARCH_DAYS = 14
WEEKS = 12
DIFFUSION_ORDER = {"spreading": 0, "underground": 1, "mainstream": 2}
LIFECYCLE_ORDER = {"emerging": 0, "rising": 0, "peak": 1, "steady": 2}
USAGE_KINDS = ("community", "news", "short")

# 표제어 언어의 나라로 둘 때는 그 나라 글자로 쓴 말만. 위키 언어판(ja)에서 받은 영어 제목 'The cake is a lie' 가 일본 카드가 됐다(2026-09-29 검토).
_SCRIPT = {"ko": r"[가-힣]", "ja": r"[\u3040-\u30ff\u4e00-\u9fff]", "zh": r"[\u4e00-\u9fff]", "th": r"[\u0e00-\u0e7f]",
           "vi": r"[ăâđêôơưĂÂĐÊÔƠƯ\u1ea0-\u1ef9]"}
# 로마자로 쓰는 목표 지역 말(인도네시아어·타갈로그어·말레이어)은 글자로 가를 수 없어 표제어 언어를 믿는다 — '전 세계' 로 보내면
# 그 나라 목록에서 빠졌다(2026-09-29 검토 2차).
_LATIN_LANGS = ("id", "tl", "fil", "ms")
_LATIN_ONLY = re.compile(r"^[\x00-\x7f\u00c0-\u024f\u1e00-\u1eff\s]+$")

# 커뮤니티 도메인의 나라. 수집기(COMMUNITY_SITES)에서 오고, 구글 뉴스가 한국어 이름으로 준 것과 나라 도메인을 더한다.
# 나라를 가를 수 없는 전 세계 플랫폼(Reddit·Bluesky·Lemmy·Hacker News·유튜브 댓글…)은 GLOBAL.
_SITE_REGION = {s: r for r, sites in COMMUNITY_SITES.items() for s in sites if s != "reddit.com"}
_SITE_REGION.update({"디시인사이드": "KR", "갤러리": "KR", "클리앙": "KR", "에펨코리아": "KR", "더쿠": "KR", "루리웹": "KR", "인스티즈": "KR",
                     "뽐뿌": "KR", "namu.wiki": "KR"})
_TLD_REGION = {".kr": "KR", ".jp": "JP", ".tw": "TW", ".hk": "HK", ".th": "TH", ".vn": "VN", ".id": "ID", ".ph": "PH", ".my": "MY", ".sg": "SG"}


def domain_region(domain: str) -> str:
    d = (domain or "").lower()
    if d.startswith("naver"):
        return "KR"
    if d in _SITE_REGION:
        return _SITE_REGION[d]
    return next((r for tld, r in _TLD_REGION.items() if d.endswith(tld)), GLOBAL)


def term_regions(term: Term, usage_regions: set[str]) -> list[str]:
    """이 용어를 보여 줄 지역. 조사가 정한 쓰는 나라(usage) 가운데 목표 지역 → 목표 지역 밖(미국 등)에서만 쓰이는 영어 표현은 '전 세계'.
    쓰는 나라 정보가 아예 없으면: 그 나라 글자로 쓴 말만 표제어 언어의 나라, 로마자로만 쓴 말은 '전 세계'.
    목표 지역 밖 한 나라에서만 쓰는 말(독일의 Ehrenmann)은 빼고, 나라 목록에 '전 세계' 를 섞지 않는다."""
    known = {r for r in usage_regions if r}              # '' 는 예전 조사가 나라 자리에 남긴 빈 값 — 정보가 없는 것
    regions = [r for r in REGIONS_FOCUS if r in known]
    if not known:
        home, script = LANG_REGION.get(term.lang), _SCRIPT.get(term.lang)
        if home in REGIONS_FOCUS and ((script and re.search(script, term.canonical)) or term.lang in _LATIN_LANGS):
            regions = [home]
        elif _LATIN_ONLY.match(term.canonical):
            return [GLOBAL]
    if GLOBAL in known or (not regions and known and term.lang == "en"):
        regions.append(GLOBAL)
    return regions


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _stale(c: KeywordCard, now: datetime) -> bool:
    """12주 동안 언급이 없고, 마지막 쓰임(화면의 '마지막 쓰임' 과 같은 값)이 STALE_DAYS 보다 오래됐다.
    몇 년 전에 쓰인 말이 '지금 쓰이는 밈' 에 섞여 있었다(디자인 개편 검토 09-29: 간 때문이야 2021.02.03)."""
    last = c.last_used or c.last_seen
    return not any(p.count for p in c.weekly) and last is not None and _utc(last) < _utc(now) - timedelta(days=STALE_DAYS)


def _is_fading(c: KeywordCard, now: datetime) -> bool:
    return c.diffusion == "fading" or c.lifecycle in ("declining", "dormant") or _stale(c, now)


def split(cards: list[KeywordCard], now: datetime | None = None) -> tuple[list[KeywordCard], list[KeywordCard], list[KeywordCard]]:
    """(지금 쓰이는 밈, 식어 가는 밈, 주의가 필요한 밈). Plan 04: 주의 밈은 지금도 쓰이는 말이라 쓰이는·식는 목록에 표시와 함께 남고,
    사용 자제는 주의 목록에만 둔다(사용 자제 먼저). 그래서 칩 건수 = 쓰이는 + 식는 + 사용 자제.
    자르지 않는다 — 쪽 나누기는 board 가 한다. now 는 카드를 만든 때(갱신 시각)."""
    now = now or datetime.now(timezone.utc)

    # 원본 언급(뉴스 제목·쇼츠·검색어)에 밈 이름이 오르는 일은 드물어 대부분 0 이다 — 그다음은 가장 최근에 쓰인 글 순
    # (0 끼리 이름순으로 서서 'Nice boat'·'TBT' 가 맨 앞이던 것, 2026-09-29).
    def recent(c: KeywordCard) -> float:
        return max((d.timestamp() for d in (c.last_used, c.last_seen) if d), default=0.0)

    usable = [c for c in cards if c.risk_level != "avoid"]
    rising = sorted((c for c in usable if not _is_fading(c, now)),
                    key=lambda c: (DIFFUSION_ORDER.get(c.diffusion or "", 3), LIFECYCLE_ORDER.get(c.lifecycle, 3), -c.mentions_4w, -recent(c)))
    fading = sorted((c for c in usable if _is_fading(c, now)), key=lambda c: -recent(c))
    caution = sorted((c for c in cards if c.risk_level in ("caution", "avoid")),
                     key=lambda c: (c.risk_level != "avoid", -c.mentions_4w, -recent(c)))
    return rising, fading, caution


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


def gen_peaks(con: Connection, term_id: str) -> list[GenPeak]:
    """네이버 데이터랩 연령대별 곡선에서 눈에 띄는 정점(평균의 1.3배 이상)만. 평평한 곡선은 뺀다. 한국어 표제어만 있다."""
    out = []
    for gen, pts in ds.get_gen_curves(con, term_id).items():
        vals = [v for _, v in pts]
        if not vals or max(vals) <= 0 or max(vals) < 1.3 * (sum(vals) / len(vals)):
            continue
        d, _ = max(pts, key=lambda p: p[1])
        out.append(GenPeak(generation=gen, date=d))
    return sorted(out, key=lambda p: p.date)


class Stored(BaseModel):
    """캐시에 두는 카드 재료. 나라별 수치는 여기에만 있고 API 로는 고른 지역을 더한 카드(KeywordCard)만 나간다."""

    card: KeywordCard                               # 나라와 상관없는 필드(뜻·단계·리스크·검색 순위 전체·연령대 정점)
    weeks: list[str]
    weekly: dict[str, list[int]] = {}               # 나라(목표 지역·GLOBAL)별 원본 주간 언급
    tone: dict[str, dict[str, int]] = {}            # 나라별 뉘앙스 수 (커뮤니티 글 포함 — 수만 나간다)
    evidences: dict[str, list[EvidenceBrief]] = {}  # 나라별 최근 근거(커뮤니티·SNS 글은 빼고). "" = 나라를 가를 수 없는 문서(위키 등)
    last_used: dict[str, datetime] = {}             # 나라별 가장 최근에 쓰인 글의 때


class _Regions:
    """근거 하나가 어느 나라 것인가 — 뉴스는 수집한 나라, 쇼츠는 영상의 나라, 커뮤니티는 도메인. 한 번 읽어 두고 쓴다."""

    def __init__(self, con: Connection, term_id: str | None = None):
        if term_id is None:
            self.news = dict(con.execute("SELECT link, region FROM news").fetchall())
            self.videos = dict(con.execute("SELECT video_id, region FROM videos").fetchall())
            return
        # 카드 하나를 고칠 때는 그 용어의 근거 주소만 찾는다 — 뉴스·영상 수만 건을 매번 읽지 않게(검토 2차)
        evs = ds.list_evidences(con, term_id)
        links = [e.url for e in evs if e.kind == "news"]
        vids = [m.group(1) for e in evs if e.kind == "short" and (m := re.search(r"(?:v=|/shorts/)([\w-]{6,})", e.url))]
        self.news = dict(con.execute(f"SELECT link, region FROM news WHERE link IN ({','.join('?' * len(links))})", links).fetchall()) if links else {}
        self.videos = dict(con.execute(f"SELECT video_id, region FROM videos WHERE video_id IN ({','.join('?' * len(vids))})", vids).fetchall()) if vids else {}

    def of(self, e: Evidence) -> str:
        if e.kind == "news":
            r = self.news.get(e.url)
            return (r if r in REGIONS_FOCUS else GLOBAL) if r else domain_region(e.source_domain)
        if e.kind == "short":
            m = re.search(r"(?:v=|/shorts/)([\w-]{6,})", e.url)
            r = self.videos.get(m.group(1)) if m else None
            return r if r in REGIONS_FOCUS else GLOBAL
        if e.kind == "community":
            return domain_region(e.source_domain)
        return ""


# 나라를 가를 수 없는 전 세계 플랫폼(블루스키·레딧)의 글은 글자로 나라를 짐작한다 — 그 용어가 이미 쓰이는 나라 가운데서만.
# 일본 표제어의 커뮤니티 근거 181건 중 178건(170건이 블루스키)이 '전 세계' 로 가 일본 카드가 비었다(검토 3차). 한자만 쓴 글은 대만·홍콩.
_TEXT_REGION = ((re.compile(r"[가-힣]"), ("KR",)), (re.compile(r"[぀-ヿ]"), ("JP",)), (re.compile(r"[฀-๿]"), ("TH",)),
                (re.compile(r"[ăâđêôơưĂÂĐÊÔƠƯạ-ỹ]"), ("VN",)), (re.compile(r"[一-鿿]"), ("TW", "HK", "JP")))


def text_region(text: str, regions: list[str]) -> str:
    """글자로 짐작한 나라(그 용어의 나라 가운데). 모르면 GLOBAL."""
    for pat, cands in _TEXT_REGION:
        if pat.search(text or ""):
            return next((r for r in cands if r in regions), GLOBAL)
    return GLOBAL


def _has_path(url: str) -> bool:
    """'https://namu.wiki/' 같은 홈페이지 주소는 근거가 아니다 — 나무위키 실시간 검색어·예전 시드에 118건 있었다(검토 2차)."""
    return urlsplit(url or "").path not in ("", "/")


def _usage_ok(e: Evidence, t: Term) -> bool:
    """쓰임으로 셀 근거 — 네이버 검색 결과는 약관상 표시 전용이고 느슨하게 맞은 글이 많아(바이킹 로우의 지식iN 글이 노르웨이 축구)
    빼고, 표제어가 실제로 든 글만(mentions)."""
    return (e.kind in USAGE_KINDS and not e.source_domain.startswith("naver")
            and mentions(f"{e.title or ''} {e.excerpt or ''}", t.canonical, t.aliases))


def build_card(con: Connection, t: Term, queries: list[tuple], regions_of: _Regions, weeks: list[str], *,
               outside: bool = False) -> Stored | None:
    """카드 재료 하나. 목표 지역 밖 용어는 대시보드에 없으므로 None — outside 면 지역을 비운 채 만든다(사전 화면용)."""
    regions = term_regions(t, {u["region"] for u in ds.get_usage(con, t.term_id)})
    if not regions and not outside:
        return None
    m = ds.current_meaning(con, t.term_id)
    ko, en = ds.get_translation(con, t.term_id, "ko"), ds.get_translation(con, t.term_id, "en")
    base = m.definition if m else ""
    # 쓰임 근거 + 설명 문서(위키·웹). 네이버 블로그 결과는 'web' 으로 들어와도 표시 전용이라 뺀다(검토 2차). 주소가 홈페이지뿐인 것도 뺀다.
    # 문서도 표제어가 든 것만 — 주제 단계가 나라마다 위키백과 검색 1위를 거르지 않고 넣어 '오살힘' 추천의 근거가 한국 배우·KBS 드라마 문서였다(검토 3차)
    evs = [e for e in ds.list_evidences(con, t.term_id)
           if (_usage_ok(e, t) or (e.kind in ("wiki", "web") and not e.source_domain.startswith("naver")
                                   and mentions(f"{e.title or ''} {e.excerpt or ''}", t.canonical, t.aliases)))
           and _has_path(e.url)]
    labels = ds.evidence_labels(con, t.term_id)
    weekly: dict[str, list[int]] = {}
    for r, cnt in ds.get_weekly_region(con, t.term_id).items():
        row = weekly.setdefault(r if r in REGIONS_FOCUS else GLOBAL, [0] * len(weeks))
        for i, w in enumerate(weeks):
            row[i] += cnt.get(w, 0)
    tone: dict[str, Counter] = {}
    examples: dict[str, list[EvidenceBrief]] = {}
    last_used: dict[str, datetime] = {}
    per_domain: Counter = Counter()
    shown: set[str] = set()
    for e in evs:
        r = regions_of.of(e)
        if r == GLOBAL and e.kind in USAGE_KINDS:
            r = text_region(f"{e.title or ''} {e.excerpt or ''}", regions)
        if e.kind in USAGE_KINDS and (r not in last_used or e.observed_at > last_used[r]):
            last_used[r] = e.observed_at
        p = labels.get(e.evidence_id, (None, None))[0]
        if p and p != "offtopic":
            tone.setdefault(r, Counter())[p] += 1
        # 커뮤니티·SNS 글은 마지막 쓰임·뉘앙스로만 세고 근거 예시로 내지 않는다(ADR 0003)
        if is_community_post(e):
            continue
        # 한 곳에 몰리지 않게 출처마다 두 건까지. 같은 주소는 한 번만 — 위키백과 문서가 web·wiki 로 두 번 들어와 같은 링크가 둘 보였다(검토 3차)
        if per_domain[e.source_domain] < 2 and len(examples.get(r, [])) < 5 and e.url not in shown:
            per_domain[e.source_domain] += 1
            shown.add(e.url)
            examples.setdefault(r, []).append(EvidenceBrief(kind=e.kind, source_domain=e.source_domain, title=(e.title or e.excerpt)[:160],
                                                            url=e.url, observed_at=e.observed_at))
    card = KeywordCard(
        term_id=t.term_id, canonical=t.canonical, lang=t.lang, category=CATEGORY_MAP.get(t.category, "other"),
        gloss_ko=ko.definition if ko else base, gloss_en=en.definition if en else base, regions=[] if outside else regions,
        lifecycle=t.lifecycle, diffusion=t.diffusion, risk_level=t.risk_level, risk_reasons=t.risk_reasons, risk_checked_at=t.risk_checked_at,
        weekly=[], mentions_4w=0, search=search_hits(t, queries), gen_peaks=gen_peaks(con, t.term_id),
        tone=Tone(), evidences=[], last_seen=t.last_seen)
    return Stored(card=card, weeks=weeks, weekly=weekly, tone={r: dict(c) for r, c in tone.items()}, evidences=examples, last_used=last_used)


def view(s: Stored, chosen: list[str]) -> KeywordCard:
    """고른 지역의 재료만 더한 카드. 나라를 가를 수 없는 문서(위키 등)는 어느 지역에서나 근거로 보인다.
    커뮤니티 사이트 이름(communities)은 채우지 않는다. 이 규칙 전에 만든 캐시의 커뮤니티 근거도 여기서 거른다(ADR 0003)."""
    series = [sum(s.weekly.get(r, [0] * len(s.weeks))[i] for r in chosen) for i in range(len(s.weeks))]
    tone: Counter = Counter()
    for r in chosen:
        tone.update(s.tone.get(r, {}))
    evs = sorted((e for r in (*chosen, "") for e in s.evidences.get(r, []) if not is_community_post(e)),
                 key=lambda e: e.observed_at, reverse=True)[:5]
    return s.card.model_copy(update={
        "weekly": [WeeklyPoint(week_start=w, count=c) for w, c in zip(s.weeks, series)],
        "mentions_4w": sum(series[-4:]),
        "search": [h for h in s.card.search if h.region in chosen],
        "communities": [],
        "tone": Tone(positive=tone["positive"], neutral=tone["neutral"], negative=tone["negative"]),
        "evidences": evs,
        "last_used": max((s.last_used[r] for r in chosen if r in s.last_used), default=None),
        "gen_peaks": s.card.gen_peaks if "KR" in chosen else [],   # 네이버 데이터랩은 한국만 — 다른 지역 보기에 한국 연령대를 내지 않는다
    })


def _weeks() -> list[str]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return [(monday - timedelta(weeks=i)).isoformat() for i in range(WEEKS - 1, -1, -1)]


def build(con: Connection) -> list[Stored]:
    queries, regions_of, weeks = _recent_queries(con), _Regions(con), _weeks()
    return [s for t in ds.list_terms(con, ("verified",)) if (s := build_card(con, t, queries, regions_of, weeks))]


def _save(con: Connection, stored: list[Stored], generated_at: str | None = None) -> None:
    ds.cache_set(con, CACHE_KEY, "[" + ",".join(s.model_dump_json() for s in stored) + "]", generated_at)


def _load(con: Connection) -> tuple[list[Stored], datetime] | None:
    cached = ds.cache_get(con, CACHE_KEY)
    if not cached:
        return None
    try:
        return [Stored.model_validate(x) for x in json.loads(cached[0])], datetime.fromisoformat(cached[1])
    except Exception:            # 예전 모양의 캐시(나라별 재료 없음) — 새로 만든다
        return None


def refresh_card(con: Connection, term_id: str) -> None:
    """검수자가 수준을 바꾸거나 뜻을 승인·제외했을 때 그 카드만 다시 만든다 — 다음 파이프라인까지 기다리지 않게."""
    loaded = _load(con)
    if loaded is None:
        return
    stored = [s for s in loaded[0] if s.card.term_id != term_id]
    t = ds.get_term(con, term_id)
    if t and t.status == "verified" and (s := build_card(con, t, _recent_queries(con), _Regions(con, term_id), _weeks())):
        stored.append(s)
    _save(con, stored, loaded[1].isoformat())       # 카드 하나를 고쳤다고 '갱신' 시각이 바뀌지 않게


def _live(con: Connection, stored: list[Stored]) -> list[Stored]:
    """캐시 카드에 지금의 상태·리스크를 덮어쓴다. 단계가 카드를 만드는 몇 초 사이의 검수 결정이 캐시 저장 경쟁에서 지워져도
    화면·추천은 사람의 결정을 따른다(검토 2차). 확인된 용어가 아니게 된 것은 뺀다."""
    now = {t.term_id: t for t in ds.list_terms(con, ("verified",))}
    out = []
    for s in stored:
        t = now.get(s.card.term_id)
        if t:
            out.append(s.model_copy(update={"card": s.card.model_copy(update={"risk_level": t.risk_level, "risk_reasons": t.risk_reasons,
                                                                              "risk_checked_at": t.risk_checked_at})}))
    return out


def _browsable(c: KeywordCard) -> bool:
    """둘러보는 목록에 낼 수 있나. 표제어 자체가 욕설·성적 표현이면 내지 않는다 — 검수자가 '문제 없음' 으로 정한 것은 낸다(오탐을 사람이 풀 수 있게)."""
    return not unsafe(c.canonical) or c.risk_level == "none"


def _loaded(con: Connection) -> tuple[list[Stored], datetime]:
    loaded = _load(con)
    if loaded is None:                # 첫 실행 전이거나 예전 캐시 — 바로 만들어 둔다
        _save(con, build(con))
        loaded = _load(con) or ([], datetime.now())
    stored, generated_at = loaded
    return [s for s in _live(con, stored) if _browsable(s.card)], generated_at


def chosen_regions(regions: list[str] | None) -> list[str]:
    known = [*REGIONS_FOCUS, GLOBAL]
    return [r for r in known if r in (regions or [])] or list(REGIONS_FOCUS)


def cards(con: Connection, regions: list[str] | None = None) -> list[KeywordCard]:
    """고른 지역의 모든 카드 — 목록 셋의 30개 자르기 없이. 추천이 후보로 쓴다(표시 목록에서 가져오면 알맞은 밈이 잘려 나갔다, 검토 2차)."""
    stored, _ = _loaded(con)
    chosen = chosen_regions(regions)
    return [view(s, chosen) for s in stored if set(s.card.regions) & set(chosen)]


def cards_by_id(con: Connection, term_ids: list[str]) -> list[KeywordCard]:
    """용어 id 로 대시보드 카드를 한 번에 (최근 변화 행에 단계·쓸 때 조심을 붙인다). 모든 지역을 더한 값이고, 둘러보는 목록에 없는 말은 빠진다.
    대시보드 첫 쪽에서 찾으면 30개 밖의 밈이 빈칸이 됐다(개편 통합 09-29)."""
    want = set(term_ids)
    stored, _ = _loaded(con)
    return [view(s, [*REGIONS_FOCUS, GLOBAL]) for s in stored if s.card.term_id in want]


def _summary(cards: list[KeywordCard], now: datetime) -> RegionSummary:
    rising, fading, caution = split(cards, now)
    top = (rising or fading or [None])[0]
    return RegionSummary(caution=len(caution), top=RegionTop(term_id=top.term_id, canonical=top.canonical, lang=top.lang) if top else None)


def board(con: Connection, regions: list[str] | None = None, page: int = 1, summary: bool = False) -> KeywordBoard:
    """고른 지역의 대시보드. regions 가 없으면 목표 지역 전체(전 세계 묶음은 빼고).
    표제어 자체가 욕설·성적 표현인 것은 둘러보는 목록에 내지 않는다(사전에서 직접 찾으면 나온다 — tools.list_terms 와 같은 규칙).
    목록마다 전체 건수(totals)를 주고, page 쪽(LIST_MAX 개씩)만 싣는다 — 30개에서 말없이 잘리던 것(디자인 개편 검토 09-29).
    summary 면 지역마다 주의 수와 대표 밈도 준다(세계 지도)."""
    stored, generated_at = _loaded(con)
    known = [*REGIONS_FOCUS, GLOBAL]
    chosen = chosen_regions(regions)
    picked = [view(s, chosen) for s in stored if set(s.card.regions) & set(chosen)]
    rising, fading, caution = split(picked, generated_at)
    page = max(1, page)
    cut = slice((page - 1) * LIST_MAX, page * LIST_MAX)
    counts = {r: sum(1 for s in stored if r in s.card.regions) for r in known}
    counts["ALL"] = sum(1 for s in stored if set(s.card.regions) & set(REGIONS_FOCUS))   # '전체' 칩 — 목표 지역 어디든(전 세계만인 것은 빼고)
    out = KeywordBoard(generated_at=generated_at, regions=chosen, counts=counts,
                       totals={"rising": len(rising), "fading": len(fading), "caution": len(caution)}, page=page, page_size=LIST_MAX,
                       rising=rising[cut], fading=fading[cut], caution=caution[cut])
    if summary:   # 지역마다 그 지역만의 수로 다시 나눈다 — 대시보드에서 그 지역을 골랐을 때와 같은 1위
        out.summary = {r: _summary([view(s, [r]) for s in stored if r in s.card.regions], generated_at) for r in known}
    return out


def card(con: Connection, term_id: str, regions: list[str] | None = None) -> KeywordCard | None:
    """용어 하나의 신호 (사전 화면의 '언급 추이'). regions 가 없으면 모든 나라를 더하고, 있으면 대시보드 행과 같은 지역만 더한다
    (대시보드와 사전 항목의 수가 달랐다, 개편 검토 2차). 목표 지역 밖 용어도 만들어 준다."""
    chosen = chosen_regions(regions) if regions else [*REGIONS_FOCUS, GLOBAL]
    for s in _live(con, (_load(con) or ([], None))[0]):
        if s.card.term_id == term_id:
            return view(s, chosen)
    t = ds.get_term(con, term_id)
    if not t or t.status != "verified":
        return None
    s = build_card(con, t, _recent_queries(con), _Regions(con, term_id), _weeks(), outside=True)
    return view(s, chosen) if s else None


def run(con: Connection) -> dict:
    with stage(con, "dashboard") as r:
        stored = build(con)
        _save(con, stored)
        r.count = len(stored)
        r.detail = {k: sum(1 for s in stored if k in s.card.regions) for k in (*REGIONS_FOCUS, GLOBAL)}
    return {"dashboard": r}
