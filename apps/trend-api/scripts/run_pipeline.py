"""파이프라인 실행. 단계별 독립, 실패해도 다음 단계로 간다. 기본은 전체를 한 번.

사용:
  uv run scripts/run_pipeline.py                      # 전체 1회
  uv run scripts/run_pipeline.py --stages collect,board
  uv run scripts/run_pipeline.py --loop               # PIPELINE_INTERVAL_HOURS 마다 반복 (Ctrl-C 로 종료)
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime

from trend_agents.config import GEMINI_DAILY_BUDGET, PIPELINE_INTERVAL_HOURS
from trend_agents.logging_setup import configure as configure_logging
from trend_agents.pipeline import (board, candidates, classify, collect, crosscheck, dashboard, fit, hunt, interpret, namu, naver, research, risk,
                                   spikes, spot, topics, track, translate)
from trend_agents.pipeline.gemini import budget_left
from trend_agents.storage import store as db

log = logging.getLogger("trend.pipeline")

STAGES = {  # 실행 순서: 해석(쇼츠→밈 이름)이 후보 추출보다 앞
    "collect": collect.run, "classify": classify.run, "spikes": spikes.run, "interpret": interpret.run, "candidates": candidates.run,
    "spot": spot.run, "namu": namu.run, "hunt": hunt.run, "research": research.run,
    "crosscheck": crosscheck.run,  # 문서 대조 (Plan 12) — 실린 뜻을 참고 위키와 맞춰 보고 어긋나면 검수 큐로. 상태·뜻은 바꾸지 않는다
    "track": track.run, "risk": risk.run, "naver": naver.run, "translate": translate.run, "fit": fit.run, "topics": topics.run, "board": board.run,
    "dashboard": dashboard.run,  # 키워드 대시보드 카드 (Plan 04) — 위 단계들이 채운 값을 모으기만 한다
}


def once(names: list[str]) -> None:
    con = db.connect()
    log.info(f"[{datetime.now():%m-%d %H:%M}] 시작 · Gemini 예산 남음 {budget_left(con)}/{GEMINI_DAILY_BUDGET}")
    for name in names:
        t0 = time.time()
        results = STAGES[name](con) or {}
        for key, r in results.items():
            mark = {"ok": "✓", "zero": "○", "error": "✗", "skipped": "–"}.get(r.status, "?")
            extra = " ".join(f"{k}={v}" for k, v in r.detail.items() if k not in ("trace",) and not isinstance(v, str) or k in ("pending", "topics", "regions", "verified_auto", "new_candidates"))
            log.info(f"  {mark} {key:<22} {r.count:>5}  {time.time() - t0:5.1f}s  {r.note[:90]} {extra}")
            if r.status == "error" and "trace" in r.detail:
                log.info("     " + r.detail["trace"].strip().splitlines()[-1][:160])
    log.info(f"[{datetime.now():%m-%d %H:%M}] 끝 · 예산 남음 {budget_left(con)}")


if __name__ == "__main__":
    configure_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default=",".join(STAGES), help="쉼표로 구분")
    ap.add_argument("--loop", action="store_true")
    a = ap.parse_args()
    names = [s.strip() for s in a.stages.split(",") if s.strip() in STAGES]
    while True:
        once(names)
        if not a.loop:
            break
        log.info(f"다음 실행까지 {PIPELINE_INTERVAL_HOURS}시간 대기")
        time.sleep(PIPELINE_INTERVAL_HOURS * 3600)
