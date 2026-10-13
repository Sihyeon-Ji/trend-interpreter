"""트렌드 브리핑·카피 검사 — 목록과 판정은 대시보드·리스크 규칙 그대로, 모델은 브리핑 요약과 카피의 '뜻에 맞게 썼나' 의견만.
모델이 없거나 자리가 없거나 실패해도 결과는 나온다. 모델 없이 인메모리 DB 로."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from trend_agents.api import app as api
from trend_agents.pipeline import briefing, copycheck, dashboard, views
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
    # 사용 자제는 공개 목록에서 뺀다(10-09) – 브리핑에도 이름을 싣지 않는다. 카피 검사의 경고에만 남는다(아래)
    assert ids == {"use_now": ["fresh"], "careful": ["warn"], "avoid": [], "fading": ["old"]}
    assert b.counts.model_dump() == {"rising": 3, "use_now": 1, "careful": 1, "undecided": 1, "avoid": 0, "fading": 1}
    assert b.regions == ["KR"] and b.summary is None and b.summary_source == "none"
    assert briefing.build(con, []).regions == dashboard.chosen_regions([])     # 지역이 없으면 목표 지역 전체 — 대시보드와 같다


def test_briefing_summary_is_written_once_per_board_and_falls_back(con, monkeypatch):
    calls = []

    def fake(_con, prompt, schema, **kw):
        calls.append(prompt)
        assert kw == {"prefer_gemini": True, "request": True}
        assert "럭키비키" in prompt and "자제말" not in prompt and "보류말" not in prompt   # 목록에 실린 이름만 넘긴다
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


def test_japanese_summary_with_hangul_outside_meme_names_falls_back_to_the_rule_sentence(con, monkeypatch):
    """일본어 요약에 밈 이름 밖의 한글이 섞였다('今使える밈としては', 10-13 시험) — 버리고 화면의 일본어 규칙 문장을 쓴다. 밈 이름의 한글은 괜찮다."""
    texts = iter(["今使える밈としては럭키비키があります。", "今週は럭키비키が使えます。"])
    monkeypatch.setattr(briefing, "model_ready", lambda: True)
    monkeypatch.setattr(briefing, "structured", lambda *a, **k: (briefing.BriefingText(text=next(texts)), "gemini-x"))
    c = TestClient(api.app)
    assert c.get("/briefing", params={"regions": "KR", "lang": "ja"}).json()["summary"] is None
    assert c.get("/briefing", params={"regions": "KR", "lang": "ja"}).json()["summary"] == "今週は럭키비키が使えます。"


def test_briefing_summary_is_warmed_by_the_pipeline_and_shared_through_the_database(con, monkeypatch):
    """새로 뜬 API 의 첫 브리핑이 Gemini 를 기다려 30초 걸렸다(10-09). dashboard 단계가 기본 지역 요약을 미리 만들어 두고,
    새 인스턴스는 board_cache 에서 읽는다. 대시보드가 새로 만들어지면 옛 요약은 지운다."""
    calls = []

    def fake(_con, prompt, schema, **kw):
        calls.append(kw["request"])
        return briefing.BriefingText(text="warm summary"), "gemini-x"

    monkeypatch.setattr(briefing, "model_ready", lambda: True)
    monkeypatch.setattr(briefing, "structured", fake)
    dashboard.run(con)
    assert calls == [False, False]                                  # 한국어·영어, 파이프라인 장부로
    briefing._cache.clear()                                         # 새 인스턴스
    monkeypatch.setattr(briefing, "structured", lambda *a, **kw: pytest.fail("미리 만든 요약을 다시 부르면 안 된다"))
    body = TestClient(api.app).get("/briefing", params={"lang": "en"}).json()
    assert body["summary"] == "warm summary" and body["summary_source"] == "gemini"
    monkeypatch.setattr(briefing, "structured", fake)
    dashboard.run(con)
    assert con.execute("SELECT count(*) FROM board_cache WHERE key LIKE 'briefing%'").fetchone()[0] == 2   # 옛 갱신의 요약은 지운다


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


def test_copy_check_opinion_on_a_japanese_screen_is_japanese(con, monkeypatch):
    """로컬 Gemma 가 일본어 화면의 의견을 한국어로 썼다(10-13 시험) — 한 번 옮기고, 그래도 아니면 비운다. 판정(맞음·다름)은 그대로."""
    from trend_agents.pipeline import generate

    monkeypatch.setattr(copycheck, "model_ready", lambda: True)
    monkeypatch.setattr(copycheck, "structured", lambda *a, **k: (copycheck.FitResult(items=[copycheck.FitItem(term_id="fresh", fit="ok", note="긍정 상황에 맞게 썼다")]), "gemini-x"))
    replies = iter([generate._Lines(lines=["前向きな場面で正しく使われている"]), generate._Lines(lines=["그대로 한국어"])])
    monkeypatch.setattr(generate, "structured", lambda *a, **k: (next(replies), "gemini-x"))
    c = TestClient(api.app)
    first = c.post("/copy-check", json={"text": "실패해서 럭키비키", "region": "KR", "lang": "ja"}).json()["memes"][0]
    assert first["fit"] == "ok" and first["fit_note"] == "前向きな場面で正しく使われている"
    second = c.post("/copy-check", json={"text": "오늘도 럭키비키", "region": "KR", "lang": "ja"}).json()["memes"][0]
    assert second["fit"] == "ok" and second["fit_note"] is None


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
    assert c.get("/terms/warn/topic").json() is None
    assert c.get("/terms/nope/topic").status_code == 404
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


def test_predicate_headwords_match_their_inflected_forms():
    """'-다' 로 실린 서술어는 카피의 활용형으로도 찾는다 — '찰진 맛' 의 찰지다를 못 찾았다(10-05). 비슷한 다른 말은 걸지 않는다."""
    from trend_agents.pipeline.explain import match_terms
    from trend_agents.pipeline.match import predicate_forms

    def term(tid, name):
        return Term(term_id=tid, canonical=name, lang="ko", status="verified")

    terms = [term("chal", "찰지다"), term("jja", "짜치다"), term("yeol", "열받다"), term("ma", "마렵다"), term("pok", "폭룡적이다"),
             term("go", "고능하다"), term("case", "사건이다")]
    found = lambda text: [t.term_id for t in match_terms(text, terms)]   # noqa: E731
    assert found("찰진 맛에 열받네, 여행 마려운 폭룡적인 굿즈") == ["chal", "yeol", "ma", "pok"]
    assert found("짜쳤다 고능해") == ["jja", "go"]
    assert found("찰흙 놀이 짜증 나는 사건인데") == []                   # 다른 말·명사 + '이다' 는 그대로
    assert predicate_forms("디토합니다") is None and predicate_forms("가이다") is None
    from trend_agents.pipeline.match import text_pattern
    assert text_pattern("마렵다").search("여행 마려운 날").group(0) == "마려운"   # 화면 인용은 어미까지


def test_slim_dictionary_index_is_reused_until_the_data_changes(con):
    """사전 색인(slim)은 만들어 둔 JSON 을 다시 쓰고, 번역이 늘면(자료가 바뀌면) 다시 만든다."""
    from trend_agents.schemas import MeaningText

    c = TestClient(api.app)
    first = c.get("/terms", params={"slim": "true"}).json()
    row = next(r for r in first if r["term"]["term_id"] == "fresh")
    assert row["en"] is None and len(row["meanings"]) == 1 and row["weekly"] == [] and row["usage"] == []
    assert c.get("/terms", params={"slim": "true"}).content == c.get("/terms", params={"slim": "true"}).content
    ds.set_translation(con, "fresh", "en", MeaningText(definition="lucky vicky", origin="o", nuance="n"), "test")
    again = next(r for r in c.get("/terms", params={"slim": "true"}).json() if r["term"]["term_id"] == "fresh")
    assert again["en"]["definition"] == "lucky vicky"



def test_slim_dictionary_index_is_kept_in_the_database_for_a_cold_api(con, monkeypatch):
    """dashboard 단계가 만들어 둔 사전 색인을 새로 뜬 API 가 다시 만들지 않고 읽는다 – 운영 첫 요청이 21초였다(10-05).
    자료가 바뀌면(번역이 늘면) 옛 색인을 읽지 않는다."""
    from trend_agents.schemas import MeaningText

    dashboard.run(con)
    assert con.execute("SELECT count(*) FROM board_cache WHERE key LIKE 'term_index:%'").fetchone()[0] == 1
    built = views.term_index_json(con)
    views._INDEX.clear()                                           # 새 인스턴스
    monkeypatch.setattr(views, "term_records", lambda *a, **k: pytest.fail("색인을 다시 만들면 안 된다"))
    assert views.term_index_json(con) == built
    monkeypatch.undo()
    ds.set_translation(con, "fresh", "en", MeaningText(definition="lucky vicky", origin="o", nuance="n"), "test")
    assert b"lucky vicky" in views.term_index_json(con)
    assert con.execute("SELECT count(*) FROM board_cache WHERE key LIKE 'term_index:%'").fetchone()[0] == 1   # 옛 색인은 지운다


def test_hangul_fast_path_gives_the_same_answer_as_the_pattern():
    """mentions() 의 한글 빠른 길(_contains)은 정규식과 같은 답을 낸다 — 띄어쓰기 없는 한글 표기만 문자열 포함으로 본다(10-05)."""
    from trend_agents.pipeline.match import _contains, term_pattern

    texts = ["오늘 점메추 해줘", "MZ세대 밈", "mz세대가 좋아함", "원영적 사고 그 자체", "원영적사고", "ㅋㅋ 웃기다", "럭키 비키", "lucky vicky!"]
    cands = ["점메추", "MZ세대", "원영적 사고", "원영적사고", "ㅋㅋ", "럭키비키", "lucky vicky", "6-7"]
    for text in texts:
        for cand in cands:
            assert _contains(text, cand) == bool(term_pattern(cand).search(text)), (text, cand)


def test_entry_shows_how_its_meaning_was_made():
    """사전 항목의 '이렇게 만들었어요'(views.provenance): 초안 모델·참고 문서·확인·감사·리스크 분류 수를 기록에서만 읽는다(10-05)."""
    from datetime import datetime, timezone

    from trend_agents.schemas import Evidence, MeaningDraft
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="찰지다", lang="ko", status="verified", first_seen=now, last_seen=now))
    m = ds.add_meaning(con, "t1", MeaningDraft(definition="맛깔나고 착 붙는다", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                               self_confidence=0.9), "verified_auto", [])
    ds.log_research(con, "t1", "offline:local", "", [], "verified_auto", [])
    ds.add_evidences(con, "t1", [Evidence(evidence_id="w1", kind="wiki", url="https://namu.wiki/w/찰지다", title="찰지다 - 나무위키",
                                          source_domain="namu.wiki", observed_at=now, excerpt="찰지다")])
    ds.set_evidence_labels(con, "t1", [("w1", "positive", "none")], "local:gemma4:e4b")
    con.execute("INSERT INTO audit_log VALUES (?,?,?,?,?,?,?)", ("t1", m.meaning_id, now.isoformat(), "ok", "[]", "local:gemma4:12b", "ok"))
    con.commit()
    t = ds.get_term(con, "t1")
    r = views.term_record(con, t)
    p = views.provenance(con, t, r.meanings, r.evidences)
    assert (p.drafted_by, p.reference, p.checked, p.audit, p.audit_by, p.risk_sentences, p.risk_by) == \
        ("gemma", "namu.wiki", "rules", "ok", "gemma", 1, "gemma")
    ds.set_verification(con, m.meaning_id, "verified_human", "reviewer")
    con.commit()
    r = views.term_record(con, t)
    assert views.provenance(con, t, r.meanings, r.evidences).checked == "person"
    assert views.term_records(con, slim=True)[0].provenance is None        # 사전 색인에는 없다
