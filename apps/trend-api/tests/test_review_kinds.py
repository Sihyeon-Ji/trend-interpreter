"""검수 큐의 제안 종류(Plan 12 §3) — 새 말·고칠 안·위키끼리 다름·사전에서 뺄지. 제안이 올라와 있는 동안 항목은 공개된 그대로이고,
사람의 결정으로만 새 판이 생기거나 빠진다. 네트워크·모델 없이."""
from datetime import datetime, timezone

from trend_agents.pipeline import views
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import db as dbmod
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

NOW = datetime.now(timezone.utc)
KYM_URL = "https://knowyourmeme.com/memes/aura-farming"


def draft(definition="멋있어 보이려고 일부러 폼을 잡는 행동", origin="게임 팬덤의 농담", nuance="놀리는 말로도 쓴다"):
    return MeaningDraft(definition=definition, origin=origin, nuance=nuance, generations=["10s"], regions=["US"], self_confidence=0.8)


def listed(con, tid, name, lang="en", verification="verified_auto", **kw):
    """확인된(공개) 항목 하나."""
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", first_seen=NOW, last_seen=NOW))
    return ds.add_meaning(con, tid, draft(**kw), verification, [])


def fix_of(m, **update):
    """지금 뜻 위에 몇 칸만 고친 안."""
    return MeaningDraft.model_validate(m.model_dump(include=set(MeaningDraft.model_fields))).model_copy(update=update)


def token(con, tid):
    """화면이 본 제안의 표(ReviewItem.token)."""
    return ds.pending_review(con, tid)["token"]


def client(monkeypatch, con):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setattr(api.dashboard, "refresh_card", lambda *a, **k: None)
    monkeypatch.setattr(api.risk, "apply", lambda *a, **k: None)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "tok")
    return TestClient(api.app), {"x-frontend-token": "tok"}


def test_existing_review_rows_become_new_after_the_migration():
    con = db.connect(":memory:")
    for sql in ("ALTER TABLE review_queue DROP COLUMN kind", "ALTER TABLE review_queue DROP COLUMN docs_json", "DROP TABLE crosscheck_log"):
        con.execute(sql)
    con.execute("INSERT INTO review_queue VALUES (?,?,?,?,?,NULL,NULL,NULL)", ("t1", draft().model_dump_json(), '["출처가 한 곳뿐"]', 1, NOW.isoformat()))
    con.commit()
    con.raw.execute((dbmod.MIGRATIONS_DIR / "007_review_kinds.sql").read_text(encoding="utf-8"))
    con.commit()
    assert ds.pending_review(con, "t1")["kind"] == "new"
    assert con.execute("SELECT kind FROM review_queue WHERE term_id='t1'").fetchone()[0] == "new"
    assert con.execute("SELECT COUNT(*) FROM crosscheck_log").fetchone()[0] == 0
    con.close()


