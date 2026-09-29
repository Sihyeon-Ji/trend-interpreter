"""밈 추천(Plan 07) — 후보·순위·이유 거르기는 규칙이다. 모델 없이 인메모리 DB 로."""
from datetime import datetime, timezone

import pytest

from trend_agents.pipeline import dashboard, recommend
from trend_agents.schemas import Evidence, MeaningDraft, MemeFit, ProductBrief, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

@pytest.fixture(autouse=True)
def _no_models(monkeypatch):
    """시험은 모델을 부르지 않는다 — 이 서버처럼 로컬 Gemma 가 떠 있으면 이유 쓰기가 실제로 돌아 느리고 결과가 흔들렸다.
    모델 경로를 보는 시험은 스스로 다시 바꾼다."""
    monkeypatch.setattr(recommend, "configured", lambda: False)
    monkeypatch.setattr(recommend, "USE_LOCAL_GEMMA", False)


LATTE = ProductBrief(product="아이스 라떼", category="food_drink", feelings=["joy", "comfort"], values=["시원함"], scene="카페")


def _term(con, tid, name, feelings, voice="wholesome", fits=(), any_category=True, lifecycle="steady", risk="none", diffusion="mainstream"):
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", lifecycle=lifecycle, first_seen=now, last_seen=now,
                             risk_level=risk, diffusion=diffusion))
    m = ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 은 기분 좋은 하루를 뜻하는 말", origin="x", nuance="y", generations=["20s"],
                                              regions=["KR"], self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, tid, [("20s", "KR", now.isoformat(), 1.0)])
    # 추천은 근거 링크가 있어야 나간다(ADR 0001) — 쓰임 기사 하나씩. 커뮤니티 글은 링크가 되지 않는다(ADR 0003)
    ds.add_evidences(con, tid, [Evidence(evidence_id=f"e_{tid}", kind="news", url=f"https://news.example/{tid}", title=f"{name} 기사",
                                         source_domain="news.example", observed_at=now, excerpt=f"{name} 진짜")])
    cur = ds.current_meaning(con, tid)
    ds.set_fit(con, tid, cur.meaning_id, MemeFit(feelings=list(feelings), uses=["reaction"], fits=list(fits), any_category=any_category, voice=voice), "test")
    return m


def _con():
    con = db.connect(":memory:")
    _term(con, "good", "좋은말", ["joy", "comfort"], fits=["food_drink"])
    _term(con, "ok", "무난한말", ["joy"])
    _term(con, "bad", "나쁜말", ["joy", "comfort"], fits=["food_drink"], risk="avoid")
    _term(con, "crude", "저속한말", ["joy", "comfort"], voice="crude")
    _term(con, "edgy", "비꼬는말", ["joy", "comfort"], voice="edgy")
    _term(con, "dead", "옛날말", ["joy"], lifecycle="dormant", diffusion="fading")
    _term(con, "nofit", "상관없는말", ["tired"], any_category=False)
    dashboard.run(con)
    return con


def test_rules_exclude_avoid_crude_off_tone_and_weak_fits():
    con = _con()
    got = [i.term_id for i in recommend.recommend(con, LATTE, "sample", ["KR"], "friendly").items]
    assert got[:2] == ["good", "ok"]                                  # 분야까지 맞는 것이 먼저
    assert not {"bad", "crude", "edgy", "dead", "nofit"} & set(got)    # 사용 자제·저속·톤 밖(비꼼)·잠잠·안 맞음은 안 나온다
    witty = [i.term_id for i in recommend.recommend(con, LATTE, "sample", ["KR"], "witty").items]
    assert "edgy" in witty and "bad" not in witty and "crude" not in witty
    premium = recommend.recommend(con, LATTE, "sample", ["KR"], "premium")
    assert all(i.term_id in ("good", "ok") for i in premium.items)   # 무난한 말투만


def test_top_five_and_explained_matches():
    con = db.connect(":memory:")
    for k in range(8):
        _term(con, f"t{k}", f"말{k}", ["joy"])
    dashboard.run(con)
    res = recommend.recommend(con, LATTE, "sample", ["KR"], "friendly")
    assert len(res.items) == recommend.TOP and res.considered == 8
    assert res.items[0].matched_feelings == ["joy"] and res.items[0].any_category and not res.items[0].matched_category


