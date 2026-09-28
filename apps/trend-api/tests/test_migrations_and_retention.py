"""마이그레이션 러너, 별칭 표, 사용자 문장 보존 기간 — 임시 스키마에서."""
from datetime import datetime, timedelta, timezone

import pytest

from trend_agents.schemas import Term
from trend_agents.storage import db, dictionary_store as ds, store


def test_migrations_apply_once_and_reject_edited_files(tmp_path):
    con = db.connect(":memory:")
    (tmp_path / "901_widgets.sql").write_text("CREATE TABLE widgets (id TEXT PRIMARY KEY);")
    assert db.apply_migrations(con, tmp_path) == ["901_widgets.sql"]
    assert db.apply_migrations(con, tmp_path) == []  # 두 번째는 건너뜀
    (tmp_path / "901_widgets.sql").write_text("CREATE TABLE widgets (id TEXT PRIMARY KEY, extra TEXT);")
    with pytest.raises(RuntimeError):
        db.apply_migrations(con, tmp_path)
    (tmp_path / "902_more.sql").write_text("ALTER TABLE widgets ADD COLUMN extra TEXT;")
    (tmp_path / "901_widgets.sql").write_text("CREATE TABLE widgets (id TEXT PRIMARY KEY);")
    assert db.apply_migrations(con, tmp_path) == ["902_more.sql"]
    con.close()


def test_bundled_migrations_are_applied_to_every_new_schema():
    con = db.connect(":memory:")
    versions = [v for (v,) in con.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
    assert versions[:1] == [1]
    con.close()


def test_aliases_are_indexed_and_follow_term_updates():
    con = db.connect(":memory:")
    ds.upsert_term(con, Term(term_id="t1", canonical="느좋", aliases=["느낌 좋다", "느좋이다"]))
    assert ds.find_term(con, "느낌좋다").term_id == "t1"
    assert ds.find_term(con, "느좋이다").term_id == "t1"
    ds.upsert_term(con, Term(term_id="t1", canonical="느좋", aliases=["느좋이다"]))
    assert ds.find_term(con, "느낌좋다") is None  # 사라진 별칭은 더 이상 찾지 않는다
    assert ds.find_term(con, "느좋").term_id == "t1"
    con.close()


def test_user_text_is_pruned_after_its_retention_window():
    con = db.connect(":memory:")
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    ds.explain_cache_set(con, "ko", "오래된 문장", [], None)
    ds.explain_cache_set(con, "ko", "새 문장", [], None)
    con.execute("UPDATE explain_cache SET created_at=? WHERE text=?", (old, "오래된 문장"))
    ds.log_lookup_miss(con, "오래된 질문", "ko")
    ds.log_lookup_miss(con, "새 질문", "ko")
    con.execute("UPDATE lookups SET last_at=? WHERE text=?", ((datetime.now(timezone.utc) - timedelta(days=31)).isoformat(), "오래된 질문"))
    con.commit()
    assert ds.prune_user_text(con) == (1, 1)
    assert ds.explain_cache_get(con, "ko", "새 문장") is not None
    assert [t for _, t, _ in ds.pending_lookups(con)] == ["새 질문"]
    con.close()


def test_pooled_sessions_share_the_migrated_schema():
    with db.session() as con:
        assert con.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] >= 1
        assert isinstance(store.top_videos(con, 1), list)
