"""트렌드 브리핑·카피 검사 — 목록과 판정은 대시보드·리스크 규칙 그대로, 모델은 브리핑 요약과 카피의 '뜻에 맞게 썼나' 의견만.
모델이 없거나 자리가 없거나 실패해도 결과는 나온다. 모델 없이 인메모리 DB 로."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from trend_agents.api import app as api
from trend_agents.pipeline import briefing, copycheck, dashboard
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _term(con, tid, name, lang="ko", region="KR", lifecycle="steady", risk=None, checked=None, last_seen=None, mentions=0):
    now = datetime.now(timezone.utc)
    seen = last_seen or now
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", lifecycle=lifecycle, first_seen=seen, last_seen=seen,
                             risk_level=risk, risk_checked_at=now if (risk or checked) else None))
    ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance="y", generations=["20s"], regions=[region],
                                          self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, tid, [("20s", region, now.isoformat(), 1.0)])
    if mentions:
        ds.set_weekly_region(con, tid, {region: {dashboard._weeks()[-1]: mentions}})


@pytest.fixture
def con(monkeypatch):
    c = db.connect(":memory:")
    long_ago = datetime.now(timezone.utc) - timedelta(days=900)
    _term(c, "fresh", "럭키비키", risk="none", mentions=5)
    _term(c, "warn", "조심말", lifecycle="rising", risk="caution", mentions=9)
    _term(c, "maybe", "보류말", checked=True, mentions=2)          # 검사했지만 근거 부족 → 판단 보류
    _term(c, "bad", "자제말", risk="avoid")
    _term(c, "old", "간 때문이야", risk="none", last_seen=long_ago)
    _term(c, "jp", "推し活", lang="ja", region="JP", risk="none", mentions=3)
    _term(c, "kjp", "오살힘", region="JP", risk="none")             # 일본에서 쓰이지만 한글 표기뿐
    dashboard.run(c)
    monkeypatch.setattr(api, "_con", c)
    monkeypatch.setattr(briefing, "model_ready", lambda: False)
    monkeypatch.setattr(copycheck, "model_ready", lambda: False)
    briefing._cache.clear()
    return c


def test_briefing_lists_follow_the_dashboard_rules(con):
    b = briefing.build(con, ["KR"])
    ids = {k: [c.term_id for c in getattr(b, k)] for k in ("use_now", "careful", "avoid", "fading")}
    assert ids == {"use_now": ["fresh"], "careful": ["warn"], "avoid": ["bad"], "fading": ["old"]}
    assert b.counts.model_dump() == {"rising": 3, "use_now": 1, "careful": 1, "undecided": 1, "avoid": 1, "fading": 1}
    assert b.regions == ["KR"] and b.summary is None and b.summary_source == "none"
    assert briefing.build(con, []).regions == dashboard.chosen_regions([])     # 지역이 없으면 목표 지역 전체 — 대시보드와 같다


def test_briefing_summary_is_written_once_per_board_and_falls_back(con, monkeypatch):
    calls = []

    def fake(_con, prompt, schema, **kw):
        calls.append(prompt)
        assert kw == {"prefer_gemini": True, "request": True}
        assert "럭키비키" in prompt and "자제말" in prompt and "보류말" not in prompt   # 목록에 실린 이름만 넘긴다
        return briefing.BriefingText(text="  이번 주 한국에서는\n럭키비키를 써 볼 만합니다. "), "gemini-x"

    monkeypatch.setattr(briefing, "model_ready", lambda: True)
    monkeypatch.setattr(briefing, "structured", fake)
    c = TestClient(api.app)
    glance = c.get("/briefing", params={"regions": "KR", "summary": "false"}).json()   # 대시보드의 '한눈에 보기' — 모델을 부르지 않는다
    assert glance["summary"] is None and calls == [] and glance["counts"]["use_now"] >= 1
    first = c.get("/briefing", params={"regions": "KR"}).json()
    again = c.get("/briefing", params={"regions": "KR"}).json()
    assert first["summary"] == again["summary"] == "이번 주 한국에서는 럭키비키를 써 볼 만합니다."
    assert first["summary_source"] == "gemini" and len(calls) == 1               # 같은 갱신·지역·언어면 다시 부르지 않는다
    c.get("/briefing", params={"regions": "KR", "lang": "en"})
    assert len(calls) == 2

    def broken(*a, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(briefing, "structured", broken)
    body = c.get("/briefing", params={"regions": "JP"}).json()
    assert body["summary"] is None and body["summary_source"] == "none" and body["counts"]["use_now"] == 2   # 보고서는 그대로 열린다


def test_copy_check_flags_by_rules_without_a_model(con):
    c = TestClient(api.app)
    text = "럭키비키! 조심말도 자제말도, 推し活 오살힘 간 때문이야 시발"
    body = c.post("/copy-check", json={"text": text, "region": "KR"}).json()
    issues = {m["term_id"]: [i["code"] for i in m["issues"]] for m in body["memes"]}
    assert [m["term_id"] for m in body["memes"]] == ["fresh", "warn", "bad", "jp", "kjp", "old"]   # 문구에 나온 순서
    assert issues == {"fresh": [], "warn": ["caution"], "bad": ["avoid"], "jp": ["not_in_region"], "kjp": ["not_in_region"],
                      "old": ["fading"]}
    assert body["unsafe"] is True and body["fit_source"] == "none" and all(m["fit"] is None for m in body["memes"])
    assert body["memes"][1]["issues"][0]["note"].endswith("비하·조롱·선정·정치 맥락으로 쓰지 말 것")   # caution_note — 근거 글을 인용하지 않는다

    jp = c.post("/copy-check", json={"text": "推し活 오살힘", "region": "JP"}).json()
    assert {m["term_id"]: [i["code"] for i in m["issues"]] for m in jp["memes"]} == {"jp": [], "kjp": ["no_script"]}
    assert c.post("/copy-check", json={"text": "아무 말", "region": "KR"}).json()["memes"] == []


def test_copy_check_input_and_limits(con):
    c = TestClient(api.app)
    assert c.post("/copy-check", json={"text": "럭키비키", "region": "US"}).status_code == 400
    assert c.post("/copy-check", json={"text": "   ", "region": "KR"}).status_code == 400
    assert c.post("/copy-check", json={"text": "가" * (copycheck.MAX_TEXT + 1), "region": "KR"}).status_code == 422
    big = '{"text": "' + "a" * (17 * 1024) + '", "region": "KR"}'
    assert c.post("/copy-check", content=big, headers={"content-type": "application/json"}).status_code == 413


def test_copy_check_meaning_fit_is_a_model_opinion_and_never_blocks(con, monkeypatch):
    monkeypatch.setattr(copycheck, "model_ready", lambda: True)

    def fake(_con, prompt, schema, **kw):
        assert "럭키비키" in prompt and kw == {"prefer_gemini": True, "request": True}
        return copycheck.FitResult(items=[copycheck.FitItem(term_id="fresh", fit="off", note="  긍정 상황에 써야 합니다 ")]), "gemini-x"

    monkeypatch.setattr(copycheck, "structured", fake)
    c = TestClient(api.app)
    body = c.post("/copy-check", json={"text": "실패해서 럭키비키", "region": "KR"}).json()
    assert body["fit_source"] == "gemini" and body["memes"][0]["fit"] == "off" and body["memes"][0]["fit_note"] == "긍정 상황에 써야 합니다"

    def broken(*a, **kw):
        raise RuntimeError("budget")

    monkeypatch.setattr(copycheck, "structured", broken)
    body = c.post("/copy-check", json={"text": "럭키비키", "region": "KR"}).json()
    assert body["fit_source"] == "failed" and body["memes"][0]["issues"] == [] and body["memes"][0]["fit"] is None

    taken = [api._model_slots.acquire(blocking=False) for _ in range(api.MODEL_SLOTS)]
    try:
        assert all(taken) and c.post("/copy-check", json={"text": "럭키비키", "region": "KR"}).json()["fit_source"] == "busy"
    finally:
        for _ in taken:
            api._model_slots.release()


def test_term_topic_returns_one_topic_and_follows_board_changes(con):
    """사전 항목의 관련 표현은 주제 하나만 받는다(보드 전체 1.5MB 대신). 보드가 다시 만들어지면 바로 따른다(해석 결과를 둔 캐시라도)."""
    from trend_agents.pipeline import board as board_stage
    from trend_agents.schemas import Text2, Topic, TopicVariant, TrendBoard

    def save(name):
        v = TopicVariant(region="KR", local_name="럭키비키", since="2024", heat=3, what_changed=Text2(ko="", en=""), term_id="fresh")
        t = Topic(id="t1", category="slang_meme", name=Text2(ko=name, en=name), summary=Text2(ko="", en=""), variants=[v])
        ds.cache_set(con, "board", TrendBoard(generated_at=datetime.now(timezone.utc), items=[], topics=[t]).model_dump_json(), "2026-10-04T00:00:00+00:00")

    c = TestClient(api.app)
    assert c.get("/terms/fresh/topic").json() is None                  # 보드가 아직 없다
    save("긍정 밈")
    assert c.get("/terms/fresh/topic").json()["name"]["ko"] == "긍정 밈"
    assert c.get("/terms/warn/topic").json() is None and c.get("/terms/nope/topic").json() is None
    save("원영적 사고")                                                   # 같은 시각으로 다시 저장해도 내용이 바뀌면 새 보드
    assert c.get("/terms/fresh/topic").json()["name"]["ko"] == "원영적 사고"
    assert board_stage.cached(con).topics[0].name.ko == "원영적 사고"


def test_single_hangul_terms_match_only_as_a_word():
    """한 글자 한글 표제어('님'·'입')는 다른 낱말 안에서 잡지 않는다 — '팀장님' 의 '님'(10-04). 두 글자 이상은 전처럼 붙여 써도 잡는다."""
    from trend_agents.pipeline.explain import match_terms

    terms = [Term(term_id="nim", canonical="님", lang="ko", status="needs_review"),
             Term(term_id="gol", canonical="과몰입", lang="ko", status="verified")]
    assert [t.term_id for t in match_terms("팀장님 갑자기 과몰입함", terms)] == ["gol"]
    assert [t.term_id for t in match_terms("오늘 님 최고", terms)] == ["nim"]