def test_reasons_come_from_stored_data_without_a_model(monkeypatch):
    """추천 이유는 모델이 쓰지 않는다 — 게시된 사전 뜻·그 나라의 국가별 해석(확신 0.5 이상)·겹친 낱말로 화면이 구성한다
    (2026-09-28 Gemma 로컬 편집 결정, Plan 07 5번). 추천하는 동안 모델을 한 번도 부르지 않는다."""
    import json

    con = _con()
    ds.set_usage(con, "good", [("20s", "TW", datetime.now(timezone.utc).isoformat(), 0.3)])
    ds.set_topic_note(con, "good", "TW", json.dumps({"what_changed": {"ko": "대만 팬 커뮤니티에서 응원 문구로 쓴다", "en": "Fans in Taiwan use it as a cheer"},
                                                    "self_confidence": 0.7}), "test")
    ds.set_topic_note(con, "good", "KR", json.dumps({"what_changed": {"ko": "근거 부족", "en": "Insufficient"}, "self_confidence": 0.2}), "test")
    dashboard.run(con)
    monkeypatch.setattr(recommend, "structured", lambda *a, **k: (_ for _ in ()).throw(AssertionError("모델을 부르면 안 됨")))
    got = {i.term_id: i for i in recommend.recommend(con, LATTE, "sample", ["KR", "TW"], "friendly").items}
    assert got["good"].local_region == "TW" and got["good"].local_note.ko.startswith("대만")      # 확신이 낮은 한국 해석은 건너뛴다
    assert got["ok"].local_note is None and got["good"].matched_category and got["good"].matched_feelings == ["joy", "comfort"]


def test_links_prefer_usage_and_never_repeat_a_url():
    """근거 링크 두 건 — 쓰임 글이 먼저, 같은 주소는 한 번만(위키백과 문서가 web·wiki 로 두 번 들어와 같은 링크가 둘 나왔다, 검토 3차).
    커뮤니티·SNS 글은 더 최근이어도 링크로 나가지 않는다(ADR 0003)."""
    con = _con()
    now = datetime.now(timezone.utc)
    url = "https://ko.wikipedia.org/wiki/%EC%A2%8B%EC%9D%80%EB%A7%90"
    ds.add_evidences(con, "good", [Evidence(evidence_id="w1", kind="web", url=url, title="Wikipedia: 좋은말", source_domain="ko.wikipedia.org", observed_at=now, excerpt="좋은말은"),
                                   Evidence(evidence_id="w2", kind="wiki", url=url, title="좋은말", source_domain="wikipedia.org", observed_at=now, excerpt="좋은말은"),
                                   Evidence(evidence_id="c1", kind="community", url="https://theqoo.net/good", title="좋은말 글", source_domain="theqoo.net",
                                            observed_at=now, excerpt="좋은말 진짜"),
                                   Evidence(evidence_id="c2", kind="web", url="https://bsky.app/profile/a/post/1", title="좋은말 ㅋㅋ", source_domain="bsky.app",
                                            observed_at=now, excerpt="좋은말 ㅋㅋ")])
    dashboard.run(con)
    item = next(i for i in recommend.recommend(con, LATTE, "sample", ["KR"], "friendly").items if i.term_id == "good")
    assert [e.url for e in item.evidences] == ["https://news.example/good", url]


def test_write_regions_need_a_form_written_in_that_language():
    """결과물 지역 선택지는 그 지역에서 쓰이고 그 말의 글자(또는 로마자)로 쓴 표기가 있는 곳만 — 한글 표기뿐인 밈으로 일본어 카피를 만들지 않는다."""
    con = _con()
    now = datetime.now(timezone.utc)
    ds.set_usage(con, "good", [("20s", "JP", now.isoformat(), 0.2)])
    dashboard.run(con)
    item = next(i for i in recommend.recommend(con, LATTE, "sample", ["KR", "JP"], "friendly").items if i.term_id == "good")
    assert set(item.regions) >= {"KR", "JP"} and item.write_regions == ["KR"]


def test_sample_brief_only_when_no_model_is_configured(monkeypatch):
    con = db.connect(":memory:")
    monkeypatch.setattr(recommend, "USE_LOCAL_GEMMA", False)   # 이 서버의 .env 와 상관없이 '아무 모델도 설정되지 않음'
    monkeypatch.setattr(recommend, "configured", lambda: False)
    assert recommend.understand(con, "아무 문구") == (recommend.SAMPLE_BRIEF, "sample")

    monkeypatch.setattr(recommend, "configured", lambda: True)

    def broken(*a, **k):
        raise RuntimeError("503")

    monkeypatch.setattr(recommend, "structured", broken)
    with pytest.raises(recommend.Unavailable):            # 모델이 있는데 실패하면 남의 예시로 추천하지 않는다
        recommend.understand(con, "아무 문구")


