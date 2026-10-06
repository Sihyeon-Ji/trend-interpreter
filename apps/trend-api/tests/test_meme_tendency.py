"""The PostgreSQL report must match a fixed legacy snapshot and reject writes."""
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import psycopg
import pytest

from trend_agents.storage import db

_spec = importlib.util.spec_from_file_location(
    "meme_tendency", Path(__file__).resolve().parents[1] / "scripts" / "meme_tendency.py"
)
tendency = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tendency)


def seed(con):
    for tid, source, categories in [
        ("a", "namu", ["2017년 인터넷 밈", "미국의 인터넷 밈"]),
        ("a", "wikidata", ["year:2020"]),
        ("b", "namu", ["2025년 인터넷 밈", "대한민국의 인터넷 밈"]),
        ("c", "trendaword", ["year:2024"]),
    ]:
        con.execute(
            "INSERT INTO wiki_catalog (term_id, source, title, categories_json) VALUES (?,?,?,?)",
            (tid, source, tid, json.dumps(categories)),
        )
    fit = json.dumps({"feelings": ["joy"], "uses": ["reaction"], "voice": "playful"})
    con.execute("INSERT INTO term_fit (term_id, meaning_id, json) VALUES (?,?,?)", ("c", "m_c", fit))
    con.execute(
        "INSERT INTO evidences (evidence_id, term_id, observed_at) VALUES (?,?,?)",
        ("e_taw_c", "c", "2024-04-01T00:00:00+00:00"),
    )
    for tid, month, views in [("a", "2023-01", 100), ("a", "2024-01", 100), ("d", "2025-03", 200)]:
        con.execute(
            "INSERT INTO term_pageviews (term_id, lang, month, views) VALUES (?,?,?,?)",
            (tid, "en", month, views),
        )
    con.commit()


def legacy(path):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE wiki_catalog (term_id TEXT, source TEXT, title TEXT, categories_json TEXT);
        CREATE TABLE term_fit (term_id TEXT, meaning_id TEXT, json TEXT);
        CREATE TABLE evidences (evidence_id TEXT, term_id TEXT, observed_at TEXT);
        CREATE TABLE term_pageviews (term_id TEXT, lang TEXT, month TEXT, views BIGINT);
    """)
    return con


def reader_for(writer, factory=db.connect_read_only):
    con = factory()
    con.raw.execute(f"SET search_path TO {writer._schema}")
    con.raw.commit()
    return con


def test_same_fixed_data_has_identical_sqlite_and_postgres_reports(tmp_path, monkeypatch):
    path = tmp_path / "snapshot.db"
    sqlite = legacy(path)
    pg = db.connect(":memory:")
    try:
        seed(sqlite)
        seed(pg)
        sqlite.close()
        reports = []
        for source in ("sqlite", "postgres"):
            output = tmp_path / source
            argv = ["meme_tendency.py", "--out", str(output)]
            if source == "sqlite":
                argv += ["--sqlite", str(path)]
            else:
                monkeypatch.setattr(tendency.db, "connect_read_only", lambda: reader_for(pg))
            monkeypatch.setattr(sys, "argv", argv)
            tendency.main()
            report = json.loads((output / "tendency.json").read_text())
            report.pop("generated_at")
            reports.append(report)
            assert "—" not in (output / "tendency.md").read_text()
        assert reports[0] == reports[1]
        assert reports[0]["peak_years"] == {
            "2024": {"n": 1, "no_source_year": 0},
            "2025": {"n": 1, "no_source_year": 1},
        }
        assert reports[0]["trendaword"]["2024-Q2"]["fit_n"] == 1
        assert reports[0]["compare"]["전체(출처 섞음, 같은 말 1회)"]["n_rows"] == 3
    finally:
        pg.close()


def test_postgres_source_is_read_only_and_does_not_apply_migrations(monkeypatch):
    pg = db.connect(":memory:")
    try:
        seed(pg)
        read_only_connect = db.connect_read_only
        monkeypatch.setattr(db, "connect", lambda *a, **kw: pytest.fail("DDL connection used"))
        monkeypatch.setattr(db, "connect_read_only", read_only_connect)
        con = tendency.connect_source(None)
        try:
            assert con.execute("SHOW default_transaction_read_only").fetchone()[0] == "on"
            with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
                con.execute("CREATE TABLE forbidden_tendency_write (id TEXT)")
        finally:
            con.close()
    finally:
        pg.close()


def test_sqlite_source_rejects_writes_and_missing_snapshot(tmp_path):
    path = tmp_path / "snapshot with spaces.db"
    legacy(path).close()
    con = tendency.connect_source(str(path))
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            con.execute("DELETE FROM wiki_catalog")
    finally:
        con.close()
    with pytest.raises(SystemExit, match="DB 사본이 없습니다"):
        tendency.connect_source(str(tmp_path / "missing.db"))


def test_empty_legacy_snapshot_without_optional_pageviews_renders(tmp_path):
    con = legacy(tmp_path / "empty.db")
    try:
        con.execute("DROP TABLE term_pageviews")
        out = tendency.analyze(con)
        assert out["peak_years"] == {}
        assert out["catalog_rows"] == {}
        assert "0행(0%)" in tendency.render(out)
    finally:
        con.close()
