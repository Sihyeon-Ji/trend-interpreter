"""SQLite 시절 데이터(data/trend.db)를 PostgreSQL 로 옮긴다. 이미 있는 행은 건너뛴다(새 파일의 값으로 바꾸지 않는다).

사용: uv run scripts/migrate_sqlite_to_postgres.py [--sqlite data/trend.db] [--database-url postgresql://...] [--fresh] [--skip-user-data]
표 목록과 컬럼은 현재 DDL 기준이다. SQLite 쪽에만 있는 컬럼은 버리고, PostgreSQL 쪽에만 있는 컬럼은 NULL 로 둔다.
단 terms.diffusion 은 용어 JSON 에서 채운다(마이그레이션 002 의 보정은 행이 들어오기 전, 처음 연결할 때 돈다).
기본키가 없는 표(pipeline_runs, research_log, interpretations, video_snapshots)는 대상이 비어 있을 때만 복사한다.
최신 파일로 다시 옮길 때는 빈 DB 에 --fresh 로 옮긴다. 이미 있는 행이 옛 값 그대로 남으면 뜻 version·검수 결정이 섞인다.
Cloud SQL 로 보낼 사본은 --skip-user-data 로 해석 캐시·미해결 질문·계정별 설정을 뺀다.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.config import DATA_DIR, DATABASE_URL  # noqa: E402
from trend_agents.storage import db, dictionary_store, store  # noqa: E402  (DDL 등록)

SKIP = {"term_aliases", "schema_migrations"}  # 이관 뒤 다시 만들거나 이 DB 가 관리하는 표
USER_DATA = {"explain_cache", "lookups", "reader_prefs"}  # --skip-user-data 로 빼는 표
RENAMED = {"reader_prefs": {"user": "reader"}}
# PostgreSQL 기본키 색인에 들어가지 않는 행. 파이프라인도 저장하지 않는다(store.upsert_news)
WHERE = {"news": f"length(CAST(link AS BLOB)) <= {store.NEWS_LINK_MAX}"}
BATCH = 1000


def migrate(sqlite_path: Path, dst: db.Connection, *, fresh: bool = False, skip_user_data: bool = False) -> None:
    if fresh and dst.execute("SELECT 1 FROM terms LIMIT 1").fetchone():
        raise SystemExit("대상 DB 의 terms 가 비어 있지 않습니다. --fresh 는 빈 DB 에만 옮깁니다 "
                         "(이미 있는 행은 새 파일의 값으로 바뀌지 않습니다).")
    src = sqlite3.connect(str(sqlite_path))
    have = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name, table in db.TABLES.items():
        if name in SKIP:
            continue
        if name not in have:
            print(f"{name:20} SQLite 에 없음")
            continue
        renamed = RENAMED.get(name, {})
        src_cols = [r[1] for r in src.execute(f"PRAGMA table_info({name})")]
        pairs = [(c, renamed.get(c, c)) for c in src_cols if renamed.get(c, c) in table.columns]
        total = src.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        if skip_user_data and name in USER_DATA:
            print(f"{name:20} 건너뜀 (--skip-user-data)  원본 {total}건")
            continue
        if not table.primary_key and dst.execute(f"SELECT 1 FROM {name} LIMIT 1").fetchone():
            print(f"{name:20} 건너뜀 (기본키 없음, 대상에 이미 행이 있음)  원본 {total}건")
            continue
        insert = (f"INSERT INTO {name} ({', '.join(d for _, d in pairs)}) VALUES ({','.join('?' * len(pairs))})"
                  " ON CONFLICT DO NOTHING")
        where = WHERE.get(name)
        left_out = src.execute(f"SELECT COUNT(*) FROM {name} WHERE NOT ({where})").fetchone()[0] if where else 0
        cur = src.execute(f"SELECT {', '.join(s for s, _ in pairs)} FROM {name}" + (f" WHERE {where}" if where else ""))
        copied = 0
        while rows := cur.fetchmany(BATCH):
            before = dst.raw.cursor()
            before.executemany(db.translate(insert, True), [tuple(db._param(v) for v in row) for row in rows])
            copied += before.rowcount if before.rowcount >= 0 else 0
            dst.commit()
        print(f"{name:20} {copied}/{total} 복사" + (f" (기본키 색인에 들어가지 않는 {left_out}건 제외)" if left_out else ""))
    filled = dst.execute("UPDATE terms SET diffusion = json::jsonb ->> 'diffusion' "
                         "WHERE diffusion IS NULL AND json::jsonb ->> 'diffusion' IS NOT NULL").rowcount
    dst.commit()
    print(f"{'terms.diffusion':20} {filled}건 채움")
    print(f"{'term_aliases':20} {dictionary_store.rebuild_aliases(dst)}건 다시 만듦")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sqlite", default=str(DATA_DIR / "trend.db"))
    ap.add_argument("--database-url", default=DATABASE_URL)
    ap.add_argument("--fresh", action="store_true", help="대상 terms 가 비어 있을 때만 옮긴다(최신 파일로 다시 옮길 때)")
    ap.add_argument("--skip-user-data", action="store_true", help="explain_cache·lookups·reader_prefs 를 옮기지 않는다(Cloud SQL 로 보낼 사본)")
    a = ap.parse_args()
    path = Path(a.sqlite)
    if not path.exists():
        raise SystemExit(f"SQLite 파일이 없습니다: {path}")
    print(f"{path} → {db.redacted(a.database_url)}")
    dst = db.connect(url=a.database_url)
    try:
        migrate(path, dst, fresh=a.fresh, skip_user_data=a.skip_user_data)
    finally:
        dst.close()


if __name__ == "__main__":
    main()