def test_correction_keeps_the_entry_public_until_a_person_publishes_it_as_a_new_version(monkeypatch):
    con = db.connect(":memory:")
    m1 = listed(con, "t_af", "aura farming", verification="verified_human")      # 사람이 승인한 뜻도 제안은 큐로만
    fix = fix_of(m1, origin="'aura' 속어에서 나와 2024년에 퍼졌다")
    ds.queue_review(con, "t_af", fix, ["문서 대조: 고칠 것", "유래가 문서와 다름", f"참고 문서: {KYM_URL}"], 3, kind="correction",
                    docs=[{"wiki": "Know Your Meme", "url": KYM_URL, "summary": "", "proposal": None}])
    # 제안이 올라와 있는 동안: 지금 뜻 그대로 공개
    assert ds.get_term(con, "t_af").status == "verified" and ds.current_meaning(con, "t_af").meaning_id == m1.meaning_id
    assert [r.term.term_id for r in views.term_records(con)] == ["t_af"] and views.term_record(con, ds.get_term(con, "t_af")).gate_reasons is None
    [item] = views.review_items(con)
    assert item.kind == "correction" and item.proposed is None and item.meaning_id == m1.meaning_id
    assert item.current.meaning_id == m1.meaning_id and item.draft.origin == fix.origin and item.draft.definition == m1.definition
    assert item.reasons[0] == "문서 대조: 고칠 것" and f"참고 문서: {KYM_URL}" in item.reasons and item.docs[0].url == KYM_URL

    c, h = client(monkeypatch, con)
    body = {"decision": "approve", "by": "kim", "meaning_id": m1.meaning_id, "token": token(con, "t_af")}
    assert c.post("/review/t_af", json=body, headers=h).status_code == 409                   # 종류를 적지 않으면(예전 화면) 새 말로 보고 막는다
    assert c.post("/review/t_af", json={**body, "kind": "correction", "meaning_id": "m_old"}, headers=h).status_code == 409
    assert c.post("/review/t_af", json={**body, "kind": "correction", "token": "0" * 16}, headers=h).status_code == 409   # 보지 않은 제안
    for missing in ("meaning_id", "token"):                                                  # 문서 대조의 제안은 둘 다 적어야 한다
        assert c.post("/review/t_af", json={k: v for k, v in {**body, "kind": "correction"}.items() if k != missing}, headers=h).status_code == 400
    r = c.post("/review/t_af", json={**body, "kind": "correction"}, headers=h)
    assert r.status_code == 200 and r.json()["version"] == 2
    old, new = ds.list_meanings(con, "t_af")
    assert old.valid_to is not None and new.valid_to is None                                 # 이전 판은 닫히고 지워지지 않는다
    assert new.verification == "verified_human" and new.created_by == "kim" and new.origin == fix.origin and new.citations == [KYM_URL]
    assert (new.definition, new.regions, new.generations) == (m1.definition, m1.regions, m1.generations)   # 유래만 고친 안도 새 판이 된다
    assert ds.pending_review(con, "t_af") is None and ds.get_term(con, "t_af").status == "verified"
    assert c.post("/review/t_af", json={**body, "kind": "correction", "meaning_id": new.meaning_id}, headers=h).status_code == 409  # 이미 결정됨
    assert [h["decision"] for h in ds.review_history(con, "t_af")] == ["approve"]              # 결정은 기록에 남는다


def test_rejecting_a_correction_only_closes_the_proposal(monkeypatch):
    con = db.connect(":memory:")
    m1 = listed(con, "t_af", "aura farming")
    ds.queue_review(con, "t_af", fix_of(m1, definition="다른 뜻"), ["문서 대조: 고칠 것"], 1, kind="correction")
    c, h = client(monkeypatch, con)
    r = c.post("/review/t_af", json={"decision": "reject", "by": "kim", "meaning_id": m1.meaning_id, "kind": "correction", "token": token(con, "t_af")},
               headers=h)
    assert r.status_code == 200
    assert [m.meaning_id for m in ds.list_meanings(con, "t_af")] == [m1.meaning_id] and ds.current_meaning(con, "t_af").verification == "verified_auto"
    assert ds.pending_review(con, "t_af") is None and ds.get_term(con, "t_af").status == "verified"


