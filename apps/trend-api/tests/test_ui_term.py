"""사전 항목 화면(화면 개편 2차: term) — 대시보드 행과 사전 항목이 같은 지역의 같은 수를 보인다."""
from datetime import datetime, timezone

from trend_agents.pipeline import dashboard
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _seed():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    week = dashboard._weeks()[-1]
    ds.upsert_term(con, Term(term_id="oshi", canonical="推し活", lang="ja", status="verified", first_seen=now, last_seen=now))
    ds.add_meaning(con, "oshi", MeaningDraft(definition="推し活 뜻", origin="x", nuance="y", generations=["20s"], regions=["JP", "TW"],
                                             self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, "oshi", [("20s", r, now.isoformat(), 1.0) for r in ("JP", "TW")])
    ds.set_weekly_region(con, "oshi", {"JP": {week: 125}, "TW": {week: 2}})
    dashboard.run(con)
    return con


def test_term_signals_follow_the_dashboard_regions():
    """지역을 주면 대시보드 행과 같은 수, 없으면 모든 지역 합계. 모르는 지역뿐이면 대시보드처럼 목표 지역 전체."""
    con = _seed()
    row = next(c for c in dashboard.board(con, ["TW"]).rising + dashboard.board(con, ["TW"]).fading if c.term_id == "oshi")
    assert dashboard.card(con, "oshi", ["TW"]).mentions_4w == row.mentions_4w == 2
    assert dashboard.card(con, "oshi").mentions_4w == 127
    assert dashboard.card(con, "oshi", ["XX"]).mentions_4w == 127       # 목표 지역 전체 = 일본 + 대만


def test_term_signals_endpoint_reads_regions(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    seen = []
    monkeypatch.setattr(api, "_public_term", lambda tid: None)
    monkeypatch.setattr(api.dashboard, "card", lambda con, tid, regions=None: seen.append((tid, regions)) or None)
    c = TestClient(api.app)
    assert c.get("/terms/oshi/signals?regions=kr, jp").status_code == 404   # 가짜 card 가 None → 404
    assert c.get("/terms/oshi/signals").status_code == 404
    assert seen == [("oshi", ["KR", "JP"]), ("oshi", None)]
