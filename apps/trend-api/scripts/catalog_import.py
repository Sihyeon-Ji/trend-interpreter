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


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--src", default="data/work/catalog/namu.json")
    a.add_argument("--limit", type=int, default=0)
    a.add_argument("--dry", action="store_true")
    args = a.parse_args()
    entries = json.loads(Path(args.src).read_text(encoding="utf-8"))
    con = db.connect()
    done = n = 0
    counts: dict[str, int] = {}
    for title, m in catalog.order(entries):
        if args.limit and n >= args.limit:
            break
        if args.dry:
            name = catalog.title_to_term(title)
            if name and not ds.find_term(con, name) and not set(m["genres"]) & catalog.SKIP_GENRES:
                n += 1
            continue
        while busy():
            time.sleep(300)
        t = catalog.add(con, title, entries[title])
        if not t:
            continue
        n += 1
        try:
            catalog.prepare(con, t, title)
            v, _ = research_one(con, t, lean=True)
        except Exception as e:
            v = f"error {type(e).__name__}"
        counts[v] = counts.get(v, 0) + 1
        done += 1
        print(f"[{datetime.now():%H:%M}] {n} {t.canonical} → {v}", flush=True)
    print(("세울 것 " if args.dry else "세운 것 ") + str(n), counts)


if __name__ == "__main__":
    main()
