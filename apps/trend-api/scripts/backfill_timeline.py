"""나라별 '처음 나타난 날'을 과거 기록에서 역산해 지도의 이동 경로(term_timeline)를 채운다.

한 나라의 날짜는 **서로 다른 현지 언론사 3곳째가 보도한 날**이다 (Google 뉴스 after:/before: 범위 검색, 이름이 제목에 실제로 있는 기사만).
3곳 미만이면 그 나라 날짜는 정하지 않는다 — 지도에서 그 나라는 선 없이 '쓰는 곳'으로만 나온다.
검증 게이트의 '독립 출처' 규칙을 날짜에 그대로 쓴 것이다.

왜 가장 이른 기사 하나가 아닌가 — 기사 날짜가 틀린 경우가 있다. 2026-09-26 실측: 무뎅 태국 뉴스의 첫 기사가 '핼러윈 분장 추천'
기사인데 날짜가 7월 10일(무뎅 생일)이었고, 3번째 기사도 같은 사이트의 날짜 틀린 기사였다. 기사 수가 아니라 언론사 수로 세야
한 사이트가 한 나라의 날짜를 석 달 앞당기지 못한다.

왜 위키백과를 기준으로 쓰지 않는가 — 문서를 빨리 만드는 곳이 먼저 나온다. 같은 날 실측: Italian brainrot 은 한국어판이,
Tung Tung Tung Sahur 는 일본어판이 가장 먼저 생겼다. 시작된 곳이 아니다. 위키백과 날짜는 있으면 출처 설명에 참고로만 붙인다.

출발점은 가장 이른 나라가 둘째보다 확실히 앞설 때만 정한다. 같은 날이면 정하지 않는다 — 무뎅은 태국·한국·일본·인도네시아가
모두 같은 날(2024-09-13) 세 번째 언론사가 보도했다. 한 주 만에 전 세계로 퍼진 밈에는 이동 경로가 없다.

나라는 Google 뉴스 로케일 단위이고(대만은 zh-TW), 제목이 그 나라 문자로 쓰인 기사만 현지 기사로 센다. 영어권 로케일은 세계 영어
기사가 섞여 들어와 현지 여부를 가릴 수 없으므로 날짜를 정하지 않는다.
관측을 시작하기(09-14) 전 일을 다루므로 수집 데이터가 아니라 과거가 남아 있는 출처만 쓴다.

한계: 뉴스는 '언론이 알아챈 날'이지 '사람들이 쓰기 시작한 날'이 아니다. 밈은 쇼츠에서 먼저 뜨고 기사는 뒤따른다.
나라별 가장 이른 쇼츠 게시일(YouTube 검색 publishedBefore)을 두 번째 출처로 붙이면 더 정확해진다 — YouTube 키가 있는 곳에서.

  uv run scripts/backfill_timeline.py --name "Tung Tung Tung Sahur" --local "KR=퉁퉁퉁 사후르" --local "JP=トゥントゥントゥンサフール" \
      --regions ID,KR,JP,US,TH,VN,PH --from 2025-01-01 --to 2025-08-31 --dry
  ... --term t_tung                                        # data/trend.db 의 term_timeline 에 쓴다
  ... --json web/lib/sample/timelines/tung.json           # 예시 데이터용
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

from trend_agents.collectors import news_rss
from trend_agents.pipeline import match
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import sqlite_store as db

RSS_CAP = 100  # Google 뉴스 RSS 는 한 번에 100건까지. 가득 차면 더 이른 기사가 잘렸을 수 있어 그 앞쪽을 다시 찾는다
K = 3  # 서로 다른 언론사가 이만큼 보도해야 그 나라에 '나타났다' 고 본다
# 그 나라 문자로 쓴 제목만 현지 기사로 센다. 영어권 로케일은 Google 뉴스가 세계 영어 기사를 섞어 준다 —
# 2026-09-26 실측: Tung Tung Tung Sahur 의 미국·필리핀·말레이시아 3곳째가 모두 같은 미국 매체(Dexerto)였고,
# Labubu 의 필리핀·미국·싱가포르 3곳째는 모두 태국 영자지(Nation Thailand)였다. 문자로 가릴 수 없는 나라는 날짜를 정하지 않는다.
SCRIPT = {
    "KR": re.compile(r"[가-힣]"),
    "JP": re.compile("[぀-ヿ]"),  # 가나. 한자만으로는 중국어와 구별되지 않는다
    "TH": re.compile("[฀-๿]"),
    # zh-Hant 피드. 홍콩은 대만과 같은 번체 매체를 공유해 문자로 가릴 수 없어 넣지 않는다 (실측: 홍콩 3곳째가 대만 야후 기사였다)
    "TW": re.compile("[一-鿿]"),
    "VN": re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.I),
    "ID": re.compile(r"\b(yang|dan|dari|untuk|dengan|ini|itu|jadi|lagi|bikin|apa)\b", re.I),  # 라틴 문자라 흔한 인도네시아어 낱말로 가린다
}
# 언론사 이름이 다른 나라 문자면 그 나라 매체의 외국어판이다. 제목 문자만으로는 못 거른다 —
# 2026-09-26 실측: 럭키비키의 일본 3곳째가 '매일경제' 일본어판이었다(제목은 가나, 언론사 이름은 한글).
OUTLET_SCRIPT = {"KR": re.compile(r"[가-힣]"), "TH": re.compile("[฀-๿]"), "JP": re.compile("[぀-ヿ]")}


def foreign_outlet(region: str, outlet: str) -> bool:
    return any(r != region and pat.search(outlet) for r, pat in OUTLET_SCRIPT.items())


# 두 글자 이하 한자 이름은 다른 문장 속에 우연히 들어 있기 쉽다 — 같은 날 실측: 대만 '推活' 의 3곳째가
# '江蘇動物園推活驢餵老虎'(당나귀를 밀어 호랑이에게 줬다) 기사였다. 용어로 쓰일 때처럼 따옴표로 감싼 것만 센다.
SHORT_CJK = re.compile("^[぀-ヿ一-鿿]{1,2}$")
QUOTES = ("「{}」", "『{}』", "“{}”", "\"{}\"", "'{}'", "‘{}’", "《{}》")


def names_in(title: str, names: list[str]) -> bool:
    for name in names:
        if SHORT_CJK.match(name):
            if any(q.format(name) in title for q in QUOTES):
                return True
        elif match.mentions(title, name):
            return True
    return False
REGION_NAME = {"KR": ("한국", "Korea"), "JP": ("일본", "Japan"), "TW": ("대만", "Taiwan"), "TH": ("태국", "Thailand"), "VN": ("베트남", "Vietnam"),
               "ID": ("인도네시아", "Indonesia"), "PH": ("필리핀", "Philippines"), "MY": ("말레이시아", "Malaysia"), "SG": ("싱가포르", "Singapore"),
               "HK": ("홍콩", "Hong Kong"), "IN": ("인도", "India"), "AU": ("호주", "Australia"), "US": ("미국", "United States"),
               "GB": ("영국", "United Kingdom"), "IT": ("이탈리아", "Italy"), "DE": ("독일", "Germany"), "BR": ("브라질", "Brazil")}


def outlet_date(region: str, names: list[str], start: date, end: date) -> dict:
    """이름이 제목에 실제로 들어 있는 기사를 모아, 서로 다른 언론사 K 곳째가 보도한 날. 못 채우면 date=None."""
    query_names = " OR ".join(f'"{n}"' for n in names)
    seen: dict[str, object] = {}
    hi = end
    for _ in range(6):
        q = f"({query_names}) after:{start.isoformat()} before:{(hi + timedelta(days=1)).isoformat()}"
        items = news_rss.fetch_news(region, query=q, limit=RSS_CAP)
        local = SCRIPT[region]
        hits = [n for n in items if n.published_at and start <= n.published_at.date() <= end
                and names_in(n.title, names) and local.search(n.title)
                and not foreign_outlet(region, n.source or "")]
        for n in hits:
            seen.setdefault(n.link, n)
        if not hits or len(items) < RSS_CAP:
            break  # 범위 안의 것을 다 받았다
        new_hi = min(n.published_at for n in hits).date() - timedelta(days=1)
        if new_hi < start or new_hi >= hi:
            break
        hi = new_hi
        time.sleep(1.0)
    ordered = sorted(seen.values(), key=lambda n: n.published_at)
    outlets: list[str] = []
    for n in ordered:
        outlet = (n.source or "").strip().lower()
        if outlet and outlet not in outlets:
            outlets.append(outlet)
            if len(outlets) == K:
                return {"date": n.published_at.date(), "title": n.title, "source": n.source or "", "url": n.link,
                        "earliest_raw": ordered[0].published_at.date().isoformat(), "articles": len(ordered),
                        "outlets": len({(x.source or "").strip().lower() for x in ordered if x.source})}
    return {"date": None, "articles": len(ordered), "outlets": len(outlets)}


def backfill(name: str, local: dict[str, list[str]], regions: list[str], start: date, end: date, wiki: dict[str, str] | None = None) -> dict:
    rows, skipped = [], []
    for region in regions:
        names = list(dict.fromkeys([*local.get(region, []), name]))
        if region not in SCRIPT:
            skipped.append({"region": region, "names": names, "articles": 0, "outlets": 0,
                            "why": "현지 기사인지 문자로 가릴 수 없는 로케일 (영어권 등)"})
            continue
        got = outlet_date(region, names, start, end)
        time.sleep(1.0)
        ko_r, en_r = REGION_NAME.get(region, (region, region))
        if got["date"] is None:
            skipped.append({"region": region, "names": names, "articles": got["articles"], "outlets": got["outlets"],
                            "why": f"현지 언론사 {K}곳 미만"})
            continue
        d = got["date"].isoformat()
        wiki_ko = f" · 위키백과 문서 {wiki[region]}" if wiki and region in wiki else ""
        wiki_en = f" · Wikipedia article {wiki[region]}" if wiki and region in wiki else ""
        rows.append({
            "region": region, "local_name": names[0], "first_date": d,
            "source_ko": f"{ko_r} 언론 {K}곳째 보도 {d}{wiki_ko}",
            "source_en": f"{K}rd outlet to report in {en_r}, {d}{wiki_en}",
            "url": got["url"], "news_title": got["title"], "news_source": got["source"],
            "news_earliest_raw": got["earliest_raw"], "news_articles": got["articles"], "news_outlets": got["outlets"],
        })
    rows.sort(key=lambda r: r["first_date"])
    origin = rows[0]["region"] if len(rows) >= 2 and rows[0]["first_date"] < rows[1]["first_date"] else None
    return {"name": name, "window": [start.isoformat(), end.isoformat()], "rule": f"{K} distinct local outlets",
            "origin": origin, "timeline": rows, "skipped": skipped}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", required=True, help="대표 이름 (모든 나라에서 함께 찾는다)")
    ap.add_argument("--local", action="append", default=[], help='나라별 현지 이름 "KR=퉁퉁퉁 사후르" (여러 번, 한 나라에 여러 개 가능)')
    ap.add_argument("--regions", required=True, help="쉼표로 구분한 Google 뉴스 로케일 (예: ID,KR,JP,US)")
    ap.add_argument("--from", dest="start", required=True, type=date.fromisoformat)
    ap.add_argument("--to", dest="end", required=True, type=date.fromisoformat)
    ap.add_argument("--wiki", action="append", default=[], help='참고용 위키백과 문서 생성일 "JP=2025-05-04" (필수 아님)')
    ap.add_argument("--term", help="term_id — 주면 data/trend.db 의 term_timeline 에 쓴다")
    ap.add_argument("--json", help="결과를 이 경로에 JSON 으로 (예시 데이터용)")
    ap.add_argument("--dry", action="store_true", help="쓰지 않고 보기만")
    a = ap.parse_args()

    local: dict[str, list[str]] = {}
    for item in a.local:
        region, _, value = item.partition("=")
        local.setdefault(region.strip().upper(), []).append(value.strip())
    wiki = {k.strip().upper(): v.strip() for k, _, v in (w.partition("=") for w in a.wiki)}
    regions = [r.strip().upper() for r in a.regions.split(",") if r.strip()]
    unknown = [r for r in regions if r not in news_rss.LOCALES]
    if unknown:
        raise SystemExit(f"Google 뉴스 로케일이 없는 나라: {unknown}")

    out = backfill(a.name, local, regions, a.start, a.end, wiki)
    for r in out["timeline"]:
        print(f"  {r['region']}  {r['first_date']}  {r['local_name']:<18} 기사 {r['news_articles']}건 · 언론사 {r['news_outlets']}곳  [첫 기사 날짜 표기 {r['news_earliest_raw']}]")
        print(f"        {K}곳째: {r['news_title'][:70]}  ({r['news_source']})")
    for s in out["skipped"]:
        print(f"  {s['region']}  —           {s['names'][0]:<18} 제외: {s['why']} (기사 {s['articles']}건 · 언론사 {s['outlets']}곳)")
    print(f"출발점: {out['origin'] or '정하지 않음 — 날짜가 확정된 나라가 둘 미만이거나, 가장 이른 날이 겹침'}")
    if a.dry:
        return
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {a.json}")
    if a.term:
        con = db.connect()
        if not ds.get_term(con, a.term):
            raise SystemExit(f"사전에 {a.term} 이 없습니다.")
        ds.set_timeline(con, a.term, out["timeline"])
        print(f"→ term_timeline: {a.term} {len(out['timeline'])}개 나라")


if __name__ == "__main__":
    main()
