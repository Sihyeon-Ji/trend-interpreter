"""로컬 개발용 SQLite. 배포 시 Firestore(문서) + BigQuery(시계열) 로 교체 예정.

Pydantic 모델을 JSON 으로 통째로 저장하고, 조회·조인에 필요한 컬럼만 따로 뽑아둔다.
video_snapshots 가 조회수 시계열 = 트렌드 곡선의 원천.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..config import DATA_DIR, DB_PATH
from ..schemas import NewsItem, ShortsInterpretation, ShortsVideo

DDL = """
CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY, region TEXT, source TEXT, published_at TEXT,
  duration_sec INT, view_count INT, first_seen TEXT, last_seen TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS video_snapshots (
  video_id TEXT, seen_at TEXT, view_count INT, like_count INT, comment_count INT);
CREATE TABLE IF NOT EXISTS interpretations (
  video_id TEXT, model TEXT, created_at TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS news (
  link TEXT PRIMARY KEY, region TEXT, query TEXT, published_at TEXT, first_seen TEXT, json TEXT);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path=None) -> sqlite3.Connection:
    from . import dictionary_store

    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(str(path or DB_PATH), check_same_thread=False)
    con.executescript(DDL)
    dictionary_store.ensure(con)
    return con


def upsert_videos(con: sqlite3.Connection, videos: list[ShortsVideo]) -> int:
    now = _now()
    for v in videos:
        con.execute(
            """INSERT INTO videos VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(video_id) DO UPDATE SET
                 view_count=excluded.view_count, last_seen=excluded.last_seen, json=excluded.json""",
            (v.video_id, v.region, v.source, v.published_at.isoformat(), v.duration_sec,
             v.view_count, now, now, v.model_dump_json()),
        )
        con.execute(
            "INSERT INTO video_snapshots VALUES (?,?,?,?,?)",
            (v.video_id, now, v.view_count, v.like_count, v.comment_count),
        )
    con.commit()
    return len(videos)


def save_interpretations(con: sqlite3.Connection, items: list[ShortsInterpretation], model: str) -> int:
    now = _now()
    for it in items:
        vid = it.url.split("v=")[-1].split("&")[0].split("/")[-1]
        con.execute("INSERT INTO interpretations VALUES (?,?,?,?)", (vid, model, now, it.model_dump_json()))
    con.commit()
    return len(items)


def upsert_news(con: sqlite3.Connection, items: list[NewsItem]) -> int:
    now = _now()
    for it in items:
        con.execute(
            "INSERT OR IGNORE INTO news VALUES (?,?,?,?,?,?)",
            (it.link, it.region, it.query, it.published_at.isoformat() if it.published_at else None,
             now, it.model_dump_json()),
        )
    con.commit()
    return len(items)


def top_videos(con: sqlite3.Connection, n: int = 3, region: str | None = None) -> list[str]:
    q = "SELECT json FROM videos" + (" WHERE region=?" if region else "") + " ORDER BY view_count DESC LIMIT ?"
    rows = con.execute(q, ((region, n) if region else (n,))).fetchall()
    return [ShortsVideo.model_validate_json(r[0]).url for r in rows]
