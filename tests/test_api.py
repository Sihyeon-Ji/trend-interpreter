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
        async def generate(self, text):
            await asyncio.sleep(1)
            return await super().generate(text)

    config = settings(model_timeout_seconds=0.01, model_max_attempts=1)
    with TestClient(create_app(config, SlowProvider())) as client:
        response = client.post("/api/analyze", json={"text": "Hello"})
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "model_timeout"


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
