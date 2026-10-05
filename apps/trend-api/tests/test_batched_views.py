"""사전 전체·검수 큐 목록은 표제어마다 조회하지 않고 표마다 한 번에 읽는다(ds.batched). Cloud SQL 은 조회마다 네트워크 왕복이 붙어
1만여 개 표제어의 /terms 가 90초를 넘겼다(staging 10-03). 한 번에 읽은 결과가 표제어마다 읽은 것과 같아야 하고, 조회 수는 표제어 수와 무관해야 한다."""
from datetime import date, datetime, timedelta, timezone

from trend_agents.pipeline import views
from trend_agents.schemas import Evidence, MeaningDraft, MeaningText, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

NOW = datetime.now(timezone.utc)
STATUSES = ("verified", "needs_review")


def draft(definition):
    return MeaningDraft(definition=definition, origin="커뮤니티 농담", nuance="가볍게 놀리는 말", generations=["10s"],
                        regions=["US"], self_confidence=0.8)


def seed(con, tid, name, status="verified"):
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="en", status=status, first_seen=NOW, last_seen=NOW))
    ds.add_meaning(con, tid, draft(f"{name} 의 첫 뜻"), "verified_auto", [])
    ds.add_meaning(con, tid, draft(f"{name} 의 고친 뜻"), "verified_auto" if status == "verified" else "unverified", [])
    ds.add_evidences(con, tid, [
        Evidence(evidence_id=f"{tid}-e{i}", kind="news", url=f"https://news.example/{tid}/{i}", title=f"{name} spreads {i}",
                 source_domain="news.example", observed_at=NOW - timedelta(days=i), excerpt=f"People say {name} a lot")
        for i in range(3)])
    ds.set_usage(con, tid, [("10s", "US", NOW.isoformat(), 0.6), ("20s", "KR", NOW.isoformat(), 0.3)])
    monday = date.today() - timedelta(days=date.today().weekday())
    ds.set_weekly(con, tid, {(monday - timedelta(weeks=w)).isoformat(): 10 + w for w in range(14)})
    for lang in ("ko", "en"):
        ds.set_translation(con, tid, lang, MeaningText(definition=f"{lang} {name}", origin="o", nuance="n", plain=f"쉬운 {name}"), "synthetic")
    for i in range(5):
        ds.add_media(con, tid, "image" if i % 2 else "video", f"https://media.example/{tid}/{i}", title=f"{name} {i}")
    for days, home in ((3, "US"), (400, "KR")):
        con.execute("INSERT INTO mention_samples VALUES (?,?,?,?,?,?)",
                    (tid, "US", f"https://outlet-{home}.example/{tid}/{days}", f"outlet-{home}", home,
                     (NOW - timedelta(days=days)).isoformat()))
    con.execute("INSERT INTO wiki_catalog VALUES (?,?,?,?,?)", (tid, "namu", name, '["2017년 인터넷 밈"]', NOW.isoformat()))
    if status == "needs_review":
        ds.queue_review(con, tid, draft(f"{name} 제안"), ["근거 부족"], 3)
    con.commit()


def counting(con):
    calls = []
    original = con.execute

    def execute(sql, *args, **kwargs):
        calls.append(sql)
        return original(sql, *args, **kwargs)

    con.execute = execute
    return calls


def test_batched_term_records_match_per_term_reads_with_constant_queries():
    con = db.connect(":memory:")
    for i, status in enumerate(("verified", "verified", "needs_review")):
        seed(con, f"t{i}", f"term {i}", status)
    expected = [views.term_record(con, t) for t in ds.list_terms(con, STATUSES)]
    calls = counting(con)
    assert views.term_records(con, STATUSES) == expected
    few = len(calls)
    for i in range(3, 9):
        seed(con, f"t{i}", f"term {i}")
    calls.clear()
    assert len(views.term_records(con, STATUSES)) == 9
    assert len(calls) == few
    assert expected[0].weekly and len(expected[0].weekly) == 12 and len(expected[0].media) <= 4
    assert any(r.gate_reasons for r in expected)


