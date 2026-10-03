"""Single-owner gateway; Ollama remains on loopback with one inference slot."""

import asyncio
import fcntl
import hmac
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .engine import chat_request

MAX_BODY_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    model: str
    digest: str
    deadline: float = 30
    lock_path: str = "/tmp/trend-model-gateway.lock"

    def __post_init__(self):
        import re

        if (
            not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", self.token)
            or not self.model
            or not re.fullmatch(r"[a-f0-9]{64}", self.digest)
            or not 0 < self.deadline <= 120
        ):
            raise ValueError("Invalid gateway configuration")


class Generate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=12000)
    max_tokens: int = Field(default=256, ge=1, le=512, strict=True)


class Gateway:
    def __init__(self, settings, client):
        self.settings, self.client = settings, client
        self.busy = False
        self.ready = False

    async def post(self, prompt, tokens):
        async with self.client.stream(
            "POST", "/api/chat", json=chat_request(self.settings.model, prompt, tokens)
        ) as response:
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                if len(data) + len(chunk) > MAX_OUTPUT_BYTES:
                    raise ValueError("Backend response limit")
                data.extend(chunk)
            import json

            result = json.loads(data)
        content = result.get("message", {}).get("content")
        if (
            result.get("model") != self.settings.model
            or result.get("done") is not True
            or not isinstance(content, str)
            or not content.strip()
            or result.get("message", {}).get("tool_calls")
        ):
            raise ValueError("Invalid backend inference")
        return content

    async def resident(self):
        response = await self.client.get("/api/ps")
        response.raise_for_status()
        matches = [
            model for model in response.json()["models"] if model.get("name") == self.settings.model
        ]
        if (
            len(matches) != 1
            or matches[0].get("digest") != self.settings.digest
            or type(matches[0].get("size_vram")) is not int
            or matches[0]["size_vram"] <= 0
        ):
            raise ValueError("Expected model is not resident on GPU")

    async def execute(self, request, payload=None):
        if self.busy:
            raise HTTPException(429, "gpu_busy", headers={"Retry-After": "1"})
        if payload is not None and not self.ready:
            raise HTTPException(503, "gpu_not_ready")
        self.busy = True

        async def inference():
            if payload is None:
                await self.post("Reply with OK.", 1)
                await self.resident()
                self.ready = True
                return {
                    "ready": True,
                    "model": self.settings.model,
                    "model_digest": self.settings.digest,
                }
            await self.resident()
            content = await self.post(payload.prompt, payload.max_tokens)
            return {
                "text": content,
                "model": self.settings.model,
                "model_digest": self.settings.digest,
            }

        async def disconnected():
            while True:
                message = await request.receive()
                if message["type"] == "http.disconnect":
                    return

        operation = asyncio.create_task(inference())
        watcher = asyncio.create_task(disconnected())
        try:
            async with asyncio.timeout(self.settings.deadline):
                done, _ = await asyncio.wait(
                    {operation, watcher}, return_when=asyncio.FIRST_COMPLETED
                )
                if watcher in done:
                    raise HTTPException(499, "client_disconnected")
                return await operation
        except TimeoutError:
            self.ready = False
            raise HTTPException(504, "gpu_deadline") from None
        except HTTPException:
            self.ready = False
            raise
        except asyncio.CancelledError:
            self.ready = False
            raise
        except Exception:  # noqa: BLE001 – Never expose backend messages or model output.
            self.ready = False
            raise HTTPException(503, "gpu_unavailable") from None
        finally:
            operation.cancel()
            watcher.cancel()
            await asyncio.gather(operation, watcher, return_exceptions=True)
            self.busy = False


class BoundedBody:
    def __init__(self, app, state):
        self.app, self.state = app, state

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/v1/generate":
            return await self.app(scope, receive, send)
        from starlette.responses import JSONResponse

        headers = dict(scope["headers"])
        expected = ("Bearer " + self.state.gateway.settings.token).encode()
        if not hmac.compare_digest(headers.get(b"authorization", b""), expected):
            return await JSONResponse({"detail": "unauthorized"}, 401)(scope, receive, send)
        data = bytearray()
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(data) + len(chunk) > MAX_BODY_BYTES:
                        return await JSONResponse({"detail": "request_too_large"}, 413)(
                            scope, receive, send
                        )
                    data.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await JSONResponse({"detail": "body_deadline"}, 408)(scope, receive, send)
        pending = True

        async def replay():
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": bytes(data), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(settings=None, client=None):
    @asynccontextmanager
    async def lifespan(app):
        config = settings
        if config is None:
            try:
                config = Settings(
                    os.environ["GATEWAY_TOKEN"],
                    os.environ["GATEWAY_MODEL"],
                    os.environ["GATEWAY_MODEL_DIGEST"],
                    lock_path=os.environ.get("GATEWAY_LOCK_PATH", "/tmp/trend-model-gateway.lock"),
                )
            except (KeyError, ValueError):
                raise RuntimeError("Invalid gateway configuration") from None
        with Path(config.lock_path).open("a") as lock:  # noqa: ASYNC230 – Acquire once at startup.
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            async with httpx.AsyncClient(
                base_url="http://127.0.0.1:11434",
                timeout=httpx.Timeout(connect=3, read=None, write=3, pool=3),
                trust_env=False,
                follow_redirects=False,
            ) as owned:
                app.state.gateway = Gateway(config, client or owned)
                yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(BoundedBody, state=app.state)

    def authorize(request: Request):
        if not hmac.compare_digest(
            request.headers.get("authorization", "").encode(),
            ("Bearer " + app.state.gateway.settings.token).encode(),
        ):
            raise HTTPException(401, "unauthorized")
        return app.state.gateway

    @app.get("/health")
    async def health():
        return {"live": True}

    @app.get("/ready")
    async def ready(request: Request, gateway: Annotated[Gateway, Depends(authorize)]):
        return await gateway.execute(request)

    @app.post("/v1/generate")
    async def generate(
        payload: Generate,
        request: Request,
        gateway: Annotated[Gateway, Depends(authorize)],
    ):
        return await gateway.execute(request, payload)

    return app


app = create_app()
