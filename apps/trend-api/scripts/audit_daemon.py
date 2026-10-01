"""사전 감사를 계속 돈다(2026-10-01 사용자 요청: 파이프라인의 실행마다 20개로는 4,000개를 보는 데 몇 주가 걸린다).
감사관은 AUDIT_MODEL/AUDIT_OLLAMA_HOST(학습 서버 GPU), 다시 쓰기는 이 서버의 로컬 모델. 파이프라인이 도는 창에는 쉰다.
여러 개를 띄울 때는 --worker i --workers n 으로 표제어를 나눈다.
  uv run scripts/audit_daemon.py --worker 0 --workers 2
"""
from __future__ import annotations

import argparse
import sys
import time
import zlib
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalog_import import busy  # noqa: E402
from trend_agents.pipeline import audit  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--worker", type=int, default=0)
    a.add_argument("--workers", type=int, default=1)
    args = a.parse_args()
    con = db.connect()
    counts: Counter = Counter()
    while True:
        while busy():
            time.sleep(300)
        todo = [t for t in audit.targets(con, limit=10_000) if zlib.crc32(t.term_id.encode()) % args.workers == args.worker][:20]
        if not todo:
            print(f"[{datetime.now():%H:%M}] 감사할 것 없음 — 1시간 뒤 다시", counts, flush=True)
            time.sleep(3600)
            continue
        for t in todo:
            try:
                v = audit.audit_one(con, t)
            except Exception as e:
                v = f"error {type(e).__name__}"
                audit._log(con, t.term_id, (audit.ds_current(con, t) or ""), "error", [str(e)[:120]], "", "error")
            counts[v] += 1
            print(f"[{datetime.now():%H:%M}] w{args.worker} {t.canonical} → {v}", flush=True)


if __name__ == "__main__":
    main()
