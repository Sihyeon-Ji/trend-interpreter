"""7단계 보드. 분류된 트렌드 검색어를 나라 × 카테고리로 묶고 사전 용어와 연결한다. 주제(나라별 변형)는 용어의 사용 지역이 2개 이상일 때 최소 형태로 만든다 — 차이 설명은 에이전트 단계가 채운다."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import json

from ..schemas import EvidenceBrief, Text2, Topic, TopicVariant, TopicVariantLink, TrendBoard, TrendItem, TrendWhy
from ..storage import dictionary_store as ds
from .runs import stage
from ..storage.db import Connection

PER_CELL = 6
WEEKS = 12
SOURCE_PRIORITY = {"bq_rising": 0, "rss_now": 1, "bq_top": 2, "namu_rank": 3}
# 출처 설명 (한국어, 영어). 나무위키 실시간 검색어가 빠져 있어 보드 단계 전체가 KeyError 로 멈췄다(2026-09-28 19시~).
SOURCE_NOTE = {"bq_rising": ("Google Trends rising",) * 2, "rss_now": ("Google Trends now",) * 2, "bq_top": ("Google Trends top",) * 2,
               "namu_rank": ("나무위키 실시간 검색어", "Namuwiki trending search")}


def _week(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


SHOPPING_CATEGORY = {"패션의류": ("fashion_beauty", "Fashion apparel"), "패션잡화": ("fashion_beauty", "Fashion accessories"), "화장품/미용": ("fashion_beauty", "Cosmetics & beauty"),
                     "식품": ("food", "Food"), "디지털/가전": ("product", "Electronics")}
AGE_LABEL = {"10": ("10대", "teens"), "20": ("20대", "20s"), "30": ("30대", "30s"), "40": ("40대", "40s"), "50": ("50대", "50s"), "60": ("60대 이상", "60+")}


def shopping_items(con: Connection) -> list[TrendItem]:
    """네이버쇼핑 분야별 클릭 추세 → 한국 보드의 패션·뷰티/음식/제품 항목. 값은 요청 내 상대지수라 방향(상승·하락)과 연령 비중만 쓴다."""
    series = ds.shopping_series(con)
    items: list[TrendItem] = []
    for cat, (tcat, en_name) in SHOPPING_CATEGORY.items():
        allpts = series.get((cat, "all"), [])
        if len(allpts) < 3:
            continue
        vals = [v for _, v in allpts][-WEEKS:]
        last, prev = vals[-1], vals[-2]
        change = "up" if last >= prev * 1.15 else ("down" if last <= prev * 0.85 else "flat")
        # 최근 주 연령 비중: 연령별 마지막 값 비교 (같은 주, 서로 다른 요청이라 대략적 비교)
        ages = {a: series[(cat, a)][-1][1] for a in AGE_LABEL if (cat, a) in series and series[(cat, a)]}
        top = max(ages, key=ages.get) if ages else None
        trend_ko = {"up": "최근 주 클릭 상승", "down": "최근 주 클릭 하락", "flat": "클릭 유지"}[change]
        trend_en = {"up": "clicks up last week", "down": "clicks down last week", "flat": "clicks steady"}[change]
        note = Text2(ko=f"네이버쇼핑 {cat} 분야 · {trend_ko}" + (f" · {AGE_LABEL[top][0]} 비중 최고" if top else ""),
                     en=f"Naver Shopping {en_name} · {trend_en}" + (f" · strongest among {AGE_LABEL[top][1]}" if top else ""))
        items.append(TrendItem(id=f"ns_{abs(hash(cat)) % 10**8}", region="KR", category=tcat, term=cat, rank=0, change=change, gain_pct=None,
                               weekly=[int(round(v)) for v in vals] or [0] * WEEKS, note=note))
    return items


def build(con: Connection) -> TrendBoard:
    cls = {row[0]: row for row in con.execute("SELECT key, term, region, category, kind, is_term_candidate, lang FROM trend_class").fetchall()}
    # (term, region) 별 등장 날짜 → 주간 등장 수 + 최신 순위
    hist: dict[tuple[str, str], set[str]] = defaultdict(set)
    latest: dict[tuple[str, str], tuple[str, int, str, int | None, str | None]] = {}
    for term, region, rank, source, d, gain, news_title in con.execute(
        "SELECT term, region, rank, source, date, percent_gain, news_title FROM trend_queries"
    ).fetchall():
        k = (term, region)
        hist[k].add(d)
        cur = latest.get(k)
        cand = (d, rank, source, gain, news_title)
        if not cur or (cand[0], -SOURCE_PRIORITY[source]) > (cur[0], -SOURCE_PRIORITY[cur[2]]):
            latest[k] = cand
    today = date.today()
    weeks = [_week(today - timedelta(weeks=i)) for i in range(WEEKS - 1, -1, -1)]
    latest_day_by_region: dict[str, str] = {}
    for (term, region), (d, *_rest) in latest.items():
        latest_day_by_region[region] = max(latest_day_by_region.get(region, ""), d)
    expl = ds.explanations_by_region(con)
    cells: dict[tuple[str, str], list[TrendItem]] = defaultdict(list)
    for (term, region), (d, rank, source, gain, news_title) in latest.items():
        c = cls.get(f"{''.join(term.split()).lower()}|{region}")
        if not c or c[4] in ("place",):
            continue
        # 오늘(그 나라 최신 날짜) 목록에 있는 것만
        if d != latest_day_by_region[region]:
            continue
        days = hist[(term, region)]
        weekly = [sum(1 for x in days if _week(date.fromisoformat(x)) == w) for w in weeks]
        first = min(days)
        change = "new" if first == d else ("up" if (gain or 0) >= 200 else "flat")
        t = ds.find_term(con, term)
        x = expl.get((''.join(term.split()).lower(), region))
        if x and x.self_confidence >= 0.5:
            note = Text2(ko=x.why_now, en=x.why_now_en or x.why_now)
        else:
            ko, en = SOURCE_NOTE[source]
            note = Text2(ko=news_title or ko, en=news_title or en)
        cells[(region, c[3])].append(TrendItem(id=f"ti_{abs(hash((term, region))) % 10**8}", region=region, category=c[3], term=term, rank=0, change=change,
                                                gain_pct=gain, weekly=weekly, term_id=t.term_id if t else None, note=note))
    for it in shopping_items(con):
        cells[(it.region, it.category)].append(it)
    items: list[TrendItem] = []
    for (region, cat), lst in cells.items():
        lst.sort(key=lambda i: (0 if i.change == "new" else 1, -(i.gain_pct or 0), i.term))
        for n, it in enumerate(lst[:PER_CELL], start=1):
            it.rank = n
            items.append(it)
    # 주제: 사용 지역 2개 이상인 검증 용어
    topics: list[Topic] = []
    for t in ds.list_terms(con, ("verified",)):
        usage = ds.get_usage(con, t.term_id)
        timeline = {row["region"]: row for row in ds.get_timeline(con, t.term_id)}
        regions = sorted({u["region"] for u in usage} | set(timeline))
        if len(regions) < 2:
            continue
        m = ds.current_meaning(con, t.term_id)
        en = ds.get_translation(con, t.term_id, "en")
        ko = ds.get_translation(con, t.term_id, "ko")
        notes = ds.get_topic_notes(con, t.term_id)
        variants = []
        for r in regions:
            n = notes.get(r)
            share = max((u["share"] for u in usage if u["region"] == r), default=0.0)
            if n and n.get("self_confidence", 0) >= 0.5:
                wc = Text2(**n["what_changed"])
                memes = [TopicVariantLink(label=x["label"], note=Text2(ko=x.get("note_ko", ""), en=x.get("note_en", ""))) for x in n.get("local_memes", [])]
                local_name = n.get("local_name") or t.canonical
            else:
                wc = Text2(ko="나라별 차이는 조사 중입니다.", en="Country differences are still being researched.")
                memes, local_name = [], t.canonical
            tl = timeline.get(r)
            if tl:
                since, dated, src = tl["first_date"], True, Text2(ko=tl["source_ko"], en=tl["source_en"])
            else:
                # 날짜를 대는 출처가 없다. 용어가 처음 잡힌 날은 참고로만 두고 순서를 정하는 데는 쓰지 않는다
                since, dated, src = (t.first_seen or datetime.now(timezone.utc)).date().isoformat(), False, None
            variants.append(TopicVariant(region=r, local_name=local_name, since=since, dated=dated, since_source=src,
                                         heat=int(100 * share), what_changed=wc, local_memes=memes, term_id=t.term_id))
        # 날짜가 확인된 나라가 먼저, 날짜순. 나머지는 관심도순.
        # 전에는 관심도로만 정렬했는데 조사 단계가 비중을 균등하게 넣어서 순서가 사실상 나라 코드의 알파벳순이었고,
        # 지도는 맨 앞 나라를 '처음 나온 곳'으로 그렸다 — 인기 순서가 이동 경로처럼 보였다.
        variants.sort(key=lambda v: (not v.dated, v.since if v.dated else "", -v.heat))
        cat = {"slang": "slang_meme", "meme": "slang_meme", "song": "song_challenge", "dance": "song_challenge", "product": "product"}.get(t.category, "people_content")
        topics.append(Topic(id=f"tp_{t.term_id}", category=cat, name=Text2(ko=t.canonical, en=t.canonical),
                            summary=Text2(ko=(ko.definition if ko else (m.definition if m else "")), en=(en.definition if en else (m.definition if m else ""))), variants=variants))
    return TrendBoard(generated_at=datetime.now(timezone.utc), items=items, topics=topics, why=why_list(con))


def run(con: Connection) -> dict:
    with stage(con, "board") as r:
        b = build(con)
        ds.cache_set(con, "board", b.model_dump_json())
        r.count = len(b.items)
        r.detail["topics"] = len(b.topics)
        r.detail["regions"] = len({i.region for i in b.items})
    return {"board": r}


def why_list(con: Connection, limit_evidence: int = 8) -> list[TrendWhy]:
    """급증 원인 설명 + 근거 요약 (이용자 카드)."""
    out: list[TrendWhy] = []
    for x in ds.explanations_by_region(con).values():
        evs = ds.list_evidences(con, f"q|{ds.norm(x.term)}|{x.region}")
        counts: dict[str, int] = {}
        for e in evs:
            counts[e.kind] = counts.get(e.kind, 0) + 1
        row = con.execute("SELECT updated_at FROM trend_explanations WHERE key=?", (f"{ds.norm(x.term)}|{x.region}",)).fetchone()
        out.append(TrendWhy(term=x.term, region=x.region, date=x.date, why_now=Text2(ko=x.why_now, en=x.why_now_en or x.why_now), trigger=x.trigger, actors=x.actors,
                            first_signal=x.first_signal, confidence=x.self_confidence, evidence_counts=counts,
                            evidence=[EvidenceBrief(kind=e.kind, source_domain=e.source_domain, title=e.title or e.excerpt, url=e.url, observed_at=e.observed_at) for e in evs[:limit_evidence]],
                            updated_at=datetime.fromisoformat(row[0]) if row else datetime.now(timezone.utc)))
    out.sort(key=lambda w: w.updated_at, reverse=True)
    return out
