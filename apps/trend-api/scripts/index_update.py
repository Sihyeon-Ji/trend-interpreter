"""문서 색인을 한 바퀴 갱신한다(하루 두 번 cron). 처음에는 여러 번 돌려 채운다.
  uv run scripts/index_update.py                      # 나무위키 1,200·그 밖 3,000, 최대 100분
  uv run scripts/index_update.py --namu 20 --other 20 # 시험
  uv run scripts/index_update.py --stats
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.pipeline import doc_index  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--namu", type=int, default=1200)
    a.add_argument("--other", type=int, default=3000)
    a.add_argument("--minutes", type=float, default=100)
    a.add_argument("--stats", action="store_true")
    args = a.parse_args()
    idx = doc_index.connect()
    if not args.stats:
        log = lambda m: print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)  # noqa: E731
        st = doc_index.update(idx, db.connect(), args.namu, args.other, time.time() + args.minutes * 60, log)
        log(f"끝 {st}")
    print(doc_index.stats(idx))


if __name__ == "__main__":
    main()
