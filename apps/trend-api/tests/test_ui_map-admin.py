"""관리 화면 개편(2026-09-29): 검수 목록은 근거와 지금 실린 뜻을 함께 보내고, 결정은 본 뜻에만, 수집 현황은 마지막 실행 시각을 보낸다."""
from datetime import datetime, timedelta, timezone

from trend_agents.pipeline import views
from trend_agents.schemas import Evidence, MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _draft(definition: str) -> MeaningDraft:
    return MeaningDraft(definition=definition, origin="x", nuance="y", generations=["10s"], regions=["KR"], self_confidence=0.4)


def _term_under_review(con, tid="t_lv", canonical="럭키비키"):
    ds.upsert_term(con, Term(term_id=tid, canonical=canonical, lang="ko", status="needs_review"))
    ds.add_meaning(con, tid, _draft("의미 없는 감탄사"), "verified_auto", [])
    m2 = ds.add_meaning(con, tid, _draft("그저 그렇다는 평가"), "unverified", [])
    now = datetime.now(timezone.utc)
    evs = [Evidence(evidence_id=ds.new_id("e", f"https://a.com/{i}"), kind="news", url=f"https://a.com/{i}", title=f"{canonical} 기사 {i}",
                    source_domain="a.com", observed_at=now - timedelta(days=i), excerpt=f"요즘 {canonical} 라고 한다 {i}") for i in range(7)]
    evs.append(Evidence(evidence_id=ds.new_id("e", "https://b.com/x"), kind="news", url="https://b.com/x", title="딴 기사", source_domain="b.com",
                        observed_at=now, excerpt="표제어가 없는 문장"))
    ds.add_evidences(con, tid, evs)
    ds.queue_review(con, tid, _draft("그저 그렇다는 평가"), ["지금 실린 뜻과 다릅니다"], len(evs))
    return m2


def test_review_item_carries_current_meaning_and_top_evidence():
    con = db.connect(":memory:")
    m2 = _term_under_review(con)
    [item] = views.review_items(con)
    assert item.proposed.meaning_id == m2.meaning_id
    assert item.current is not None and item.current.definition == "의미 없는 감탄사"   # 비교할 '지금 실린 뜻'
    assert item.lang == "ko"
    assert len(item.evidences) == 5                                                  # 상위 5건만
    assert all("럭키비키" in (e.excerpt or "") for e in item.evidences)                   # 표제어가 든 근거만


def test_new_meaning_has_no_current():
    con = db.connect(":memory:")
    ds.upsert_term(con, Term(term_id="t_new", canonical="사보필", status="needs_review"))
    ds.add_meaning(con, "t_new", _draft("줄임말"), "unverified", [])
    ds.queue_review(con, "t_new", _draft("줄임말"), ["출처가 한 곳뿐"], 1)
    [item] = views.review_items(con)
    assert item.current is None and item.evidences == []


def test_decision_on_a_stale_meaning_is_refused(monkeypatch):
    """화면을 연 뒤 조사가 새 판을 만들었으면 보지 않은 뜻을 싣지 않는다 — 409."""
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    con = db.connect(":memory:")
    m2 = _term_under_review(con)
    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setattr(api.dashboard, "refresh_card", lambda *a, **k: None)
    monkeypatch.setattr(api.risk, "apply", lambda *a, **k: None)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "tok")
    c = TestClient(api.app)
    h = {"x-frontend-token": "tok"}
    r = c.post("/review/t_lv", json={"decision": "approve", "by": "kim", "meaning_id": "m_old"}, headers=h)
    assert r.status_code == 409
    assert ds.get_term(con, "t_lv").status == "needs_review"                          # 아무것도 바꾸지 않았다
    r = c.post("/review/t_lv", json={"decision": "approve", "by": "kim", "meaning_id": m2.meaning_id}, headers=h)
    assert r.status_code == 200 and ds.get_term(con, "t_lv").status == "verified"


def test_stage_rows_split_status_and_carry_last_run_times():
    con = db.connect(":memory:")

    def run(stage, count, status, note="", ago_h=0.0):
        rid = ds.run_start(con, stage)
        ds.run_finish(con, rid, count, status, note)
        if ago_h:
            when = (datetime.now(timezone.utc) - timedelta(hours=ago_h)).isoformat()
            con.execute("UPDATE pipeline_runs SET started_at=?, finished_at=? WHERE run_id=?", (when, when, rid))
            con.commit()

    run("collect.youtube", 120, "ok")
    run("hunt", 0, "zero", "0건")
    run("interpret", 0, "error", "HTTPError: 429")
    run("collect.news", 0, "skipped", "키 없음")
    run("collect.trends_bq", 5, "ok", ago_h=30)                                       # 24시간 밖
    by = {s.key: s for s in views.pipeline_stages(con)}
    assert by["collect.youtube"].run_status == "ok" and by["collect.youtube"].last_started_at
    assert by["hunt"].run_status == "idle"                                            # 0건은 실패가 아니다
    assert by["interpret"].run_status == "error" and by["collect.news"].run_status == "skipped"
    assert by["collect.trends_bq"].run_status is None and by["collect.trends_bq"].last_finished_at   # 24시간 안에 실행 없음, 시각은 남는다
    assert by["spikes"].run_status is None and by["spikes"].last_started_at is None
