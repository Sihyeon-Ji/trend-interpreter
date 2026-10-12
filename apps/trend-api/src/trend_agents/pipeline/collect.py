"""1단계 수집. 키 없는 소스(뉴스 RSS·트렌드 RSS·위키)는 항상, YouTube·BigQuery 는 키·ADC 가 있을 때만."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..collectors import google_trends as gt
from ..collectors import news_rss, wikipedia_search, wikipedia_top, youtube
from ..config import ENGLISH_EDITIONS, GOOGLE_CLOUD_PROJECT, REGIONS_ALL, REGIONS_FOCUS, YOUTUBE_API_KEY, home_region, next_region, region_cycle
from ..lifecycle import recheck_interval_days
from ..storage import approvals
from ..storage import dictionary_store as ds
from ..storage import store as db
from .match import mentions
from .runs import stage
from ..storage.db import Connection

SEARCH_REGIONS_PER_RUN = 4  # search.list 는 100 unit → 하루 쿼터 안에서 집중 국가를 돌려 가며
# 매체의 나라(Plan 04). 뉴스판(版)이 곧 매체의 나라는 아니다 — 싱가포르판에서 찾은 'vibe' 기사 16건에 싱가포르 매체는 0곳이었고,
# 홍콩판의 領便當 기사는 LINE TODAY 등 대만·태국 매체였다(2026-09-30 실측). 최근 머리기사의 대부분이 한 판에서 나온 매체만 그 나라 매체로 본다.
HOME_DAYS = 28
HOME_SHARE = 0.8
HOME_ROWS = 10       # 머리기사에 드물게 뜬 매체(한 판에 몇 번 걸린 K-pop·시계 사이트)를 그 나라 매체로 보지 않게


def _rotate(items: list[str], k: int) -> list[str]:
    if k >= len(items):
        return items
    start = (date.today().toordinal() * k) % len(items)
    return [items[(start + i) % len(items)] for i in range(k)]


def mention_order(con, terms: list, n: int = 30) -> list:
    """뉴스 검색으로 언급을 잴 n 개 — 한 번도 안 잰 것·가장 오래전에 잰 것부터. 재검증 주기로만 줄 세우면 같은 30개(주기가 같으면
    이름순)만 매번 재서, 그 30개만 언급이 쌓이고 나머지는 늘 0 이라 생애주기가 뒤집혔다(2026-09-29 검토 2차).
    칸은 사전에 오른 말(verified, 대시보드·추천이 쓰는 말)에 3분의 2, 검수 대기·조사 중인 말에 3분의 1 — 확인된 말이 늘 먼저면 검수 대기 말은
    영영 재지 않아 게이트에 필요한 뉴스 근거를 얻지 못했다(검토 3차: 확인된 말 148개가 30칸을 늘 다 차지). 한쪽이 모자라면 다른 쪽이 채운다."""
    sampled = ds.mention_sampled(con)

    def stale(t):
        return (sampled.get(t.term_id, ""), recheck_interval_days(t.lifecycle))

    verified = sorted((t for t in terms if t.status == "verified"), key=stale)
    others = sorted((t for t in terms if t.status != "verified"), key=stale)
    take = min(len(verified), max(n - len(others), n * 2 // 3))
    return verified[:take] + others[:n - take]


def home_edition(t) -> str:
    """표제어의 나라 뉴스판(광동어는 홍콩, 다른 중국어는 대만). 뉴스판이 없는 나라·언어는 미국판."""
    region = home_region(t.canonical, t.lang) or {"de": "DE", "pt": "BR", "es": "MX"}.get(t.lang, "US")
    return region if region in news_rss.LOCALES else "US"


def mention_regions(t, last: str | None = None) -> list[str]:
    """이 표제어의 언급을 잴 뉴스판. 첫째는 표제어의 나라 판(광동어는 홍콩, 다른 중국어는 대만)으로 매번 잰다 — 생애주기가 보는 틀이다
    (대만·홍콩을 번갈아 재면 홍콩을 잰 주에는 대만 기사가 비어 '지는 중' 으로 읽힐 수 있었다). 여러 목표 지역이 같이 쓰는 말은 다른 판을 더한다:
    중국어는 홍콩판, 영어는 싱가포르·말레이시아·필리핀 영어판 하나(지난번 다음 차례)."""
    home = home_edition(t)
    others = ENGLISH_EDITIONS if t.lang == "en" else tuple(r for r in region_cycle(t.canonical, t.lang) if r != home)
    return [home, next_region(others, last)] if others else [home]


def source_homes(con: Connection) -> dict[str, str]:
    """매체 → 그 매체의 나라(뉴스판). 최근 HOME_DAYS 일 머리기사의 HOME_SHARE 이상이 한 판에서 나왔고 HOME_ROWS 건 이상인 매체만 —
    여러 판에 뜨는 매체(BBC 는 영국판 40%)와 머리기사에 드문 매체는 나라가 없다. 실측(09-14~29 머리기사): The Straits Times 93%·CNA 97%
    싱가포르, The Star 93% 말레이시아, Inquirer.net 100% 필리핀, 香港01 100% 홍콩, 自由時報 99% 대만, LINE TODAY 91% 태국."""
    since = (datetime.now(timezone.utc) - timedelta(days=HOME_DAYS)).isoformat()
    out: dict[str, str] = {}
    for source, by in db.headline_sources(con, since).items():
        region, n = by.most_common(1)[0]
        total = sum(by.values())
        if total >= HOME_ROWS and n >= HOME_SHARE * total:
            out[source] = region
    return out


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
                rows = wikipedia_top.top_articles(lang)
                ds.upsert_wiki_top(con, rows)
                n += len(rows)   # 받은 수. 새로 넣은 수를 세면 하루 두 번째 실행부터 0 이라 '소스 확인' 경고가 거짓으로 떴다
            except Exception as e:
                r.note += f"{lang}:{type(e).__name__} "
        r.count = n
        out["wikipedia"] = r
    # 사전 용어의 언급 추적용 뉴스 검색 (재검증 주기가 짧은 것부터)
    with stage(con, "collect.mentions") as r:
        terms = ds.list_terms(con, ("verified", "needs_review", "researching"))
        last = ds.mention_rotation(con)
        homes = source_homes(con)
        n = 0
        for t in mention_order(con, terms, mention_terms):
            regions = mention_regions(t, last.get(t.term_id))
            evidence = {home_edition(t), *(u["region"] for u in ds.get_usage(con, t.term_id))}
            try:
                for i, region in enumerate(regions):
                    items = news_rss.fetch_news(region, query=t.canonical, limit=20)
                    n += len(items)
                    # 근거(news)는 표제어의 나라 판·조사가 정한 쓰는 나라의 판에서 받은 기사, 그 밖의 판에서는 그 판의 나라 매체가 낸 기사만.
                    # 다른 나라 매체가 그 판에 뜬 것(싱가포르판의 BBC·Bloomberg)은 근거로 보이거나 게이트에 세지 않고 mention_samples 에만 둔다 —
                    # news 에 넣으면 같은 기사를 나중에 미국판에서 받아도 주소가 같아 근거가 되지 못했다(검토 09-30)
                    db.upsert_news(con, [x for x in items if region in evidence or homes.get(x.source) == region])
                    ds.add_mention_samples(con, t.term_id, [x for x in items if mentions(x.title, t.canonical, t.aliases)], homes)
                    if i == 0:
                        ds.mark_mention_sampled(con, t.term_id, regions[-1])   # 결과가 0건이어도 잰 것이다. 돌아가며 재는 판은 다음에 다음 차례
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
        copies = approvals.prune(con)
        r.count, r.status = n, "ok"
        r.note = (f"30일 경과 삭제 {n}건" if n else "삭제 대상 없음") + (f" · 근거 없는 엣지 {pruned}건 정리" if pruned else "") \
            + (f" · 해석 캐시 {cache}건(7일)" if cache else "") + (f" · 미해결 질문 {lookups}건(30일)" if lookups else "") \
            + (f" · 문구 승인 본문 {copies}건(30일)" if copies else "")
        out["retention"] = r
    return out
