"""1단계 수집. 키 없는 소스(뉴스 RSS·트렌드 RSS·위키)는 항상, YouTube·BigQuery 는 키·ADC 가 있을 때만."""
from __future__ import annotations

from datetime import date, timedelta

from ..collectors import google_trends as gt
from ..collectors import news_rss, wikipedia_search, wikipedia_top, youtube
from ..config import GOOGLE_CLOUD_PROJECT, REGIONS_ALL, REGIONS_FOCUS, YOUTUBE_API_KEY
from ..lifecycle import recheck_interval_days
from ..storage import dictionary_store as ds
from ..storage import store as db
from .runs import stage
from ..storage.db import Connection

SEARCH_REGIONS_PER_RUN = 4  # search.list 는 100 unit → 하루 쿼터 안에서 집중 국가를 돌려 가며


def _rotate(items: list[str], k: int) -> list[str]:
    if k >= len(items):
        return items
    start = (date.today().toordinal() * k) % len(items)
    return [items[(start + i) % len(items)] for i in range(k)]


def run(con: Connection, mention_terms: int = 30) -> dict:
    news_rss.reset_breaker()  # 상류 차단기는 수집 한 바퀴 단위 — 이 뒤의 spikes·topics 는 같은 판정을 이어받고, 다음 실행은 다시 시도한다
    out: dict = {}
    with stage(con, "collect.youtube") as r:
        if not YOUTUBE_API_KEY:
            r.status, r.note = "skipped", "YOUTUBE_API_KEY 없음"
        else:
            n = 0
            for region in REGIONS_ALL:
                n += db.upsert_videos(con, youtube.fetch_most_popular(region, shorts_only=False))
            for region in _rotate(REGIONS_FOCUS, SEARCH_REGIONS_PER_RUN):
                n += db.upsert_videos(con, youtube.search_shorts("#shorts", region, hours=48, lang=wikipedia_search.lang_for(region)))  # regionCode 만으로는 KR 검색의 86% 가 힌디 쇼츠였다(09-15 실측)
            r.count = n
        out["youtube"] = r
    with stage(con, "collect.news") as r:
        n = 0
        for region in news_rss.LOCALES:
            try:
                n += db.upsert_news(con, news_rss.fetch_news(region))
            except Exception as e:  # 한 로케일 실패는 건너뛴다
                r.note += f"{region}:{type(e).__name__} "
        r.count = n
        out["news"] = r
    with stage(con, "collect.trends_rss") as r:
        n = 0
        for region in REGIONS_ALL:
            try:
                n += ds.upsert_trend_queries(con, gt.trending_now(region))
            except Exception as e:
                r.note += f"{region}:{type(e).__name__} "
        r.count = n
        out["trends_rss"] = r
    with stage(con, "collect.trends_bq") as r:
        if not GOOGLE_CLOUD_PROJECT:
            r.status, r.note = "skipped", "GOOGLE_CLOUD_PROJECT 없음"
        else:
            d = gt.latest_refresh_date()
            avail = set(gt.countries(d))
            n = 0
            for region in [x for x in REGIONS_ALL if x in avail]:
                n += ds.upsert_trend_queries(con, gt.rising_terms(region, d))
                n += ds.upsert_trend_queries(con, gt.top_terms(region, d))
            r.count, r.note = n, f"refresh_date={d} countries={len(avail)}"
        out["trends_bq"] = r
    with stage(con, "collect.wikipedia") as r:
        n = 0
        for lang in wikipedia_top.LANG_REGION:
            try:
                n += ds.upsert_wiki_top(con, wikipedia_top.top_articles(lang))
            except Exception as e:
                r.note += f"{lang}:{type(e).__name__} "
        r.count = n
        out["wikipedia"] = r
    # 사전 용어의 언급 추적용 뉴스 검색 (재검증 주기가 짧은 것부터)
    with stage(con, "collect.mentions") as r:
        terms = ds.list_terms(con, ("verified", "needs_review", "researching"))
        terms.sort(key=lambda t: recheck_interval_days(t.lifecycle))
        n = 0
        for t in terms[:mention_terms]:
            region = "KR" if t.lang == "ko" else {"ja": "JP", "id": "ID", "th": "TH", "vi": "VN", "de": "DE", "pt": "BR", "es": "MX"}.get(t.lang, "US")
            if region not in news_rss.LOCALES:
                region = "US"
            try:
                n += db.upsert_news(con, news_rss.fetch_news(region, query=t.canonical, limit=20))
            except Exception as e:
                r.note += f"{t.canonical}:{type(e).__name__} "
        r.count = n
        r.detail["terms"] = len(terms)
        out["mentions"] = r
    # YouTube API 약관: 저장한 메타데이터는 30일 안에 갱신하거나 지운다. 해석(interpretations)에 쓰인 영상은 URL·해석만 남기고 원본 메타는 지운다
    with stage(con, "collect.retention") as r:
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        n = con.execute("DELETE FROM video_snapshots WHERE seen_at < ?", (cutoff,)).rowcount
        n += con.execute("DELETE FROM videos WHERE last_seen < ?", (cutoff,)).rowcount
        con.commit()
        pruned = ds.prune_dangling_edges(con)
        cache, lookups = ds.prune_user_text(con)
        r.count, r.status = n, "ok"
        r.note = (f"30일 경과 삭제 {n}건" if n else "삭제 대상 없음") + (f" · 근거 없는 엣지 {pruned}건 정리" if pruned else "") \
            + (f" · 해석 캐시 {cache}건(7일)" if cache else "") + (f" · 미해결 질문 {lookups}건(30일)" if lookups else "")
        out["retention"] = r
    return out
