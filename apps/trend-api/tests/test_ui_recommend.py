"""밈 추천 화면 개편(2차) — 표제어의 말(lang)과 사전 항목에서 먼저 고른 밈(pin). 모델 없이 인메모리 DB 로."""
import pytest

from trend_agents.pipeline import dashboard, recommend
from trend_agents.storage import store as db

from .test_recommend import LATTE, _con, _term


@pytest.fixture(autouse=True)
def _no_models(monkeypatch):
    monkeypatch.setattr(recommend, "configured", lambda: False)
    monkeypatch.setattr(recommend, "USE_LOCAL_GEMMA", False)


def test_items_carry_the_headword_language():
    res = recommend.recommend(_con(), LATTE, "sample", ["KR"], "friendly")
    assert res.items and all(i.lang == "ko" for i in res.items)
    assert not any(i.pinned for i in res.items)


def test_pinned_meme_is_added_after_the_ranked_list():
    """사전 항목의 '이 밈으로 만들기' — 순위 문턱(톤·맞는 정도)에 걸린 밈도 목록 끝에 넣는다."""
    con = _con()
    ranked = [i.term_id for i in recommend.recommend(con, LATTE, "sample", ["KR"], "friendly").items]
    assert "nofit" not in ranked
    got = recommend.recommend(con, LATTE, "sample", ["KR"], "friendly", pin="nofit").items
    assert [i.term_id for i in got] == [*ranked, "nofit"]
    assert got[-1].pinned and not got[-1].matched_category and got[-1].matched_feelings == []


def test_pinned_meme_already_in_the_list_keeps_its_place():
    con = _con()
    got = recommend.recommend(con, LATTE, "sample", ["KR"], "friendly", pin="good").items
    assert got[0].term_id == "good" and got[0].pinned
    assert sum(i.pinned for i in got) == 1 and len({i.term_id for i in got}) == len(got)


def test_pin_does_not_bypass_avoid_crude_or_region():
    con = _con()
    for tid in ("bad", "crude", "missing"):
        items = recommend.recommend(con, LATTE, "sample", ["KR"], "friendly", pin=tid).items
        assert tid not in {i.term_id for i in items}
    # 고른 지역에서 쓰이지 않는 밈은 넣지 않는다
    other = db.connect(":memory:")
    _term(other, "kr", "한국말", ["joy"])
    dashboard.run(other)
    assert recommend.recommend(other, LATTE, "sample", ["JP"], "friendly", pin="kr").items == []


def test_recommend_api_passes_the_pinned_term(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", _con())
    monkeypatch.setattr(api, "_recommend_limit", recommend.RateLimit())
    c = TestClient(api.app)
    r = c.post("/recommend", data={"text": "여름 라떼", "regions": "KR", "term": "nofit"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[-1]["term_id"] == "nofit" and items[-1]["pinned"] is True and items[-1]["lang"] == "ko"
