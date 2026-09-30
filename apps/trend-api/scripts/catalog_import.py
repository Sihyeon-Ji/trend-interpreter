"""위키 밈 분류 일괄 넣기 (Plan 16). data/work/catalog/namu.json({문서: [분류]})을 읽어 표제어를 세우고 가벼운 조사를 돌린다.
파이프라인과 겹치지 않게 cron 창(9·14·19·23시 15분부터 한 시간)·잠금 중·새벽 2~8시(MCTI)는 쉰다. 멈췄다 다시 돌려도 이어서 한다.
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


def busy() -> bool:
    now = datetime.now()
    if 2 <= now.hour < 8:
        return True
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
    args = a.parse_args()
    con = db.connect()
    if args.source == "trendaword":                 # 지난 호 전부 — 게시글마다 단어·날짜를 읽는다(3초 간격)
        from trend_agents.collectors import trendaword
        n = 0
        for url in trendaword.archive():
            if args.limit and n >= args.limit:
                break
            while busy():
                time.sleep(300)
            p = trendaword.post(url)
            t = catalog.add_trendaword(con, p) if p else None
            if t:
                n += 1
                try:
                    v, _ = research_one(con, t, lean=True)
                except Exception as e:
                    v = f"error {type(e).__name__}"
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
                catalog.prepare(con, t, title)
            elif args.source in fandom.SITES:
                catalog.prepare_fandom(con, t, args.source, title)
            else:
                catalog.prepare_wikidata(con, t, it)
            v, _ = research_one(con, t, lean=True)
        except Exception as e:
            v = f"error {type(e).__name__}"
        counts[v] = counts.get(v, 0) + 1
        print(f"[{datetime.now():%H:%M}] {args.source} {n} {t.canonical} → {v}", flush=True)
    print(("세울 것 " if args.dry else "세운 것 ") + str(n), counts, f"이미 있는 말에 링크 {linked}")

if __name__ == "__main__":
    main()
