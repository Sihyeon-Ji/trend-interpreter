"""마이그레이션 러너, 별칭 표, 사용자 문장 보존 기간 — 임시 스키마에서."""
from datetime import datetime, timedelta, timezone

import pytest
import psycopg

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


def test_pool_replaces_connection_lost_while_idle(monkeypatch):
    previous_pool = db._pool
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(db, "DB_POOL_SIZE", 1)
    try:
        with db.session() as con:
            old_pid = con.execute("SELECT pg_backend_pid()").fetchone()[0]
        with psycopg.connect(db.DATABASE_URL, autocommit=True) as killer:
            assert killer.execute("SELECT pg_terminate_backend(%s)", (old_pid,)).fetchone()[0]
        with db.session() as con:
            assert con.execute("SELECT 1").fetchone()[0] == 1
            assert con.execute("SELECT pg_backend_pid()").fetchone()[0] != old_pid
    finally:
        db._pool.close()
        db._pool = previous_pool


def test_read_only_connection_skips_schema_setup_and_refuses_writes(monkeypatch):
    """평가·표본 스크립트의 연결 — DDL·마이그레이션을 보내지 않고 쓰기는 서버가 거부한다. connect() 로 붙던 때는 병합 전 가지의
    스크립트를 운영 DB 에 돌리면 그 가지의 마이그레이션이 적용되고 checksum 이 남았다(검토)."""
    import psycopg

    monkeypatch.setattr(db, "apply_migrations", lambda *a, **k: pytest.fail("마이그레이션을 적용하면 안 된다"))
    monkeypatch.setattr(db.Connection, "executescript", lambda *a, **k: pytest.fail("DDL 을 보내면 안 된다"))
    con = db.connect_read_only()
    assert con.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        con.execute("CREATE TABLE read_only_probe (x TEXT)")
    assert con.execute("SELECT 2").fetchone()[0] == 2          # 거부된 뒤에도 읽는다
    con.close()


def test_jamo_only_headwords_are_corrected_to_korean():
    """017: 자모만 쓴 표제어가 일본어·영어로 저장된 것을 한국어로 고친다(ㅋㅋ, 10-05). 다른 말은 그대로."""
    con = db.connect(":memory:")
    for tid, name, lang in (("kk", "ㅋㅋ", "ja"), ("mc", "ㅁㅊㄷ ㅁㅊㅇ", "en"), ("ja", "ぴえん", "ja"), ("mixed", "ㅋㅋ草", "ja")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified"))
    con.commit()
    con.raw.execute((db.MIGRATIONS_DIR / "017_jamo_terms_korean.sql").read_text(encoding="utf-8"))
    con.commit()
    assert {t: ds.get_term(con, t).lang for t in ("kk", "mc", "ja", "mixed")} == {"kk": "ko", "mc": "ko", "ja": "ja", "mixed": "ja"}
    assert con.execute("SELECT lang FROM terms WHERE term_id='kk'").fetchone()[0] == "ko"
    con.close()