def test_conflict_needs_a_choice_and_the_chosen_description_becomes_the_new_version(monkeypatch):
    con = db.connect(":memory:")
    m1 = listed(con, "t_sk", "skibidi", definition="뜻 없이 붙이는 감탄·수식어")
    wiki = "https://en.wikipedia.org/wiki/Skibidi_Toilet"
    docs = [{"wiki": "Know Your Meme", "url": "https://knowyourmeme.com/memes/skibidi-toilet", "summary": "뜻 없이 붙이는 말", "proposal": None},
            {"wiki": "위키백과(en)", "url": wiki, "summary": "'이상하다' 는 뜻으로 쓴다",
             "proposal": fix_of(m1, definition="주로 '이상하다·별로다' 라는 뜻으로 붙이는 말").model_dump()}]
    ds.queue_review(con, "t_sk", None, ["문서 대조: 위키끼리 다름", "문서마다 뜻이 다름", *[f"참고 문서: {d['url']}" for d in docs]], 2, kind="conflict", docs=docs)
    [item] = views.review_items(con)
    assert item.kind == "conflict" and item.current.meaning_id == m1.meaning_id and item.draft is None
    assert [d.wiki for d in item.docs] == ["Know Your Meme", "위키백과(en)"] and item.docs[0].proposal is None
    assert item.docs[1].proposal.definition.startswith("주로")

    c, h = client(monkeypatch, con)
    body = {"decision": "approve", "by": "lee", "meaning_id": m1.meaning_id, "kind": "conflict", "token": token(con, "t_sk")}
    for bad in (None, docs[0]["url"], "https://en.wikipedia.org/wiki/Other", "all"):          # 고르지 않았거나, 고칠 안이 없는 문서, 없는 문서
        assert c.post("/review/t_sk", json={**body, "choice": bad}, headers=h).status_code == 400, bad
    assert c.post("/review/t_sk", json={**body, "choice": 1}, headers=h).status_code == 422    # 번호로는 고르지 않는다(주소로)
    assert len(ds.list_meanings(con, "t_sk")) == 1 and ds.pending_review(con, "t_sk")
    r = c.post("/review/t_sk", json={**body, "choice": "https://en.wikipedia.org/wiki/Skibidi%5FToilet"}, headers=h)   # 같은 문서의 다른 꼴 주소
    assert r.status_code == 200
    new = ds.current_meaning(con, "t_sk")
    assert new.version == 2 and new.verification == "verified_human" and new.definition.startswith("주로") and new.citations == [wiki]

    ds.queue_review(con, "t_sk", None, ["문서 대조: 위키끼리 다름"], 2, kind="conflict", docs=docs)
    r = c.post("/review/t_sk", json={**body, "meaning_id": new.meaning_id, "choice": "keep", "token": token(con, "t_sk")}, headers=h)   # 지금 뜻 그대로
    assert r.status_code == 200 and ds.current_meaning(con, "t_sk").meaning_id == new.meaning_id and ds.pending_review(con, "t_sk") is None
    assert con.execute("SELECT decision FROM review_queue WHERE term_id='t_sk'").fetchone()[0] == "keep"


def test_retire_is_proposed_by_rules_but_only_a_person_retires(monkeypatch):
    con = db.connect(":memory:")
    m1 = listed(con, "t_cookie", "viral Crumbl Labubu cookie")
    ds.queue_review(con, "t_cookie", None, ["문서 대조: 밈이 아님", "문서가 쿠키 상품을 다룬다", "참고 문서: https://en.wikipedia.org/wiki/Crumbl"],
                    1, kind="retire", docs=[{"wiki": "위키백과(en)", "url": "https://en.wikipedia.org/wiki/Crumbl", "summary": "", "proposal": None}])
    assert ds.get_term(con, "t_cookie").status == "verified"                                  # 제안만으로는 빠지지 않는다
    [item] = views.review_items(con)
    assert item.kind == "retire" and item.current.meaning_id == m1.meaning_id and item.draft is None and item.proposed is None

    c, h = client(monkeypatch, con)
    body = {"by": "kim", "meaning_id": m1.meaning_id, "kind": "retire"}
    assert c.post("/review/t_cookie", json={**body, "decision": "reject", "token": token(con, "t_cookie")}, headers=h).status_code == 200   # 그대로 둔다
    assert ds.get_term(con, "t_cookie").status == "verified" and ds.current_meaning(con, "t_cookie").verification == "verified_auto"
    ds.queue_review(con, "t_cookie", None, ["문서 대조: 밈이 아님"], 1, kind="retire")
    assert c.post("/review/t_cookie", json={**body, "decision": "approve", "token": token(con, "t_cookie")}, headers=h).status_code == 200
    assert ds.get_term(con, "t_cookie").status == "retired" and ds.current_meaning(con, "t_cookie").verification == "rejected"
    assert views.term_records(con) == []
