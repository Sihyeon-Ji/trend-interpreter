import base64
import binascii
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("uvicorn.error").getChild("alert_relay")
DISCORD_RED = 0xE5484D
DISCORD_GREEN = 0x30A46C
MAX_FIELD_LENGTH = 1024
MAX_TITLE_LENGTH = 256
ALLOWED_INCIDENT_HOSTS = {"console.cloud.google.com", "app.google.stackdriver.com"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    discord_webhook_url: str
    discord_timeout_seconds: float = Field(default=5.0, gt=0, le=15)

    @field_validator("discord_webhook_url")
    @classmethod
    def validate_discord_webhook_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname not in {"discord.com", "discordapp.com"}:
            raise ValueError("DISCORD_WEBHOOK_URL must be an HTTPS Discord webhook URL")
        if not parsed.path.startswith("/api/webhooks/"):
            raise ValueError("DISCORD_WEBHOOK_URL must use the Discord webhook path")
        return value


class PubSubMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    data: str = Field(min_length=1)
    message_id: str = Field(alias="messageId", min_length=1, max_length=256)


class PubSubEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: PubSubMessage


class MonitoredResource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    labels: dict[str, str] = Field(default_factory=dict)


class Incident(BaseModel):
    model_config = ConfigDict(extra="ignore")

    incident_id: str = Field(min_length=1, max_length=256)
    state: str = Field(min_length=1, max_length=32)
    policy_name: str = Field(default="Unknown policy", max_length=512)
    condition_name: str = Field(default="", max_length=512)
    resource_name: str = Field(default="", max_length=512)
    resource: MonitoredResource = Field(default_factory=MonitoredResource)
    started_at: int | float | None = None
    ended_at: int | float | None = None
    observed_value: str = Field(default="", max_length=256)
    url: str = Field(default="", max_length=2048)


class MonitoringNotification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    incident: Incident


def safe_log(level: int, event: str, **fields: str | int) -> None:
    logger.log(level, json.dumps({"event": event, **fields}, separators=(",", ":")))


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def event_time(incident: Incident) -> datetime:
    timestamp = incident.ended_at if incident.state.lower() == "closed" else incident.started_at
    if timestamp is None:
        return datetime.now(UTC)
    try:
        return datetime.fromtimestamp(timestamp, UTC)
    except (OverflowError, OSError, ValueError):
        return datetime.now(UTC)


def safe_incident_url(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.hostname in ALLOWED_INCIDENT_HOSTS:
        return value
    return None


def discord_payload(incident: Incident) -> dict[str, Any]:
    is_closed = incident.state.lower() == "closed"
    state_label = "복구" if is_closed else "장애 발생"
    labels = incident.resource.labels
    fields = [
        {
            "name": "상태",
            "value": truncate(incident.state.upper(), MAX_FIELD_LENGTH),
            "inline": True,
        },
        {
            "name": "Incident ID",
            "value": truncate(incident.incident_id, MAX_FIELD_LENGTH),
            "inline": True,
        },
    ]
    optional_fields = (
        ("조건", incident.condition_name),
        ("서비스", labels.get("service_name", "")),
        ("리비전", labels.get("revision_name", "")),
        ("리소스", incident.resource_name),
        ("관측값", incident.observed_value),
    )
    fields.extend(
        {"name": name, "value": truncate(value, MAX_FIELD_LENGTH), "inline": True}
        for name, value in optional_fields
        if value
    )
    embed: dict[str, Any] = {
        "title": truncate(f"Builder Cup {state_label} · {incident.policy_name}", MAX_TITLE_LENGTH),
        "color": DISCORD_GREEN if is_closed else DISCORD_RED,
        "fields": fields,
        "timestamp": event_time(incident).isoformat().replace("+00:00", "Z"),
    }
    incident_url = safe_incident_url(incident.url)
    if incident_url:
        embed["url"] = incident_url
    return {"username": "Builder Cup Alerts", "embeds": [embed]}


def decode_notification(message: PubSubMessage) -> MonitoringNotification:
    try:
        decoded = base64.b64decode(message.data, validate=True)
        payload = json.loads(decoded)
        return MonitoringNotification.model_validate(payload)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("invalid monitoring notification") from exc


def create_app(
    settings: Settings | None = None,
    discord_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    config = settings or Settings()  # type: ignore[call-arg]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_client = discord_client is None
        app.state.discord_client = discord_client or httpx.AsyncClient(
            timeout=config.discord_timeout_seconds
        )
        yield
        if owns_client:
            await app.state.discord_client.aclose()

    app = FastAPI(title="Builder Cup Alert Relay", docs_url=None, redoc_url=None, lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/", status_code=204)
    async def relay(envelope: PubSubEnvelope) -> Response:
        try:
            notification = decode_notification(envelope.message)
        except ValueError as exc:
            safe_log(
                logging.WARNING,
                "invalid_notification",
                message_id=envelope.message.message_id,
            )
            raise HTTPException(status_code=400, detail="Invalid notification") from exc

        incident = notification.incident
        try:
            response = await app.state.discord_client.post(
                config.discord_webhook_url,
                json=discord_payload(incident),
            )
        except httpx.RequestError as exc:
            safe_log(
                logging.ERROR,
                "discord_delivery_failed",
                message_id=envelope.message.message_id,
                incident_id=incident.incident_id,
                failure="network",
            )
            raise HTTPException(status_code=503, detail="Discord unavailable") from exc

        if 200 <= response.status_code < 300:
            safe_log(
                logging.INFO,
                "discord_delivery_succeeded",
                message_id=envelope.message.message_id,
                incident_id=incident.incident_id,
                discord_status=response.status_code,
            )
            return Response(status_code=204)

        safe_log(
            logging.ERROR,
            "discord_delivery_failed",
            message_id=envelope.message.message_id,
            incident_id=incident.incident_id,
            discord_status=response.status_code,
        )
        raise HTTPException(status_code=503, detail="Discord rejected notification")

    return app
