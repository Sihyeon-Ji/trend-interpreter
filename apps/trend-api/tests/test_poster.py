"""시장별 포스터 시안 — 구성안은 규칙, 그림은 이미지 모델 한 번. 실제 모델은 부르지 않는다(가짜 클라이언트만)."""
import base64
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from trend_agents import config, model_client
from trend_agents.pipeline import gemini, poster
from trend_agents.schemas import MeaningDraft, MemeFit, ProductBrief, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
LATTE = ProductBrief(product="장원영 같다 느낌의 아이스 라떼", category="food_drink", feelings=["joy"], values=["시원함", "럭키비키"],
                     scene="장원영 처럼 웃는 오후 카페", colors=["갈색", "흰색"])
FIT = MemeFit(feelings=["pride", "joy"], uses=["praise"], voice="playful")
MEMES = [(["장원영 같다", "원영적 사고"], FIT), (["럭키비키"], None)]


@pytest.fixture(autouse=True)
def _off(monkeypatch):
    """기본은 꺼짐 — 시험마다 켤 것만 켠다."""
    monkeypatch.setattr(config, "IMAGE_BACKEND", "off")
    monkeypatch.setattr(config, "MODEL_PROVIDER", "mock")
    monkeypatch.setattr(config, "MODEL_REQUESTS_ENABLED", False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(gemini, "local_ok", lambda: False)


def _on(monkeypatch, images=(PNG,), seen=None):
    """api 접속으로 켜고 클라이언트는 가짜로 바꾼다. 응답은 inline 이미지."""
    monkeypatch.setattr(config, "IMAGE_BACKEND", "api")
    monkeypatch.setattr(config, "MODEL_REQUESTS_ENABLED", True)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake")

    class Models:
        def generate_content(self, model, contents, config):
            if seen is not None:
                seen.append((model, contents, config))
            parts = [SimpleNamespace(inline_data=SimpleNamespace(data=b, mime_type="image/png")) for b in images]
            return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))], usage_metadata=None)

    monkeypatch.setattr(model_client, "image_client", lambda: SimpleNamespace(models=Models()))


def test_plan_keeps_meme_and_person_names_out_of_the_prompt():
    p = poster.plan(LATTE, "KR", MEMES)
    for name in ("장원영", "원영적", "럭키비키", "같다"):
        assert name not in p.prompt and name not in p.product and name not in p.scene
    assert "아이스 라떼" in p.product and "시원함" in p.prompt
    assert p.mood == ["confident and bold", "bright and cheerful", "fun, casual styling"]   # 밈은 느낌·말투(닫힌 낱말)로만 들어간다
    low = p.prompt.lower()
    assert "no text" in low or "any text" in low
    assert "no real persons" in low and "no celebrities" in low
    assert "copyrighted" in low and "meme characters" in low
    assert "keep that product exactly as it is" in low and "only the background" in low
    assert poster.plan(LATTE, "KR", MEMES) == p                       # 규칙이라 같은 입력이면 같은 지시문


def test_plan_falls_back_to_brief_feelings_and_rejects_other_markets():
    assert poster.plan(LATTE, "JP").mood == ["bright and cheerful"]
    assert "Japan" in poster.plan(LATTE, "JP").prompt
    with pytest.raises(ValueError):
        poster.plan(LATTE, "TW")


def test_off_never_creates_a_client():
    con = db.connect(":memory:")
    factory = Mock()
    with pytest.MonkeyPatch.context() as m:
        m.setattr(model_client.genai, "Client", factory)
        assert not poster.enabled()
        with pytest.raises(poster.NotConfigured):
            poster.generate(con, poster.plan(LATTE, "KR"), PNG)
    factory.assert_not_called()
    assert ds.gemini_budget_left(con, config.IMAGE_DAILY, poster.IMAGE_LEDGER) == config.IMAGE_DAILY


