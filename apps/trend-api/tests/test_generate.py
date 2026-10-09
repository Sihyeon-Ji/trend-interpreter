"""콘텐츠 생성(Plan 08) — 모델 호출 수·규칙 검사에 걸린 안 빼기·지역과 말. 모델은 가짜로 바꿔 끼운다."""
from datetime import datetime, timezone

import pytest

from trend_agents.pipeline import generate
from trend_agents.schemas import ContentDraft, MeaningDraft, ProductBrief, ScriptScene, ShortScript, SocialCopy, Term, ThumbnailPlan
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

BRIEF = ProductBrief(product="아이스 라떼", category="food_drink", feelings=["joy"], values=["시원함"], scene="카페")


@pytest.fixture(autouse=True)
def _no_local_model(monkeypatch):
    """시험은 이 서버의 USE_LOCAL_GEMMA 와 상관없이 돈다 — 모델 경로를 보는 시험은 스스로 다시 바꾼다."""
    monkeypatch.setattr(generate, "USE_LOCAL_GEMMA", False)


def _con():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name, risk, aliases in (("lv", "럭키비키", "none", ["ラッキービッキー"]), ("bad", "나쁜말", "avoid", [])):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, aliases=aliases, lang="ko", status="verified", first_seen=now, last_seen=now))
        ds.set_risk(con, tid, risk, [], now)
        ds.add_meaning(con, tid, MeaningDraft(definition="나쁜 상황도 좋게 보는 말", origin="x", nuance="긍정", generations=["20s"], regions=["KR"],
                                              self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, "lv", [("20s", "KR", now.isoformat(), 0.5), ("20s", "JP", now.isoformat(), 0.5)])
    ds.upsert_term(con, Term(term_id="kronly", canonical="오살힘", lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.set_usage(con, "kronly", [("20s", "KR", now.isoformat(), 1.0)])
    # 일본에서도 쓴다고 조사됐지만 한글 표기뿐인 밈 — 일본어 카피에 그대로 넣을 수 없다
    ds.upsert_term(con, Term(term_id="hangul", canonical="건어물녀", lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.set_usage(con, "hangul", [("all", "KR", now.isoformat(), 0.5), ("all", "JP", now.isoformat(), 0.5)])
    return con


def _draft(copy_text: str, x_text: str = "럭키비키 오후") -> ContentDraft:
    return ContentDraft(
        copies=[SocialCopy(platform="instagram", text=copy_text), SocialCopy(platform="instagram", text="럭키비키 한 잔"),
                SocialCopy(platform="x", text=x_text), SocialCopy(platform="x", text="오늘도 럭키비키")],
        script=ShortScript(title="럭키비키", duration_s=15, scenes=[ScriptScene(start_s=0, end_s=15, visual="라떼", caption="럭키비키")]),
        thumbnail=ThumbnailPlan(headline="럭키비키", layout="왼쪽 제품", colors=["갈색"]))


def _fake(monkeypatch, drafts: list):
    """drafts 의 항목을 차례로 돌려준다. 예외 인스턴스면 그것을 던진다."""
    calls = []

    def structured(con, prompt, schema, **kw):
        calls.append((schema, prompt))
        got = drafts.pop(0)
        if isinstance(got, Exception):
            raise got
        return got, "gemini-test"

    monkeypatch.setattr(generate, "structured", structured)
    monkeypatch.setattr(generate, "configured", lambda: True)
    return calls


def test_one_model_call_when_everything_passes(monkeypatch):
    """요청 때 모델은 생성 한 번 — 검사는 규칙이 한다(2026-09-28 Gemma 로컬 편집 결정, Plan 08 완료 기준)."""
    con = _con()
    calls = _fake(monkeypatch, [_draft("여름엔 럭키비키")])
    res = generate.run(con, ["lv"], BRIEF, "KR", "friendly")
    assert len(calls) == 1 and res.model_calls == 1
    assert len(res.copies) == 4 and res.script and res.thumbnail and not res.dropped
    assert res.language == "ko" and res.memes == ["럭키비키"]


def test_failed_items_are_regenerated_once_then_dropped(monkeypatch):
    """규칙에 걸린 안은 문제를 적어 한 번 다시 만들고, 또 걸리면 빼고 이유(코드)를 남긴다. 호출은 두 번을 넘지 않는다."""
    con = _con()
    calls = _fake(monkeypatch, [_draft("밈 없는 카피"), _draft("여전히 없는 카피")])
    res = generate.run(con, ["lv"], BRIEF, "KR", "friendly")
    assert len(calls) == 2 and res.model_calls == 2
    assert "copy0" in calls[1][1] and "고른 밈이 글에 없음" in calls[1][1]          # 다시 만들 때 문제를 알려 준다
    assert [(d.id, d.code) for d in res.dropped] == [("copy0", "no_meme")]
    assert len(res.copies) == 3 and res.script and res.thumbnail                   # 걸린 안만 빠진다


def test_second_draft_fixes_are_kept(monkeypatch):
    con = _con()
    _fake(monkeypatch, [_draft("밈 없는 카피"), _draft("今日もラッキービッキー!")])
    res = generate.run(con, ["lv"], BRIEF, "JP", "witty")
    assert not res.dropped and res.copies[0].text == "今日もラッキービッキー!" and res.language == "ja"


def test_regeneration_failure_keeps_what_already_passed(monkeypatch):
    """다시 만들기가 실패해도(예산·장애·형식 오류) 첫 안에서 통과한 것은 돌려준다 — 통째로 503 이 났다(검토 3차)."""
    con = _con()
    _fake(monkeypatch, [_draft("밈 없는 카피"), generate.Unavailable("지금은 결과물을 만들지 못했습니다")])
    res = generate.run(con, ["lv"], BRIEF, "KR", "friendly")
    assert len(res.copies) == 3 and res.script and res.thumbnail
    assert [(d.id, d.code) for d in res.dropped] == [("copy0", "no_meme")] and res.model_calls == 2


def test_rules():
    con = _con()
    lv = [ds.get_term(con, "lv")]
    brief = BRIEF.model_copy(update={"avoid": ["다이어트"]})
    got = generate.check({"copy0": SocialCopy(platform="x", text="씨발 럭키비키"), "copy1": SocialCopy(platform="x", text="아무 말"),
                          "copy2": SocialCopy(platform="x", text="럭키비키 " + "가" * 140),
                          "copy3": SocialCopy(platform="instagram", text="럭키비키 다이어트 라떼")}, lv, brief)
    assert {k: v[0] for k, v in got.items()} == {"copy0": "unsafe", "copy1": "no_meme", "copy2": "x_too_long", "copy3": "avoid_word"}
    with pytest.raises(ValueError):
        generate.run(con, ["bad"], BRIEF, "KR", "friendly")                    # 사용 자제 밈으로는 만들지 않는다


def test_rules_catch_copy_that_talks_about_the_meme():
    """밈을 쓰지 않고 소개·비교한 카피는 뺀다 — 사람 판정(10-09)에서 'Know Your Meme 에 검색하면'·'『いまいち萌えない娘』みたいな' 가 못 쓸 카피였다.
    문장 속 말로 쓰거나 해시태그에만 넣은 것은 통과한다."""
    con = _con()
    lv = [ds.get_term(con, "lv")]
    got = generate.check({"copy0": SocialCopy(platform="x", text="오늘 라떼는 '럭키비키'처럼 상큼해요"),
                          "copy1": SocialCopy(platform="x", text="Tastes just like 럭키비키 vibes"),
                          "copy2": SocialCopy(platform="x", text="비 와도 라떼 한 잔이면 완전 럭키비키잖아"),
                          "copy3": SocialCopy(platform="instagram", text="더운 오후엔 라떼 한 잔", hashtags=["럭키비키"])}, lv, BRIEF)
    assert {k: v[0] for k, v in got.items()} == {"copy0": "meta_meme", "copy1": "meta_meme"}


def test_x_length_counts_cjk_as_two_and_includes_hashtags():
    assert generate.x_length("a" * 280) == 280 and generate.x_length("가" * 140) == 280
    assert generate.x_length("สวัสดี") == 6                                      # 태국 글자는 1
    copy = SocialCopy(platform="x", text="럭키비키 " + "가" * 135, hashtags=["여름한정"])      # 본문 279 + 해시태그 11
    assert generate.copy_text(copy).endswith("\n\n#여름한정") and generate.x_length(generate.copy_text(copy)) > 280


def test_sample_only_when_nothing_is_configured(monkeypatch):
    """예시는 모델이 아예 설정되지 않은 개발 환경에서만 — 설정된 모델이 꺼져 있으면 남의 제품 카피 대신 오류로 알린다(검토 3차)."""
    con = _con()
    monkeypatch.setattr(generate, "configured", lambda: False)
    res = generate.run(con, ["lv", "bad"], BRIEF, "KR", "friendly")
    assert res.source == "sample" and res.model_calls == 0 and res.memes == ["럭키비키"] and res.language == "ko"

    monkeypatch.setattr(generate, "USE_LOCAL_GEMMA", True)

    def down(*a, **k):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(generate, "structured", down)
    with pytest.raises(generate.Unavailable):
        generate.run(con, ["lv"], BRIEF, "KR", "friendly")


def test_generate_api_rejects_non_target_regions_and_big_bodies(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(generate, "configured", lambda: False)
    c = TestClient(api.app)
    body = {"term_ids": ["t_x"], "brief": BRIEF.model_dump(), "region": "US", "tone": "friendly"}
    assert c.post("/generate", json=body).status_code == 400
    assert c.post("/generate", json={**body, "term_ids": []}).status_code == 422
    huge = {**body, "region": "KR", "brief": {**BRIEF.model_dump(), "product": "x" * 20000}}
    assert c.post("/generate", json=huge).status_code == 413                  # 제품 설명을 브라우저에서 다시 받는다 — 몸통 크기를 먼저 막는다


def test_brief_text_is_clipped():
    b = ProductBrief(product="x" * 1000, category="food_drink", feelings=["joy"], scene="y" * 1000)
    assert len(b.product) == 120 and len(b.scene) == 200


def test_prefer_gemini_does_not_fall_into_the_local_text_path(monkeypatch):
    """생성은 Gemini 가 맡는다 — 로컬 Gemma 가 켜져 있어도 prefer_gemini 면 Gemini 를 부르고 구조화 결과(.parsed)를 돌려준다.
    (문자열 프롬프트는 generate() 가 로컬로 돌리던 탓에 .parsed 가 없어 실패했다, 2026-09-29)"""
    from types import SimpleNamespace

    from trend_agents.pipeline import gemini

    con = db.connect(":memory:")
    seen = {}

    class Models:
        def generate_content(self, model, contents, config):
            seen["model"] = model
            return SimpleNamespace(parsed={"ok": True})

    monkeypatch.setattr(gemini, "client", lambda: SimpleNamespace(models=Models()))
    monkeypatch.setattr(gemini, "configured", lambda: True)
    monkeypatch.setattr(gemini, "local_ok", lambda: True)
    parsed, used = gemini.structured(con, "prompt", dict, prefer_gemini=True)
    assert parsed == {"ok": True} and used == seen["model"] and not used.startswith("local")


def test_user_requests_do_not_wait_and_rejected_attempts_are_refunded(monkeypatch):
    """이용자 요청은 모델마다 한 번만, 기다리지 않고, 429·503 으로 거절된 시도는 장부에서 돌려놓는다 — 503 이 몰리면 요청 하나가
    하루 몫(12)의 절반을 썼다(검토 3차). 로컬 Gemma 가 있으면 그쪽으로 넘어가고, 없으면 오류를 그대로 낸다."""
    from types import SimpleNamespace

    from google.genai import errors

    from trend_agents.pipeline import gemini

    con = db.connect(":memory:")
    tries = []

    class Models:
        def generate_content(self, model, contents, config):
            tries.append(model)
            raise errors.APIError(503, {"error": {"message": "overloaded"}})

    monkeypatch.setattr(gemini, "client", lambda: SimpleNamespace(models=Models()))
    monkeypatch.setattr(gemini, "configured", lambda: True)
    monkeypatch.setattr(gemini, "local_ok", lambda: False)
    monkeypatch.setattr(gemini.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("기다리면 안 됨")))
    before = gemini.budget_left(con, request=True)
    with pytest.raises(errors.APIError):
        gemini.structured(con, "prompt", dict, prefer_gemini=True, request=True)
    assert len(tries) == 2 and gemini.budget_left(con, request=True) == before   # 기본 모델·폴백 한 번씩, 장부는 그대로

    from trend_agents.pipeline import local_llm

    monkeypatch.setattr(gemini, "local_ok", lambda: True)
    monkeypatch.setattr(local_llm, "structured", lambda *a, **k: {"from": "local"})
    assert gemini.structured(con, "prompt", dict, prefer_gemini=True, request=True)[0] == {"from": "local"}


def test_only_memes_writable_in_the_target_region(monkeypatch):
    """그 지역에서 쓰이고, 그 말로 쓴 글에 그대로 넣을 표기가 있는 밈만 — 한국 밈을 일본 카피에 넣으면 가타카나로 옮겨 적어
    읽히지도 검사를 통과하지도 않았다(2026-09-29 실측, 검토 3차: 일본에서도 쓴다고 조사된 한글 표기 밈)."""
    con = _con()
    _fake(monkeypatch, [_draft("今日もラッキービッキー")])
    with pytest.raises(ValueError):
        generate.run(con, ["kronly"], BRIEF, "JP", "friendly")                  # 일본에서 쓰이지 않는다
    with pytest.raises(ValueError):
        generate.run(con, ["hangul"], BRIEF, "JP", "friendly")                  # 쓰이지만 일본어로 쓸 표기가 없다
    res = generate.run(con, ["kronly", "hangul", "lv"], BRIEF, "JP", "friendly")
    assert res.memes == ["럭키비키"]                                              # 가타카나 별칭이 있다
    assert generate.writable(ds.get_term(con, "hangul"), "KR", {"KR", "JP"})
    # 영어권(GLOBAL, Plan 20): 로마자 표기가 있고 영어권에서 쓰이는 말만
    assert generate.REGION_LANG["GLOBAL"] == "en"
    assert not generate.writable(ds.get_term(con, "hangul"), "GLOBAL", {"KR", "GLOBAL"})


def test_caution_line_never_quotes_evidence(monkeypatch):
    """'쓸 때 조심' 은 사전 뜻풀이의 주의점과 위험 유형으로만 — 검수 화면용 이유는 남의 글을 인용해 생성 프롬프트에 들어갔다(검토 3차).
    검수자가 정한 주의는 그 결정을 그대로 전한다."""
    con = _con()
    t = ds.get_term(con, "lv")
    t.risk_level, t.risk_reasons = "caution", ["위험 유형이 붙은 근거 2건: “…남의 글 인용…” (bsky.app)"]
    note = generate.caution_note(con, t)
    assert "남의 글" not in note and "쓰지 말 것" in note
    t.risk_human = "caution"
    assert "검수자" in generate.caution_note(con, t)


def test_explanations_follow_the_screen_language(monkeypatch):
    """설명 칸이 화면 언어가 아니면 비운다 — 영어 화면에 한국어 설명이 나왔다(검토 3차). 밈 이름·인용은 빼고 본다."""
    con = _con()
    lv = [ds.get_term(con, "lv")]
    d = _draft("여름엔 럭키비키")
    d.copies[0].note_ko, d.copies[1].note_ko = "밈을 기분 전환에 붙였다", "Uses '럭키비키' as a cheerful twist"
    d.thumbnail.layout, d.thumbnail.colors = "왼쪽 제품", ["brown", "갈색"]
    out = generate._explanations_in_ui_language(d, "en", lv)
    assert out.copies[0].note_ko == "" and out.copies[1].note_ko.startswith("Uses")
    assert out.thumbnail.layout == "" and out.thumbnail.colors == ["brown"]
    assert out.copies[0].text == "여름엔 럭키비키"                                 # 결과물 본문(목표 지역의 말)은 건드리지 않는다


def test_hashtags_are_single_tokens():
    """해시태그는 공백·기호에서 끊긴다 — '#aura farming' 은 #aura 만 걸렸다(검토 3차). 태국어 모음 부호(결합 부호)는 남긴다."""
    c = SocialCopy(platform="instagram", text="x", hashtags=["#aura farming", "6-7", " 여름 한정 ", "ที่นี่", "여름한정", "😀"])
    assert c.hashtags == ["aurafarming", "67", "여름한정", "ที่นี่"]


def test_draft_shape_is_repaired_when_thumbnail_lands_inside_script():
    """작은 모델이 thumbnail 을 script 안에, script 의 note_ko 를 장면 목록 끝에 넣었다(2026-09-29 로컬 Gemma 18번 중 7번). 모양만 바로잡는다."""
    raw = {"copies": [{"platform": "x", "text": "럭키비키"}],
           "script": {"title": "t", "duration_s": 15, "scenes": [{"start_s": 0, "end_s": 15, "visual": "v"}, {"note_ko": "대본 설명"}],
                      "thumbnail": {"headline": "h", "layout": "l"}}}
    d = ContentDraft.model_validate(raw)
    assert d.thumbnail.headline == "h" and len(d.script.scenes) == 1 and d.script.note_ko == "대본 설명"


def test_model_chain_skips_models_closed_for_the_day(monkeypatch):
    """무료 몫은 모델마다 따로 — 그날 끝난 모델(429 PerDay)은 건너뛰고 다음 모델로, 검색 grounding 이 닫히면 모델을 바꿔도 시도하지 않는다."""
    from types import SimpleNamespace

    from google.genai import errors, types

    from trend_agents.pipeline import gemini

    con = db.connect(":memory:")
    tries = []

    class Models:
        def generate_content(self, model, contents, config):
            tries.append(model)
            if model == "gemini-3.8-flash":
                raise errors.APIError(429, {"error": {"message": "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"}})
            if config and config.tools:
                raise errors.APIError(429, {"error": {"message": "You exceeded your current quota"}})
            return SimpleNamespace(text="ok")

    monkeypatch.setattr(gemini, "client", lambda: SimpleNamespace(models=Models()))
    monkeypatch.setattr(gemini, "local_ok", lambda: False)
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    monkeypatch.setattr(gemini, "_busy", {})          # 앞 시험의 503 쉬는 시간이 남지 않게
    _, used = gemini.generate(con, "hi", model="gemini-3.8-flash")
    assert used == "gemini-3.7-flash" and tries == ["gemini-3.8-flash", "gemini-3.7-flash"]
    assert "gemini-3.8-flash" not in gemini.models(con)                                   # 그날은 다시 고르지 않는다
    search = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    with pytest.raises(gemini.BudgetExhausted):
        gemini.generate(con, "hi", search)
    n = len(tries)
    with pytest.raises(gemini.BudgetExhausted):
        gemini.generate(con, "hi", search)
    assert len(tries) == n and gemini.models(con, grounded=True) == []                    # 닫힌 grounding 은 부르지 않는다



def test_capacity_errors_move_on_without_retrying(monkeypatch):
    """503 은 같은 모델로 다시 두드리지 않는다 — 재시도가 분당 몫을 채웠다(AI Studio 3.8 RPM 5/5, 10-01)."""
    from types import SimpleNamespace

    from google.genai import errors

    from trend_agents.pipeline import gemini

    con = db.connect(":memory:")
    tries = []

    class Models:
        def generate_content(self, model, contents, config):
            tries.append(model)
            if model == "gemini-3.8-flash":
                raise errors.APIError(503, {"error": {"message": "high demand"}})
            return SimpleNamespace(text="ok")

    monkeypatch.setattr(gemini, "client", lambda: SimpleNamespace(models=Models()))
    monkeypatch.setattr(gemini, "local_ok", lambda: False)
    monkeypatch.setattr(gemini, "_busy", {})
    monkeypatch.setattr(gemini.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("기다리면 안 됨")))
    assert gemini.generate(con, "hi")[1] == "gemini-3.7-flash" and tries == ["gemini-3.8-flash", "gemini-3.7-flash"]
    assert gemini.models(con)[-1] == "gemini-3.8-flash"                      # 쉬는 동안은 맨 뒤
