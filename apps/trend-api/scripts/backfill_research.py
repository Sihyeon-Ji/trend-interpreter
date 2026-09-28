"""후보 대기열을 조사·검증으로 밀어 넣는다. 위키에서 받은 이름 수백 건을 한 번에 소화시키려고 만든 일회성 도구.

평소 파이프라인은 한 번에 4건만 조사한다(상시 운영 기준). 백필은 그것과 별개로 크게 돌린다.
Gemini 하루 예산이 떨어지면 자동으로 오프라인(로컬 Gemma) 조사로 내려가고, 게이트가 통과 여부를 정한다.

  uv run scripts/backfill_research.py --batches 10 --size 20
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.pipeline import research  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=10)
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--pause", type=float, default=5.0, help="배치 사이 쉬는 시간(초). 외부 API 예의")
    ap.add_argument("--recheck", type=int, default=0, help="배치마다 다시 볼 기존 표제어 수 "
                                                          "(뜻이 '근거 부족' 으로 남은 것을 다시 쓰게 한다)")
    a = ap.parse_args()

    con = db.connect()
    total_ok = 0
    for i in range(1, a.batches + 1):
        left = con.execute("SELECT COUNT(*) FROM candidates WHERE status='new'").fetchone()[0]
        if not left and not a.recheck:
            print("남은 후보 없음")
            break
        t0 = time.time()
        res = research.run(con, max_new=a.size, max_recheck=a.recheck)["research"]
        ok = (res.detail or {}).get("verified_auto", 0)
        total_ok += ok
        counts = {s: len(ds.list_terms(con, (s,))) for s in ("verified", "needs_review")}
        print(f"[{i}/{a.batches}] {res.count}건 {time.time() - t0:.0f}초 · 통과 {ok} · "
              f"검증됨 {counts['verified']} · 검수대기 {counts['needs_review']} · 후보 {left}건 남음", flush=True)
        time.sleep(a.pause)
    print(f"끝. 이번 백필로 자동 검증 통과 {total_ok}건")


if __name__ == "__main__":
    main()
