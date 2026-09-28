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
    """쓰임 근거를 종류별로 센다(네이버 표시 전용 결과 제외). 확산 단계 판정에 쓴다."""
    c: Counter = Counter()
    for (j,) in con.execute("SELECT json FROM evidences WHERE term_id=?", (term_id,)).fetchall():
        e = Evidence.model_validate_json(j)
        if e.kind in USAGE_KINDS and not e.source_domain.startswith("naver"):
            c[e.kind] += 1
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


def weekly_counts(con: Connection, term: str, aliases: list[str], term_id: str | None = None) -> Counter:
    keys = {_norm(term), *(_norm(a) for a in aliases)}
    c: Counter = Counter()
    for (j,) in con.execute("SELECT json FROM news").fetchall():
        n = NewsItem.model_validate_json(j)
        if mentions(n.title, term, aliases):
            d = (n.published_at or datetime.now(timezone.utc)).date()
            c[_week(d)] += 1
    for j, vj in con.execute("SELECT i.json, v.json FROM interpretations i LEFT JOIN videos v ON v.video_id=i.video_id").fetchall():
        it = ShortsInterpretation.model_validate_json(j)
        if any(same_term(m.name, term, aliases) for m in it.memes):
            d = ShortsVideo.model_validate_json(vj).published_at.date() if vj else date.today()
            c[_week(d)] += 1
    for t, d in con.execute("SELECT term, date FROM trend_queries").fetchall():
        if _norm(t) in keys:
            c[_week(date.fromisoformat(d))] += 1
    if term_id:
        c.update(evidence_weeks(con, term_id))
    return c


def run(con: Connection) -> dict:
    with stage(con, "track") as r:
        today = date.today()
        weeks = [_week(today - timedelta(weeks=i)) for i in range(WEEKS - 1, -1, -1)]
        n = 0
        for t in ds.list_terms(con, ("verified", "needs_review", "researching")):
            raw = weekly_counts(con, t.canonical, t.aliases)
            c = raw + evidence_weeks(con, t.term_id)
            counts = {w: c.get(w, 0) for w in weeks}
            ds.set_weekly(con, t.term_id, counts)
            observed = [datetime.fromisoformat(w) for w, v in c.items() if v]
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
            t.diffusion = diffusion(usage_kinds(con, t.term_id), t.lifecycle)
            t.first_seen = first.replace(tzinfo=timezone.utc)
            if observed:
                t.last_seen = max(observed).replace(tzinfo=timezone.utc)
            ds.upsert_term(con, t)
            n += 1
        r.count = n
    return {"track": r}
