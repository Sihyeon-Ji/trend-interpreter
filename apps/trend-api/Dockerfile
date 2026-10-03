FROM ghcr.io/astral-sh/uv:0.12.15 AS uv
FROM python:3.12-slim-bookworm

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY scripts/ scripts/
RUN uv sync --locked --no-dev \
    && useradd --uid 10001 --create-home trend \
    && mkdir -p /app/data \
    && chown trend:trend /app/data

USER trend
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
CMD ["uvicorn", "trend_agents.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
