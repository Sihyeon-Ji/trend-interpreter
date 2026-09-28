"""SQLite 시절 데이터(data/trend.db)를 PostgreSQL 로 옮긴다. 이미 있는 행은 건너뛴다.

사용: uv run scripts/migrate_sqlite_to_postgres.py [--sqlite data/trend.db] [--database-url postgresql://...]
표 목록과 컬럼은 현재 DDL 기준이다. SQLite 쪽에만 있는 컬럼은 버리고, PostgreSQL 쪽에만 있는 컬럼은 NULL 로 둔다.
기본키가 없는 표(pipeline_runs, research_log, interpretations, video_snapshots)는 대상이 비어 있을 때만 복사한다.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.config import DATA_DIR, DATABASE_URL  # noqa: E402
from trend_agents.storage import db, dictionary_store, store  # noqa: E402,F401  (DDL 등록)

RENAMED = {"reader_prefs": {"user": "reader"}}
BATCH = 1000


def migrate(sqlite_path: Path, url: str) -> None:
    src = sqlite3.connect(str(sqlite_path))
    dst = db.connect(url=url)
    have = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name, table in db.TABLES.items():
        if name not in have:
            print(f"{name:20} SQLite 에 없음")
            continue
        renamed = RENAMED.get(name, {})
        src_cols = [r[1] for r in src.execute(f"PRAGMA table_info({name})")]
        pairs = [(c, renamed.get(c, c)) for c in src_cols if renamed.get(c, c) in table.columns]
        total = src.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        if not table.primary_key and dst.execute(f"SELECT 1 FROM {name} LIMIT 1").fetchone():
            print(f"{name:20} 건너뜀 (기본키 없음, 대상에 이미 행이 있음)  원본 {total}건")
            continue
        insert = (f"INSERT INTO {name} ({', '.join(d for _, d in pairs)}) VALUES ({','.join('?' * len(pairs))})"
                  " ON CONFLICT DO NOTHING")
        cur = src.execute(f"SELECT {', '.join(s for s, _ in pairs)} FROM {name}")
        copied = 0
        while rows := cur.fetchmany(BATCH):
            before = dst.raw.cursor()
            before.executemany(db.translate(insert, True), [tuple(db._param(v) for v in row) for row in rows])
            copied += before.rowcount if before.rowcount >= 0 else 0
            dst.commit()
        print(f"{name:20} {copied}/{total} 복사")
    dst.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sqlite", default=str(DATA_DIR / "trend.db"))
    ap.add_argument("--database-url", default=DATABASE_URL)
    a = ap.parse_args()
    path = Path(a.sqlite)
    if not path.exists():
        raise SystemExit(f"SQLite 파일이 없습니다: {path}")
    print(f"{path} → {db.redacted(a.database_url)}")
    migrate(path, a.database_url)


if __name__ == "__main__":
    main()