def test_image_type_is_read_from_bytes_and_rate_is_limited():
    assert recommend.sniff_image(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert recommend.sniff_image(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert recommend.sniff_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert recommend.sniff_image(b"GIF89a") is None and recommend.sniff_image(b"<svg") is None
    lim = recommend.RateLimit(per_minute=2)
    assert lim.allow(0) and lim.allow(1) and not lim.allow(2) and lim.allow(61)


def test_recommend_api_checks_input_before_any_model_call(monkeypatch):
    """크기·형식·빈 입력은 모델을 부르기 전에 막고, 사진은 바이트 머리로 형식을 본다."""
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", _con())
    monkeypatch.setattr(recommend, "USE_LOCAL_GEMMA", False)
    monkeypatch.setattr(recommend, "configured", lambda: False)     # 모델 없는 개발 환경 → 고정 예시 설명
    c = TestClient(api.app)
    assert c.post("/recommend", data={"text": ""}).status_code == 400
    assert c.post("/recommend", data={"text": "가" * 501}).status_code == 400
    assert c.post("/recommend", data={"text": "라떼", "tone": "angry"}).status_code == 400
    assert c.post("/recommend", files={"image": ("x.png", b"<svg onload=alert(1)>", "image/png")}).status_code == 415
    big = b"\xff\xd8\xff" + b"0" * (recommend.MAX_IMAGE + 1)
    assert c.post("/recommend", files={"image": ("x.jpg", big, "image/jpeg")}).status_code == 413
    r = c.post("/recommend", data={"text": "여름 라떼", "regions": "KR", "tone": "friendly"})
    assert r.status_code == 200
    body = r.json()
    assert body["brief_source"] == "sample" and body["items"][0]["term_id"] == "good"
    assert "bad" not in {i["term_id"] for i in body["items"]}


def test_fit_stage_tags_only_new_or_changed_meanings(monkeypatch):
    """쓰임 낱말은 뜻이 바뀐 표제어만 다시 붙이고, 로컬 모델이 없으면 건너뛰어 붙인 것을 그대로 둔다."""
    from trend_agents.pipeline import fit
    from trend_agents.schemas import FitLabel

    con = _con()
    assert fit.todo(con) == []                               # 모두 붙어 있다
    ds.add_meaning(con, "good", MeaningDraft(definition="뜻이 바뀐 말", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                             self_confidence=0.9), "verified_auto", [])
    assert [t.term_id for t, _ in fit.todo(con)] == ["good"]  # 새 판만 다시

    monkeypatch.setattr(fit, "local_ok", lambda: False)
    assert fit.run(con)["fit"].status == "skipped" and [t.term_id for t, _ in fit.todo(con)] == ["good"]

    monkeypatch.setattr(fit, "local_ok", lambda: True)
    monkeypatch.setattr(fit, "structured", lambda con, prompt, schema: ([FitLabel(i=0, feelings=["joy"], uses=["praise"], voice="wholesome")], "test"))
    assert fit.run(con)["fit"].count == 1 and fit.todo(con) == []


# ---------- 검토 2차 ----------

def test_pool_is_not_cut_to_the_display_lists():
    """추천 후보는 대시보드 표시 목록(30개씩)이 아니라 고른 지역의 모든 카드 — 알맞은 밈이 잘려 나갔다."""
    con = db.connect(":memory:")
    for k in range(35):
        _term(con, f"t{k:02d}", f"말{k:02d}", ["tired"], any_category=False)      # 안 맞는 말 35개가 목록을 채운다
    _term(con, "best", "딱맞는말", ["joy", "comfort"], fits=["food_drink"])
    dashboard.run(con)
    got = [i.term_id for i in recommend.recommend(con, LATTE, "sample", ["KR"], "friendly").items]
    assert got == ["best"]


def test_unknown_voice_fails_closed():
    assert MemeFit.model_validate({"feelings": ["joy"], "uses": ["reaction"], "voice": "???"}).voice == "edgy"
    assert MemeFit.model_validate({"feelings": ["joy"], "uses": ["reaction"], "voice": ""}).voice == "edgy"


def test_sample_only_when_nothing_is_configured(monkeypatch):
    """로컬 모델이 설정돼 있는데 꺼져 있으면 예시로 대신하지 않는다. 빈 구조화 응답도 오류로."""
    con = db.connect(":memory:")
    monkeypatch.setattr(recommend, "USE_LOCAL_GEMMA", True)
    monkeypatch.setattr(recommend, "configured", lambda: False)

    def down(*a, **k):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(recommend, "structured", down)
    with pytest.raises(recommend.Unavailable):
        recommend.understand(con, "문구")
    monkeypatch.setattr(recommend, "structured", lambda *a, **k: (None, "gemini-x"))
    with pytest.raises(recommend.Unavailable):
        recommend.understand(con, "문구")


def test_region_without_candidates_skips_the_model(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", _con())
    called = []
    monkeypatch.setattr(recommend, "structured", lambda *a, **k: called.append(1) or (None, "x"))
    c = TestClient(api.app)
    r = c.post("/recommend", data={"text": "라떼", "regions": "VN"})
    assert r.status_code == 200 and r.json()["brief_source"] == "none" and r.json()["items"] == [] and not called


def test_chunked_upload_without_length_is_refused(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    c = TestClient(api.app)

    def body():
        yield b"--x\r\n"

    r = c.post("/recommend", content=body(), headers={"content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 411


def test_request_ledger_is_separate_from_the_pipeline_budget():
    from trend_agents.pipeline import gemini

    con = db.connect(":memory:")
    before = gemini.budget_left(con)
    ds.gemini_spend(con, 3, gemini.REQUEST_LEDGER)
    assert gemini.budget_left(con) == before and gemini.budget_left(con, request=True) == gemini.REQUEST_GEMINI_DAILY - 3
