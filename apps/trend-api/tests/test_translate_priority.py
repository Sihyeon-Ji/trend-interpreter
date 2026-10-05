"""번역 단계는 대시보드에 앞서 보이는 말의 영어판부터 만든다(이름순 12개씩이던 것, 10-04). 모델 없이."""
from datetime import datetime, timezone

from trend_agents.pipeline import dashboard, translate
from trend_agents.schemas import MeaningDraft, MeaningText, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def test_translate_starts_with_english_for_memes_shown_first(monkeypatch):
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)

    def term(tid, name, **kw):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now, **kw))
        ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻풀이", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                              self_confidence=0.9), "verified_auto", [])
        ds.set_usage(con, tid, [("20s", "KR", now.isoformat(), 1.0)])

    term("a", "가나다", lifecycle="steady")                    # 이름순으로는 먼저지만 목록에서는 뒤
    term("z", "하하하", lifecycle="rising", diffusion="spreading")   # 막 퍼지는 말 — 대시보드 맨 앞
    dashboard.run(con)
    assert [t.term_id for t in translate.priority(con)] == ["z", "a"]
    assert all(c.en_pending for c in dashboard.cards(con, ["KR"]))   # 영어판이 없으면 gloss_en 은 한국어 원문 — 표시로 알린다

    calls = []

    def fake(_con, name, m, lang):
        calls.append((name, lang))
        return MeaningText(definition=f"{name} in {lang}", origin="o", nuance="n"), "test"

    monkeypatch.setattr(translate, "make_text", fake)
    translate.run(con, max_calls=1)
    assert calls == [("하하하", "en")]                         # 영어 먼저, 한도에 닿으면 멈춘다
    translate.run(con, max_calls=2)
    assert calls[1:] == [("하하하", "ko"), ("가나다", "en")]

    dashboard.run(con)
    cards = {c.term_id: c for c in dashboard.cards(con, ["KR"])}
    assert not cards["z"].en_pending and cards["z"].gloss_en == "하하하 in en"
    assert cards["a"].en_pending is False                     # 이제 영어판이 있다


def test_korean_screen_does_not_show_a_japanese_only_meaning():
    """한국어판이 없고 원문 뜻에 한글이 없으면 ko_pending — 한국어 화면에 일본어 원문이 그대로 나가던 것(10-05, 대시보드 25개)."""
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name, lang, definition in (("ja", "科目三", "ja", "中国発祥のインターネット現象。膝を左右に揺らすダンス。"),
                                        ("jk", "推し活", "ja", "좋아하는 아이돌·캐릭터를 응원하는 활동 전반.")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", lifecycle="steady", first_seen=now, last_seen=now))
        ds.add_meaning(con, tid, MeaningDraft(definition=definition, origin="x", nuance="y", generations=["20s"], regions=["JP"],
                                              self_confidence=0.9), "verified_auto", [])
        ds.set_usage(con, tid, [("20s", "JP", now.isoformat(), 1.0)])
    dashboard.run(con)
    cards = {c.term_id: c for c in dashboard.cards(con, ["JP"])}
    assert cards["ja"].ko_pending and not cards["jk"].ko_pending    # 원문 뜻이 이미 한국어면 그대로 보인다

    ds.set_translation(con, "ja", "ko", MeaningText(definition="중국에서 시작된 인터넷 춤 유행.", origin="o", nuance="n"), "test")
    dashboard.run(con)
    assert not {c.term_id: c for c in dashboard.cards(con, ["JP"])}["ja"].ko_pending
