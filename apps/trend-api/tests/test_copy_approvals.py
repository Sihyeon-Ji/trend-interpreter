"""문구 승인 기록(Plan 20 ⑤)과 모든 문구 다시 검사(④) — 권한(익명 거부·검수자만·읽기 전용은 보기만), 규칙으로만 정하는 묶음,
결정 때 다시 하는 규칙 검사, 30일 보존. 모델 없이 인메모리 DB 로."""
import json
import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from trend_agents import auth
from trend_agents.api import app as api
from trend_agents.pipeline import copycheck, dashboard, generate
from trend_agents.schemas import MeaningDraft, MemeFit, ProductBrief, Term
from trend_agents.storage import approvals
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

TOKEN = {"x-frontend-token": "tok"}


def _term(con, tid, name, risk="none", checked=True, region="KR", mentions=4):
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", lifecycle="steady", first_seen=now, last_seen=now,
                             risk_level=risk, risk_checked_at=now if checked else None))
    m = ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance="y", generations=["20s"], regions=[region],
                                              self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, tid, [("20s", region, now.isoformat(), 1.0)])
    ds.set_weekly_region(con, tid, {region: {dashboard._weeks()[-1]: mentions}})
    return m


@pytest.fixture
def con(monkeypatch):
    c = db.connect(":memory:")
    _term(c, "fresh", "럭키비키")
    _term(c, "warn", "조심말", risk="caution")
    _term(c, "bad", "자제말", risk="avoid")
    m = _term(c, "rude", "저속말")
    ds.set_fit(c, "rude", m.meaning_id, MemeFit(feelings=["funny"], uses=["reaction"], voice="crude", audience="online", kind="expr"), "test")
    _term(c, "touchy", "자살각", risk=None, checked=False)          # 리스크를 아직 보지 않았는데 민감한 소재
    m = _term(c, "wojak", "워잭")
    ds.set_fit(c, "wojak", m.meaning_id, MemeFit(feelings=["relatable"], uses=["format"], voice="playful", audience="online", kind="meme_name"), "test")
    dashboard.run(c)
    monkeypatch.setattr(api, "_con", c)
    monkeypatch.setattr(copycheck, "model_ready", lambda: False)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "tok")
    monkeypatch.setenv("ACCOUNTS", json.dumps([
        {"user": "rev", "hash": auth.hash_password("pw"), "reviewer": True},
        {"user": "mk", "hash": auth.hash_password("pw")},
        {"user": "mk2", "hash": auth.hash_password("pw")},
        {"user": "judge", "hash": auth.hash_password("pw"), "reviewer": True, "readonly": True},
    ]))
    yield c
    c.close()


def body(*texts, term="fresh", by="mk", fit="ok", decision=None, market="KR"):
    copies = [{"platform": "instagram" if i < 2 else "x", "text": t, "hashtags": ["여름"]} for i, t in enumerate(texts)]
    out = {"by": by, "market": market, "term_id": term, "product": "여름 한정 라떼", "copies": copies, "fit": fit, "fit_note": "뜻대로 썼어요", "fit_copy": 0}
    return {**out, "decision": decision} if decision else out


# ---------- ④ 모든 문구 다시 검사 ----------

