import base64
import json
import logging

import httpx
from fastapi.testclient import TestClient

from alert_relay.main import Settings, create_app

WEBHOOK_URL = "https://discord.com/api/webhooks/test/token"


def envelope(payload: dict, message_id: str = "message-1") -> dict:
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": encoded, "messageId": message_id}}


def notification(state: str = "open") -> dict:
    return {
        "incident": {
            "incident_id": "incident-123",
            "state": state,
            "policy_name": "Builder Cup availability",
            "condition_name": "Health check failed",
            "resource_name": "builder-cup",
            "resource": {
                "labels": {
                    "service_name": "builder-cup",
                    "revision_name": "builder-cup-00005-cib",
                }
            },
            "started_at": 1_790_172_249,
            "ended_at": 1_790_172_549,
            "observed_value": "0",
            "url": "https://console.cloud.google.com/monitoring/alerting/incidents/123",
            "summary": "must never be forwarded",
        }
    }


def test_open_notification_is_sent_without_raw_summary(caplog):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(204)

    discord = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(Settings(discord_webhook_url=WEBHOOK_URL), discord)
    with caplog.at_level(logging.INFO, logger="uvicorn.error.alert_relay"):
        with TestClient(app) as client:
            response = client.post("/", json=envelope(notification()))

    assert response.status_code == 204
    serialized = json.dumps(captured)
    assert "must never be forwarded" not in serialized
    assert "장애 발생" in captured["embeds"][0]["title"]
    assert captured["embeds"][0]["color"] == 0xE5484D
    assert "discord_delivery_succeeded" in caplog.text
    assert "must never be forwarded" not in caplog.text


def test_closed_notification_uses_recovery_style():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(204)

    discord = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(Settings(discord_webhook_url=WEBHOOK_URL), discord)
    with TestClient(app) as client:
        response = client.post("/", json=envelope(notification("closed")))

    assert response.status_code == 204
    assert "복구" in captured["embeds"][0]["title"]
    assert captured["embeds"][0]["color"] == 0x30A46C


def test_invalid_payload_is_rejected_without_discord_call():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(204)

    discord = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(Settings(discord_webhook_url=WEBHOOK_URL), discord)
    with TestClient(app) as client:
        response = client.post("/", json={"message": {"data": "not-base64", "messageId": "x"}})

    assert response.status_code == 400
    assert calls == 0


def test_discord_failure_requests_pubsub_retry():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"retry_after": 1})

    discord = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(Settings(discord_webhook_url=WEBHOOK_URL), discord)
    with TestClient(app) as client:
        response = client.post("/", json=envelope(notification()))

    assert response.status_code == 503
    assert response.json() == {"detail": "Discord rejected notification"}


def test_health():
    discord = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(204)))
    app = create_app(Settings(discord_webhook_url=WEBHOOK_URL), discord)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
