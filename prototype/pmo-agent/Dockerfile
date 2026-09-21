# Cloud Run 배포용. 계산 로직에 외부 의존성이 없어 이미지가 얇다.
# 저장소 루트가 아니라 이 디렉터리에서 빌드한다: docker build -t pmo-agent prototype/pmo-agent
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Cloud Run 이 PORT 를 주입한다. 키는 이미지에 굽지 않고 Secret Manager/환경변수로 넣는다.
ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn pmo_agent.api:app --host 0.0.0.0 --port ${PORT}
