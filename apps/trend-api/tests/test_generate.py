"""콘텐츠 생성(Plan 08) — 모델 호출 수·검사에 걸린 안 빼기·규칙 검사. 모델은 가짜로 바꿔 끼운다."""
from datetime import datetime, timezone

import pytest

from trend_agents.pipeline import generate
from trend_agents.schemas import ContentDraft, DraftCheck, MeaningDraft, ProductBrief, ScriptScene, ShortScript, SocialCopy, Term, ThumbnailPlan
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

BRIEF = ProductBrief(product="아이스 라떼", category="food_drink", feelings=["joy"], values=["시원함"], scene="카페")


def _con():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name, risk in (("lv", "럭키비키", "none"), ("bad", "나쁜말", "avoid")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now))
        ds.set_risk(con, tid, risk, [], risk, now)
        ds.add_meaning(con, tid, MeaningDraft(definition="나쁜 상황도 좋게 보는 말", origin="x", nuance="긍정", generations=["20s"], regions=["KR"],
                                              self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, "lv", [("20s", "KR", now.isoformat(), 0.5), ("20s", "JP", now.isoformat(), 0.5)])
    ds.upsert_term(con, Term(term_id="kronly", canonical="오살힘", lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.set_usage(con, "kronly", [("20s", "KR", now.isoformat(), 1.0)])
    return con


def _draft(copy_text: str) -> ContentDraft:
    return ContentDraft(
        copies=[SocialCopy(platform="instagram", text=copy_text), SocialCopy(platform="instagram", text="럭키비키 한 잔"),
                SocialCopy(platform="x", text="럭키비키 오후"), SocialCopy(platform="x", text="오늘도 럭키비키")],
        script=ShortScript(title="럭키비키", duration_s=15, scenes=[ScriptScene(start_s=0, end_s=15, visual="라떼", caption="럭키비키")]),
        thumbnail=ThumbnailPlan(headline="럭키비키", layout="왼쪽 제품", colors=["갈색"]))


def _fake(monkeypatch, drafts: list[ContentDraft], checks: list[list[DraftCheck]]):
    calls = []

    def structured(con, prompt, schema, **kw):
        calls.append(schema)
        if schema is ContentDraft:
            return drafts.pop(0), "gemini-test"
        return checks.pop(0), "local:test"

    monkeypatch.setattr(generate, "structured", structured)
    monkeypatch.setattr(generate, "configured", lambda: True)
    monkeypatch.setattr(generate, "local_ok", lambda: True)
    return calls


def test_two_model_calls_when_everything_passes(monkeypatch):
    con = _con()
    calls = _fake(monkeypatch, [_draft("여름엔 럭키비키")], [[]])
    res = generate.run(con, ["lv"], BRIEF, "KR", "friendly")
    assert len(calls) == 2 and res.model_calls == 2
    assert len(res.copies) == 4 and res.script and res.thumbnail and not res.dropped
    assert res.language == "ko" and res.memes == ["럭키비키"]


def test_failed_items_are_regenerated_once_then_dropped(monkeypatch):
    """규칙(밈이 글에 없음)과 모델 검사에 걸린 안은 한 번 다시 만들고, 또 걸리면 빼고 이유를 남긴다. 호출은 네 번을 넘지 않는다."""
    con = _con()
    bad_script = [DraftCheck(id="script", ok=False, problem="긍정의 말을 조롱으로 씀")]
    calls = _fake(monkeypatch, [_draft("밈 없는 카피"), _draft("여전히 없는 카피")], [bad_script, bad_script])
    res = generate.run(con, ["lv"], BRIEF, "KR", "friendly")
    assert len(calls) == 4 and res.model_calls == 4
    assert {d.id for d in res.dropped} == {"copy0", "script"}
    assert res.script is None and len(res.copies) == 3                       # 걸린 안은 화면에 나오지 않는다
    assert any("조롱" in d.reason for d in res.dropped) and any("밈이 글에 없음" in d.reason for d in res.dropped)


def test_second_draft_fixes_are_kept(monkeypatch):
    con = _con()
    _fake(monkeypatch, [_draft("밈 없는 카피"), _draft("이번엔 럭키비키!")], [[], []])
    res = generate.run(con, ["lv"], BRIEF, "JP", "witty")
    assert not res.dropped and res.copies[0].text == "이번엔 럭키비키!" and res.language == "ja"


def test_rules_and_inputs():
    con = _con()
    probs = generate.rule_problems({"copy0": SocialCopy(platform="x", text="씨발 럭키비키"), "copy1": SocialCopy(platform="x", text="아무 말")},
                                   [ds.get_term(con, "lv")])
    assert probs == {"copy0": "욕설·선정 표현이 들어 있음", "copy1": "고른 밈이 글에 없음"}
    with pytest.raises(ValueError):
        generate.run(con, ["bad"], BRIEF, "KR", "friendly")                    # 사용 자제 밈으로는 만들지 않는다


def test_sample_without_any_model(monkeypatch):
    con = _con()
    monkeypatch.setattr(generate, "configured", lambda: False)
    monkeypatch.setattr(generate, "local_ok", lambda: False)
    res = generate.run(con, ["lv", "bad"], BRIEF, "KR", "friendly")
    assert res.source == "sample" and res.model_calls == 0 and res.memes == ["럭키비키"]


def test_generate_api_rejects_non_target_regions(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(generate, "configured", lambda: False)
    monkeypatch.setattr(generate, "local_ok", lambda: False)
    c = TestClient(api.app)
    body = {"term_ids": ["t_x"], "brief": BRIEF.model_dump(), "region": "US", "tone": "friendly"}
    assert c.post("/generate", json=body).status_code == 400
    assert c.post("/generate", json={**body, "term_ids": []}).status_code == 422


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


def test_only_memes_used_in_the_target_region(monkeypatch):
    """한국에서만 쓰는 밈으로 일본 카피를 만들지 않는다 — 가타카나로 옮겨 적어 읽히지도, 검사를 통과하지도 않았다(2026-09-29 실측)."""
    con = _con()
    _fake(monkeypatch, [_draft("여름엔 럭키비키")], [[]])
    with pytest.raises(ValueError):
        generate.run(con, ["kronly"], BRIEF, "JP", "friendly")
    res = generate.run(con, ["kronly", "lv"], BRIEF, "JP", "friendly")
    assert res.memes == ["럭키비키"]

