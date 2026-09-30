"""일괄 등재로 실린 말을 고친 방식(붙인 문서만 보기·밈 쓰임 문장·밈으로서의 뜻)으로 다시 쓴다 (Plan 16, 2026-09-30 표본 검토 뒤).
사람이 확인한 뜻은 건드리지 않는다(research_one 이 지킨다). 이전 판은 valid_to 로 닫힌다.
  uv run scripts/catalog_redo.py --names "ライラック|Big Iron"      # 몇 개만
  uv run scripts/catalog_redo.py --all                               # 일괄 등재로 실린 것 전부
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.pipeline import catalog  # noqa: E402
from trend_agents.pipeline.research import research_one  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_import import busy  # noqa: E402


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--names", default="")
    a.add_argument("--all", action="store_true")
    args = a.parse_args()
    con = db.connect()
    rows = con.execute("SELECT term_id, source, title FROM wiki_catalog").fetchall()
    want = {x for x in args.names.split("|") if x}
    for tid, source, title in rows:
        t = ds.get_term(con, tid)
        if not t or (want and t.canonical not in want and title not in want) or (not want and not (args.all and t.status == "verified")):
            continue
        while busy() and not want:
            time.sleep(300)
        if source == "namu":
            catalog.prepare(con, t, title)
        elif source in ("pttpedia", "evchk"):
            catalog.prepare_fandom(con, t, source, title)
        v, _ = research_one(con, t, lean=True)
        m = ds.current_meaning(con, tid)
        print(f"{t.canonical} → {v} v{m.version if m else '-'} | {(m.definition if m else '')[:110]}", flush=True)


if __name__ == "__main__":
    main()