def test_every_copy_is_checked_by_rules_and_the_ai_is_asked_once(con, monkeypatch):
    calls = []

    def fake(_con, prompt, schema, **kw):
        calls.append(prompt)
        return copycheck.FitResult(items=[copycheck.FitItem(term_id="fresh", fit="off", note="뜻이 달라요")]), "gemini-x"

    monkeypatch.setattr(copycheck, "model_ready", lambda: True)
    monkeypatch.setattr(copycheck, "structured", fake)
    c = TestClient(api.app)
    texts = ["오늘도 조심말", "럭키비키 라떼", "저속말 한 잔", "자살각 더위", "자제말 시발"]
    got = c.post("/copy-check/all", json={"texts": texts, "region": "KR", "opinion": 1}).json()
    codes = [[i["code"] for m in item["memes"] for i in m["issues"]] for item in got["items"]]
    assert codes == [["caution"], [], ["crude"], ["sensitive"], ["avoid"]]
    assert [item["unsafe"] for item in got["items"]] == [False, False, False, False, True]
    assert len(calls) == 1 and "럭키비키 라떼" in calls[0]                 # AI 의견은 시장마다 한 번 — 고른 문구 하나에만
    assert got["opinion"] == 1 and got["items"][1]["fit_source"] == "gemini" and got["items"][1]["memes"][0]["fit"] == "off"
    assert all(item["fit_source"] == "none" for i, item in enumerate(got["items"]) if i != 1)
    none = c.post("/copy-check/all", json={"texts": texts[:2], "region": "KR", "opinion": None}).json()
    assert none["opinion"] is None and len(calls) == 1                    # 의견을 청하지 않으면 모델을 부르지 않는다


def test_copy_check_all_input_limits(con):
    c = TestClient(api.app)
    assert c.post("/copy-check/all", json={"texts": ["럭키비키"], "region": "US"}).status_code == 400
    assert c.post("/copy-check/all", json={"texts": ["럭키비키", "  "], "region": "KR"}).status_code == 400
    assert c.post("/copy-check/all", json={"texts": ["a"] * 7, "region": "KR"}).status_code == 422
    assert c.post("/copy-check/all", json={"texts": ["가" * 1000 + " #해시태그"], "region": "KR"}).status_code == 200   # 본문 1000자에 해시태그
    assert c.post("/copy-check/all", json={"texts": ["가" * 2001], "region": "KR"}).status_code == 400
    full = json.dumps({"texts": ["가" * 2000] * 6, "region": "KR"}, ensure_ascii=False)    # 한도 안의 가장 큰 초안(36KB)은 받는다
    assert c.post("/copy-check/all", content=full.encode(), headers={"content-type": "application/json"}).status_code == 200
    big = json.dumps({"texts": ["가" * 3000] * 6, "region": "KR"}, ensure_ascii=False)
    assert c.post("/copy-check/all", content=big.encode(), headers={"content-type": "application/json"}).status_code == 413


# ---------- ⑤ 승인 기록: 권한 ----------

def test_only_signed_in_accounts_can_ask_and_only_reviewers_can_approve(con, monkeypatch):
    c = TestClient(api.app)
    assert c.post("/approvals", json=body("럭키비키 라떼")).status_code == 401                    # 웹 서버를 거치지 않은 요청
    assert c.post("/approvals", json=body("럭키비키 라떼", by="someone"), headers=TOKEN).status_code == 403   # 익명·없는 계정의 문구는 쌓지 않는다
    assert c.post("/approvals", json=body("럭키비키 라떼", by="judge"), headers=TOKEN).status_code == 403    # 읽기 전용은 보기만
    assert c.post("/approvals", json=body("럭키비키 라떼", decision="approve"), headers=TOKEN).status_code == 403   # 검수자가 아니면 승인 못 함
    assert con.execute("SELECT COUNT(*) FROM copy_approvals").fetchone()[0] == 0
    asked = c.post("/approvals", json=body("럭키비키 라떼"), headers=TOKEN)
    assert asked.status_code == 200 and asked.headers["cache-control"] == "private, no-store"
    assert asked.json()["status"] == "pending" and asked.json()["requested_by"] == "mk" and "copies" not in asked.json()   # 상태에는 본문이 없다
    monkeypatch.delenv("ACCOUNTS")
    assert c.post("/approvals", json=body("럭키비키 라떼"), headers=TOKEN).status_code == 403       # 계정이 설정되지 않으면 아무도 못 쌓는다


