# For deploying to Cloud Run. The calculation has no external dependencies, so the image is thin.
# Build from this directory, not the repository root: docker build -t pmo-agent prototype/pmo-agent
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Cloud Run injects PORT. Keys are never baked into the image — use Secret Manager or env vars.
ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn pmo_agent.api:app --host 0.0.0.0 --port ${PORT}
