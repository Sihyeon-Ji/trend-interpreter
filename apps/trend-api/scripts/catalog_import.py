"""위키 밈 분류 일괄 넣기 (Plan 16). data/work/catalog/namu.json({문서: [분류]})을 읽어 표제어를 세우고 가벼운 조사를 돌린다.
파이프라인과 겹치지 않게 cron 창(9·14·19·23시 15분부터 한 시간)·잠금 중에는 쉰다. 실패(오류·문서에 닿지 못함)는 catalog_failed 에 남기고
--retry-failed 로 다시 돈다. 멈췄다 다시 돌려도 이어서 한다.
  uv run scripts/catalog_import.py --limit 50          # 50개만
  uv run scripts/catalog_import.py --dry               # 세울 것만 센다
"""
from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.collectors import fandom, wikidata_memes  # noqa: E402
from trend_agents.pipeline import catalog  # noqa: E402
from trend_agents.pipeline.research import research_one  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

LOCK = "/tmp/trend-pipeline.lock"


def failed(con, source: str, title: str, reason: str) -> None:
    con.execute("CREATE TABLE IF NOT EXISTS catalog_failed (source TEXT, title TEXT, reason TEXT, at TEXT, PRIMARY KEY(source, title))")
    con.execute("INSERT OR REPLACE INTO catalog_failed VALUES (?,?,?,?)", (source, title, reason[:200], datetime.now().isoformat()))
    con.commit()


def cleared(con, source: str, title: str) -> None:
    con.execute("CREATE TABLE IF NOT EXISTS catalog_failed (source TEXT, title TEXT, reason TEXT, at TEXT, PRIMARY KEY(source, title))")
    con.execute("DELETE FROM catalog_failed WHERE source=? AND title=?", (source, title))
    con.commit()


