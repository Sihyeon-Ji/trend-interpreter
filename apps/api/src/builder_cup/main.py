import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from builder_cup import database
from builder_cup.config import Settings
from builder_cup.graph_lab import GraphResult, run_graph
from builder_cup.providers import Provider, ProviderFailure, create_provider
from builder_cup.schemas import AnalyzeRequest, AnalyzeResponse
from builder_cup.workflow import analyze


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "severity": record.levelname,
                "message": record.getMessage(),
                **getattr(record, "fields", {}),
            }
        )


logger = logging.getLogger("builder_cup")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
logger.setLevel(logging.INFO)
logger.propagate = False


def create_app(settings: Settings | None = None, provider: Provider | None = None) -> FastAPI:
    config = settings or Settings()
    if os.getenv("K_SERVICE") and not config.demo_api_key:
        raise RuntimeError("DEMO_API_KEY is required on Cloud Run")
    if config.database_lab_enabled and (os.getenv("K_SERVICE") or config.model_provider != "mock"):
        raise RuntimeError("Database lab is only available in local mock mode")
    if config.workflow_lab_enabled and (os.getenv("K_SERVICE") or config.model_provider != "mock"):
        raise RuntimeError("Workflow lab is only available in local mock mode")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.provider = provider or create_provider(config)
        yield
        await app.state.provider.close()

    app = FastAPI(title="AI Builder Cup", lifespan=lifespan)

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Never emit provider payloads, credentials, or raw input in logs.
            logger.error(
                "request_failed",
                extra={
                    "fields": {
                        "request_id": request.state.request_id,
                        "exception_type": type(exc).__name__,
                    }
                },
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "request_id": request.state.request_id,
                    }
                },
            )
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(
            "http_request",
            extra={
                "fields": {
                    "request_id": request.state.request_id,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": int((time.monotonic() - start) * 1000),
                }
            },
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, _exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_input",
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.exception_handler(ProviderFailure)
    async def provider_error(request: Request, exc: ProviderFailure):
        status = 504 if exc.code == "model_timeout" else 502
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": exc.code,
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "provider": config.model_provider}

    @app.post("/api/analyze", response_model=AnalyzeResponse)
    async def analyze_text(body: AnalyzeRequest, request: Request):
        expected = f"Bearer {config.demo_api_key}"
        received = request.headers.get("Authorization", "")
        if config.demo_api_key and not hmac.compare_digest(received.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="Invalid demo access code")
        result = await analyze(
            body.text, request.state.request_id, request.app.state.provider, config
        )
        logger.info("analysis_completed", extra={"fields": result.model_dump(exclude={"result"})})
        return result

    if config.database_lab_enabled:

        @app.exception_handler(database.DatabaseUnavailable)
        async def database_error(request: Request, _exc: database.DatabaseUnavailable):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "database_unavailable",
                        "request_id": request.state.request_id,
                    }
                },
            )

        @app.post("/api/lab/records", response_model=database.LabRecord, status_code=201)
        def create_lab_record():
            return database.create_record(config)

        @app.get("/api/lab/records/{record_id}", response_model=database.LabRecord)
        def read_lab_record(record_id: uuid.UUID):
            record = database.read_record(config, record_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Lab record not found")
            return record

    if config.workflow_lab_enabled:

        @app.post("/api/lab/workflow", response_model=GraphResult)
        async def workflow_lab(body: AnalyzeRequest, request: Request):
            return await run_graph(
                body.text, request.state.request_id, request.app.state.provider, config
            )

    # Keep unknown API routes from falling through to the static site.
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def unknown_api(path: str):
        raise HTTPException(status_code=404, detail="Not found")

    if Path(config.web_dist).is_dir():
        app.mount("/", StaticFiles(directory=config.web_dist, html=True), name="web")
    return app
