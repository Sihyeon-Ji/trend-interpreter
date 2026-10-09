"""밈 추천(Plan 07) — 후보·순위·이유 거르기는 규칙이다. 모델 없이 인메모리 DB 로."""
import base64
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


def _term(con, tid, name, feelings, voice="wholesome", fits=(), any_category=True, lifecycle="steady", risk="none", diffusion="mainstream",
          audience="general", kind="expr"):
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
    ds.set_fit(con, tid, cur.meaning_id, MemeFit(feelings=list(feelings), uses=["reaction"], fits=list(fits), any_category=any_category, voice=voice,
                                                       audience=audience, kind=kind), "test")
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


def test_excluded_lists_related_candidates_with_the_rule_that_blocked_them():
    """'뺀 말'(Plan 20): 제품과 이어지는데 규칙이 막은 것만, 막은 이유와 함께. 제품과 상관없는 말은 늘어놓지 않는다."""
    con = _con()
    res = recommend.recommend(con, LATTE, "sample", ["KR"], "friendly")
    why = {e.term_id: e.code for e in res.excluded}
    # nofit(느낌도 분야도 안 겹침)은 없다. 사용 자제(bad)는 공개 목록에서 빠져 '뺀 말' 에도 이름이 나오지 않는다(10-09)
    assert why == {"crude": "crude", "edgy": "tone", "dead": "fading"}
    assert res.pool["KR"] == 6 and res.considered_by_region["KR"] == res.considered


def test_each_market_gets_its_own_top_picks():
    """시장마다 따로 상위를 뽑는다 — 셋을 통틀어 TOP 개만 뽑으면 한국 말이 다 차지해 일본 열이 늘 비었다(10-06)."""
    con = db.connect(":memory:")
    for k in range(8):
        _term(con, f"k{k}", f"한국말{k}", ["joy", "comfort"], fits=["food_drink"])
    _term(con, "jp", "推し活", ["joy"])
    now = datetime.now(timezone.utc)
    t = ds.get_term(con, "jp")
    t.lang = "ja"
    ds.upsert_term(con, t)
    ds.set_usage(con, "jp", [("20s", "JP", now.isoformat(), 1.0)])
    dashboard.run(con)
    res = recommend.recommend(con, LATTE, "sample", ["KR", "JP"], "friendly")
    assert any("JP" in i.write_regions for i in res.items)                  # 점수가 낮아도 일본 몫이 있다
    assert sum("KR" in i.write_regions for i in res.items) == recommend.TOP


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
    # 만들기(Plan 20)에서 고른 분야는 읽은 분야보다 앞서고, 모르는 값은 무시한다
    assert c.post("/recommend", data={"text": "여름 라떼", "regions": "KR", "category": "game"}).json()["brief"]["category"] == "game"
    assert c.post("/recommend", data={"text": "여름 라떼", "regions": "KR", "category": "x"}).json()["brief"]["category"] == body["brief"]["category"]


# 1×1 PNG — 바이트 머리(\x89PNG)로 형식을 본다
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def test_photo_alone_goes_through_to_suggestions(monkeypatch):
    """사진만 올려도 추천까지 간다(Plan 07 완료 기준 1의 사진 입력). 모델 없는 개발 환경이라 제품 설명은 고정 예시지만, 사진은 PNG 로 읽혀
    그대로(메모리의 바이트와 형식) 이해 단계까지 넘어간다."""
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", _con())
    monkeypatch.setattr(api, "_recommend_limit", recommend.RateLimit())
    seen = []
    real = recommend.understand

    def spy(con, text="", image=None, lang="ko"):
        seen.append((text, image))
        return real(con, text, image, lang)

    monkeypatch.setattr(recommend, "understand", spy)
    r = TestClient(api.app).post("/recommend", files={"image": ("latte.png", PNG, "image/png")}, data={"regions": "KR", "tone": "friendly"})
    assert r.status_code == 200
    body = r.json()
    assert body["brief_source"] == "sample" and [i["term_id"] for i in body["items"]][:2] == ["good", "ok"]
    assert all(i["evidences"] for i in body["items"])                   # 근거 링크 없는 추천은 없다(ADR 0001)
    assert seen == [("", (PNG, "image/png"))]


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
    got = ds.all_fits(con)["good"][1]
    assert (got.audience, got.kind) == ("online", "expr")           # 모델이 빠뜨린 칸은 기본값으로 — 다시 붙이지 않는다


def test_fit_stage_retags_fits_made_before_audience(monkeypatch):
    """audience 칸이 생기기 전에 붙인 쓰임 낱말은 뜻이 그대로여도 다시 붙인다(10-09)."""
    from trend_agents.pipeline import fit

    con = _con()
    m = ds.current_meaning(con, "ok")
    ds.set_fit(con, "ok", m.meaning_id, MemeFit(feelings=["joy"], uses=["reaction"], any_category=True, voice="wholesome"), "old")
    assert [t.term_id for t, _ in fit.todo(con)] == ["ok"]


def test_topics_are_not_recommended():
    """밈의 소재(인물·작품·노래)는 추천하지 않고, 일반 낱말(word)은 그 분야 제품에만 권한다(10-09 판정)."""
    con = db.connect(":memory:")
    _term(con, "song", "노래제목", ["joy", "comfort"], fits=["food_drink"], kind="topic")
    _term(con, "plain", "보통말", ["joy", "comfort"], fits=["food_drink"], kind="word")
    _term(con, "chat", "채팅말", ["joy", "comfort"], kind="word")             # 어디에나 붙는 일반 낱말(lol)은 분야가 없어 빠진다
    dashboard.run(con)
    assert [i.term_id for i in recommend.recommend(con, LATTE, "sample", ["KR"], "friendly").items] == ["plain"]


