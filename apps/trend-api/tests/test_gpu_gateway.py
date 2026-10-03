import json

import httpx
import pytest
from trend_agents import config
from trend_agents.interpreters import gpu_gateway, local_chat


@pytest.fixture
def transport(monkeypatch):
    calls = []
    result = {
        "model": "audit:approved",
        "model_digest": "a" * 64,
        "text": '{"ok":true}',
        "ready": True,
    }
    status = {"code": 200}

    def handle(request):
        calls.append(request)
        return httpx.Response(status["code"], json=result)

    client = httpx.Client(
        transport=httpx.MockTransport(handle),
        base_url="https://gpu.internal:8443",
        headers={"authorization": "Bearer synthetic"},
    )
    monkeypatch.setattr(gpu_gateway, "client", lambda: client)
    monkeypatch.setattr(config, "GPU_GATEWAY_URL", "https://gpu.internal:8443")
    monkeypatch.setattr(config, "GPU_GATEWAY_REQUESTS_ENABLED", True)
    monkeypatch.setattr(config, "GPU_GATEWAY_MODEL", "audit:approved")
    monkeypatch.setattr(config, "GPU_GATEWAY_MODEL_DIGEST", "a" * 64)
    yield calls, result, status
    client.close()


def test_local_text_uses_gateway_without_direct_ollama(transport, monkeypatch):
    calls, _, _ = transport
    monkeypatch.setattr(
        local_chat, "_client", lambda *_: pytest.fail("Direct Ollama bypass")
    )
    assert (
        local_chat.chat_text("synthetic prompt", model="audit:approved")
        == '{"ok":true}'
    )
    assert calls[0].url.path == "/v1/generate"
    assert json.loads(calls[0].content) == {
        "prompt": "synthetic prompt",
        "max_tokens": 512,
    }
    assert local_chat.available("audit:approved") is True


@pytest.mark.parametrize("kind", ["model", "digest", "status"])
def test_wrong_release_or_error_has_no_local_fallback(transport, monkeypatch, kind):
    _, result, status = transport
    if kind == "model":
        result["model"] = "other"
    if kind == "digest":
        result["model_digest"] = "b" * 64
    if kind == "status":
        status["code"] = 429
    monkeypatch.setattr(
        local_chat, "_client", lambda *_: pytest.fail("Direct Ollama bypass")
    )
    with pytest.raises(gpu_gateway.GatewayUnavailable):
        local_chat.chat_text("synthetic prompt", model="audit:approved")


@pytest.mark.parametrize("kind", ["different-model", "image", "host", "tools"])
def test_gateway_unsupported_requests_fail_before_transport(transport, kind):
    calls, _, _ = transport
    with pytest.raises(gpu_gateway.GatewayUnavailable):
        if kind == "different-model":
            local_chat.chat_text("hi", model="other")
        if kind == "image":
            local_chat._chat("hi", 0, "audit:approved", image=(b"data", "image/png"))
        if kind == "host":
            local_chat._chat("hi", 0, "audit:approved", host="http://other")
        if kind == "tools":
            local_chat.chat_with_tools([], [], model="audit:approved")
    assert not calls


def test_disabled_gateway_and_invalid_trust_are_closed(monkeypatch):
    gpu_gateway.client.cache_clear()
    monkeypatch.setattr(config, "GPU_GATEWAY_REQUESTS_ENABLED", False)
    monkeypatch.setattr(config, "GPU_GATEWAY_URL", "https://gpu.internal:8443")
    with pytest.raises(gpu_gateway.GatewayUnavailable):
        gpu_gateway.client()
    assert gpu_gateway.available("not-configured") is False


def test_oversized_response_is_rejected(transport):
    _, result, _ = transport
    result["text"] = "x" * 65536
    with pytest.raises(gpu_gateway.GatewayUnavailable, match="response limit"):
        gpu_gateway.generate("hi", "audit:approved")


@pytest.mark.parametrize(
    "url",
    [
        "http://gpu.internal:8443",
        "https://user:password@gpu.internal:8443",
        "https://gpu.internal:8443/path",
    ],
)
def test_insecure_or_credential_bearing_origins_are_refused(monkeypatch, url):
    gpu_gateway.client.cache_clear()
    monkeypatch.setattr(config, "GPU_GATEWAY_URL", url)
    monkeypatch.setattr(config, "GPU_GATEWAY_REQUESTS_ENABLED", True)
    with pytest.raises(gpu_gateway.GatewayUnavailable):
        gpu_gateway.client()


def test_trust_bundle_is_required_and_tls_cannot_be_disabled(monkeypatch):
    gpu_gateway.client.cache_clear()
    for key, value in {
        "GPU_GATEWAY_URL": "https://gpu.internal:8443",
        "GPU_GATEWAY_REQUESTS_ENABLED": True,
        "GPU_GATEWAY_TOKEN": "synthetic-" + "x" * 32,
        "GPU_GATEWAY_MODEL": "audit:approved",
        "GPU_GATEWAY_MODEL_DIGEST": "a" * 64,
        "GPU_GATEWAY_CA_FILE": "/not-present/ca.pem",
    }.items():
        monkeypatch.setattr(config, key, value)
    with pytest.raises(gpu_gateway.GatewayUnavailable, match="trust configuration"):
        gpu_gateway.client()


def test_disabling_requests_blocks_even_a_cached_transport(transport, monkeypatch):
    calls, _, _ = transport
    monkeypatch.setattr(config, "GPU_GATEWAY_REQUESTS_ENABLED", False)
    assert local_chat.available("audit:approved") is False
    with pytest.raises(gpu_gateway.GatewayUnavailable):
        local_chat.chat_text("hi", model="audit:approved")
    assert not calls


def test_enabled_gateway_without_url_never_falls_back(monkeypatch):
    monkeypatch.setattr(config, "GPU_GATEWAY_URL", "")
    monkeypatch.setattr(config, "GPU_GATEWAY_REQUESTS_ENABLED", True)
    monkeypatch.setattr(
        local_chat, "_client", lambda *_: pytest.fail("Direct Ollama bypass")
    )
    with pytest.raises(gpu_gateway.GatewayUnavailable):
        local_chat.chat_text("hi", model="not-configured")


def test_invalid_model_output_is_not_in_structured_error(transport):
    from pydantic import BaseModel

    class Response(BaseModel):
        ok: bool

    calls, result, _ = transport
    result["text"] = "private generated output"
    with pytest.raises(ValueError) as error:
        local_chat.structured("synthetic input", Response, model="audit:approved")
    assert "private generated output" not in str(error.value)
    assert len(calls) == 2
