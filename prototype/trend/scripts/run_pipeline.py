"""파이프라인 실행. 단계별 독립, 실패해도 다음 단계로 간다. 기본은 전체를 한 번.

사용:
  uv run scripts/run_pipeline.py                      # 전체 1회
  uv run scripts/run_pipeline.py --stages collect,board
  uv run scripts/run_pipeline.py --loop               # PIPELINE_INTERVAL_HOURS 마다 반복 (Ctrl-C 로 종료)
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime

from trend_agents.config import GEMINI_DAILY_BUDGET, PIPELINE_INTERVAL_HOURS
from trend_agents.pipeline import (board, candidates, classify, collect, hunt, interpret, naver, research, spikes, spot,
                                   topics, track, translate)
from trend_agents.pipeline.gemini import budget_left
from trend_agents.storage import sqlite_store as db

STAGES = {  # 실행 순서: 해석(쇼츠→밈 이름)이 후보 추출보다 앞
    "collect": collect.run, "classify": classify.run, "spikes": spikes.run, "interpret": interpret.run, "candidates": candidates.run,
    "spot": spot.run, "hunt": hunt.run, "research": research.run, "track": track.run, "naver": naver.run, "translate": translate.run, "topics": topics.run, "board": board.run,
}


def once(names: list[str]) -> None:
    con = db.connect()
    print(f"[{datetime.now():%m-%d %H:%M}] 시작 · Gemini 예산 남음 {budget_left(con)}/{GEMINI_DAILY_BUDGET}")
    for name in names:
        t0 = time.time()
        results = STAGES[name](con) or {}
        for key, r in results.items():
            mark = {"ok": "✓", "zero": "○", "error": "✗", "skipped": "–"}.get(r.status, "?")
            extra = " ".join(f"{k}={v}" for k, v in r.detail.items() if k not in ("trace",) and not isinstance(v, str) or k in ("pending", "topics", "regions", "verified_auto", "new_candidates"))
            print(f"  {mark} {key:<22} {r.count:>5}  {time.time() - t0:5.1f}s  {r.note[:90]} {extra}")
            if r.status == "error" and "trace" in r.detail:
                print("     " + r.detail["trace"].strip().splitlines()[-1][:160])
    print(f"[{datetime.now():%m-%d %H:%M}] 끝 · 예산 남음 {budget_left(con)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default=",".join(STAGES), help="쉼표로 구분")
    ap.add_argument("--loop", action="store_true")
    a = ap.parse_args()
    names = [s.strip() for s in a.stages.split(",") if s.strip() in STAGES]
    while True:
        once(names)
        if not a.loop:
            break
        print(f"다음 실행까지 {PIPELINE_INTERVAL_HOURS}시간 대기")
        time.sleep(PIPELINE_INTERVAL_HOURS * 3600)
