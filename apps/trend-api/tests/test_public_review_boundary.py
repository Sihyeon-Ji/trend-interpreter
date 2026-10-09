"""Drafts stay in reviewer reads and never become public explanations."""
import pytest
from fastapi.testclient import TestClient

from trend_agents.api import app as api
from trend_agents.pipeline import explain, tools
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import db


def draft(text):
    return MeaningDraft(definition=text, origin="origin", nuance="nuance", generations=["20s"], regions=["KR"], self_confidence=0.9)


def add(con, tid, status="verified", verification="verified_auto"):
    ds.upsert_term(con, Term(term_id=tid, canonical=tid, lang="en", status=status))
    return ds.add_meaning(con, tid, draft(f"{tid} approved or proposed definition"), verification, [])


@pytest.fixture
def boundary(monkeypatch):
    con = db.connect(":memory:")
    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "test-review-server-token")
    monkeypatch.setattr(api.risk, "apply", lambda *a, **kw: None)
    monkeypatch.setattr(api.dashboard, "refresh_card", lambda *a, **kw: None)
    yield con, TestClient(api.app), {"x-frontend-token": "test-review-server-token"}
    con.close()


@pytest.mark.parametrize("path", [
    "/review/queue", "/review/stats", "/review/terms", "/review/terms/pending",
    "/pipeline/stages", "/model-usage", "/candidates",
])
def test_review_reads_refuse_missing_wrong_or_disabled_token(boundary, monkeypatch, path):
    _, client, headers = boundary
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"x-frontend-token": "wrong", "x-reviewer": "true"}).status_code == 401
    monkeypatch.delenv("FRONTEND_API_TOKEN")
    assert client.get(path, headers=headers).status_code == 401


def test_public_list_detail_history_and_related_routes_hide_drafts(boundary):
    con, client, headers = boundary
    old = add(con, "published", verification="unverified")
    current = ds.add_meaning(con, "published", draft("approved current definition"), "verified_human", [])
    add(con, "pending", "needs_review", "unverified")
    add(con, "researching", "researching", "unverified")
    add(con, "retired", "retired", "rejected")
    add(con, "inconsistent", "verified", "unverified")
    for path in ("/terms", "/terms?slim=true"):
        response = client.get(path)
        assert response.status_code == 200
        assert [r["term"]["term_id"] for r in response.json()] == ["published"]
        assert old.meaning_id not in response.text
    public = client.get("/terms/published").json()
    assert [m["meaning_id"] for m in public["meanings"]] == [current.meaning_id]
    for tid in ("pending", "researching", "retired", "inconsistent"):
        for suffix in ("", "/topic", "/graph", "/signals", "/generations"):
            assert client.get(f"/terms/{tid}{suffix}").status_code == 404
    assert client.get("/terms?status=all").status_code == 422
    response = client.get("/review/terms/pending", headers=headers)
    assert response.status_code == 200 and response.json()["term"]["status"] == "needs_review"
    assert response.headers["cache-control"] == "private, no-store"
    reviewed = client.get("/review/terms/published", headers=headers).json()
    assert old.meaning_id in [m["meaning_id"] for m in reviewed["meanings"]]
    assert {r["term"]["term_id"] for r in client.get("/review/terms", headers=headers).json()} == {
        "published", "pending", "inconsistent",
    }


def test_profane_headword_is_hidden_from_public_reads_until_a_reviewer_clears_it(boundary, monkeypatch):
    con, client, headers = boundary
    add(con, "published")
    ds.upsert_term(con, Term(term_id="rude", canonical="Fuck Tha Police", lang="en", status="verified"))
    ds.add_meaning(con, "rude", draft("rude approved definition"), "verified_auto", [])
    monkeypatch.setattr(explain, "rewrite", lambda *a, **kw: None)
    for path in ("/terms", "/terms?slim=true"):
        assert [r["term"]["term_id"] for r in client.get(path).json()] == ["published"]
    for suffix in ("", "/topic", "/graph", "/signals", "/generations"):
        assert client.get(f"/terms/rude{suffix}").status_code == 404
    assert client.post("/explain", json={"text": "Fuck Tha Police"}).json()["term_ids"] == []
    feed = {i.get("term_id") for i in client.get("/updates?kinds=all").json()["items"]}
    assert "published" in feed and "rude" not in feed
    assert "rude" in {r["term"]["term_id"] for r in client.get("/review/terms", headers=headers).json()}
    # 오탐은 검수자가 '특이 사항 없음' 으로 풀면 다시 공개된다
    t = ds.get_term(con, "rude")
    t.risk_human = t.risk_level = "none"
    ds.upsert_term(con, t, human=True)
    assert client.get("/terms/rude").status_code == 200
    assert "rude" in [r["term"]["term_id"] for r in client.get("/terms?slim=true").json()]