def test_batched_review_items_match_per_term_reads():
    con = db.connect(":memory:")
    for i in range(3):
        seed(con, f"r{i}", f"review {i}", "needs_review")
    queue = ds.review_queue(con)
    expected = views._review_items(con, queue)
    assert len(expected) == 3
    assert views.review_items(con) == expected


def test_reads_outside_the_batch_are_live():
    con = db.connect(":memory:")
    seed(con, "t0", "term 0")
    with ds.batched(con, ["t0"]):
        assert ds.current_meaning(con, "t0").definition == "term 0 의 고친 뜻"
    ds.add_meaning(con, "t0", draft("term 0 의 세 번째 뜻"), "verified_auto", [])
    assert ds.current_meaning(con, "t0").definition == "term 0 의 세 번째 뜻"
    with ds.batched(con, []):
        assert ds.list_meanings(con, "t0") == []


def test_large_list_responses_are_compressed(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    con = db.connect(":memory:")
    for i in range(3):
        seed(con, f"t{i}", f"term {i}")
    monkeypatch.setattr(api, "_con", con)
    response = TestClient(api.app).get("/terms", headers={"accept-encoding": "gzip"})
    assert response.status_code == 200 and response.headers["content-encoding"] == "gzip"
    assert len(response.json()) == 3


def test_selected_tables_are_cached_and_the_rest_read_live():
    con = db.connect(":memory:")
    seed(con, "t0", "term 0")
    expected = (ds.get_usage(con, "t0"), ds.list_meanings(con, "t0"))
    with ds.batched(con, ["t0"], tables=("usage",)):
        con.execute("DELETE FROM usage WHERE term_id='t0'")
        assert ds.get_usage(con, "t0") == expected[0]          # 블록이 읽어 둔 표
        assert ds.list_meanings(con, "t0") == expected[1]      # 고르지 않은 표는 직접 조회
        ds.add_meaning(con, "t0", draft("term 0 의 새 뜻"), "verified_auto", [])
        assert ds.current_meaning(con, "t0").definition == "term 0 의 새 뜻"


def test_chat_list_tool_and_entry_lookup_query_counts_do_not_grow_with_the_dictionary():
    """목록 도구는 고른 12개의 뜻만 따로 읽는다 — 12개가 넘으면 사전이 커져도 조회 수가 같아야 한다."""
    from trend_agents.pipeline import tools

    con = db.connect(":memory:")
    for i in range(13):
        seed(con, f"t{i}", f"term {i}")
    calls = counting(con)
    first = tools.list_terms(tools.Ctx(con), {"region": "US"})
    tools._entries(con)
    few = len(calls)
    for i in range(13, 20):
        seed(con, f"t{i}", f"term {i}")
    calls.clear()
    assert tools.list_terms(tools.Ctx(con), {"region": "US"}) and len(tools._entries(con)) == 20
    assert len(calls) == few and "term" in first


def test_dictionary_scans_by_description_do_not_query_per_entry():
    """이름을 모를 때 뜻으로 찾는 도구(search_terms·_by_meaning)도 사전 전체를 훑는다 — 표제어마다 조회하지 않는다."""
    from trend_agents.pipeline import tools

    con = db.connect(":memory:")
    for i in range(13):
        seed(con, f"t{i}", f"term {i}")
    calls = counting(con)
    tools._by_meaning(con, "커뮤니티 농담 가볍게 놀리는 말")
    tools.search_terms(tools.Ctx(con), {"query": "가볍게 놀리는"})
    few = len(calls)
    for i in range(13, 20):
        seed(con, f"t{i}", f"term {i}")
    calls.clear()
    assert len(tools._by_meaning(con, "커뮤니티 농담 가볍게 놀리는 말")) == 5
    assert "가장 가까운 것" in tools.search_terms(tools.Ctx(con), {"query": "가볍게 놀리는"})
    assert len(calls) == few
