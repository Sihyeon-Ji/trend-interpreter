"""Plan 12 검토(2026-09-29) — 검토자의 시험(probe 1~10)을 뒤집어 옮기고, 고친 것마다 되돌아가지 않게 본다. 네트워크·모델 없이."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from trend_agents.pipeline import crosscheck, views
from trend_agents.pipeline.crosscheck import AuditRecord
from trend_agents.schemas import CrosscheckJudgement, Evidence, MeaningDraft, MeaningFix, Term
from trend_agents.storage import db as dbmod
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

NOW = datetime.now(timezone.utc)
WIKI = "https://en.wikipedia.org/wiki/Aura_farming"
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def listed(con, tid, name, lang="en", verification="verified_auto"):
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", first_seen=NOW, last_seen=NOW))
    return ds.add_meaning(con, tid, MeaningDraft(definition="멋있어 보이려고 일부러 폼을 잡는 행동", origin="게임 팬덤의 농담", nuance="놀리는 말",
                                                 generations=["10s"], regions=["US"], self_confidence=0.8), verification, [])


def client(monkeypatch, con):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setattr(api.dashboard, "refresh_card", lambda *a, **k: None)
    monkeypatch.setattr(api.risk, "apply", lambda *a, **k: None)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "tok")
    return TestClient(api.app), {"x-frontend-token": "tok"}


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wiki_ev(url=WIKI, excerpt="Aura farming is acting cool on purpose."):
    return Evidence(evidence_id=ds.new_id("e", url), kind="wiki", url=url, title="Aura farming", source_domain="wikipedia.org",
                    observed_at=NOW, excerpt=excerpt)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """네트워크를 쓰지 않는다 — 가로채지 않은 요청은 바로 실패한다. TestClient 는 전송 계층을 따로 쓰므로 막지 않는다."""
    def blocked(*a, **k):
        raise AssertionError(f"시험에서 네트워크 호출: {a[:2]}")

    for name in ("get", "post", "request"):
        monkeypatch.setattr(httpx, name, blocked)


# ---------- 1. 사람이 결정한 제안을 되살리지 않고, 결정 기록을 지우지 않는다 ----------

def test_probe1_reimport_does_not_resurrect_a_rejected_proposal_and_keeps_the_decision(monkeypatch):
    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    recs = [AuditRecord.model_validate({"term_id": "t_af", "verdict": "fix", "problems": ["유래 다름"], "sources": [WIKI],
                                        "proposal": {"origin": "새 유래"}})]
    crosscheck.import_audit(con, recs, queue=True)
    c, h = client(monkeypatch, con)
    m = ds.current_meaning(con, "t_af")
    q = ds.pending_review(con, "t_af")
    assert c.post("/review/t_af", json={"decision": "reject", "by": "kim", "meaning_id": m.meaning_id, "kind": "correction", "token": q["token"]},
                  headers=h).status_code == 200
    rep = crosscheck.import_audit(con, recs, queue=True)                                        # 같은 파일을 다시
    row = con.execute("SELECT decision, decided_by, kind FROM review_queue WHERE term_id='t_af'").fetchone()
    assert rep["queued"] == [] and ("aura farming", "사람이 이미 결정한 같은 제안") in rep["skipped"]
    assert row == ("reject", "kim", "correction")                                               # 김의 결정이 그대로 남는다
    assert [(x["kind"], x["decision"], x["decided_by"]) for x in ds.review_history(con, "t_af")] == [("correction", "reject", "kim")]
    other = [AuditRecord.model_validate({**recs[0].model_dump(), "proposal": {"origin": "또 다른 유래"}})]
    assert crosscheck.import_audit(con, other, queue=True)["queued"]                           # 내용이 다른 제안은 올라간다
    assert [x["decision"] for x in ds.review_history(con, "t_af")] == ["reject"]               # 덮여도 결정 기록은 남는다


def test_rejected_proposal_is_not_brought_back_by_the_stage_recheck(monkeypatch):
    from trend_agents.pipeline import gemini

    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    ds.add_evidences(con, "t_af", [wiki_ev()])
    fix = CrosscheckJudgement(verdict="fix", reason="유래가 문서 1과 다름", proposal=MeaningFix(origin="'aura' 속어에서"))
    monkeypatch.setattr(gemini, "local_ok", lambda: True)
    monkeypatch.setattr(crosscheck, "gather", lambda term: ([], []))
    monkeypatch.setattr(crosscheck, "judge", lambda term, meaning, docs: (fix, "local:test"))
    assert crosscheck.run(con)["crosscheck"].detail["aura farming"] == "고칠 것 → queued"
    q = ds.pending_review(con, "t_af")
    assert ds.claim_review(con, "t_af", q["queued_at"], "reject", "kim")
    ds.add_evidences(con, "t_af", [wiki_ev("https://en.wikipedia.org/wiki/Aura_(slang)", "Aura farming comes from the aura slang.")])   # 문서가 바뀌었다
    assert [t.term_id for t in crosscheck.targets(con, 8, judging=True)] == ["t_af"]
    assert crosscheck.run(con)["crosscheck"].detail["aura farming"] == "고칠 것 → decided"    # 같은 고칠 안은 다시 올리지 않는다
    assert con.execute("SELECT decision, decided_by FROM review_queue WHERE term_id='t_af'").fetchone() == ("reject", "kim")


def test_decisions_already_in_the_queue_are_backfilled_into_the_history():
    con = db.connect(":memory:")
    con.execute("DROP TABLE review_history")                                                   # 마이그레이션 전의 모양
    con.execute("INSERT INTO review_queue VALUES (?,?,?,?,?,?,?,?,?,?)", ("t1", None, "[]", 1, "2026-09-01T00:00:00+00:00", "approve",
                                                                         "2026-09-02T00:00:00+00:00", "kim", "new", None))
    con.execute("INSERT INTO review_queue VALUES (?,?,?,?,?,?,?,?,?,?)", ("t2", None, "[]", 1, "2026-09-01T00:00:00+00:00", "auto_rejected",
                                                                         "2026-09-02T00:00:00+00:00", "gate", "new", None))
    con.commit()
    con.raw.execute((dbmod.MIGRATIONS_DIR / "008_review_history.sql").read_text(encoding="utf-8"))
    con.commit()
    assert [(x["decision"], x["decided_by"]) for x in ds.review_history(con, "t1")] == [("approve", "kim")]
    assert ds.review_history(con, "t2") == []                                                   # 게이트가 스스로 닫은 줄은 두지 않는다
    con.close()


# ---------- 2. 오래된 화면이 보지 않은 제안을 싣지 않는다 ----------

def test_probe2_stale_page_cannot_publish_a_proposal_the_reviewer_never_saw(monkeypatch):
    con = db.connect(":memory:")
    m1 = listed(con, "t_af", "aura farming")
    ds.queue_review(con, "t_af", crosscheck.merged(m1, {"origin": "유래 A"}), ["문서 대조: 고칠 것"], 1, kind="correction")
    seen = ds.pending_review(con, "t_af")["token"]                                              # 이의 화면은 고칠 안 A 를 본다
    stale = {"decision": "approve", "by": "lee", "meaning_id": m1.meaning_id, "kind": "correction", "token": seen}
    c, h = client(monkeypatch, con)
    assert c.post("/review/t_af", json={**stale, "decision": "reject", "by": "kim"}, headers=h).status_code == 200
    assert crosscheck.propose(con, ds.get_term(con, "t_af"), "fix", ["문서 대조: 고칠 것"],
                              draft=crosscheck.merged(m1, {"origin": "유래 B"})) == "queued"
    r = c.post("/review/t_af", json=stale, headers=h)
    assert r.status_code == 409 and ds.current_meaning(con, "t_af").origin == "게임 팬덤의 농담"      # 지금 뜻 그대로
    assert c.post("/review/t_af", json={k: v for k, v in stale.items() if k != "token"}, headers=h).status_code == 400
    assert ds.pending_review(con, "t_af")["draft"].origin == "유래 B"                             # 새 제안은 그대로 기다린다


def test_a_proposal_is_claimed_once(monkeypatch):
    con = db.connect(":memory:")
    m1 = listed(con, "t_af", "aura farming")
    ds.queue_review(con, "t_af", crosscheck.merged(m1, {"origin": "유래 A"}), ["문서 대조: 고칠 것"], 1, kind="correction")
    q = ds.pending_review(con, "t_af")
    assert ds.claim_review(con, "t_af", q["queued_at"], "approve", "kim") is True
    assert ds.claim_review(con, "t_af", q["queued_at"], "approve", "lee") is False                # 두 번째 결정은 409 로 막힌다
    assert con.execute("SELECT decided_by FROM review_queue WHERE term_id='t_af'").fetchone() == ("kim",)


def test_conflict_choice_is_the_document_address_so_hidden_documents_do_not_shift_it(monkeypatch):
    con = db.connect(":memory:")
    m1 = listed(con, "t_sk", "skibidi")
    wiki = "https://en.wikipedia.org/wiki/Skibidi_Toilet"
    docs = [{"wiki": "broken"},                                                                  # 모양이 틀린 문서 — 화면에서 빠진다
            {"wiki": "나무위키", "url": "https://namu.wiki/w/Skibidi%20Toilet", "summary": "뜻 없이", "proposal": None},
            {"wiki": "위키백과", "url": wiki, "summary": "이상하다", "proposal": crosscheck.merged(m1, {"definition": "주로 '이상하다' 는 뜻"}).model_dump()}]
    ds.queue_review(con, "t_sk", None, ["문서 대조: 위키끼리 다름"], 2, kind="conflict", docs=docs)
    [item] = views.review_items(con)
    assert [d.url for d in item.docs] == ["https://namu.wiki/w/Skibidi%20Toilet", wiki]
    c, h = client(monkeypatch, con)
    r = c.post("/review/t_sk", json={"decision": "approve", "by": "kim", "meaning_id": m1.meaning_id, "kind": "conflict", "token": item.token,
                                      "choice": item.docs[1].url}, headers=h)
    assert r.status_code == 200 and ds.current_meaning(con, "t_sk").definition == "주로 '이상하다' 는 뜻"


# ---------- 3. 점검 스크립트가 사람이 보고 있는 제안을 지우지 않는다 ----------

def test_probe3_audit_apply_keeps_a_pending_correction_and_does_not_demote(monkeypatch, capsys):
    con = db.connect(":memory:")
    m1 = listed(con, "t_af", "aura farming")                       # 참고 문서 근거가 없는 예전 항목
    ds.queue_review(con, "t_af", crosscheck.merged(m1, {"origin": "유래 A"}), ["문서 대조: 고칠 것"], 1, kind="correction")
    script = load("audit_dictionary")
    monkeypatch.setattr(script.db, "connect", lambda *a, **k: con)
    monkeypatch.setattr("sys.argv", ["audit_dictionary.py", "--apply"])
    script.main()
    q = ds.pending_review(con, "t_af")
    assert q["kind"] == "correction" and q["draft"].origin == "유래 A" and ds.get_term(con, "t_af").status == "verified"
    assert ds.current_meaning(con, "t_af").verification == "verified_auto"
    assert "검수 중이라 내리지 않은 것 1개" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["audit_dictionary.py", "--downgrade", "aura farming"])
    script.main()
    assert ds.pending_review(con, "t_af")["kind"] == "correction" and ds.get_term(con, "t_af").status == "verified"
    assert "강등 건너뜀(문서 대조 제안 검수 중): aura farming" in capsys.readouterr().out


def test_a_new_word_row_never_replaces_another_pending_kind():
    con = db.connect(":memory:")
    m1 = listed(con, "t_af", "aura farming")
    ds.queue_review(con, "t_af", crosscheck.merged(m1, {"origin": "유래 A"}), ["문서 대조: 고칠 것"], 1, kind="correction")
    assert ds.queue_review(con, "t_af", MeaningDraft.model_validate(m1.model_dump(include=set(MeaningDraft.model_fields))), ["조사"], 1) is False
    assert ds.pending_review(con, "t_af")["kind"] == "correction"
    ds.decide_review(con, "t_af", "reject", "kim")
    assert ds.queue_review(con, "t_af", None, ["조사"], 1) is True                                 # 결정된 줄은 기록에 남기고 덮는다


# ---------- 4. 그라운딩 조사도 Know Your Meme 을 끈 설정을 따른다 ----------

def test_probe5_grounded_web_evidence_does_not_fetch_kym_with_the_flag_off(monkeypatch):
    from trend_agents import config
    from trend_agents.pipeline import research

    assert config.KNOWYOURMEME_ENABLED is False
    seen = []

    def fake_send(self, request, **k):
        seen.append(str(request.url))
        if "grounding-api-redirect" in str(request.url):                                         # 구글의 넘겨주기 → Know Your Meme
            return httpx.Response(302, request=request, headers={"location": "https://knowyourmeme.com/memes/aura-farming"})
        return httpx.Response(200, request=request, text="<title>Aura Farming | Know Your Meme</title><p>Aura farming is a body sentence copied from the page.</p>")

    monkeypatch.setattr(httpx.Client, "send", fake_send)
    grounding = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"
    evs = research.web_evidence("aura farming", ["https://knowyourmeme.com/memes/aura-farming", grounding])
    assert evs == [] and seen == [grounding]                                                     # Know Your Meme 문서는 열지 않는다

    from trend_agents.collectors import knowyourmeme

    monkeypatch.setattr(config, "KNOWYOURMEME_ENABLED", True)
    asked = []
    monkeypatch.setattr(knowyourmeme, "from_url", lambda url, term, aliases=(): asked.append(url) or [
        Evidence(evidence_id="e_k", kind="wiki", url=url, title="Know Your Meme: Aura Farming", source_domain="knowyourmeme.com", observed_at=NOW)])
    seen.clear()
    [e] = research.web_evidence("aura farming", [grounding])
    assert asked == ["https://knowyourmeme.com/memes/aura-farming"] and seen == [grounding]    # 켜져 있으면 수집기 규칙대로(주소·제목만)
    assert e.excerpt == "" and "body sentence" not in e.title


# ---------- 5. 전수조사 파일은 참고 문서 주소만 받는다 ----------

def test_probe6_import_drops_community_urls_instead_of_taking_them_as_reference_documents(monkeypatch):
    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    reddit = "https://www.reddit.com/r/memes/comments/abc/aura_farming"
    rec = AuditRecord.model_validate({"term_id": "t_af", "verdict": "fix", "problems": ["x"], "sources": [reddit], "proposal": {"origin": "새 유래"}})
    rep = crosscheck.import_audit(con, [rec], queue=True)
    assert rep["queued"] == [] and ("aura farming", reddit) in rep["dropped_urls"] and ("aura farming", "참고 문서 주소가 없음") in rep["skipped"]
    assert ds.pending_review(con, "t_af") is None
    rec = AuditRecord.model_validate({"term_id": "t_af", "verdict": "fix", "problems": ["x"], "sources": [reddit, "https://en.wikipedia.org/wiki/Aura farming"],
                                      "proposal": {"origin": "새 유래"}})
    crosscheck.import_audit(con, [rec], queue=True)
    [item] = views.review_items(con)
    assert f"참고 문서: {WIKI}" in item.reasons and not any("reddit" in r for r in item.reasons) and [d.url for d in item.docs] == [WIKI]
    c, h = client(monkeypatch, con)
    m = ds.current_meaning(con, "t_af")
    assert c.post("/review/t_af", json={"decision": "approve", "by": "kim", "meaning_id": m.meaning_id, "kind": "correction", "token": item.token},
                  headers=h).status_code == 200
    assert ds.current_meaning(con, "t_af").citations == [WIKI]                                  # 공개되는 출처도 참고 문서뿐


def test_probe7_fix_without_any_source_is_not_queued(monkeypatch):
    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    rec = AuditRecord.model_validate({"term_id": "t_af", "verdict": "fix", "proposal": {"definition": "모델이 지어낸 새 뜻입니다"}})
    rep = crosscheck.import_audit(con, [rec], queue=True)
    assert rep["queued"] == [] and ds.pending_review(con, "t_af") is None and ("aura farming", "참고 문서 주소가 없음") in rep["skipped"]


def test_import_rejects_unknown_keys_and_stores_one_copy_of_a_document(monkeypatch):
    from trend_agents.collectors import namuwiki

    with pytest.raises(ValueError):
        AuditRecord.model_validate({"term_id": "t", "verdict": "fix", "sourcse": ["https://namu.wiki/w/x"]})
    with pytest.raises(ValueError):
        AuditRecord.model_validate({"term_id": "t", "verdict": "fix", "proposal": {"definitoin": "오타"}})
    con = db.connect(":memory:")
    ds.upsert_term(con, Term(term_id="t_lv", canonical="럭키비키", lang="ko", status="verified", first_seen=NOW, last_seen=NOW))
    sentence = "럭키비키는 장원영의 말에서 나온 밈이다."
    monkeypatch.setattr(namuwiki, "page_text", lambda title: f"… {sentence} …" if title == "럭키비키" else "")
    raw = "https://namu.wiki/w/럭키비키"
    encoded = "https://namu.wiki/w/%EB%9F%AD%ED%82%A4%EB%B9%84%ED%82%A4"
    recs = [AuditRecord.model_validate({"term_id": "t_lv", "verdict": "keep", "excerpt": {"url": u, "title": "럭키비키", "text": sentence}}) for u in (raw, encoded)]
    rep = crosscheck.import_audit(con, recs, store_evidence=True)
    assert [u for _, u in rep["evidence"]] == [encoded] and [e.url for e in ds.list_evidences(con, "t_lv")] == [encoded]


# ---------- 6. 닿지 못한 것은 '문서 없음' 이 아니다 ----------

def test_probe4_wikipedia_429_is_unreachable_not_no_doc(monkeypatch):
    from trend_agents.collectors import wikipedia_search

    calls = []

    def fake_get(url, params=None, headers=None, timeout=None, **k):
        calls.append(url)
        return httpx.Response(429, request=httpx.Request("GET", url))

    monkeypatch.setattr(wikipedia_search.httpx, "get", fake_get)
    monkeypatch.setattr(wikipedia_search.time, "sleep", lambda s: None)
    con = db.connect(":memory:")
    listed(con, "t_oshi", "推し活", lang="ja")
    res = crosscheck.check(con, ds.get_term(con, "t_oshi"), judging=False)
    assert calls and res["verdict"] == crosscheck.UNREACHABLE and res["unreachable"] == ["wiki:ja"]
    assert ds.last_crosschecks(con)["t_oshi"]["verdict"] == crosscheck.UNREACHABLE              # '문서 없음'(규칙) 줄이 아니다
    assert [t.term_id for t in crosscheck.targets(con, 8)] == ["t_oshi"]                        # 다음 실행에 다시 본다


def test_probe8_namu_failure_is_not_cached_as_not_found(monkeypatch, tmp_path):
    from trend_agents.collectors import namuwiki

    monkeypatch.setattr(namuwiki, "CACHE", tmp_path / "namu.json")
    monkeypatch.setattr(namuwiki, "_get", lambda path, timeout=15.0: httpx.Response(429, request=httpx.Request("GET", "https://namu.wiki" + path)))
    assert namuwiki.lookup("럭키비키") is None
    calls = []
    monkeypatch.setattr(namuwiki, "_get", lambda path, timeout=15.0: calls.append(path) or httpx.Response(404, request=httpx.Request("GET", "https://namu.wiki" + path)))
    assert namuwiki.lookup("럭키비키") == [] and len(calls) == 1                                   # 캐시에서 '없음' 을 꺼내지 않고 다시 물었다
    assert namuwiki.lookup("럭키비키") == [] and len(calls) == 1                                   # 없다고 확인된 것은 하루 캐시


def test_collect_script_lists_unreachable_terms_apart_from_the_no_doc_list(monkeypatch, capsys):
    con = db.connect(":memory:")
    listed(con, "t_a", "aura farming")
    listed(con, "t_b", "라을라", lang="ko")
    monkeypatch.setattr(crosscheck, "gather", lambda term: ([], ["wiki:en"]) if term.term_id == "t_a" else ([], []))
    script = load("crosscheck_dictionary")
    monkeypatch.setattr(script.db, "connect", lambda *a, **k: con)
    monkeypatch.setattr("sys.argv", ["crosscheck_dictionary.py", "collect"])
    script.main()
    out = capsys.readouterr().out
    unreachable, no_doc = out.split("닿지 못함")[1].split("문서 없음 —")
    assert "aura farming: wiki:en" in unreachable and "라을라" in no_doc and "aura farming" not in no_doc


# ---------- 7~10 ----------

def test_probe9_namu_recheck_slots_are_not_spent_on_terms_under_review(monkeypatch):
    from trend_agents.collectors import namuwiki
    from trend_agents.pipeline import gemini, namu, research

    con = db.connect(":memory:")
    names = [f"가{i}밈" for i in range(7)]
    for i, n in enumerate(names):
        ds.upsert_term(con, Term(term_id=f"t{i}", canonical=n, lang="ko", status="verified", first_seen=NOW, last_seen=NOW))
        m = ds.add_meaning(con, f"t{i}", MeaningDraft(definition="긍정적으로 받아들이는 태도의 밈", origin="아이돌 발언", nuance="밝게",
                                                      generations=["10s"], regions=["KR"], self_confidence=0.8), "verified_auto", [])
        con.execute("INSERT INTO research_log VALUES (?,?,?,?,?,?,?)", (f"t{i}", (NOW - timedelta(days=3)).isoformat(), "x", "", "[]", "verified_auto", "[]"))
        con.commit()
        if i < 6:   # 여섯 개에 고칠 안이 올라와 있다
            ds.queue_review(con, f"t{i}", crosscheck.merged(m, {"origin": "새 유래"}), ["문서 대조: 고칠 것"], 1, kind="correction")
    edited = NOW - timedelta(days=1)
    monkeypatch.setattr(namuwiki, "ranking", lambda: [])
    monkeypatch.setattr(namuwiki, "category", lambda name="유행어": [])
    monkeypatch.setattr(namuwiki, "lookup", lambda name: [Evidence(evidence_id="e_" + name, kind="wiki", url=f"https://namu.wiki/w/{name}", title=f"나무위키: {name}",
                                                                    source_domain="namu.wiki", observed_at=edited, excerpt=f"{name}는 유행어다")])
    monkeypatch.setattr(gemini, "local_ok", lambda: True)
    called = []
    monkeypatch.setattr(research, "research_one", lambda con, t: (called.append(t.canonical), ("unverified", []))[1])
    namu.run(con)
    assert called == ["가6밈"]                                                                  # 다시 조사할 수 있는 말이 칸을 받는다


def test_title_only_documents_are_not_sent_to_the_model(monkeypatch):
    from trend_agents.pipeline import gemini

    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    kym = Evidence(evidence_id="e_k", kind="wiki", url="https://knowyourmeme.com/memes/aura-farming", title="Know Your Meme: Aura Farming",
                   source_domain="knowyourmeme.com", observed_at=NOW)
    monkeypatch.setattr(gemini, "local_ok", lambda: True)
    monkeypatch.setattr(crosscheck, "gather", lambda term: ([kym], []))
    monkeypatch.setattr(crosscheck, "judge", lambda *a, **k: (_ for _ in ()).throw(AssertionError("빈 글로 묻지 않는다")))
    assert crosscheck.run(con)["crosscheck"].detail["aura farming"] == crosscheck.LABEL[crosscheck.NO_TEXT]
    assert ds.last_crosschecks(con)["t_af"]["verdict"] == crosscheck.NO_TEXT
    assert crosscheck.targets(con, 8, judging=True) == []                                       # 글이 있는 문서가 생길 때까지 다시 묻지 않는다
    ds.add_evidences(con, "t_af", [wiki_ev()])
    assert [t.term_id for t in crosscheck.targets(con, 8, judging=True)] == ["t_af"]


def test_probe10_kym_follows_only_same_site_meme_redirects(monkeypatch):
    from trend_agents import config
    from trend_agents.collectors import knowyourmeme

    monkeypatch.setattr(config, "KNOWYOURMEME_ENABLED", True)
    monkeypatch.setattr(knowyourmeme.time, "sleep", lambda s: None)
    seen = []

    def fake_get(url, headers=None, timeout=None, follow_redirects=True, **k):
        seen.append((url, follow_redirects))
        req = httpx.Request("GET", url)
        if url.endswith("/memes/old-name"):
            return httpx.Response(301, request=req, headers={"location": "/memes/new-name"})
        if url.endswith("/memes/lost"):
            return httpx.Response(302, request=req, headers={"location": "/search?q=lost"})
        return httpx.Response(200, request=req, text="ok")

    monkeypatch.setattr(knowyourmeme.httpx, "get", fake_get)
    r = knowyourmeme._get("/memes/old-name")
    assert [u for u, _ in seen] == ["https://knowyourmeme.com/memes/old-name", "https://knowyourmeme.com/memes/new-name"]
    assert all(f is False for _, f in seen) and r.status_code == 200                           # 스스로 따라가지 않고 /memes/ 만 한 칸씩
    seen.clear()
    r = knowyourmeme._get("/memes/lost")
    assert [u for u, _ in seen] == ["https://knowyourmeme.com/memes/lost"] and r.status_code == 302   # /search 로는 가지 않는다


def test_review_stats_count_new_words_and_proposals_apart():
    con = db.connect(":memory:")
    m1 = listed(con, "t_af", "aura farming")
    listed(con, "t_sk", "skibidi")
    ds.upsert_term(con, Term(term_id="t_new", canonical="galau", lang="id", status="needs_review"))
    ds.queue_review(con, "t_new", None, ["출처가 한 곳뿐"], 1)
    ds.queue_review(con, "t_af", crosscheck.merged(m1, {"origin": "새 유래"}), ["문서 대조: 고칠 것"], 1, kind="correction")
    ds.queue_review(con, "t_sk", None, ["문서 대조: 밈이 아님"], 1, kind="retire")
    s = views.review_stats(con)
    assert (s.needs_review, s.proposals, s.verified_auto) == (1, 2, 2)