def test_a_reviewer_approves_on_the_draft_in_one_record(con):
    c = TestClient(api.app)
    got = c.post("/approvals", json=body("럭키비키 라떼", "오늘도 럭키비키", by="rev", decision="approve"), headers=TOKEN).json()
    assert got["status"] == "approved" and got["requested_by"] == got["decided_by"] == "rev" and got["decided_at"] == got["requested_at"]
    row = approvals.get(con, got["approval_id"])
    assert row["canonical"] == "럭키비키" and json.loads(row["copies_json"])[1]["text"] == "오늘도 럭키비키"


def test_groups_come_from_rules_and_the_server_checks_again(con):
    c = TestClient(api.app)
    ask = lambda *texts, **kw: c.post("/approvals", json=body(*texts, **kw), headers=TOKEN).json()   # noqa: E731
    clean = ask("럭키비키 라떼", "오늘도 럭키비키")
    assert (clean["group"], clean["reasons"]) == ("clean", [])
    assert ask("럭키비키 라떼", fit="off")["reasons"] == ["fit_off"]
    assert ask("럭키비키 라떼", fit=None)["reasons"] == ["fit_none"]                    # AI 의견을 받지 못했으면 읽어 본다
    flagged = ask("럭키비키 라떼", "조심말 한 잔", fit="unsure")
    assert (flagged["group"], flagged["reasons"]) == ("read", ["caution", "fit_unsure"])
    blocked = ask("럭키비키 라떼", "저속말 한 잔", "자제말이야")
    assert (blocked["group"], blocked["reasons"]) == ("blocked", ["avoid", "crude"])
    assert ask("럭키비키 시발")["group"] == "blocked"                                   # 욕설·선정 표현
    # 막힌 초안은 검수자도 바로 승인할 수 없다 — 이유를 돌려주고 아무것도 적지 않는다
    before = con.execute("SELECT COUNT(*) FROM copy_approvals").fetchone()[0]
    r = c.post("/approvals", json=body("자제말 라떼", by="rev", decision="approve"), headers=TOKEN)
    assert r.status_code == 409 and r.json() == {"detail": "blocked", "reasons": ["avoid"]}
    assert con.execute("SELECT COUNT(*) FROM copy_approvals").fetchone()[0] == before
    stored = approvals.get(con, blocked["approval_id"])
    assert [ch["issues"] for ch in json.loads(stored["checks_json"])] == [[], ["crude"], ["avoid"]]   # 문구마다의 검사 결과


def test_unknown_memes_and_bad_shapes_are_refused(con):
    c = TestClient(api.app)
    assert c.post("/approvals", json=body("라떼", term="nope"), headers=TOKEN).status_code == 400
    assert c.post("/approvals", json=body("럭키비키", market="US"), headers=TOKEN).status_code == 400
    assert c.post("/approvals", json={**body("럭키비키"), "group": "clean"}, headers=TOKEN).status_code == 422   # 묶음은 받지 않는다
    assert c.post("/approvals", json={**body("럭키비키"), "copies": []}, headers=TOKEN).status_code == 422


# ---------- 결정 ----------

def test_reviewers_decide_once_and_read_only_accounts_cannot(con):
    c = TestClient(api.app)
    req = c.post("/approvals", json=body("럭키비키 라떼"), headers=TOKEN).json()
    path = f"/review/approvals/{req['approval_id']}/decision"
    assert c.post(path, json={"decision": "approve", "by": "judge"}, headers=TOKEN).status_code == 403
    assert c.post(path, json={"decision": "approve", "by": "mk"}, headers=TOKEN).status_code == 403
    assert c.post(path, json={"decision": "approve", "by": "rev"}).status_code == 401
    done = c.post(path, json={"decision": "approve", "by": "rev", "memo": " 좋아요 "}, headers=TOKEN).json()
    assert done["status"] == "approved" and done["decided_by"] == "rev" and done["memo"] == "좋아요"
    again = c.post(path, json={"decision": "reject", "by": "rev"}, headers=TOKEN)
    assert again.status_code == 409 and again.json()["detail"] == "decided"
    assert c.post("/review/approvals/ap_missing/decision", json={"decision": "reject", "by": "rev"}, headers=TOKEN).status_code == 404


