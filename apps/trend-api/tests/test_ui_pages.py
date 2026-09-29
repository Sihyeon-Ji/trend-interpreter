"""화면 개편 2차(메시지 해석·사전·계정) — 질문 답 카드가 화면이 붙일 단계·쓸 때 조심 코드를 함께 싣는다."""
from datetime import datetime, timezone

from trend_agents.pipeline import tools
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _term(con, **kw) -> Term:
    t = ds.upsert_term(con, Term(term_id=kw.pop("term_id"), canonical=kw.pop("canonical"), status="verified", **kw), human=True)
    ds.add_meaning(con, t.term_id, MeaningDraft(definition="저녁 메뉴를 추천해 달라는 말", expansion="저녁 메뉴 추천", origin="점메추에서 파생",
                                                 nuance="친한 사이의 구어", generations=["20s"], regions=["KR"], self_confidence=0.9),
                   "verified_auto", [])
    return ds.get_term(con, t.term_id)


def test_term_and_list_cards_carry_status_codes():
    con = db.connect(":memory:")
    checked = datetime(2026, 9, 28, 5, 0, tzinfo=timezone.utc)
    t = _term(con, term_id="t_jmc", canonical="저메추", lang="ko", lifecycle="steady", diffusion="mainstream",
              risk_level="caution", risk_checked_at=checked)
    card = tools._term_card(con, t, ds.current_meaning(con, t.term_id))
    # 예전 화면과 모델 근거를 위한 한국어 이름은 그대로 두고, 코드를 더한다
    assert card["lifecycle"] == tools.LIFECYCLE["steady"]
    assert card["lifecycle_code"] == "steady" and card["diffusion"] == "mainstream" and card["lang"] == "ko"
    assert card["risk_level"] == "caution" and card["risk_checked_at"].startswith("2026-09-28")

    listed = tools._list_card(con, "같은 계열", [t])["items"][0]
    assert listed["lifecycle_code"] == "steady" and listed["risk_level"] == "caution"


def test_unchecked_risk_is_null_not_missing():
    """검사 전(risk_checked_at 없음)과 판단 보류(검사했는데 None)를 화면이 가를 수 있게 둘 다 키를 싣는다."""
    con = db.connect(":memory:")
    t = _term(con, term_id="t_new", canonical="새말", lang="ko")
    card = tools._term_card(con, t, ds.current_meaning(con, t.term_id))
    assert "risk_level" in card and card["risk_level"] is None
    assert "risk_checked_at" in card and card["risk_checked_at"] is None
