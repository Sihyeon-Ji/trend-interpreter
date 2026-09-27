# API + 파이프라인 컨테이너 (Cloud Run). 웹은 web/Dockerfile.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY scripts ./scripts
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" PORT=8080 API_PORT=8080
# 기본은 API. 파이프라인 잡은 같은 이미지로 `python scripts/run_pipeline.py` 를 Cloud Run Job 으로 실행.
CMD ["python", "scripts/serve_api.py"]