def test_backends_reuse_the_existing_clients(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(model_client.genai, "Client", factory)
    monkeypatch.setattr(config, "IMAGE_BACKEND", "api")
    assert not model_client.image_requests_enabled()                  # 키가 있어도 MODEL_REQUESTS_ENABLED 가 꺼져 있으면 부르지 않는다
    monkeypatch.setattr(config, "MODEL_REQUESTS_ENABLED", True)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake")
    model_client.image_client()
    factory.assert_called_once_with(vertexai=False, api_key="fake")
    monkeypatch.setattr(config, "IMAGE_BACKEND", "vertex")
    monkeypatch.setattr(config, "MODEL_PROVIDER", "vertex")
    monkeypatch.setattr(config, "GCP_PROJECT_ID", "builder-cup-test")
    sentinel = object()
    monkeypatch.setattr(model_client, "client", lambda: sentinel)
    assert model_client.image_client() is sentinel


def test_fake_image_comes_back_as_png_and_is_counted(monkeypatch):
    con = db.connect(":memory:")
    seen = []
    _on(monkeypatch, images=(PNG, b"not a png"), seen=seen)
    p = poster.plan(LATTE, "US", MEMES)
    assert poster.generate(con, p, PNG) == [PNG]
    model, contents, cfg = seen[0]
    assert model == config.IMAGE_MODEL and cfg.response_modalities == ["IMAGE"]
    assert contents[0].inline_data.data == PNG and contents[-1] == p.prompt     # 사진은 메모리의 Part 로만
    assert ds.gemini_budget_left(con, config.IMAGE_DAILY, poster.IMAGE_LEDGER) == config.IMAGE_DAILY - 1
    assert gemini.budget_left(con, request=True) == config.REQUEST_GEMINI_DAILY - 1


def test_daily_image_cap_stops_before_the_call(monkeypatch):
    con = db.connect(":memory:")
    seen = []
    _on(monkeypatch, seen=seen)
    monkeypatch.setattr(poster, "IMAGE_DAILY", 2)
    p = poster.plan(LATTE, "KR")
    poster.generate(con, p)
    poster.generate(con, p)
    with pytest.raises(poster.Unavailable):
        poster.generate(con, p)
    assert len(seen) == 2


def test_failed_call_is_refunded(monkeypatch):
    con = db.connect(":memory:")
    _on(monkeypatch)

    class Boom:
        def generate_content(self, **k):
            raise gemini.errors.APIError(503, {"error": {"message": "busy"}})

    monkeypatch.setattr(model_client, "image_client", lambda: SimpleNamespace(models=Boom()))
    with pytest.raises(poster.Unavailable):
        poster.generate(con, poster.plan(LATTE, "KR"))
    assert ds.gemini_budget_left(con, config.IMAGE_DAILY, poster.IMAGE_LEDGER) == config.IMAGE_DAILY


def _api(monkeypatch):
    from fastapi.testclient import TestClient
    from trend_agents.api import app as api

    con = db.connect(":memory:")
    now = datetime.now(UTC)
    ds.upsert_term(con, Term(term_id="wy", canonical="장원영 같다", aliases=["원영적 사고"], lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.add_meaning(con, "wy", MeaningDraft(definition="아주 좋다는 뜻", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                           self_confidence=0.9), "verified_auto", [])
    ds.set_fit(con, "wy", ds.current_meaning(con, "wy").meaning_id, FIT, "test")
    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setattr(api, "_poster_limit", api.recommend_stage.RateLimit())
    return TestClient(api.app)


def test_api_off_returns_the_plan_only(monkeypatch):
    c = _api(monkeypatch)
    r = c.post("/campaign/poster", data={"market": "kr", "brief": LATTE.model_dump_json(), "term_ids": "wy,missing"},
               files={"image": ("x.png", PNG, "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False and body["images"] == [] and body["plan"]["market"] == "KR"
    assert "장원영" not in body["plan"]["prompt"] and "confident and bold" in body["plan"]["mood"]
    assert c.post("/campaign/poster", data={"market": "TW", "text": "라떼"}).status_code == 400
    assert c.post("/campaign/poster", data={"market": "KR"}).status_code == 400
    assert c.post("/campaign/poster", data={"market": "KR", "brief": "{"}).status_code == 400
    assert c.post("/campaign/poster", data={"market": "KR", "text": "라떼"}, files={"image": ("x.png", b"<svg>", "image/png")}).status_code == 415


def test_api_on_returns_data_url(monkeypatch):
    c = _api(monkeypatch)
    _on(monkeypatch)
    r = c.post("/campaign/poster", data={"market": "US", "text": "iced latte", "term_ids": "wy"})
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True and [base64.b64decode(i.removeprefix("data:image/png;base64,")) for i in body["images"]] == [PNG] and body["images"][0].startswith("data:image/png;base64,")
