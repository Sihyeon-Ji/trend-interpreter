"""근거 문장 분류(리스크 단계의 분류)를 밀린 만큼 몰아서 한다(2026-10-06). 파이프라인은 실행마다 30개만 보는데, track 이 끊겨
리스크 단계가 09-30 이후 돌지 못해 대시보드 '지금 쓰이는 밈' 대부분이 '아직 판단 전' 이었다(팀 변경 공유 10-05).
로컬 Gemma 라 비용이 없다. 파이프라인과 겹치지 않게 같은 잠금(/tmp/trend-pipeline.lock)을 묶음마다 잡고, 잡혀 있으면 쉰다.
지금 쓰이는(생애주기가 살아 있는) 말부터.
  uv run scripts/risk_backfill.py            # 다 끝날 때까지
  uv run scripts/risk_backfill.py --max 60   # 시험
"""
from __future__ import annotations

import argparse
import fcntl
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.pipeline import risk  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

ACTIVE = {"emerging": 0, "rising": 0, "peak": 0, "steady": 1, "declining": 2}


def pending(con) -> list:
    out = []
    for t in ds.list_terms(con, ("verified",)):
        done = ds.evidence_labels(con, t.term_id)
        left = sum(1 for e in risk._usage(con, t) if e.evidence_id not in done)
        if left:
            out.append((ACTIVE.get(t.lifecycle, 3), -left, t))
    return [t for *_, t in sorted(out, key=lambda x: (x[0], x[1]))]


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--max", type=int, default=100000)
    a.add_argument("--batch", type=int, default=20)
    args = a.parse_args()
    con = db.connect()
    log = lambda m: print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)  # noqa: E731
    todo = pending(con)
    log(f"분류할 문장이 남은 표제어 {len(todo)}개")
    done = labeled = 0
    lock = open("/tmp/trend-pipeline.lock", "w")
    while todo and done < args.max:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("파이프라인이 도는 중 — 5분 쉼")
            time.sleep(300)
            continue
        try:
            batch, todo = todo[:args.batch], todo[args.batch:]
            for t in batch:
                try:
                    labeled += risk.classify(con, t)
                except Exception as e:
                    log(f"  {t.canonical}: {type(e).__name__}")
                fresh = ds.get_term(con, t.term_id)          # 검수자가 그사이 바꾼 것을 덮지 않게 다시 읽어 판정
                if fresh and fresh.status == "verified":
                    risk.apply(con, fresh)
                done += 1
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
        log(f"  {done}개 · 분류한 문장 {labeled}")
    log(f"끝 — 표제어 {done}개, 문장 {labeled}개")


if __name__ == "__main__":
    main()
