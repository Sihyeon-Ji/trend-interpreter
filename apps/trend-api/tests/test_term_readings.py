"""표제어 읽기(term_readings, 마이그레이션 026) — 원문은 그대로 두고 화면 언어로 읽는 법을 곁에 붙인다(10-13 사용자 요청). 모델 없이."""
from datetime import datetime, timezone

from trend_agents.pipeline import dashboard, views
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _term(con, tid, name, lang="ko"):
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", lifecycle="steady", first_seen=now, last_seen=now))
    ds.add_meaning(con, tid, MeaningDraft(definition="아이브 장원영의 긍정적인 사고방식.", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                          self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, tid, [("20s", "KR", now.isoformat(), 1.0)])


def test_entry_card_and_recommend_item_carry_the_readings():
    con = db.connect(":memory:")
    _term(con, "jw", "장원영")
    ds.set_reading(con, "jw", "ja", "장원영", "チャン・ウォニョン", "test")
    ds.set_reading(con, "jw", "en", "장원영", "Jang Won-young", "test")
    assert views.term_record(con, ds.get_term(con, "jw")).readings == {"ja": "チャン・ウォニョン", "en": "Jang Won-young"}
    dashboard.run(con)
    card = next(c for c in dashboard.cards(con, ["KR"]) if c.term_id == "jw")
    assert card.readings["ja"] == "チャン・ウォニョン"
    item = views.RecommendItem(**card.model_dump(include=set(views.RecommendItem.model_fields)), matched_category=True, any_category=False,
                               matched_feelings=[], score=1.0)
    assert item.readings["en"] == "Jang Won-young"


def test_a_reading_made_for_an_old_headword_is_not_shown():
    con = db.connect(":memory:")
    _term(con, "jw", "장원영")
    ds.set_reading(con, "jw", "ja", "원영", "ウォニョン", "test")              # 표제어가 바뀌기 전에 만든 읽기
    assert views.term_record(con, ds.get_term(con, "jw")).readings == {}


def test_list_views_read_the_readings_in_one_query():
    con = db.connect(":memory:")
    _term(con, "a", "갓생")
    _term(con, "b", "꾸안꾸")
    ds.set_reading(con, "a", "ja", "갓생", "ガッセン", "test")
    with ds.batched(con, ["a", "b"]):
        assert ds.get_readings(con, ds.get_term(con, "a")) == {"ja": "ガッセン"}
        assert ds.get_readings(con, ds.get_term(con, "b")) == {}
