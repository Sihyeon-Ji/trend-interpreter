"""5단계 추적. 뉴스 제목·쇼츠 해석·트렌드 검색어에서 용어 언급을 주 단위로 세고, 생애주기 규칙으로 단계와 재검증 주기를 정한다."""
from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from ..lifecycle import stage as life_stage
from ..schemas import NewsItem, ShortsInterpretation, ShortsVideo
from ..storage import dictionary_store as ds
from .match import mentions, same_term
from .runs import stage

WEEKS = 12


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _week(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


def weekly_counts(con: sqlite3.Connection, term: str, aliases: list[str]) -> Counter:
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
    return c


def run(con: sqlite3.Connection) -> dict:
    with stage(con, "track") as r:
        today = date.today()
        weeks = [_week(today - timedelta(weeks=i)) for i in range(WEEKS - 1, -1, -1)]
        n = 0
        for t in ds.list_terms(con, ("verified", "needs_review", "researching")):
            c = weekly_counts(con, t.canonical, t.aliases)
            counts = {w: c.get(w, 0) for w in weeks}
            ds.set_weekly(con, t.term_id, counts)
            observed = [datetime.fromisoformat(w) for w, v in c.items() if v]
            first = min([t.first_seen.replace(tzinfo=None) if t.first_seen else datetime.now()] + observed)
            weeks_since = max(0, (datetime.now() - first).days // 7)
            t.lifecycle = life_stage([counts[w] for w in weeks], weeks_since)
            t.first_seen = first.replace(tzinfo=timezone.utc)
            if observed:
                t.last_seen = max(observed).replace(tzinfo=timezone.utc)
            ds.upsert_term(con, t)
            n += 1
        r.count = n
    return {"track": r}
