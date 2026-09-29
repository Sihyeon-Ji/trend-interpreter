"""수집 원본 저장(PostgreSQL). 사전·파이프라인 상태는 dictionary_store, 연결은 db 모듈이 맡는다.

Pydantic 모델을 JSON 으로 통째로 저장하고, 조회·조인에 필요한 컬럼만 따로 뽑아둔다.
video_snapshots 가 조회수 시계열 = 트렌드 곡선의 원천.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from ..config import DATA_DIR
from ..schemas import NewsItem, ShortsInterpretation, ShortsVideo
from . import db
from .db import Connection

DDL = """
CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY, region TEXT, source TEXT, published_at TEXT,
  duration_sec BIGINT, view_count BIGINT, first_seen TEXT, last_seen TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS video_snapshots (
  video_id TEXT, seen_at TEXT, view_count BIGINT, like_count BIGINT, comment_count BIGINT);
CREATE TABLE IF NOT EXISTS interpretations (
  video_id TEXT, model TEXT, created_at TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS news (
  link TEXT PRIMARY KEY, region TEXT, query TEXT, published_at TEXT, first_seen TEXT, json TEXT);
"""
db.register_schema(DDL)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str | None = None) -> Connection:
    """DATA_DIR 은 로그·시드·계정 메모가 쓰므로 계속 만들어 둔다. 데이터 자체는 PostgreSQL 에 있다."""
    DATA_DIR.mkdir(exist_ok=True)
    return db.connect(path)


def upsert_videos(con: Connection, videos: list[ShortsVideo]) -> int:
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


def save_interpretations(con: Connection, items: list[ShortsInterpretation], model: str) -> int:
    now = _now()
    for it in items:
        vid = it.url.split("v=")[-1].split("&")[0].split("/")[-1]
        con.execute("INSERT INTO interpretations VALUES (?,?,?,?)", (vid, model, now, it.model_dump_json()))
    con.commit()
    return len(items)


# 뉴스 주소는 기본키다. PostgreSQL 기본키(btree) 색인은 한 항목이 2,704바이트까지라 그보다 긴 Google 뉴스 주소가 하나 섞이면
# 그 묶음이 통째로 롤백됐다(2026-09-29 트윈 이관 실측: 42,776건 중 2,901바이트 1건). 이보다 긴 주소의 뉴스는 저장하지 않는다.
NEWS_LINK_MAX = 2048  # UTF-8 바이트


def upsert_news(con: Connection, items: list[NewsItem]) -> int:
    now = _now()
    items = [it for it in items if len(it.link.encode()) <= NEWS_LINK_MAX]
    for it in items:
        con.execute(
            "INSERT OR IGNORE INTO news VALUES (?,?,?,?,?,?)",
            (it.link, it.region, it.query, it.published_at.isoformat() if it.published_at else None,
             now, it.model_dump_json()),
        )
    con.commit()
    return len(items)


def headline_sources(con: Connection, since: str) -> dict[str, Counter]:
    """since 이후 받은 머리기사(키워드 없이 받은 판별 뉴스)의 매체마다 판별 건수 — 매체의 나라를 가르는 재료(collect.source_homes)."""
    out: dict[str, Counter] = {}
    for region, j in con.execute("SELECT region, json FROM news WHERE query IS NULL AND first_seen >= ?", (since,)).fetchall():
        source = json.loads(j).get("source") or ""
        if source:
            out.setdefault(source, Counter())[region] += 1
    return out


def top_videos(con: Connection, n: int = 3, region: str | None = None) -> list[str]:
    q = "SELECT json FROM videos" + (" WHERE region=?" if region else "") + " ORDER BY view_count DESC LIMIT ?"
    rows = con.execute(q, ((region, n) if region else (n,))).fetchall()
    return [ShortsVideo.model_validate_json(r[0]).url for r in rows]
