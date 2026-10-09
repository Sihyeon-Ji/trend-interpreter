"""쓰임 낱말(fit 단계)을 밀린 만큼 몰아서 붙인다(2026-10-09). audience 칸이 생겨 이미 붙인 4,500여 개를 다시 붙여야 하는데,
파이프라인은 실행마다 40개만 본다. 로컬 Gemma 라 비용이 없다. 파이프라인과 겹치지 않게 같은 잠금(/tmp/trend-pipeline.lock)을
묶음마다 잡고, 잡혀 있으면 쉰다. 추천 후보(대시보드 카드)부터 붙인다 — 추천이 바로 새 칸을 쓰게.
  USE_LOCAL_GEMMA=1 uv run scripts/fit_backfill.py            # 다 끝날 때까지
  USE_LOCAL_GEMMA=1 uv run scripts/fit_backfill.py --max 80   # 시험
"""
from __future__ import annotations

import argparse
import fcntl
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.pipeline import dashboard, fit  # noqa: E402
from trend_agents.pipeline.gemini import local_ok  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--max", type=int, default=100000)
    args = a.parse_args()
    if not local_ok():
        sys.exit("로컬 Gemma 가 없다 — USE_LOCAL_GEMMA=1 과 Ollama 모델을 확인하라")
    con = db.connect()
    log = lambda m: print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)  # noqa: E731
    cards = {c.term_id for c in dashboard.cards(con, ["KR", "JP", "GLOBAL"])}   # 만들기 화면의 시장
    todo = sorted(fit.todo(con), key=lambda x: x[0].term_id not in cards)[:args.max]
    log(f"붙일 표제어 {len(todo)}개 (추천 후보 {sum(1 for t, _ in todo if t.term_id in cards)}개 먼저)")
    done = 0
    lock = open("/tmp/trend-pipeline.lock", "w")
    while todo:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("파이프라인이 도는 중 — 5분 쉼")
            time.sleep(300)
            continue
        try:
            batch, todo = todo[:fit.BATCH], todo[fit.BATCH:]
            try:
                done += fit.label(con, batch)
            except Exception as e:                  # 한 묶음의 형식 실패가 나머지를 막지 않는다
                log(f"  묶음 실패: {type(e).__name__}")
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
        log(f"  {done}개 붙임 · 남은 {len(todo)}")
    log(f"끝 — {done}개")


if __name__ == "__main__":
    main()