def test_avoid_verdict_is_hidden_from_public_reads(boundary, monkeypatch):
    con, client, headers = boundary
    add(con, "published")
    add(con, "slogan")
    t = ds.get_term(con, "slogan")
    t.risk_human = t.risk_level = "avoid"
    ds.upsert_term(con, t, human=True)
    monkeypatch.setattr(explain, "rewrite", lambda *a, **kw: None)
    assert [r["term"]["term_id"] for r in client.get("/terms?slim=true").json()] == ["published"]
    assert client.get("/terms/slogan").status_code == 404
    assert client.post("/explain", json={"text": "slogan"}).json()["term_ids"] == []
    assert "slogan" not in {i.get("term_id") for i in client.get("/updates?kinds=all").json()["items"]}
    assert "slogan" in {r["term"]["term_id"] for r in client.get("/review/terms", headers=headers).json()}
    # 사용 자제를 거두면 다시 공개된다
    t.risk_human = t.risk_level = "caution"
    ds.upsert_term(con, t, human=True)
    assert client.get("/terms/slogan").status_code == 200


def test_slim_cache_changes_when_current_approval_changes(boundary):
    con, client, _ = boundary
    m = add(con, "published")
    assert len(client.get("/terms?slim=true").json()) == 1
    ds.set_verification(con, m.meaning_id, "unverified", "test")
    assert client.get("/terms?slim=true").json() == []
    ds.set_verification(con, m.meaning_id, "verified_human", "test")
    assert len(client.get("/terms?slim=true").json()) == 1


def test_review_queue_and_operational_reads_remain_available_to_reviewer(boundary):
    con, client, headers = boundary
    add(con, "pending", "needs_review", "unverified")
    ds.queue_review(con, "pending", draft("pending proposed definition"), ["review required"], 1)
    for path in ("/review/queue", "/review/stats", "/pipeline/stages", "/model-usage", "/candidates"):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
    assert client.get("/review/queue", headers=headers).json()[0]["term_id"] == "pending"


def test_explanation_discards_legacy_draft_cache_and_rechecks_retired_entries(boundary, monkeypatch):
    con, client, _ = boundary
    add(con, "published")
    add(con, "pending", "needs_review", "unverified")
    ds.explain_cache_set(con, "ko", "published pending", ["published", "pending"], "DRAFT REWRITE")
    seen = []

    def rewrite(text, lang, glossary, reader):
        seen.append(glossary)
        return "APPROVED REWRITE" if glossary else None

    monkeypatch.setattr(explain, "rewrite", rewrite)
    result = client.post("/explain", json={"text": "published pending"}).json()
    assert result == {"term_ids": ["published"], "plain": "APPROVED REWRITE"}
    assert [name for name, _ in seen[0]] == ["published"]
    t = ds.get_term(con, "published")
    t.status = "retired"
    ds.upsert_term(con, t, human=True)
    assert client.post("/explain", json={"text": "published pending"}).json() == {"term_ids": [], "plain": None}


def test_chat_exact_fuzzy_and_definition_search_only_read_approved_entries(boundary):
    con, _, _ = boundary
    add(con, "published")
    add(con, "pending", "needs_review", "unverified")
    add(con, "inconsistent", "verified", "unverified")
    assert tools._find(con, "pending") is None
    assert tools._fuzzy_find(con, "pendin") is None
    assert tools._by_meaning(con, "pending") == []
    assert tools._find(con, "inconsistent") is None
    assert [t.term_id for t in tools._entries(con)] == ["published"]
    assert "published" in tools.lookup_term(tools.Ctx(con), {"term": "published"})


def test_approval_publishes_and_rejection_removes_entry(boundary, monkeypatch):
    con, client, headers = boundary
    m = add(con, "pending", "needs_review", "unverified")
    ds.queue_review(con, "pending", draft("pending proposed definition"), ["review required"], 1)
    monkeypatch.setattr(explain, "rewrite", lambda *a, **kw: None)
    assert client.get("/terms/pending").status_code == 404
    assert client.post("/review/pending", json={"decision": "approve", "meaning_id": m.meaning_id}).status_code == 401
    result = client.post("/review/pending", headers=headers, json={"decision": "approve", "meaning_id": m.meaning_id})
    assert result.status_code == 200
    assert client.get("/terms/pending").status_code == 200
    assert client.post("/explain", json={"text": "pending"}).json()["term_ids"] == ["pending"]
    assert client.post("/review/pending", headers=headers, json={"decision": "reject", "meaning_id": m.meaning_id}).status_code == 200
    assert client.get("/terms/pending").status_code == 404
    assert client.post("/explain", json={"text": "pending"}).json()["term_ids"] == []
