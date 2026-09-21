import json

import httpx
import pytest
from builder_cup.config import Settings
from builder_cup.providers import OllamaProvider, ProviderFailure
from builder_cup.workflow import analyze


def make_provider(handler):
    config = Settings(_env_file=None, model_provider="ollama", model_max_attempts=1)
    provider = OllamaProvider(config)
    return config, provider, httpx.MockTransport(handler)


@pytest.mark.parametrize("usage", [True, False])
async def test_ollama_schema_options_and_reported_usage(usage):
    def handler(request):
        body = json.loads(request.content)
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        assert request.url.path == "/api/chat"
        assert body["stream"] is False and body["think"] is False
        assert body["format"]["additionalProperties"] is False
        assert body["options"] == {"temperature": 0, "num_ctx": 4096, "num_predict": 1024}
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "message": {"content": '{"summary":"Hi","key_points":["Hi"]}'},
                **(
                    {"prompt_eval_count": 20, "eval_count": 10, "load_duration": 1000}
                    if usage
                    else {}
                ),
            },
        )

    config, provider, transport = make_provider(handler)
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(base_url=config.ollama_base_url, transport=transport)
    try:
        result = await analyze("Hi", "test", provider, config)
        assert result.provider == "ollama"
        assert result.usage.input_tokens == (20 if usage else None)
        assert provider.last_timings["load_duration"] == (1000 if usage else None)
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "response",
    [
        {"done": True, "done_reason": "length", "message": {"content": "{}"}},
        {"done": False},
        {"done": True, "done_reason": "stop", "message": {"content": "invalid-json"}},
        {"error": "private-model-payload"},
    ],
)
async def test_ollama_invalid_or_truncated_output_never_falls_back(response):
    def handler(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        return httpx.Response(200, json=response)

    config, provider, transport = make_provider(handler)
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(base_url=config.ollama_base_url, transport=transport)
    try:
        with pytest.raises(ProviderFailure, match="invalid_model_response"):
            await analyze("Hi", "test", provider, config)
    finally:
        await provider.close()


async def test_ollama_cloud_model_is_rejected_before_text_is_sent():
    def handler(request):
        assert request.url.path == "/api/show"
        assert "private-input" not in request.content.decode()
        return httpx.Response(
            200, json={"remote_host": "https://ollama.com", "capabilities": ["completion"]}
        )

    config, provider, transport = make_provider(handler)
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(base_url=config.ollama_base_url, transport=transport)
    try:
        with pytest.raises(ProviderFailure, match="model_unavailable"):
            await analyze("private-input", "test", provider, config)
    finally:
        await provider.close()


async def test_ollama_connection_failure_never_falls_back():
    def handler(request):
        raise httpx.ConnectError("private-connection-detail")

    config, provider, transport = make_provider(handler)
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(base_url=config.ollama_base_url, transport=transport)
    try:
        with pytest.raises(ProviderFailure, match="model_unavailable"):
            await analyze("Hi", "test", provider, config)
    finally:
        await provider.close()


def test_ollama_requires_local_endpoint():
    with pytest.raises(ValueError, match="local host endpoint"):
        OllamaProvider(Settings(_env_file=None, ollama_base_url="https://ollama.com"))
