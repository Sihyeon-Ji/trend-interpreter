FROM ghcr.io/astral-sh/uv:0.12.15 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/gateway-venv UV_LINK_MODE=copy PYTHONUNBUFFERED=1 GATEWAY_LOCK_PATH=/run/trend-gateway/owner.lock
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home gateway
USER gateway
CMD ["/opt/gateway-venv/bin/uvicorn", "model_gateway.app:app", "--host", "0.0.0.0", "--port", "8443", "--workers", "1", "--no-access-log", "--ssl-keyfile", "/run/tls/key.pem", "--ssl-certfile", "/run/tls/cert.pem"]
