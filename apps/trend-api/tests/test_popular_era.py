"""유행 시기(Plan 02 진단 10-05) — 생애주기는 최근 쓰임으로만 정하고, 위키 분류의 연도·연대는 따로 '언제 유행했나' 로 보인다."""
from datetime import datetime, timezone

from trend_agents.pipeline import views
from trend_agents.schemas import Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

NOW = datetime.now(timezone.utc)


def term(con, tid, *catalog):
    ds.upsert_term(con, Term(term_id=tid, canonical=tid, lang="ko", status="verified", first_seen=NOW, last_seen=NOW))
    for i, cats in enumerate(catalog):
        con.execute("INSERT INTO wiki_catalog VALUES (?,?,?,?,?)", (tid, "namu", f"{tid}-{i}", cats, NOW.isoformat()))
    con.commit()
    return views.term_record(con, ds.get_term(con, tid))


def test_year_category_gives_year_and_decade():
    r = term(db.connect(":memory:"), "가즈아", '["2017년 인터넷 밈", "인터넷 밈/대한민국"]')
    assert (r.popular_year, r.popular_decade) == (2017, 2010)
    assert r.term.lifecycle == "unknown"   # 생애주기는 그대로 둔다


def test_decade_only_and_tagged_year():
    con = db.connect(":memory:")
    assert (term(con, "a", '["2000년대 인터넷 밈"]').popular_year, term(con, "a2", '["2000년대 인터넷 밈"]').popular_decade) == (None, 2000)
    assert term(con, "b", '["region:KR", "유행어", "year:2025"]').popular_year == 2025


def test_no_catalog_or_no_date_leaves_it_empty():
    con = db.connect(":memory:")
    r = term(con, "c")
    assert (r.popular_year, r.popular_decade) == (None, None)
    r = term(con, "d", '["인터넷 밈/게임"]')
    assert (r.popular_year, r.popular_decade) == (None, None)


def test_earliest_year_wins_across_wiki_sources():
    r = term(db.connect(":memory:"), "e", '["2019년 인터넷 밈"]', '["Internet memes introduced in 2016"]')
    assert (r.popular_year, r.popular_decade) == (2016, 2010)
