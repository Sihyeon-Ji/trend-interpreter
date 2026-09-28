"""환경 변수와 모델 ID. .env 는 프로젝트 루트에서 읽는다."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "mock")
MODEL_REQUESTS_ENABLED = os.getenv("MODEL_REQUESTS_ENABLED", "false").lower() == "true"
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
NAVER_API_HUB = os.getenv("NAVER_API_HUB", "1") == "1"  # 1 = NAVER API HUB(네이버 클라우드, 2026-07-30 이후 신규), 0 = 구 개발자센터 키
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")  # 선택: reddit.com/prefs/apps (script) — 없으면 Reddit 검색은 건너뜀
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "")  # 선택: Bluesky 계정 + 앱 비밀번호 — 없으면 건너뜀
BLUESKY_APP_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD", "")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMMA_LOCAL_MODEL = os.getenv("GEMMA_LOCAL_MODEL", "gemma4:12b")
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "").rstrip("/")  # 비우면 Ollama(localhost:11434). OpenAI 호환 서버(vLLM 등)면 예: http://127.0.0.1:11437/v1 — 모델 이름은 GEMMA_LOCAL_MODEL(served-model-name)
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")  # 3.8 이 503(무료 등급 용량)일 때만
GEMINI_DAILY_BUDGET = int(os.getenv("GEMINI_DAILY_BUDGET", "36"))  # 하루 Gemini 호출 상한. 무료 등급 실측(09-15): 모델당 하루 20회(GenerateRequestsPerDayPerProjectPerModel-FreeTier) → 3.8+3.5 합쳐 약 40. 결제(Tier 1) 연결 시 400 정도로
USE_LOCAL_GEMMA = os.getenv("USE_LOCAL_GEMMA", "0") == "1"  # 번역·재작성에 로컬 Gemma 를 쓸지 (꺼져 있으면 Gemini)
PIPELINE_INTERVAL_HOURS = float(os.getenv("PIPELINE_INTERVAL_HOURS", "6"))
API_PORT = int(os.getenv("API_PORT", "8080"))
# 계정. 비밀번호는 해시만 저장한다 — scripts/set_account.py 로 만든다. 자세한 형식은 auth.py.
ACCOUNTS = os.getenv("ACCOUNTS", "")
FRONTEND_API_TOKEN = os.getenv("FRONTEND_API_TOKEN", "")  # 프론트 서버만 아는 값. 로그인이 필요한 API 는 이게 있어야 받는다
WEB_ORIGINS = [o for o in os.getenv("WEB_ORIGINS", "http://localhost:3100,http://localhost:3000").split(",") if o]
GOOGLE_CLOUD_PROJECT = GCP_PROJECT_ID  # BigQuery·Spanner 클라우드 (ADC 와 함께)

DATA_DIR = ROOT / "data"  # 로그·시드·계정 메모. 데이터는 PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trend:trend@localhost:5432/trend")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "8"))  # API 연결 풀 크기 = Cloud Run 인스턴스당 동시 요청 수

# 수집 대상 국가 (ISO 3166-1 alpha-2). 트렌드는 전세계 대상.
# REGIONS_ALL: mostPopular 는 1 unit/회 → 넓게 돈다. REGIONS_FOCUS: search 는 100 unit/회 → 쿼터상 집중 국가만.
REGIONS_ALL = [
    "KR", "JP", "TW", "HK", "TH", "VN", "ID", "PH", "MY", "SG", "IN", "AU",   # JAPAC
    "US", "CA", "GB", "DE", "FR", "ES", "IT", "BR", "MX", "AR", "TR", "SA", "EG", "NG", "ZA",  # 글로벌
]
# 목표 지역(ADR 0001): 동·동남아 10개국. 중국 본토는 제외. 미국·브라질 등은 REGIONS_ALL 로 계속 모은다.
REGIONS_FOCUS = ["KR", "JP", "TW", "HK", "TH", "VN", "ID", "PH", "MY", "SG"]
REGIONS = REGIONS_FOCUS  # 기존 참조 호환
# 표제어 언어 → 그 말을 쓰는 나라. 조사할 곳과, 조사가 나라를 비워 둔 용어를 대시보드에 둘 곳. 중국어는 대만(본토 제외, ADR 0001).
LANG_REGION = {"ko": "KR", "ja": "JP", "id": "ID", "th": "TH", "vi": "VN", "zh": "TW", "tl": "PH", "fil": "PH", "ms": "MY"}


def require(name: str, value: str) -> str:
    if not value:
        raise SystemExit(f"[config] {name} 가 .env 에 없습니다. .env.example 을 참고해 채워주세요.")
    return value
