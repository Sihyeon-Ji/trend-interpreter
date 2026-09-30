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
# 사전 감사관(pipeline/audit.py). 두 번의 시험에서 가장 안정적이던 Gemma 4 12B 체크리스트형(2026-09-30). 다른 GPU 서버의 Ollama 를 쓸 수 있다.
AUDIT_MODEL = os.getenv("AUDIT_MODEL", "gemma4:12b")
AUDIT_OLLAMA_HOST = os.getenv("AUDIT_OLLAMA_HOST", "")
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "").rstrip("/")  # 비우면 Ollama(localhost:11434). OpenAI 호환 서버(vLLM 등)면 예: http://127.0.0.1:11437/v1 — 모델 이름은 GEMMA_LOCAL_MODEL(served-model-name)
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")  # 3.8 이 503(무료 등급 용량)일 때만
GEMINI_DAILY_BUDGET = int(os.getenv("GEMINI_DAILY_BUDGET", "36"))
# 이용자 요청(추천의 사진·문구 읽기, 만들기)이 쓰는 하루 Gemini 호출 — 파이프라인 예산과 장부를 따로 둔다. 익명 요청이 파이프라인 몫을 다 쓰면
# 그날 조사·해석이 멈췄다(2026-09-29 검토). 다 쓰면 로컬 Gemma 로, 그것도 없으면 '오늘 한도' 로 알린다.
REQUEST_GEMINI_DAILY = int(os.getenv("REQUEST_GEMINI_DAILY", "12"))  # 하루 Gemini 호출 상한. 무료 등급 실측(09-15): 모델당 하루 20회(GenerateRequestsPerDayPerProjectPerModel-FreeTier) → 3.8+3.5 합쳐 약 40. 결제(Tier 1) 연결 시 400 정도로
USE_LOCAL_GEMMA = os.getenv("USE_LOCAL_GEMMA", "0") == "1"  # 번역·재작성에 로컬 Gemma 를 쓸지 (꺼져 있으면 Gemini)
# Know Your Meme 수집기(Plan 12). 기본 꺼짐 — 이용 약관(자동 접근은 사람 수준의 속도만, 내용은 개인적 정보 이용만·동의 없는 복제·게시 금지,
# 서면 허락 없는 상업적 이용 금지) 때문에 제품에 쓸지는 사용자가 정한다. 켜도 문서 주소와 제목만 근거로 둔다.
KNOWYOURMEME_ENABLED = os.getenv("KNOWYOURMEME_ENABLED", "false").lower() in ("1", "true")
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
# 표제어 하나의 나라는 home_region 으로 본다(광동어는 홍콩).
LANG_REGION = {"ko": "KR", "ja": "JP", "id": "ID", "th": "TH", "vi": "VN", "zh": "TW", "tl": "PH", "fil": "PH", "ms": "MY"}
# 광동어에만 쓰는 글자. 이런 글자가 든 표제어는 홍콩 말이다 — 중국어를 모두 대만으로 보내 홍콩 말도 대만 뉴스·커뮤니티에서 조사했다(Plan 04).
CANTONESE_CHARS = frozenset("㗎咗嘅冇佢啲喺嘢嚟唔")
# 광동어 언어 코드. ISO 639-1 에 없어 모델이 'yue' 를 주거나 두 글자로 잘린 'yu' 가 온다(spot 이 行得㗎啦 를 zh·yu 로 두 번 넣었다, 09-28).
CANTONESE_LANGS = ("yue", "yu")


def home_region(text: str, lang: str | None) -> str | None:
    """표제어의 나라. 광동어(광동어 글자가 들었거나 언어 코드가 광동어)는 홍콩, 그 밖에는 LANG_REGION(다른 중국어는 대만)."""
    if (lang or "").lower() in CANTONESE_LANGS or any(ch in CANTONESE_CHARS for ch in text or ""):
        return "HK"
    return LANG_REGION.get(lang or "")


# 여러 목표 지역이 같이 쓰는 말(첫째가 표제어의 나라). 뉴스 언급은 표제어의 나라 판에 더해 나머지 나라 판도 재고, 커뮤니티 조사는 이 나라들로
# 번갈아 한다(Plan 04). 광동어는 홍콩만 — 중국어를 대만 뉴스판에서만 재서 홍콩 키워드 검색이 0건이었다(2026-09-29).
ALTERNATE_REGIONS = {"zh": ("TW", "HK")}
# 영어 표제어는 미국 뉴스판에 더해 이 나라 영어판을 하나씩 돌아가며 재고, 커뮤니티도 이 나라 사이트를 돌아가며 뒤진다 — 영어 표제어를
# 미국 뉴스에서만 쟀다(키워드 검색 US 195 · SG 2 · MY 3 · PH 2, 2026-09-29). 이 영어판 결과는 그 나라 매체가 낸 기사(또는 조사가 그 나라에서
# 쓴다고 정한 말)만 근거로 쓴다: 미국판에 없던 기사에도 BBC·Bloomberg 같은 전 세계 매체가 섞여 그 나라 기사라는 보장이 없다(Plan 04 실측).
ENGLISH_EDITIONS = ("SG", "MY", "PH")


def region_cycle(text: str, lang: str | None) -> tuple[str, ...]:
    """이 표제어를 같이 볼 나라들(ALTERNATE_REGIONS). 광동어는 홍콩 말이라 홍콩만 본다(빈 튜플이면 표제어의 나라 하나)."""
    return () if home_region(text, lang) == "HK" else ALTERNATE_REGIONS.get(lang or "", ())


def next_region(cycle: tuple[str, ...], last: str | None) -> str:
    """돌아가며 볼 나라 가운데 지난번 다음 차례. 처음이거나 지난번이 목록에 없으면 첫 나라."""
    return cycle[(cycle.index(last) + 1) % len(cycle)] if last in cycle else cycle[0]


def require(name: str, value: str) -> str:
    if not value:
        raise SystemExit(f"[config] {name} 가 .env 에 없습니다. .env.example 을 참고해 채워주세요.")
    return value
