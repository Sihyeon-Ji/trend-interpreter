import uuid

import psycopg
import pytest

from scripts import restore_rehearsal as rehearsal
from trend_agents.config import DATABASE_URL


@pytest.fixture
def schemas():
    names = [f"r_{uuid.uuid4().hex[:12]}" for _ in range(2)]
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        for name in names:
            conn.execute(f"CREATE SCHEMA {name}")
            conn.execute(f"CREATE TABLE {name}.terms (term_id TEXT PRIMARY KEY, json JSONB, seen INTEGER NOT NULL)")
            conn.execute(f"CREATE INDEX terms_seen ON {name}.terms (seen)")
        yield conn, names
        for name in names:
            conn.execute(f"DROP SCHEMA {name} CASCADE")


def insert(conn, schema, rows):
    conn.cursor().executemany(f"INSERT INTO {schema}.terms VALUES (%s, %s, %s)", rows)


def test_fingerprint_ignores_row_order_but_detects_changed_content(schemas):
    conn, (source, restored) = schemas
    rows = [("a", '{"x": 1}', 1), ("b", None, 2)]
    insert(conn, source, rows)
    insert(conn, restored, list(reversed(rows)))
    assert rehearsal.differences(rehearsal.fingerprint(conn, source), rehearsal.fingerprint(conn, restored)) == []

    conn.execute(f"UPDATE {restored}.terms SET seen = 3 WHERE term_id = 'b'")
    assert rehearsal.differences(rehearsal.fingerprint(conn, source), rehearsal.fingerprint(conn, restored)) == [
        "rows or content of terms"
    ]


def test_fingerprint_detects_missing_index_and_table(schemas):
    conn, (source, restored) = schemas
    conn.execute(f"DROP INDEX {restored}.terms_seen")
    conn.execute(f"CREATE TABLE {source}.extra (id INTEGER)")
    assert rehearsal.differences(rehearsal.fingerprint(conn, source), rehearsal.fingerprint(conn, restored)) == [
        "table extra",
        "columns",
        "indexes",
    ]
