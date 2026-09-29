"""화면 개편 통합(09-29) — 여러 화면이 같은 규칙을 쓰는지. 모델 없이 인메모리 DB 로."""
from datetime import datetime, timezone

from trend_agents.pipeline import board
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _term(con, tid, name, regions, risk=None):
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", lifecycle="steady", first_seen=now, last_seen=now,
                             risk_level=risk, risk_checked_at=now if risk else None))
    ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance="y", generations=["20s"], regions=regions,
                                          self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, tid, [("20s", r, now.isoformat(), 0.5) for r in regions])


def test_map_topics_hide_profane_headwords_like_the_dashboard():
    """세계 지도 '나라를 건너간 밈' 도 둘러보는 목록이다 — 표제어 자체가 욕설이면 내지 않는다(검수자가 '특이 사항 없음' 으로 정하면 보인다)."""
    con = db.connect(":memory:")
    _term(con, "ok", "럭키비키", ["KR", "JP"])
    _term(con, "bad", "좆밥", ["KR", "JP"], risk="avoid")
    _term(con, "cleared", "씨발비용", ["KR", "TW"], risk="none")
    ids = {t.id for t in board.build(con).topics}
    assert "tp_ok" in ids and "tp_bad" not in ids and "tp_cleared" in ids
