"""사전 항목의 '지금 다시 분류해 보기'(ejchoi 계획 1단계). 네트워크·GPU 없이 – 기사·gateway·모델을 바꿔 끼운다."""
from datetime import datetime, timezone

import pytest

from trend_agents.pipeline import live_risk
from trend_agents.schemas import EvidenceLabel, MeaningDraft, NewsItem, Term
from trend_agents.storage import db
from trend_agents.storage import dictionary_store as ds

NOW = datetime.now(timezone.utc)


@pytest.fixture
def con(monkeypatch):
    c = db.connect(":memory:")
    ds.upsert_term(c, Term(term_id="t_lv", canonical="럭키비키", lang="ko", status="verified", first_seen=NOW, last_seen=NOW,
                           risk_level="none", risk_reasons=["분류된 근거 9건에 위험 신호가 없다."]))
    ds.add_meaning(c, "t_lv", MeaningDraft(definition="안 좋은 일도 좋게 받아들이는 태도", origin="x", nuance="y", generations=["20s"],
                                           regions=["KR"], self_confidence=0.9), "verified_auto", [])
    live_risk._cache.clear()
    monkeypatch.setattr(live_risk.config, "GPU_GATEWAY_MODEL", "gemma4:12b")
    monkeypatch.setattr(live_risk.gpu_gateway, "configured", lambda: True)
    monkeypatch.setattr(live_risk.gpu_gateway, "available", lambda model, timeout=None: True)
    yield c
    c.close()


def news(n, word="럭키비키"):
    return [NewsItem(title=f"오늘 {word} 기사 {i}", link=f"https://news{i % 3}.example/{i}", published_at=NOW, source=f"매체{i % 3}", region="KR")
            for i in range(n)]


def test_gpu_not_ready_answers_at_once_without_fetching_or_logging(con, monkeypatch):
    monkeypatch.setattr(live_risk.gpu_gateway, "available", lambda model, timeout=None: False)
    monkeypatch.setattr(live_risk.news_rss, "fetch_news", lambda *a, **k: pytest.fail("GPU 가 없으면 기사도 모으지 않는다"))
    out = live_risk.run(con, ds.get_term(con, "t_lv"))
    assert out.status == "not_ready" and out.batch_level == "none" and out.level is None
    assert con.execute("SELECT count(*) FROM live_risk_runs").fetchone()[0] == 0


def test_classifies_fresh_titles_with_the_batch_rules_and_never_touches_the_public_entry(con, monkeypatch):
    calls = []
    monkeypatch.setattr(live_risk.news_rss, "fetch_news", lambda *a, **k: news(7) + news(2, word="다른말"))

    def fake(prompt, schema, **kw):
        calls.append((prompt, kw))
        assert "다른말" not in prompt and "럭키비키" in prompt                 # 표제어가 든 제목만 넘긴다
        return [EvidenceLabel(i=i, polarity="negative" if i < 3 else "positive", risk="politics" if i < 3 else "none") for i in range(7)]

    monkeypatch.setattr(live_risk.local_chat, "structured", fake)
    before = ds.get_term(con, "t_lv")
    out = live_risk.run(con, before)
    assert out.status == "ok" and len(out.sentences) == 7 and out.found == 7
    assert calls[0][1] == {"model": "gemma4:12b"}
    # 위험 문장 3건·두 곳 이상이지만 쓰임의 절반을 넘지 않는다 → 배치와 같은 규칙으로 '주의'
    assert out.level == "caution" and out.same_as_batch is False and out.batch_level == "none"
    assert any("위험 유형이 붙은 근거 3건" in r for r in out.reasons)
    after = ds.get_term(con, "t_lv")
    assert after.risk_level == before.risk_level and after.risk_reasons == before.risk_reasons      # 공개 판정은 그대로
    assert con.execute("SELECT count(*) FROM evidence_labels").fetchone()[0] == 0                   # 근거 분류 표에도 쓰지 않는다
    row = con.execute("SELECT term_id, status, sentences, level, model FROM live_risk_runs").fetchall()
    assert row == [("t_lv", "ok", 7, "caution", "gemma4:12b")]                                     # 문장·출력 원문은 남기지 않는다
    again = live_risk.run(con, after)
    assert again.cached and again.level == "caution" and len(calls) == 1                          # 10분 안에는 다시 부르지 않는다


def test_too_few_titles_skip_the_model(con, monkeypatch):
    monkeypatch.setattr(live_risk.news_rss, "fetch_news", lambda *a, **k: news(3))
    monkeypatch.setattr(live_risk.local_chat, "structured", lambda *a, **k: pytest.fail("5개 미만이면 모델을 부르지 않는다"))
    out = live_risk.run(con, ds.get_term(con, "t_lv"))
    assert out.status == "too_few" and out.found == 3


