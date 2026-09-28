"""SQL 변환은 DB 없이 검사한다. 저장소 함수가 SQLite 시절 문장을 그대로 써도 PostgreSQL 이 받는 형태가 되어야 한다."""
from datetime import date, datetime, timezone

from trend_agents.storage import db, dictionary_store, store  # noqa: F401  (DDL 등록)


def test_qmark_placeholders_become_psycopg_format_outside_string_literals():
    assert db.translate("SELECT a FROM t WHERE b=? AND c='?'", True) == "SELECT a FROM t WHERE b=%s AND c='?'"


def test_percent_is_escaped_only_when_parameters_are_sent():
    assert db.translate("SELECT '100%' FROM t WHERE k=?", True) == "SELECT '100%%' FROM t WHERE k=%s"
    assert db.translate("SELECT '100%' FROM t", False) == "SELECT '100%' FROM t"


def test_insert_or_replace_updates_every_non_key_column():
    sql = db.translate("INSERT OR REPLACE INTO translations VALUES (?,?,?,?,?)", True)
    assert sql == ("INSERT INTO translations VALUES (%s,%s,%s,%s,%s) "
                   "ON CONFLICT (term_id, lang) DO UPDATE SET json=EXCLUDED.json, updated_at=EXCLUDED.updated_at, model=EXCLUDED.model")


def test_insert_or_ignore_skips_conflicts():
    assert db.translate("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?,?,?)", True).endswith(" ON CONFLICT DO NOTHING")


def test_inline_primary_key_is_parsed():
    assert db.TABLES["gemini_calls"].primary_key == ("day",)
    assert db.TABLES["trend_queries"].primary_key == ("term", "region", "source", "date")
    assert db.TABLES["reader_prefs"].columns == ("reader", "json", "updated_at")


def test_parameters_are_stored_the_way_sqlite_stored_them():
    assert db._param(True) == 1 and db._param(False) == 0
    assert db._param(date(2026, 9, 28)) == "2026-09-28"
    assert db._param(datetime(2026, 9, 28, 1, 2, tzinfo=timezone.utc)) == "2026-09-28T01:02:00+00:00"
    assert db._param("x") == "x" and db._param(None) is None


def test_read_only_statements_are_detected():
    assert db._is_read("  select 1") and db._is_read("WITH x AS (SELECT 1) SELECT * FROM x")
    assert not db._is_read("UPDATE t SET a=1")