def test_the_requester_reads_only_the_state_of_their_own_request(con):
    c = TestClient(api.app)
    req = c.post("/approvals", json=body("럭키비키 라떼"), headers=TOKEN).json()
    path = f"/approvals/{req['approval_id']}"
    mine = c.get(path, params={"viewer": "mk"}, headers=TOKEN)
    assert mine.status_code == 200 and mine.json()["status"] == "pending" and "copies" not in mine.json()
    assert c.get(path, params={"viewer": "mk2"}, headers=TOKEN).status_code == 404       # 남의 요청은 없는 것과 같다
    assert c.get(path, params={"viewer": "rev"}, headers=TOKEN).status_code == 200
    assert c.get(path, params={"viewer": "mk"}).status_code == 401
    c.post(f"/review/approvals/{req['approval_id']}/decision", json={"decision": "reject", "by": "rev", "memo": "다시 써 주세요"}, headers=TOKEN)
    got = c.get(path, params={"viewer": "mk"}, headers=TOKEN).json()
    assert (got["status"], got["decided_by"], got["memo"]) == ("rejected", "rev", "다시 써 주세요")


def test_approval_checks_the_rules_again_with_todays_dictionary(con):
    """요청한 뒤 그 말이 사용 자제가 되면 승인하지 않는다 — 묶음을 막힘으로 고쳐 적고 이유를 돌려준다. 반려는 그대로 된다."""
    c = TestClient(api.app)
    req = c.post("/approvals", json=body("럭키비키 라떼", "오늘도 조심말"), headers=TOKEN).json()
    assert req["group"] == "read"
    ds.set_risk(con, "warn", "avoid", ["새로 확인된 비하 맥락"], datetime.now(timezone.utc))
    path = f"/review/approvals/{req['approval_id']}/decision"
    r = c.post(path, json={"decision": "approve", "by": "rev"}, headers=TOKEN)
    assert r.status_code == 409 and r.json() == {"detail": "blocked", "reasons": ["avoid"]}
    row = approvals.get(con, req["approval_id"])
    assert row["status"] == "pending" and row["grp"] == "blocked" and json.loads(row["checks_json"])[1]["issues"] == ["avoid"]
    assert c.post(path, json={"decision": "reject", "by": "rev"}, headers=TOKEN).json()["status"] == "rejected"


# ---------- 관리 화면 목록 ----------

def test_the_queue_is_for_reviewers_and_read_only_accounts(con):
    c = TestClient(api.app)
    first = c.post("/approvals", json=body("럭키비키 라떼"), headers=TOKEN).json()
    second = c.post("/approvals", json=body("조심말 라떼"), headers=TOKEN).json()
    c.post(f"/review/approvals/{first['approval_id']}/decision", json={"decision": "approve", "by": "rev"}, headers=TOKEN)
    assert c.get("/review/approvals", params={"viewer": "mk"}, headers=TOKEN).status_code == 403     # 본문이 있어 검수자만
    assert c.get("/review/approvals", params={"viewer": "rev"}).status_code == 401
    got = c.get("/review/approvals", params={"viewer": "judge"}, headers=TOKEN)                      # 읽기 전용 계정은 볼 수 있다
    assert got.status_code == 200 and got.headers["cache-control"] == "private, no-store"
    data = got.json()
    assert [p["approval_id"] for p in data["pending"]] == [second["approval_id"]]
    assert [h["approval_id"] for h in data["history"]] == [first["approval_id"]]
    item = data["pending"][0]
    assert item["product"] == "여름 한정 라떼" and item["copies"][0] == {"platform": "instagram", "text": "조심말 라떼", "hashtags": ["여름"], "issues": ["caution"]}
    assert item["group"] == "read" and item["fit"] == "ok" and item["fit_note"] == "뜻대로 썼어요" and item["image_meme"] is False


