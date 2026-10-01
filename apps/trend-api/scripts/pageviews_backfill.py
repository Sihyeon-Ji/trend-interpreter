"""확인된 표제어의 위키백과 월별 조회수(과거 관심 추이)를 받아 term_pageviews 에 쌓는다.
제목이 표제어인 위키백과 참고 문서가 있는 표제어만. 이미 받은 것은 건너뛰고(30일마다 새로), 파이프라인 창에는 쉰다.
  uv run scripts/pageviews_backfill.py --limit 30
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalog_import import busy  # noqa: E402
from trend_agents import verification  # noqa: E402
from trend_agents.collectors import wikipedia_search  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

REFRESH = timedelta(days=30)


def wiki_doc(con, term) -> tuple[str, str] | None:
    """(lang, 문서 제목). 제목이 표제어인 *.wikipedia.org/wiki/ 참고 문서가 없으면 None."""
    for e in ds.list_evidences(con, term.term_id):
        host = (urlsplit(e.url or "").hostname or "").lower()
        if not host.endswith(".wikipedia.org") or "/wiki/" not in e.url:
            continue
        if verification.reference_doc(e) and verification.doc_titled(term.canonical, e, term.aliases):
            return host.split(".")[0], unquote(urlsplit(e.url).path.split("/wiki/", 1)[1]).replace("_", " ")
    return None


def targets(con) -> list[tuple]:
    out = []
    for t in ds.list_terms(con, ("verified",)):
        d = wiki_doc(con, t)
        if d:
            out.append((t, *d))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="이번에 새로 받을 최대 개수(0 이면 전부)")
    ap.add_argument("--dry", action="store_true", help="대상 수만 센다")
    a = ap.parse_args()
    con = db.connect()
    tg = targets(con)
    print(f"대상 {len(tg)}개", flush=True)
    if a.dry:
        return
    con.execute("CREATE TABLE IF NOT EXISTS pageviews_done (term_id TEXT PRIMARY KEY, at TEXT)")
    con.commit()
    fresh = {r[0] for r in con.execute("SELECT term_id FROM pageviews_done WHERE at > ?", ((datetime.now() - REFRESH).isoformat(),))}
    done = got = 0
    for t, lang, title in tg:
        if t.term_id in fresh:
            continue
        while busy():
            time.sleep(60)
        try:
            rows = wikipedia_search.monthly_views(lang, title)
        except wikipedia_search.Unreachable:
            print(f"닿지 못함: {title}", flush=True)
            continue
        if rows:
            ds.set_pageviews(con, t.term_id, lang, title, rows)
            got += 1
        con.execute("INSERT OR REPLACE INTO pageviews_done VALUES (?,?)", (t.term_id, datetime.now().isoformat()))
        con.commit()
        done += 1
        if done % 50 == 0:
            print(f"{done}개 조회, 조회수 붙음 {got}", flush=True)
        if a.limit and done >= a.limit:
            break
    print(f"끝: {done}개 조회, 조회수 붙음 {got}", flush=True)


if __name__ == "__main__":
    main()
