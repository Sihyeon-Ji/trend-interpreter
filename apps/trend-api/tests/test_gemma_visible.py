"""배포본에서 Gemma 가 한 일을 보이기(Plan 14 0단계): 사전 항목의 근거 문장별 분류, 관리 화면 모델 기록(단계별 결과 수·호출 수·시간)."""
from datetime import datetime, timedelta, timezone

from trend_agents.pipeline import views
from trend_agents.schemas import Evidence, MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _setup():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="찰지다", lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.add_meaning(con, "t1", MeaningDraft(definition="맛깔나고 착 붙는다", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                           self_confidence=0.9), "verified_auto", [])

    def ev(eid, kind, domain, text, ago):
        return Evidence(evidence_id=eid, kind=kind, url=f"https://{domain}/{eid}", title=text, source_domain=domain,
                        observed_at=now - timedelta(days=ago), excerpt=text)

    ds.add_evidences(con, "t1", [
        ev("n1", "news", "news.example.com", "발음이 찰지다는 평이 이어졌다", 1),
        ev("n2", "news", "daily.example.com", "찰지다 못해 쫀득한 연기", 2),
        ev("s1", "short", "youtube.com", "오늘 떡볶이 찰지다", 3),
        ev("c1", "community", "dcinside.com", "이 짤 진짜 찰지다 ㅋㅋ", 4),
        ev("o1", "news", "news.example.com", "찰지다 쌀 품종 개량 소식", 5),
    ])
    ds.set_evidence_labels(con, "t1", [("n1", "positive", "none"), ("n2", "negative", "mockery"), ("s1", "neutral", "none"),
                                       ("c1", "negative", "hate"), ("o1", "offtopic", "none")], "local:gemma4:12b")
    return con, now


def test_entry_lists_sentence_labels_but_not_community_posts():
    con, _ = _setup()
    b = views.risk_breakdown(con, ds.get_term(con, "t1"))
    assert b is not None
    shown = {s.evidence_id: s for s in b.sentences}
    assert set(shown) == {"n1", "n2", "s1", "o1"}                      # 커뮤니티 글은 문장 없이 건수만(ADR 0003)
    assert b.community == 1
    assert (b.counted, b.offtopic, b.risky, b.negative) == (4, 1, 2, 2)  # 판정은 커뮤니티 글까지 센다 — risk.judge 와 같은 문장
    assert shown["n2"].risk == "mockery" and shown["n2"].by == "gemma"
    assert shown["o1"].on_topic is False and shown["o1"].polarity is None
    assert all("dcinside" not in s.url for s in b.sentences)


def test_entry_without_labels_has_no_breakdown():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t2", canonical="없음", lang="ko", status="verified", first_seen=now, last_seen=now))
    assert views.risk_breakdown(con, ds.get_term(con, "t2")) is None


def test_about_gemma_counts_records_by_model_for_verified_terms_only():
    con, now = _setup()
    ds.upsert_term(con, Term(term_id="t9", canonical="검수중", lang="ko", status="needs_review", first_seen=now, last_seen=now))
    ds.set_evidence_labels(con, "t9", [("x", "positive", "none")], "local:gemma4:12b")      # 공개되지 않은 항목은 세지 않는다
    con.execute("INSERT INTO translations VALUES (?,?,?,?,?)", ("t1", "en", "{}", now.isoformat(), "local:gemma4:e4b"))
    con.execute("INSERT INTO research_log VALUES (?,?,?,?,?,?,?)", ("t1", now.isoformat(), "gemini-3.8-flash", "", "[]", "verified_auto", "[]"))
    con.commit()
    u = views.gemma_usage(con)
    by = {s.stage: s for s in u.stages}
    assert (by["risk"].gemma, by["risk"].terms, by["risk"].models) == (5, 1, ["gemma4:12b"])
    assert (by["translate"].gemma, by["translate"].models) == (1, ["gemma4:e4b"])
    assert (by["research"].gemma, by["research"].gemini) == (0, 1)
    assert [x["term_id"] for x in u.samples] == ["t1"]


def test_stage_run_records_model_calls_and_time_for_admin():
    from trend_agents.pipeline import runs

    con = db.connect(":memory:")
    with runs.stage(con, "crosscheck") as r:
        runs.record_model("local:gemma4:12b", 2.0)        # local_llm 이 잰 호출
        runs.record_model("local:gemma4:12b", 3.0)
        runs.record_model("local:gemma4:12b")             # 바깥 층이 다시 적은 같은 호출 — 세지 않는다
        r.count = 1
    with runs.stage(con, "research") as r:
        runs.record_model("gemini-3.5-flash", 4.0, n=2)
        r.count = 1
    runs.record_model("local:gemma4:12b", 9.0)            # 단계 밖(이용자 요청)은 실행 기록에 없다
    models, raw = con.execute("SELECT models, model_calls FROM pipeline_runs WHERE stage='crosscheck'").fetchone()
    assert models == "local:gemma4:12b" and "[2, 5.0]" in raw
    calls = {(c.stage, c.model): c for c in views.gemma_usage(con).calls_24h}
    assert (calls[("crosscheck", "gemma4:12b")].calls, calls[("crosscheck", "gemma4:12b")].seconds) == (2, 5.0)
    assert calls[("crosscheck", "gemma4:12b")].maker == "gemma" and calls[("crosscheck", "gemma4:12b")].label == "문서 대조"
    assert (calls[("research", "gemini-3.5-flash")].calls, calls[("research", "gemini-3.5-flash")].maker) == (2, "gemini")
    assert len(calls) == 2


def test_local_llm_call_is_recorded_even_when_a_stage_calls_it_directly(monkeypatch):
    from trend_agents.pipeline import local_llm, runs
    from trend_agents.interpreters import local_chat
    from pydantic import BaseModel

    class Out(BaseModel):
        ok: bool

    monkeypatch.setattr(local_chat, "structured", lambda prompt, adapter, temperature, image=None: Out(ok=True))
    con = db.connect(":memory:")
    with runs.stage(con, "audit") as r:                  # 감사·문서 대조는 gemini.py 를 거치지 않는다
        local_llm.structured("p", Out)
        r.count = 1
    models, raw = con.execute("SELECT models, model_calls FROM pipeline_runs WHERE stage='audit'").fetchone()
    assert models.startswith("local:") and '": [1, ' in raw
