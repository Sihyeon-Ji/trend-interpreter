"""Private batch reads and exact-hash approval never publish dictionary changes."""
import pytest
from fastapi.testclient import TestClient

from trend_agents.api import app as api
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import db, dictionary_store as ds, publications as pub


@pytest.fixture
def review_api(monkeypatch):
    con = db.connect(":memory:")
    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "private-review-token")
    ds.upsert_term(con, Term(term_id="t_test", canonical="test meme", status="verified"))
    draft = MeaningDraft(definition="a documented current meaning", origin="origin", nuance="nuance",
                         generations=["20s"], regions=["KR"], self_confidence=0.9)
    meaning = ds.add_meaning(con, "t_test", draft, "verified_auto", [])
    proposed = draft.model_copy(update={"definition": "a proposed meaning never shown publicly"})
    b = pub.ChangeBatch(batch_id="private_batch", snapshot_id="test", snapshot_sha256="a" * 64,
                        model_id="mock", prompt_version="p1", rule_version="r1", items=[
                            pub.ChangeItem(term_id="t_test", expected_meaning_id=meaning.meaning_id, meaning=proposed)])
    staged = pub.stage(con, b)
    yield con, TestClient(api.app), {"x-frontend-token": "private-review-token"}, staged["payload_sha256"]
    con.close()


@pytest.mark.parametrize("path,method", [("/review/batches", "get"),
    ("/review/batches/private_batch", "get"), ("/review/batches/private_batch/decision", "post")])
def test_batch_routes_refuse_missing_wrong_or_unconfigured_server_token(review_api, monkeypatch, path, method):
    _, client, headers, checksum = review_api
    kwargs = {"json": {"payload_sha256": checksum, "decision": "approve", "by": "reviewer"}} if method == "post" else {}
    call = getattr(client, method)
    assert call(path, **kwargs).status_code == 401
    assert call(path, headers={"x-frontend-token": "wrong"}, **kwargs).status_code == 401
    monkeypatch.delenv("FRONTEND_API_TOKEN")
    assert call(path, headers=headers, **kwargs).status_code == 401


def test_private_comparison_and_exact_hash_review_keep_public_meaning(review_api):
    con, client, headers, checksum = review_api
    response = client.get("/review/batches", headers=headers)
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["total"] == 1
    assert client.get("/review/batches?offset=1", headers=headers).json()["items"] == []
    assert client.get("/review/batches?limit=101", headers=headers).status_code == 422
    comparison = client.get("/review/batches/private_batch", headers=headers)
    assert comparison.headers["cache-control"] == "private, no-store"
    assert not comparison.json()["current"]["t_test"]["baseline_changed"]
    assert client.get("/review/batches/missing", headers=headers).status_code == 404
    decision = {"payload_sha256": "b" * 64, "decision": "approve", "by": "actual-reviewer"}
    assert client.post("/review/batches/private_batch/decision", headers=headers, json=decision).status_code == 409
    decision["payload_sha256"] = checksum
    response = client.post("/review/batches/private_batch/decision", headers=headers, json=decision)
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    assert pub.inspect(con, "private_batch")["reviewed_by"] == "actual-reviewer"
    assert ds.current_meaning(con, "t_test").definition == "a documented current meaning"
    assert client.post("/review/batches/private_batch/decision", headers=headers, json=decision).status_code == 409
    assert con.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 0


def test_comparison_reports_baseline_change_and_reject_does_not_publish(review_api):
    con, client, headers, checksum = review_api
    t = ds.get_term(con, "t_test")
    t.risk_human = "avoid"
    ds.upsert_term(con, t, human=True)
    result = client.get("/review/batches/private_batch", headers=headers).json()
    assert result["current"]["t_test"]["baseline_changed"]
    response = client.post("/review/batches/private_batch/decision", headers=headers,
                           json={"payload_sha256": checksum, "decision": "reject", "by": "reviewer"})
    assert response.status_code == 200 and response.json()["status"] == "rejected"
