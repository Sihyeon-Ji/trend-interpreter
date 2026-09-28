"""사전에 오른 표제어에 대표 그림·영상 주소를 붙인다.

파일은 받지 않는다 — 위키미디어 공용의 자유 라이선스 그림과 유튜브 주소만 두고 출처·라이선스를 함께 적는다.
영어판에 직접 올라온 공정이용 그림은 collectors/wikipedia_search.free_image 가 거른다.
위키백과가 429 를 내므로 표제어 사이를 쉬어 간다.

  uv run scripts/attach_media.py --limit 60 --pause 3
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.pipeline.research import attach_media  # noqa: E402
from trend_agents.schemas import Evidence  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--pause", type=float, default=3.0)
    ap.add_argument("--status", default="verified,needs_review")
    ap.add_argument("--youtube", action="store_true",
                    help="유튜브 검색으로 대표 영상까지 찾는다 (검색 1회 100 unit, 하루 10,000 unit)")
    a = ap.parse_args()

    con = db.connect()
    todo = [t for t in ds.list_terms(con, tuple(a.status.split(","))) if not ds.has_media(con, t.term_id)][: a.limit]
    print(f"매체 없는 표제어 {len(todo)}개", flush=True)
    got = 0
    for i, t in enumerate(todo, 1):
        evs = [Evidence.model_validate_json(j) for (j,) in
               con.execute("SELECT json FROM evidences WHERE term_id=?", (t.term_id,)).fetchall()]
        try:
            n = attach_media(con, t, evs, youtube=a.youtube)
        except Exception as e:
            n = 0
            print(f"  [{i}] {t.canonical}: {type(e).__name__}", flush=True)
        if n:
            got += 1
            print(f"  [{i}/{len(todo)}] {t.canonical}: {n}건 {[m['kind'] for m in ds.get_media(con, t.term_id)]}", flush=True)
        time.sleep(a.pause)
    print(f"끝. {got}개 표제어에 매체를 붙였다.", flush=True)


if __name__ == "__main__":
    main()
