FROM ghcr.io/astral-sh/uv:0.12.15 AS uv
FROM python:3.12-slim-bookworm

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

COPY apps/alert-relay/pyproject.toml apps/alert-relay/uv.lock ./
COPY apps/alert-relay/src/ src/
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home app

USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
CMD ["uvicorn", "alert_relay.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