def busy() -> bool:
    now = datetime.now()
    # 새벽(MCTI 시간)에도 쉬지 않는다 — 2026-09-30 사용자 결정. 파이프라인이 도는 창만 비킨다.
    if now.hour in (9, 14, 19, 23) and now.minute >= 15 or now.hour in (10, 15, 20, 0) and now.minute < 15:
        return True
    with open(LOCK, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True


def entries_for(source: str, src: str) -> tuple[dict[str, list[str]], dict[str, dict]]:
    """({제목: [분류·꼬리표]}, {제목: 위키데이터 항목}). 꼬리표 region:XX·year:YYYY 는 catalog.meta 가 읽는다."""
    if source == "namu":
        return json.loads(Path(src).read_text(encoding="utf-8")), {}
    if source in fandom.SITES:
        region = fandom.SITES[source]["region"]
        return {t: c + [f"region:{region}"] for t, c in fandom.tree(source).items()}, {}
    items: dict[str, dict] = {}
    out: dict[str, list[str]] = {}
    pref = {"JP": ("ja",), "KR": ("ko",), "TW": ("zh-tw", "zh-hant", "zh"), "HK": ("zh-hk", "zh-hant", "zh"), "CN": ("zh",)}
    for it in wikidata_memes.memes():
        langs = next((pref[c] for c in it["countries"] if c in pref), ()) + ("en", "ko", "ja", "zh")
        name = next((it["labels"][x] for x in langs if x in it["labels"]), None)
        if not name or name.startswith("Q"):
            continue
        out[name] = [f"region:{c}" for c in it["countries"]] + ([f"year:{it['year']}"] if it["year"] else [])
        items[name] = it
    return out, items


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--source", default="namu", choices=["namu", *fandom.SITES, "wikidata", "trendaword"])
    a.add_argument("--src", default="data/work/catalog/namu.json")
    a.add_argument("--limit", type=int, default=0)
    a.add_argument("--dry", action="store_true")
    a.add_argument("--retry-failed", action="store_true", help="catalog_failed 에 남은 것을 다시 돈다")
    args = a.parse_args()
    con = db.connect()
    if args.retry_failed:
        failed(con, "_", "_", "_"); cleared(con, "_", "_")          # 표가 없으면 만든다
        rows = con.execute("SELECT source, title FROM catalog_failed WHERE source=?", (args.source,)).fetchall()
        print(f"다시 돌 것 {len(rows)}", flush=True)
        entries, items = entries_for(args.source, args.src) if args.source != "trendaword" else ({}, {})
        from trend_agents.collectors import trendaword
        for source, title in rows:
            while busy():
                time.sleep(300)
            if source == "trendaword":
                p = trendaword.post(title)
                t = catalog.add_trendaword(con, p) if p else None
                t = t or (ds.find_term(con, catalog.title_to_term(p["word"]) or p["word"]) if p else None)
            else:
                t = catalog.add(con, title, entries.get(title, []), source=source) or ds.find_term(con, catalog.title_to_term(title) or title)
                if t and source == "namu":
                    catalog.prepare(con, t, title)
                elif t and source in fandom.SITES:
                    catalog.prepare_fandom(con, t, source, title)
                elif t and title in items:
                    catalog.prepare_wikidata(con, t, items[title])
            if not t:
                continue
            try:
                v, _ = research_one(con, t, lean=True)
                cleared(con, source, title)
            except Exception as e:
                v = f"error {type(e).__name__}"
                failed(con, source, title, v)
            print(f"[{datetime.now():%H:%M}] retry {source} {t.canonical} → {v}", flush=True)
        return
    if args.source == "trendaword":                 # 지난 호 전부 — 게시글마다 단어·날짜를 읽는다(3초 간격)
        from trend_agents.collectors import trendaword
        n = 0
        for url in trendaword.archive():
            if args.limit and n >= args.limit:
                break
            if con.execute("SELECT 1 FROM evidences WHERE url=? LIMIT 1", (url.split("?")[0],)).fetchone():
                continue                      # 이미 넣은 호 — 다시 받지 않는다
            while busy():
                time.sleep(300)
            p = trendaword.post(url)
            if not p:
                failed(con, "trendaword", url, "게시글에 닿지 못했거나 단어를 못 읽음")
                continue
            t = catalog.add_trendaword(con, p)
            if t:
                n += 1
                try:
                    v, _ = research_one(con, t, lean=True)
                    cleared(con, "trendaword", url)
                except Exception as e:
                    v = f"error {type(e).__name__}"
                    failed(con, "trendaword", url, v)
                print(f"[{datetime.now():%H:%M}] trendaword {n} #{p.get('issue')} {t.canonical} → {v}", flush=True)
        return
    entries, items = entries_for(args.source, args.src)
    n = linked = 0
    counts: dict[str, int] = {}
    for title, m in catalog.order(entries):
        if args.limit and n >= args.limit:
            break
        it = items.get(title)
        aliases = [v for k, v in (it or {}).get("labels", {}).items() if v != title]
        if args.dry:
            name = catalog.title_to_term(title)
            if name and not ds.find_term(con, name) and not set(m["genres"]) & catalog.SKIP_GENRES:
                n += 1
            continue
        while busy():
            time.sleep(300)
        t = catalog.add(con, title, entries[title], source=args.source, aliases=aliases)
        if not t:
            have = ds.find_term(con, title) or next((ds.find_term(con, x) for x in aliases if ds.find_term(con, x)), None)
            if have and it:                     # 이미 있는 말에 참고 문서 링크를 더한다 — 판정을 다시 받으면 실릴 수 있다(regate.py)
                linked += catalog.prepare_wikidata(con, have, it)
            continue
        n += 1
        try:
            if args.source == "namu":
                got = catalog.prepare(con, t, title)
            elif args.source in fandom.SITES:
                got = catalog.prepare_fandom(con, t, args.source, title)
            else:
                got = catalog.prepare_wikidata(con, t, it)
            v, _ = research_one(con, t, lean=True)
            # 위키데이터 항목은 외부 문서 연결이 없을 수 있다 — 닿지 못한 것이 아니다(09-30: 171건이 잘못 실패로 적혔다)
            failed(con, args.source, title, "문서에 닿지 못함") if not got and args.source != "wikidata" else cleared(con, args.source, title)
        except Exception as e:
            v = f"error {type(e).__name__}"
            failed(con, args.source, title, v)
        counts[v] = counts.get(v, 0) + 1
        print(f"[{datetime.now():%H:%M}] {args.source} {n} {t.canonical} → {v}", flush=True)
    print(("세울 것 " if args.dry else "세운 것 ") + str(n), counts, f"이미 있는 말에 링크 {linked}")

if __name__ == "__main__":
    main()
