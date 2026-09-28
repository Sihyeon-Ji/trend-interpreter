"""5단계 추적. 뉴스 제목·쇼츠 해석·트렌드 검색어에서 용어 언급을 주 단위로 세고, 생애주기 규칙으로 단계와 재검증 주기를 정한다."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from ..lifecycle import diffusion, recency_stage, stage as life_stage
from ..schemas import Evidence, NewsItem, ShortsInterpretation, ShortsVideo
from ..storage import dictionary_store as ds
from .match import mentions, same_term
from .runs import stage
from ..storage.db import Connection

WEEKS = 12


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _week(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


# 쓰임을 실제로 관측한 근거만 센다. 위키·웹은 설명 문서이고, 데이터랩은 지수라 '언급' 이 아니다.
# 네이버 검색 결과는 약관상 표시 전용이라 신호로도 쓰지 않는다.
USAGE_KINDS = ("community", "news", "short")


def evidence_weeks(con: Connection, term_id: str) -> Counter:
    """조사가 모은 근거를 관측한 주에 센다. 이게 빠져서 근거 50건짜리 표제어도 언급 0 → unknown 이었다
    (2026-09-28 표본 30개 전부. Plan 02)."""
    c: Counter = Counter()
    seen: set[tuple[str, str]] = set()
    for (j,) in con.execute("SELECT json FROM evidences WHERE term_id=?", (term_id,)).fetchall():
        e = Evidence.model_validate_json(j)
        if e.kind not in USAGE_KINDS or e.source_domain.startswith("naver"):
            continue
        w = _week(e.observed_at.date())
        if (e.url, w) in seen:
            continue
        seen.add((e.url, w))
        c[w] += 1
    return c


def usage_kinds(con: Connection, term_id: str) -> dict[str, int]:
    """쓰임 근거를 종류별로 센다(네이버 표시 전용 결과 제외). 확산 단계 판정에 쓴다.
    'documented' 는 백과사전 문서(위키백과·나무위키) 근거 수 — 쓰임은 아니지만 자리 잡은 말인지 가른다."""
    c: Counter = Counter()
    for (j,) in con.execute("SELECT json FROM evidences WHERE term_id=?", (term_id,)).fetchall():
        e = Evidence.model_validate_json(j)
        if e.kind in USAGE_KINDS and not e.source_domain.startswith("naver"):
            c[e.kind] += 1
        elif e.kind == "wiki" or (e.kind == "web" and e.source_domain.endswith("wikipedia.org")):
            c["documented"] += 1   # 나무위키·위키백과 문서. 나무위키 실시간 검색어(datalab)는 문서가 아니다
    return dict(c)


def newest_usage(con: Connection, term_id: str) -> datetime | None:
    """조사가 찾은 쓰임 근거 중 가장 최근 관측 시각."""
    newest = None
    for (j,) in con.execute("SELECT json FROM evidences WHERE term_id=?", (term_id,)).fetchall():
        e = Evidence.model_validate_json(j)
        if e.kind in USAGE_KINDS and not e.source_domain.startswith("naver"):
            at = e.observed_at if e.observed_at.tzinfo else e.observed_at.replace(tzinfo=timezone.utc)
            newest = at if newest is None or at > newest else newest
    return newest


def weekly_counts(con: Connection, term: str, aliases: list[str], term_id: str | None = None,
                  by_region: dict[str, Counter] | None = None) -> Counter:
    """원본(뉴스 제목·쇼츠 해석·검색어)에서 주별 언급 수. by_region 을 주면 같은 한 번의 훑기로 나라별로도 센다(Plan 04)."""
    keys = {_norm(term), *(_norm(a) for a in aliases)}
    c: Counter = Counter()

    def add(week: str, region: str | None) -> None:
        c[week] += 1
        if by_region is not None and region:
            by_region.setdefault(region, Counter())[week] += 1

    for (j,) in con.execute("SELECT json FROM news").fetchall():
        n = NewsItem.model_validate_json(j)
        if mentions(n.title, term, aliases):
            d = (n.published_at or datetime.now(timezone.utc)).date()
            add(_week(d), n.region)
    for j, vj in con.execute("SELECT i.json, v.json FROM interpretations i LEFT JOIN videos v ON v.video_id=i.video_id").fetchall():
        it = ShortsInterpretation.model_validate_json(j)
        if any(same_term(m.name, term, aliases) for m in it.memes):
            v = ShortsVideo.model_validate_json(vj) if vj else None
            add(_week(v.published_at.date() if v else date.today()), v.region if v else None)
    for t, d, region in con.execute("SELECT term, date, region FROM trend_queries").fetchall():
        if _norm(t) in keys:
            add(_week(date.fromisoformat(d)), region)
    if term_id:
        c.update(evidence_weeks(con, term_id))
    return c


def run(con: Connection) -> dict:
    with stage(con, "track") as r:
        today = date.today()
        weeks = [_week(today - timedelta(weeks=i)) for i in range(WEEKS - 1, -1, -1)]
        n = 0
        for t in ds.list_terms(con, ("verified", "needs_review", "researching")):
            by_region: dict[str, Counter] = {}
            raw = weekly_counts(con, t.canonical, t.aliases, by_region=by_region)
            # 주간 언급·마지막 본 때는 원본만. 조사 근거는 조사한 주에 몰려 '최근 조사한 것' 이 '요즘 뜨는 것' 으로
            # 보였다(2026-09-29 검토: 2017년 가즈아·날아다니는 스파게티 괴물이 '10대 유행어' 윗줄). 근거는 처음 본 때와
            # '마지막으로 쓰인 때'(recency_stage) 에만 쓴다.
            ds.set_weekly(con, t.term_id, {w: raw.get(w, 0) for w in weeks})
            ds.set_weekly_region(con, t.term_id, {r: {w: cnt.get(w, 0) for w in weeks} for r, cnt in by_region.items()})
            observed_raw = [datetime.fromisoformat(w) for w, v in raw.items() if v]
            observed = observed_raw + [datetime.fromisoformat(w) for w, v in evidence_weeks(con, t.term_id).items() if v]
            first = min([t.first_seen.replace(tzinfo=None) if t.first_seen else datetime.now()] + observed)
            weeks_since = max(0, (datetime.now() - first).days // 7)
            # 모양(오르는 중·정점)은 꾸준히 모으는 원본(뉴스·쇼츠·검색어)으로만 판정한다. 조사 근거는 조사한 주에만
            # 몰려서, 그대로 넣으면 '우리가 언제 조사했나' 를 잰다(2026-09-28: 2017년 유행어 가즈아가 '오르는 중').
            # 원본에 언급이 없으면 조사 근거로는 '마지막으로 쓰인 때' 만 본다.
            raw_series = [raw.get(w, 0) for w in weeks]
            if sum(raw_series):
                t.lifecycle = life_stage(raw_series, weeks_since)
            else:
                t.lifecycle = recency_stage(newest_usage(con, t.term_id))
            lifecycle, dif = t.lifecycle, diffusion(usage_kinds(con, t.term_id), t.lifecycle)
            # 다른 필드는 저장된 쪽에서 — 훑는 몇 분 사이 검수자가 승인·제외한 것을 시작 때 읽은 사본이 덮지 않게
            fresh = ds.get_term(con, t.term_id) or t
            fresh.lifecycle, fresh.diffusion = lifecycle, dif
            fresh.first_seen = first.replace(tzinfo=timezone.utc)
            if observed_raw:
                fresh.last_seen = max(observed_raw).replace(tzinfo=timezone.utc)
            ds.upsert_term(con, fresh)
            n += 1
        r.count = n
    return {"track": r}
