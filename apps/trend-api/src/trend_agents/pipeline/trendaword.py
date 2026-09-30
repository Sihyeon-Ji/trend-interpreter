"""파이프라인 'Trend A Word' 단계 — 새 호(RSS)의 단어를 사전 후보로 세우고 가벼운 조사를 돌린다(2026-09-30, Plan 16).
실행마다 새 호만 본다(보통 하루 한 편). 지난 호는 scripts/catalog_import.py --source trendaword 로 한 번 넣는다."""
from __future__ import annotations

import sqlite3

from ..collectors import trendaword
from . import catalog
from .runs import stage

MAX_PER_RUN = 3


def run(con: Connection) -> dict:
    from .research import research_one

    with stage(con, "trendaword") as r:
        done = {u for (u,) in con.execute("SELECT title FROM wiki_catalog WHERE source='trendaword'").fetchall()}
        for item in trendaword.feed():
            if r.count >= MAX_PER_RUN:
                break
            if item["word"] in done:
                continue
            p = trendaword.post(item["url"])
            if not p:
                continue
            t = catalog.add_trendaword(con, p)
            if t:
                try:
                    v, _ = research_one(con, t, lean=True)
                except Exception as e:              # 한 말의 실패가 단계를 막지 않는다
                    v = f"error {type(e).__name__}"
                r.detail[t.canonical] = v
                r.count += 1
    return {"trendaword": r}
