"""대시보드 목록 규칙(디자인 개편 2차 검토 09-29) — 세 목록은 겹치지 않고, 오래 안 쓰인 말은 '식어 가는' 으로, 건수는 자르기 전 전체, 쪽으로 나눈다.
모델 없이 인메모리 DB 로."""
from datetime import datetime, timedelta, timezone

from trend_agents.pipeline import dashboard
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _term(con, tid, name, lang="ko", region="KR", lifecycle="steady", risk=None, last_seen=None, mentions=0):
    now = datetime.now(timezone.utc)
    seen = last_seen or now
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", lifecycle=lifecycle, first_seen=seen, last_seen=seen,
                             risk_level=risk, risk_checked_at=now if risk else None))
    ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance="y", generations=["20s"], regions=[region],
                                          self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, tid, [("20s", region, now.isoformat(), 1.0)])
    if mentions:
        ds.set_weekly_region(con, tid, {region: {dashboard._weeks()[-1]: mentions}})


def test_lists_do_not_overlap_and_stale_memes_are_fading():
    con = db.connect(":memory:")
    long_ago = datetime.now(timezone.utc) - timedelta(days=900)
    _term(con, "fresh", "럭키비키", mentions=5)
    _term(con, "quiet", "갓생")                                   # 언급은 없지만 최근에 보였다 → 그대로 '지금 쓰이는'
    _term(con, "old", "간 때문이야", last_seen=long_ago)         # 12주 언급 0, 마지막 쓰임 900일 전 → '식어 가는'
    _term(con, "warn", "조심말", lifecycle="rising", risk="caution", mentions=9)
    _term(con, "bad", "자제말", risk="avoid")
    _term(con, "jp", "推し活", lang="ja", region="JP", mentions=3)
    dashboard.run(con)

    b = dashboard.board(con, ["KR"])
    ids = [[c.term_id for c in lst] for lst in (b.rising, b.fading, b.caution)]
    assert ids == [["fresh", "quiet"], ["old"], ["bad", "warn"]]   # 주의 목록은 사용 자제 먼저, 다른 목록과 겹치지 않는다
    assert b.totals == {"rising": 2, "fading": 1, "caution": 2}
    assert sum(b.totals.values()) == b.counts["KR"] == 5          # 탭 건수의 합이 칩 건수와 같다
    assert b.counts["ALL"] == 6 and b.counts["JP"] == 1

    whole = dashboard.board(con)
    assert sum(whole.totals.values()) == whole.counts["ALL"]


def test_board_is_paged_with_real_totals():
    con = db.connect(":memory:")
    for i in range(dashboard.LIST_MAX + 5):
        _term(con, f"t{i:02d}", f"말{i:02d}", mentions=100 - i)
    dashboard.run(con)

    first, second, beyond = (dashboard.board(con, ["KR"], page=p) for p in (1, 2, 3))
    assert first.totals["rising"] == second.totals["rising"] == dashboard.LIST_MAX + 5
    assert len(first.rising) == dashboard.LIST_MAX and len(second.rising) == 5 and beyond.rising == []
    assert first.rising[0].term_id == "t00" and second.rising[0].term_id == f"t{dashboard.LIST_MAX:02d}"
    assert (first.page, second.page, first.page_size) == (1, 2, dashboard.LIST_MAX)
    assert not {c.term_id for c in first.rising} & {c.term_id for c in second.rising}
    assert dashboard.board(con, ["KR"], page=0).page == 1


def test_dashboard_api_takes_page(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    con = db.connect(":memory:")
    _term(con, "fresh", "럭키비키", mentions=5)
    dashboard.run(con)
    monkeypatch.setattr(api, "_con", con)
    c = TestClient(api.app)
    body = c.get("/dashboard", params={"regions": "KR", "page": 2}).json()
    assert body["page"] == 2 and body["rising"] == [] and body["totals"]["rising"] == 1
    assert c.get("/dashboard", params={"page": 0}).status_code == 422