def test_image_memes_carry_a_rights_note(con):
    c = TestClient(api.app)
    got = c.post("/approvals", json=body("그 기분 아시죠", term="wojak"), headers=TOKEN).json()
    assert got["image_meme"] is True
    brief = ProductBrief(product="라떼", category="food_drink", feelings=["joy"])
    assert generate.run(con, ["wojak"], brief, "KR", "friendly").image_memes == ["wojak"]   # 결과에도 — 화면이 권리 안내를 붙인다
    assert generate.run(con, ["fresh"], brief, "KR", "friendly").image_memes == []


# ---------- 보존 기간·기록 ----------

def test_copy_text_is_cleared_after_thirty_days_and_never_logged(con, caplog):
    caplog.set_level(logging.DEBUG)
    c = TestClient(api.app)
    old = c.post("/approvals", json=body("럭키비키 비밀 신제품"), headers=TOKEN).json()
    new = c.post("/approvals", json=body("럭키비키 새 문구"), headers=TOKEN).json()
    con.execute("UPDATE copy_approvals SET requested_at=? WHERE approval_id=?",
                ((datetime.now(timezone.utc) - timedelta(days=31)).isoformat(), old["approval_id"]))
    con.commit()
    data = c.get("/review/approvals", params={"viewer": "rev"}, headers=TOKEN).json()   # 목록을 읽을 때 지운다
    gone = next(p for p in data["pending"] if p["approval_id"] == old["approval_id"])
    assert gone["expired"] is True and gone["product"] is None and gone["fit_note"] is None
    assert gone["copies"] == [{"platform": "instagram", "text": None, "hashtags": [], "issues": []}]   # 검사 결과 코드는 남는다
    assert next(p for p in data["pending"] if p["approval_id"] == new["approval_id"])["copies"][0]["text"] == "럭키비키 새 문구"
    r = c.post(f"/review/approvals/{old['approval_id']}/decision", json={"decision": "approve", "by": "rev"}, headers=TOKEN)
    assert r.status_code == 409 and r.json()["detail"] == "expired"                    # 다시 검사할 본문이 없으면 승인하지 않는다
    assert c.post(f"/review/approvals/{old['approval_id']}/decision", json={"decision": "reject", "by": "rev"}, headers=TOKEN).status_code == 200
    assert approvals.prune(con) == 0                                                   # 한 번만 지운다
    assert "비밀 신제품" not in caplog.text and "새 문구" not in caplog.text and "라떼" not in caplog.text


def test_a_stored_blocked_request_is_never_approved_without_a_new_check(con):
    """결정 함수를 바로 부르는 쪽(스크립트 등)이 다시 검사하지 않으면 적어 둔 묶음대로 막는다."""
    row = approvals.create(con, market="KR", term_id="bad", canonical="자제말", lang="ko", product="", copies=[
        {"platform": "x", "text": "자제말", "hashtags": []}], issues=[["avoid"]], fit="ok", fit_copy=0, fit_note=None, image_meme=False,
        by="mk", approve=False)
    with pytest.raises(approvals.ApprovalError) as e:
        approvals.decide(con, row["approval_id"], True, "rev")
    assert e.value.code == "blocked" and e.value.reasons == ["avoid"]
    assert approvals.decide(con, row["approval_id"], False, "rev")["status"] == "rejected"


def test_groups_without_the_api():
    assert approvals.group([[], ["fading"]], "ok") == ("read", ["fading"])
    assert approvals.group([["no_script"], ["unsafe"]], "off") == ("blocked", ["unsafe", "no_script", "fit_off"])
    assert approvals.group([[]], "ok") == ("clean", [])
    assert approvals.copy_issues(["fading", "avoid", "fading"], True) == ["avoid", "unsafe", "fading"]
