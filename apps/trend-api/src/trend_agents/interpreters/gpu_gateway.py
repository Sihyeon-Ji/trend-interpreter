"""Bounded TLS transport for the explicitly selected private model release."""

import json
import re
import ssl
from functools import lru_cache
from urllib.parse import urlsplit

import httpx

from .. import config


class GatewayUnavailable(RuntimeError):
    pass


def configured():
    return bool(config.GPU_GATEWAY_URL) or config.GPU_GATEWAY_REQUESTS_ENABLED


@lru_cache(maxsize=1)
def client():
    url = urlsplit(config.GPU_GATEWAY_URL)
    if (
        not config.GPU_GATEWAY_REQUESTS_ENABLED
        or url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
        or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", config.GPU_GATEWAY_TOKEN)
        or not re.fullmatch(r"[a-f0-9]{64}", config.GPU_GATEWAY_MODEL_DIGEST)
        or not config.GPU_GATEWAY_MODEL
        or not config.GPU_GATEWAY_CA_FILE
    ):
        raise GatewayUnavailable("GPU gateway configuration unavailable")
    try:
        context = ssl.create_default_context(cafile=config.GPU_GATEWAY_CA_FILE)
    except (OSError, ssl.SSLError):
        raise GatewayUnavailable(
            "GPU gateway trust configuration unavailable"
        ) from None
    return httpx.Client(
        base_url=config.GPU_GATEWAY_URL.rstrip("/"),
        verify=context,
        trust_env=False,
        follow_redirects=False,
        timeout=httpx.Timeout(connect=3, read=31, write=3, pool=3),
        headers={"authorization": "Bearer " + config.GPU_GATEWAY_TOKEN},
    )


def call(path, body=None, timeout=None):
    """timeout 을 주면 그 요청만 짧게 기다린다(readiness 확인 – 모델 적재 중인 GPU 를 30초씩 기다리지 않게)."""
    if not config.GPU_GATEWAY_REQUESTS_ENABLED:
        raise GatewayUnavailable("GPU gateway requests disabled")
    try:
        extra = {} if timeout is None else {"timeout": httpx.Timeout(timeout)}
        with client().stream(
            "GET" if body is None else "POST", path, json=body, **extra
        ) as response:
            if response.status_code != 200:
                raise GatewayUnavailable(f"GPU gateway status {response.status_code}")
            raw = bytearray()
            for chunk in response.iter_bytes():
                if len(raw) + len(chunk) > 64 * 1024:
                    raise GatewayUnavailable("GPU gateway response limit")
                raw.extend(chunk)
            result = json.loads(raw)
        if (
            result.get("model") != config.GPU_GATEWAY_MODEL
            or result.get("model_digest") != config.GPU_GATEWAY_MODEL_DIGEST
        ):
            raise GatewayUnavailable("GPU gateway release mismatch")
        return result
    except GatewayUnavailable:
        raise
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise GatewayUnavailable("GPU gateway transport unavailable") from None


def available(model, timeout=None):
    if model != config.GPU_GATEWAY_MODEL:
        return False
    try:
        return call("/ready", timeout=timeout).get("ready") is True
    except GatewayUnavailable:
        return False


def generate(prompt, model):
    if model != config.GPU_GATEWAY_MODEL or not prompt.strip() or len(prompt) > 12000:
        raise GatewayUnavailable("Unsupported GPU gateway request")
    result = call("/v1/generate", {"prompt": prompt, "max_tokens": 512})
    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        raise GatewayUnavailable("GPU gateway invalid output")
    return text