def test_niche_memes_only_for_entertainment_and_game():
    """특정 작품·팬덤 밈은 엔터·게임 제품에만 권한다 — 서브컬처 캐릭터 밈이 화장품·러닝화에 나왔다(사람 판정 10-09)."""
    con = db.connect(":memory:")
    _term(con, "otaku", "캐릭터밈", ["joy", "comfort"], fits=["food_drink", "entertainment"], audience="niche")
    _term(con, "plain", "모두아는말", ["joy", "comfort"], fits=["food_drink", "entertainment"])
    dashboard.run(con)
    assert [i.term_id for i in recommend.recommend(con, LATTE, "sample", ["KR"], "friendly").items] == ["plain"]
    show = LATTE.model_copy(update={"category": "entertainment"})
    assert {i.term_id for i in recommend.recommend(con, show, "sample", ["KR"], "friendly").items} == {"otaku", "plain"}


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


def test_category_memes_stay_in_their_category_and_popularity_only_breaks_ties():
    """분야가 정해진 밈은 다른 분야 제품에 나오지 않는다. 분야도 없고 어디에나 쓰는 반응도 아니면 느낌이 둘은 겹쳐야 한다.
    퍼진 정도는 순위를 가르는 보조 — 제품과 더 맞는 밈을 앞지르지 못한다(09-30: 몇 개가 모든 제품의 윗줄을 차지했다)."""
    con = db.connect(":memory:")
    _term(con, "fandom", "팬덤말", ["joy", "comfort"], fits=["entertainment"], any_category=False, diffusion="spreading", lifecycle="rising")
    _term(con, "one", "느낌하나", ["joy"], any_category=False)
    _term(con, "two", "느낌둘", ["joy", "comfort"], any_category=False)
    _term(con, "food", "먹방말", ["joy"], fits=["food_drink"], any_category=False)
    _term(con, "hot", "뜨는반응", ["joy"], diffusion="spreading", lifecycle="rising")
    dashboard.run(con)
    got = [i.term_id for i in recommend.recommend(con, LATTE, "sample", ["KR"], "friendly").items]
    assert "fandom" not in got and "one" not in got and "two" in got
    assert got.index("food") < got.index("hot")                     # 분야가 맞는 쪽이 인기 가산보다 앞선다


def test_score_skips_fading_and_unjudged_sensitive_memes():
    """식어 가는 밈과, 리스크 판단 전인데 자살·정치 같은 민감한 소재인 밈은 권하지 않는다(라떼 광고에 점메추·'죽고 싶지만…', 10-04)."""
    from trend_agents.pipeline.views import KeywordCard, Tone

    fit = MemeFit(feelings=["joy", "comfort"], uses=["reaction"], fits=[], any_category=True, voice="wholesome")

    def card(name, gloss="", lifecycle="steady", risk="none", dated=False):
        return KeywordCard(term_id=name, canonical=name, lang="ko", category="meme", gloss_ko=gloss, gloss_en="", regions=["KR"],
                           lifecycle=lifecycle, diffusion="mainstream", risk_level=risk, weekly=[], mentions_4w=3, search=[], tone=Tone(),
                           evidences=[], dated=dated, last_seen=datetime.now(timezone.utc))

    assert recommend.score(LATTE, fit, card("럭키"), "friendly") is not None
    assert recommend.score(LATTE, fit, card("점메추", lifecycle="declining"), "friendly") is None
    assert recommend.score(LATTE, fit, card("철지난", dated=True), "friendly") is None
    assert recommend.score(LATTE, fit, card("죽고 싶지만 떡볶이는 먹고 싶어", "우울한 감정", risk=None), "friendly") is None
    assert recommend.score(LATTE, fit, card("오살힘", "하루를 버티게 해 주는 것", risk=None), "friendly") is not None   # 판단 전이어도 소재가 무난하면


def test_same_input_reuses_the_first_product_brief(monkeypatch):
    """같은 문구·사진은 처음 읽은 제품 이해를 다시 쓴다 — 실행마다 느낌 태그가 달라져 추천이 바뀌었다(10-09)."""
    con = db.connect(":memory:")
    monkeypatch.setattr(recommend, "configured", lambda: True)
    calls = []

    def read(con, prompt, schema, **k):
        calls.append(prompt)
        return LATTE.model_copy(update={"feelings": ["joy"] if len(calls) == 1 else ["cool"]}), "gemini-x"

    monkeypatch.setattr(recommend, "structured", read)
    first = recommend.understand(con, "아이스 라떼 문구")
    assert recommend.understand(con, "아이스 라떼 문구") == first and len(calls) == 1
    assert recommend.understand(con, "다른 문구")[0].feelings == ["cool"] and len(calls) == 2
    assert recommend.understand(con, "아이스 라떼 문구", (b"png", "image/png"))[0].feelings == ["cool"]   # 사진이 붙으면 다른 입력
    rows = con.execute("SELECT key, text FROM explain_cache").fetchall()
    assert len(rows) == 3 and not [r for r in rows if "라떼" in r[0] or r[1]]      # 원문을 남기지 않는다
    assert not con.execute("SELECT 1 FROM board_cache WHERE key LIKE 'brief:%'").fetchall()     # 공개 파생 표에 두지 않는다
    ds.prune_user_text(con, cache_days=-1)                                            # 해석 캐시와 같이 기한이 지나면 지운다
    assert not con.execute("SELECT 1 FROM explain_cache").fetchall()