def test_one_run_at_a_time_and_failures_are_reported(con, monkeypatch):
    live_risk._run_lock.acquire()
    try:
        assert live_risk.run(con, ds.get_term(con, "t_lv")).status == "busy"
    finally:
        live_risk._run_lock.release()
    monkeypatch.setattr(live_risk.news_rss, "fetch_news", lambda *a, **k: news(6))

    def broken(*a, **k):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(live_risk.local_chat, "structured", broken)
    out = live_risk.run(con, ds.get_term(con, "t_lv"))
    assert out.status == "failed" and out.level is None


def test_endpoint_is_for_reviewers_only(con, monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "tok")
    monkeypatch.setattr(live_risk.gpu_gateway, "available", lambda model, timeout=None: False)
    c = TestClient(api.app)
    assert c.post("/terms/t_lv/live-risk").status_code == 401
    assert c.post("/terms/t_none/live-risk", headers={"x-frontend-token": "tok"}).status_code == 404
    body = c.post("/terms/t_lv/live-risk", headers={"x-frontend-token": "tok"}).json()
    assert body["status"] == "not_ready" and body["batch_level"] == "none"


# ── 2단계: 관리자 수동 실행(미리보기) ──────────────────────────────────────────────

def _usage(c):
    from trend_agents.schemas import Evidence
    evs = [Evidence(evidence_id=f"e{i}", kind="news", url=f"https://news{i % 2}.example/{i}", title=f"럭키비키 기사 {i}",
                    source_domain=f"news{i % 2}.example", observed_at=NOW) for i in range(5)]
    evs.append(Evidence(evidence_id="p0", kind="community", url="https://www.reddit.com/r/x/1", title="커뮤니티 글 럭키비키",
                        source_domain="reddit.com", observed_at=NOW))
    ds.add_evidences(c, "t_lv", evs)
    ds.set_evidence_labels(c, "t_lv", [(e.evidence_id, "positive", "none") for e in evs], "gemma4:12b")
    return evs


def test_rerun_previews_the_batch_risk_stage_without_saving(con, monkeypatch):
    evs = _usage(con)

    def fake(prompt, schema, **kw):
        assert "커뮤니티 글 럭키비키" in prompt          # 판정에 세는 글은 모델에 넘긴다 – 화면에만 옮기지 않는다
        return [EvidenceLabel(i=i, polarity="negative" if i < 3 else "positive", risk="politics" if i < 3 else "none") for i in range(len(evs))]

    monkeypatch.setattr(live_risk.local_chat, "structured", fake)
    before = ds.get_term(con, "t_lv")
    out = live_risk.rerun(con, before)
    assert out.status == "ok" and out.stage == "risk" and len(out.sentences) == 6
    assert out.before_level == "none" and out.after_level == "caution" and out.public_level == "none"
    assert out.changed == 3 and sum(s.changed for s in out.sentences) == 3
    post = [s for s in out.sentences if s.kind == "community"]
    assert post and post[0].text is None and post[0].source is None                                   # 커뮤니티 글은 옮기지 않는다(ADR 0003)
    assert all(s.text for s in out.sentences if s.kind == "news")
    assert ds.evidence_labels(con, "t_lv") == {e.evidence_id: ("positive", "none") for e in evs}       # 저장된 분류는 그대로
    after = ds.get_term(con, "t_lv")
    assert (after.risk_level, after.risk_reasons) == (before.risk_level, before.risk_reasons)
    row = con.execute("SELECT term_id, status, sentences, level, kind FROM live_risk_runs").fetchall()
    assert row == [("t_lv", "ok", 6, "caution", "rerun")]


def test_rerun_waits_for_nothing_when_the_gpu_is_off_and_shares_the_one_gpu(con, monkeypatch):
    _usage(con)
    monkeypatch.setattr(live_risk.gpu_gateway, "available", lambda model, timeout=None: False)
    out = live_risk.rerun(con, ds.get_term(con, "t_lv"))
    assert out.status == "not_ready" and out.before_level == "none" and out.after_level is None
    live_risk._run_lock.acquire()
    try:
        assert live_risk.rerun(con, ds.get_term(con, "t_lv")).status == "busy"
    finally:
        live_risk._run_lock.release()


def test_rerun_endpoint_is_for_reviewers_only(con, monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "tok")
    monkeypatch.setattr(live_risk.gpu_gateway, "available", lambda model, timeout=None: False)
    c = TestClient(api.app)
    assert c.post("/terms/t_lv/risk-rerun").status_code == 401
    assert c.post("/terms/t_none/risk-rerun", headers={"x-frontend-token": "tok"}).status_code == 404
    assert c.post("/terms/t_lv/risk-rerun", headers={"x-frontend-token": "tok"}).json()["status"] == "not_ready"
