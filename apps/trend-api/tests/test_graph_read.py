"""지식그래프 읽기: 급증 검색어 이웃 · 여러 검색어에 걸친 인물/위키 · 용어로 판정된 검색어. 네트워크·모델 없음."""
from datetime import datetime, timezone

from trend_agents.pipeline import views
from trend_agents.schemas import Evidence
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import sqlite_store as db


def _explanation(con, key, term, region):
    con.execute("INSERT INTO trend_explanations VALUES (?,?,?,?,?,?,?,?,?)", (key, term, region, "2026-09-15", "event", 0.9, "{}", ds.now_s(), ds.now_s()))
    con.commit()


def test_query_graph_collects_neighbors_and_evidence():
    con = db.connect(":memory:")
    e = Evidence(evidence_id="e_1", kind="news", url="https://a.com/x", title="Allison Janney wins", source_domain="a.com", observed_at=datetime.now(timezone.utc), excerpt="")
    ds.add_evidences(con, "q|allisonjanney|US", [e])
    ds.add_edge(con, "query", "allisonjanney|US", "EVIDENCED_BY", "evidence", "e_1")
    ds.add_edge(con, "query", "allisonjanney|US", "TRIGGERED_BY", "actor", "Allison Janney")
    ds.add_edge(con, "query", "allisonjanney|US", "ABOUT", "wiki", "en:Allison Janney")
    ds.add_edge(con, "query", "allisonjanney|US", "IS_TERM", "term", "t_aj")
    _explanation(con, "allisonjanney|US", "allison janney", "US")
    g = views.query_graph(con, "allisonjanney|US")
    assert g and g.explained and g.term == "allison janney" and g.region == "US"
    assert g.actors == ["Allison Janney"] and g.wiki == ["en:Allison Janney"] and g.term_id == "t_aj"
    assert [x.title for x in g.evidence] == ["Allison Janney wins"]
    assert views.query_graph(con, "없음|KR") is None


def test_shared_nodes_rank_cross_region_first():
    con = db.connect(":memory:")
    ds.add_edge(con, "query", "ohtani|JP", "TRIGGERED_BY", "actor", "大谷翔平")
    ds.add_edge(con, "query", "dodgers|US", "TRIGGERED_BY", "actor", "大谷翔平")
    ds.add_edge(con, "query", "대법관|KR", "ABOUT", "wiki", "ko:대법관")
    ds.add_edge(con, "query", "대한민국의대법관|KR", "ABOUT", "wiki", "ko:대법관")
    ds.add_edge(con, "query", "solo|BR", "TRIGGERED_BY", "actor", "혼자")  # 검색어 하나뿐 → 제외
    nodes = views.shared_nodes(con)
    assert [(n.id, n.regions) for n in nodes] == [("大谷翔平", ["JP", "US"]), ("ko:대법관", ["KR"])]
    assert nodes[1].label == "대법관" and nodes[1].type == "wiki"


def test_term_graph_lists_queries_judged_as_the_term():
    con = db.connect(":memory:")
    ds.add_edge(con, "query", "6-7|US", "IS_TERM", "term", "t_67")
    ds.add_edge(con, "query", "sixseven|GB", "IS_TERM", "term", "t_67")
    _explanation(con, "6-7|US", "6-7", "US")
    qs = views.term_graph(con, "t_67")
    assert [(q.term, q.region, q.date) for q in qs] == [("6-7", "US", "2026-09-15"), ("sixseven", "GB", None)]
    assert views.term_graph(con, "t_none") == []
