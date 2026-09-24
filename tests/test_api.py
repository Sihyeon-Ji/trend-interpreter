import asyncio

import httpx
import pytest
from builder_cup.config import Settings
from builder_cup.main import create_app
from builder_cup.providers import (
    GeminiProvider,
    Generation,
    MockProvider,
    ProviderFailure,
    VllmProvider,
)
from builder_cup.schemas import Usage
from builder_cup.workflow import analyze
from fastapi.testclient import TestClient
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials


def settings(**kwargs):
    return Settings(_env_file=None, **kwargs)


def test_auth_input_and_request_id():
    with TestClient(create_app(settings(demo_api_key="test-secret"))) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/analyze", json={"text": "Hello"}).status_code == 401
        headers = {"Authorization": "Bearer test-secret"}
        for text in ("", "   ", "x" * 8001):
            response = client.post("/api/analyze", json={"text": text}, headers=headers)
            assert response.status_code == 422
            assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
        response = client.post("/api/analyze", json={"text": "Hello"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["result"]["summary"] == "Hello"
        assert response.json()["estimated_cost_usd"] is None
        assert client.get("/api/missing").status_code == 404


class FlakyProvider(MockProvider):
    calls = 0

    async def generate(self, text):
        self.calls += 1
        if self.calls == 1:
            raise ProviderFailure("model_unavailable", retryable=True)
        return await super().generate(text)


async def test_transient_failure_is_retried():
    provider = FlakyProvider()
    result = await analyze("hello", "test", provider, settings())
    assert result.attempts == 2
    assert provider.calls == 2


async def test_invalid_output_is_not_passed_to_user():
    class InvalidProvider(MockProvider):
        async def generate(self, text):
            return Generation('{"summary":"hello","key_points":[]}', Usage())

    with pytest.raises(ProviderFailure, match="invalid_model_response"):
        await analyze("hello", "test", InvalidProvider(), settings())


def test_timeout_is_bounded_and_reported():
    class SlowProvider(MockProvider):
        calls = 0

        async def generate(self, text):
            self.calls += 1
            if self.calls == 1:
                await asyncio.sleep(1)
            return await super().generate(text)

    config = settings(model_timeout_seconds=0.01, model_max_attempts=1)
    provider = SlowProvider()
    with TestClient(create_app(config, provider)) as client:
        response = client.post("/api/analyze", json={"text": "Hello"})
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "model_timeout"
        assert client.post("/api/analyze", json={"text": "Recovered"}).status_code == 200


def test_disabled_and_unauthorized_requests_never_call_model():
    class CountingProvider(MockProvider):
        calls = 0

        async def generate(self, text):
            self.calls += 1
            return await super().generate(text)

    provider = CountingProvider()
    app = create_app(settings(demo_api_key="test-secret", model_requests_enabled=False), provider)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/analyze", json={"text": "Hello"}).status_code == 401
        response = client.post(
            "/api/analyze",
            json={"text": "Hello"},
            headers={"Authorization": "Bearer test-secret"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "model_disabled"
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert provider.calls == 0


def test_rate_limit_returns_retry_after_and_recovers():
    class CountingProvider(MockProvider):
        calls = 0

        async def generate(self, text):
            self.calls += 1
            return await super().generate(text)

    provider = CountingProvider()
    app = create_app(settings(model_requests_per_minute=2), provider)
    now = 1000.0
    app.state.model_request_gate.clock = lambda: now
    with TestClient(app) as client:
        for _ in range(2):
            assert client.post("/api/analyze", json={"text": "Hello"}).status_code == 200
        limited = client.post("/api/analyze", json={"text": "Hello"})
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"
        assert limited.json()["error"]["code"] == "model_rate_limited"
        assert provider.calls == 2
        now += 60
        assert client.post("/api/analyze", json={"text": "Hello"}).status_code == 200
    assert provider.calls == 3


async def test_concurrency_limit_and_cancel_release_slot():
    class WaitingProvider(MockProvider):
        def __init__(self):
            self.calls = 0
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def generate(self, text):
            self.calls += 1
            if self.calls == 1:
                self.entered.set()
                await self.release.wait()
            return await super().generate(text)

    provider = WaitingProvider()
    app = create_app(settings(model_max_concurrent_requests=1), provider)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            pending = asyncio.create_task(client.post("/api/analyze", json={"text": "First"}))
            await asyncio.wait_for(provider.entered.wait(), 1)
            limited = await client.post("/api/analyze", json={"text": "Second"})
            assert limited.status_code == 429
            assert limited.headers["Retry-After"] == "1"
            assert provider.calls == 1
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert app.state.model_request_gate.active == 0
            recovered = await client.post("/api/analyze", json={"text": "Second"})
            assert recovered.status_code == 200
            assert provider.calls == 2


@pytest.mark.parametrize(
    "output",
    [
        '{"summary":" ","key_points":["Valid"]}',
        '{"summary":"Valid","key_points":[""]}',
        '{"summary":"Valid","key_points":["  "]}',
        '{"summary":"Valid","key_points":[]}',
        '{"summary":"Valid","key_points":["a","b","c","d","e","f"]}',
        '{"summary":"Valid","key_points":["' + "x" * 501 + '"]}',
        '{"summary":"Valid","key_points":["Valid"],"extra":"x"}',
        '{"summary":"Valid","key_points":["incomplete"}',
    ],
)
async def test_invalid_model_output_is_rejected(output):
    class InvalidProvider(MockProvider):
        async def generate(self, text):
            return Generation(output, Usage())

    with pytest.raises(ProviderFailure, match="invalid_model_response"):
        await analyze("Hello", "test", InvalidProvider(), settings())


@pytest.mark.parametrize("usage", [{"prompt_tokens": 10, "completion_tokens": 5}, {}, None])
async def test_vllm_contract_and_usage(usage):
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer local-development-only"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"summary":"Hi","key_points":["Hi"]}'}}],
                "usage": usage,
            },
        )

    provider = VllmProvider(settings())
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(
        base_url="http://localhost:8001/v1/",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer local-development-only"},
    )
    result = await analyze("Hi", "test", provider, settings(input_price_per_million=1))
    assert result.usage.input_tokens == (10 if usage else None)
    assert result.usage.output_tokens == (5 if usage else None)
    if usage:
        assert result.estimated_cost_usd == pytest.approx(0.00001)
    else:
        assert result.estimated_cost_usd is None
    await provider.close()


def test_cloud_run_requires_access_code(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "builder-cup")
    with pytest.raises(RuntimeError, match="DEMO_API_KEY"):
        create_app(settings())


@pytest.mark.parametrize("has_usage", [True, False])
async def test_gemini_sdk_contract_and_thinking_usage(has_usage):
    def handler(request):
        assert "publishers/google/models/gemini-3.5-flash:generateContent" in request.url.path
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": '{"summary":"Hello","key_points":["Hello"]}'}],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 12,
                    "candidatesTokenCount": 8,
                    "thoughtsTokenCount": 3,
                }
                if has_usage
                else None,
            },
        )

    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "gemini-3.5-flash"
    provider.client = genai.Client(
        vertexai=True,
        project="test-project",
        location="global",
        credentials=Credentials(token="test-token-not-a-real-credential"),
        http_options=types.HttpOptions(
            httpx_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ),
    )
    try:
        result = await analyze("Hello", "sdk-test", provider, settings())
        assert result.result.summary == "Hello"
        assert result.usage.input_tokens == (12 if has_usage else None)
        assert result.usage.output_tokens == (11 if has_usage else None)
    finally:
        await provider.close()
