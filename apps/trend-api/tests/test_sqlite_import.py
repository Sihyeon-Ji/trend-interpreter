"""SQLite 시절 파일을 PostgreSQL 로 옮기는 스크립트(Plan 01) — 트윈과 같은 모양의 작은 SQLite 파일을 임시 스키마로 옮긴다."""
import importlib.util
import random
import sqlite3
import string
from pathlib import Path

import pytest

from trend_agents.schemas import NewsItem, Term
from trend_agents.storage import db, dictionary_store as ds, store

_spec = importlib.util.spec_from_file_location(
    "migrate_sqlite_to_postgres", Path(__file__).resolve().parents[1] / "scripts" / "migrate_sqlite_to_postgres.py")
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)

# 트윈(SQLite)의 표 모양 그대로 — terms 에 diffusion 열이 없고, reader_prefs 의 열 이름이 user 다
TWIN_DDL = """
CREATE TABLE terms (term_id TEXT PRIMARY KEY, norm TEXT, canonical TEXT, lang TEXT, category TEXT, status TEXT, lifecycle TEXT,
  first_seen TEXT, last_seen TEXT, json TEXT);
CREATE TABLE news (link TEXT PRIMARY KEY, region TEXT, query TEXT, published_at TEXT, first_seen TEXT, json TEXT);
CREATE TABLE explain_cache (key TEXT PRIMARY KEY, lang TEXT, text TEXT, term_ids_json TEXT, plain TEXT, created_at TEXT);
CREATE TABLE reader_prefs (user TEXT PRIMARY KEY, json TEXT, updated_at TEXT);
"""


def _long_link(n: int = 2900) -> str:
    """색인이 압축하지 못하는 긴 주소 — 실제 Google 뉴스 주소처럼 base64 조각이다(같은 글자 반복은 압축돼 들어가 버린다)."""
    rnd = random.Random(0)
    return "https://news.google.com/rss/articles/" + "".join(rnd.choices(string.ascii_letters + string.digits + "-_", k=n))


def _news(link: str) -> NewsItem:
    return NewsItem(title="기사", link=link, published_at=None, source="s", region="US")


def _twin(tmp_path: Path, *terms: Term, links: tuple[str, ...] = ()) -> Path:
    path = tmp_path / "trend.db"
    src = sqlite3.connect(path)
    src.executescript(TWIN_DDL)
    for t in terms:
        src.execute("INSERT INTO terms VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (t.term_id, ds.norm(t.canonical), t.canonical, t.lang, t.category, t.status, t.lifecycle, None, None, t.model_dump_json()))
    for link in links:
        src.execute("INSERT INTO news VALUES (?,?,?,?,?,?)", (link, "US", None, None, "2026-09-29T00:00:00+00:00", _news(link).model_dump_json()))
    src.execute("INSERT INTO explain_cache VALUES (?,?,?,?,?,?)", ("k1", "ko", "붙여 넣은 문장", "[]", None, "2026-09-28T00:00:00+00:00"))
    src.execute("INSERT INTO reader_prefs VALUES (?,?,?)", ("reader1", '{"generation": "20s"}', "2026-09-16T00:00:00+00:00"))
    src.commit()
    src.close()
    return path


def test_diffusion_column_is_filled_from_the_term_json(tmp_path):
    # 마이그레이션 002 의 보정은 표가 비어 있을 때(연결할 때) 돌았다 — 옮긴 뒤 열이 비어 있었다
    con = db.connect(":memory:")
    path = _twin(tmp_path, Term(term_id="t1", canonical="럭키비키", diffusion="mainstream", aliases=["럭키 비키"]),
                 Term(term_id="t2", canonical="느좋"))
    mig.migrate(path, con)
    assert dict(con.execute("SELECT term_id, diffusion FROM terms").fetchall()) == {"t1": "mainstream", "t2": None}
    assert ds.find_term(con, "럭키 비키").term_id == "t1"  # 별칭 표도 다시 만든다
    con.close()


def test_fresh_refuses_a_database_that_already_has_terms(tmp_path):
    con = db.connect(":memory:")
    ds.upsert_term(con, Term(term_id="t1", canonical="럭키비키", status="needs_review"))
    path = _twin(tmp_path, Term(term_id="t1", canonical="럭키비키", status="verified"))
    with pytest.raises(SystemExit):
        mig.migrate(path, con, fresh=True)
    assert con.execute("SELECT COUNT(*) FROM explain_cache").fetchone()[0] == 0  # 아무것도 옮기지 않았다
    mig.migrate(path, con)  # --fresh 없이는 이미 있는 행을 건너뛴다 — 새 파일의 값이 아니라 옛 값이 남는다
    assert ds.get_term(con, "t1").status == "needs_review"
    con.close()


def test_news_links_too_long_for_the_primary_key_index_are_left_out(tmp_path):
    # PostgreSQL 기본키(btree) 색인은 한 항목 2,704바이트까지 — 트윈의 2,901바이트 주소 하나에 이관이 news 에서 멈췄다(2026-09-29)
    con = db.connect(":memory:")
    ok = "https://news.google.com/rss/articles/CBMiabc"
    mig.migrate(_twin(tmp_path, links=(ok, _long_link())), con)
    assert [r[0] for r in con.execute("SELECT link FROM news").fetchall()] == [ok]
    con.close()


def test_pipeline_skips_news_whose_link_does_not_fit_the_index():
    # 수집에 같은 주소가 하나 섞이면 그 나라 뉴스 묶음이 통째로 롤백됐다
    con = db.connect(":memory:")
    assert store.upsert_news(con, [_news("https://a.example/1"), _news(_long_link()), _news("https://a.example/2")]) == 2
    assert sorted(r[0] for r in con.execute("SELECT link FROM news").fetchall()) == ["https://a.example/1", "https://a.example/2"]
    con.close()


def test_user_data_stays_out_of_a_copy_for_cloud_sql(tmp_path):
    path = _twin(tmp_path)
    local, cloud = db.connect(":memory:"), db.connect(":memory:")
    mig.migrate(path, local)
    assert local.execute("SELECT reader FROM reader_prefs").fetchall() == [("reader1",)]  # 열 이름 user → reader
    assert local.execute("SELECT COUNT(*) FROM explain_cache").fetchone()[0] == 1
    mig.migrate(path, cloud, skip_user_data=True)
    assert cloud.execute("SELECT COUNT(*) FROM explain_cache").fetchone()[0] == 0
    assert cloud.execute("SELECT COUNT(*) FROM reader_prefs").fetchone()[0] == 0
    local.close()
    cloud.close()
