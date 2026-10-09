"""쓰임 근거로 생애주기를 정하지 못한 표제어의 검색 관심도를 받는다. track은 이를 생애주기와 별도로 기록한다.
- 한국어: 네이버 데이터랩 검색어 트렌드, 주별 1년, 다섯 개씩 한 번에(하루 한도 1,000회 — 파이프라인 naver 단계가 하루 약 240회 쓴다)
- 그 밖: 위키 밈 분류에서 온 위키백과 문서의 월별 조회수 2년(분류의 문서 제목이 곧 그 밈 문서다)
  uv run scripts/interest_backfill.py --naver-calls 400 --wiki 3000
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.collectors import naver_datalab, wikipedia_search  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

REFRESH_DAYS = 14


def naver_targets(con) -> list:
    stale = (datetime.now(timezone.utc) - timedelta(days=REFRESH_DAYS)).isoformat()
    fresh = {r[0] for r in con.execute("SELECT DISTINCT term_id FROM search_interest WHERE source='naver' AND fetched_at > ?", (stale,))}
    return [t for t in ds.list_terms(con, ("verified",)) if t.lang == "ko" and t.lifecycle == "unknown" and t.term_id not in fresh]


def wiki_targets(con) -> list[tuple]:
    have = {r[0] for r in con.execute("SELECT DISTINCT term_id FROM term_pageviews")}
    unknown = {t.term_id for t in ds.list_terms(con, ("verified",)) if t.lifecycle == "unknown"}   # SQLite·PostgreSQL 공통(json_extract 없이)
    rows = con.execute("SELECT term_id, source, title FROM wiki_catalog WHERE source LIKE 'wiki-%'").fetchall()
    out, seen = [], set()
    for tid, source, title in rows:
        if tid not in unknown or tid in have or tid in seen:
            continue
        seen.add(tid)
        out.append((tid, source[5:], title))
    return out


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--naver-calls", type=int, default=400)
    a.add_argument("--wiki", type=int, default=3000)
    args = a.parse_args()
    con = db.connect()
    log = lambda m: print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)  # noqa: E731
    end = date.today()
    start = end - timedelta(days=364)
    now = datetime.now(timezone.utc).isoformat()

    todo = naver_targets(con)
    log(f"네이버 데이터랩 대상 {len(todo)}개 (이번에 최대 {args.naver_calls * 5}개)")
    calls = got = 0
    for i in range(0, len(todo), 5):
        if calls >= args.naver_calls:
            break
        batch = todo[i:i + 5]
        by_title: dict = {}
        try:
            res = naver_datalab.search_trend([t.canonical for t in batch], start.isoformat(), end.isoformat(), time_unit="week")
            calls += 1
            by_title = {g["title"]: g.get("data", []) for g in res.get("results", [])}
        except Exception as e:
            if "400" not in str(e):
                log(f"  데이터랩 오류 {type(e).__name__}: {str(e)[:80]} — 멈춤(한도일 수 있다)")
                break
            # 데이터랩이 받지 않는 말(특수문자 등)이 섞인 묶음 — 하나씩 다시 부르고 안 되는 말만 빈 값으로 둔다
            for t in batch:
                try:
                    r1 = naver_datalab.search_trend([t.canonical], start.isoformat(), end.isoformat(), time_unit="week")
                    by_title.update({g["title"]: g.get("data", []) for g in r1.get("results", [])})
                except Exception:
                    pass
                calls += 1
        for t in batch:
            rows = [(d["period"], float(d["ratio"])) for d in by_title.get(t.canonical, [])]
            ds.set_interest(con, t.term_id, "naver", rows, now)           # 빈 것도 적는다 — 열나흘 동안 다시 묻지 않게
            got += bool(rows)
        if calls % 50 == 0:
            log(f"  {calls}회 · 관심도 붙음 {got}")
    log(f"데이터랩 {calls}회 · 관심도 붙은 표제어 {got}")

    wt = wiki_targets(con)[:args.wiki]
    log(f"위키 조회수 대상 {len(wt)}개")
    first = (end.replace(day=1) - timedelta(days=730)).strftime("%Y%m01") + "00"
    n = 0
    for k, (tid, lang, title) in enumerate(wt, 1):
        try:
            rows = wikipedia_search.monthly_views(lang, title, start=first)
        except Exception:
            continue
        if rows:
            ds.set_pageviews(con, tid, lang, title, rows)
            n += 1
        if k % 200 == 0:
            log(f"  {k}/{len(wt)} · 조회수 붙음 {n}")
    log(f"위키 조회수 붙은 표제어 {n}")


if __name__ == "__main__":
    main()
