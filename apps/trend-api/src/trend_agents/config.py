"""환경 변수와 모델 ID. .env 는 프로젝트 루트에서 읽는다."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "mock")
MODEL_REQUESTS_ENABLED = os.getenv("MODEL_REQUESTS_ENABLED", "false").lower() == "true"
# 마지막 게시가 이보다 오래되면 오래된 자료다. 수집 PC 가 하루 네 번 게시하던 기준이 12시간이고, 며칠에 한 번 갱신하는 운영 DB(Plan 19)는 Job 에서 늘린다
STALE_AFTER_HOURS = int(os.getenv("STALE_AFTER_HOURS", "12"))
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
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "gemma4:12b")  # 콘텐츠 조사 에이전트·ADK 조사 에이전트(AUDIT_OLLAMA_HOST 에서)
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "").rstrip("/")  # 비우면 Ollama(localhost:11434). OpenAI 호환 서버(vLLM 등)면 예: http://127.0.0.1:11437/v1 — 모델 이름은 GEMMA_LOCAL_MODEL(served-model-name)
GPU_GATEWAY_URL = os.getenv("GPU_GATEWAY_URL", "").rstrip("/")
GPU_GATEWAY_REQUESTS_ENABLED = os.getenv("GPU_GATEWAY_REQUESTS_ENABLED", "false").lower() == "true"
GPU_GATEWAY_TOKEN = os.getenv("GPU_GATEWAY_TOKEN", "")
GPU_GATEWAY_CA_FILE = os.getenv("GPU_GATEWAY_CA_FILE", "")
GPU_GATEWAY_MODEL = os.getenv("GPU_GATEWAY_MODEL", "")
GPU_GATEWAY_MODEL_DIGEST = os.getenv("GPU_GATEWAY_MODEL_DIGEST", "")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")  # 3.8 이 503(무료 등급 용량)일 때만
# 무료 등급 한도는 모델마다 따로다 — AI Studio 'Rate limit' 화면(무료 등급, 2026-10-01 사용자 확인):
#   3.8·3.7·3.6·3.5·3 Flash: 분당 5 · 하루 20 / 3.5·3.1 Flash Lite: 분당 15 · 하루 500 / Gemma 4 31B·26B: 분당 30 · 하루 14,400(토큰 분당 16K)
#   2.5 계열은 '새 사용자에게 더는 열지 않음'(404), 3.1 Pro 는 0.
# 검색 grounding 은 무료 등급에서 Gemini 3 이 '0 / 0' — 몫이 끝난 것이 아니라 처음부터 없다(2.x 만 하루 1,500 인데 2.x 는 404).
# 그래서 기본은 grounding 을 부르지 않는다(GEMINI_SEARCH_GROUNDING=1 은 결제 등급에서만). 'latest' 별칭은 같은 몫을 나눠 쓸 수 있어 넣지 않는다.
GEMINI_MODELS = [m for m in os.getenv("GEMINI_MODELS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,"
                                       "gemini-3-flash-preview,gemini-3.5-flash-lite,gemini-3.1-flash-lite").split(",") if m]
# Gemma 4 는 API(하루 14,400)가 아니라 로컬(Ollama)로 쓴다 — 검색·주소 읽기가 안 되고 분당 토큰 16K 라 긴 일에 맞지 않았다(10-01 실측).
# 모델 배치(10-01, docs: 모델 배치): Gemini 는 사람이 보는 품질이 중요한 일, 로컬 Gemma 는 양이 많거나 오래 도는 일.
#   Gemini Flash(위 사슬 앞쪽)  : 쇼츠 영상 해석, 새 표제어 뜻 조사 정리, 추천·생성
#   Gemini Flash Lite(하루 500) : 사전에 묻기(챗봇) 도구 루프, 조사 에이전트의 밈 후보 제안
#   로컬 Gemma 4                : 번역·쉽게 풀어 쓰기·리스크 분류·추천용 특징·분류·발굴·나라별 서술(e4b, 22번),
#                                 감사관(12B QLoRA)·콘텐츠 조사 에이전트·위키 일괄 등재 뜻풀이(12B, 23번)
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.5-flash-lite")      # 챗봇 도구 루프의 첫 모델(분당 15·하루 500)
LITE_MODEL = os.getenv("LITE_MODEL", "gemini-3.5-flash-lite")
GEMINI_LIMITS = {  # 모델: (분당, 하루). 목록에 없는 모델은 (5, 20)
    "gemini-3.8-flash": (5, 20), "gemini-3.7-flash": (5, 20), "gemini-3.6-flash": (5, 20), "gemini-3.5-flash": (5, 20),
    "gemini-3-flash-preview": (5, 20), "gemini-3.5-flash-lite": (15, 500), "gemini-3.1-flash-lite": (15, 500),
    "gemma-4-31b-it": (30, 14400), "gemma-4-26b-a4b-it": (30, 14400),
}
CHAT_BACKEND = os.getenv("CHAT_BACKEND", "gemini")  # 사전에 묻기(도구 호출 루프)의 모델: gemini(한도·장애 때 로컬 Gemma) | local
GEMINI_SEARCH_GROUNDING = os.getenv("GEMINI_SEARCH_GROUNDING", "0") == "1"
GEMINI_PER_MODEL_DAILY = int(os.getenv("GEMINI_PER_MODEL_DAILY", "20"))   # GEMINI_LIMITS 에 없는 모델의 하루 몫
# 모델 몫을 다 합치면 약 3만이지만(Gemma 4 가 대부분) 파이프라인 한 바퀴가 그만큼 돌면 몇 시간이 걸린다 — 하루 상한은 1,500 으로 둔다
GEMINI_DAILY_BUDGET = int(os.getenv("GEMINI_DAILY_BUDGET", "1500"))
# 이용자 요청(추천의 사진·문구 읽기, 만들기)이 쓰는 하루 Gemini 호출 — 파이프라인 예산과 장부를 따로 둔다. 익명 요청이 파이프라인 몫을 다 쓰면
# 그날 조사·해석이 멈췄다(2026-09-29 검토). 다 쓰면 로컬 Gemma 로, 그것도 없으면 '오늘 한도' 로 알린다.
REQUEST_GEMINI_DAILY = int(os.getenv("REQUEST_GEMINI_DAILY", "300"))  # 이용자 요청 하루 상한 — 챗봇을 Gemini 로 돌리면서(질문 하나에 2~3회) 12 → 300(Flash Lite 하루 500 두 개가 받친다, 10-01)
# Vertex AI 유료 호출의 한 달 금액 상한(USD). 0 이면 금액으로 막지 않는다 — 개발 기본값은 호출 자체가 꺼져 있다.
# Cloud Run 서비스는 Terraform 이 넣는다(10-03 사용자 결정: 월 $20). 예산 알림은 지출을 막지 않으므로 이 장부가 실제로 막는다.
GEMINI_MONTHLY_USD = float(os.getenv("GEMINI_MONTHLY_USD", "0"))
# 출력(추론 토큰 포함) 상한 — 호출 한 번의 최악 비용을 정해 두려고. 구조화 응답·질문 답은 수백~수천 토큰이다.
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "8192"))
GEMINI_RESERVE_INPUT_TOKENS = 32_000  # 호출 전에 잡아 두는 입력 토큰. 실제 비용은 응답의 사용량으로 다시 센다
# Vertex AI global 단가(USD / 100만 토큰: 입력, 출력·추론). 2026-10-03 공식 가격표. 3.6~3.8 Flash 는 2026-12-31 까지 할인가 —
# 2027-01-01 부터 1.5 / 7.5. 금액 상한이 켜져 있으면 이 표에 없는 모델은 부르지 않는다.
GEMINI_PRICES = {
    "gemini-3.8-flash": (0.75, 3.75), "gemini-3.7-flash": (0.75, 3.75), "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.5-flash": (1.50, 9.00), "gemini-3.5-flash-lite": (0.30, 2.50), "gemini-3.1-flash-lite": (0.25, 1.50),
}
# 시장별 포스터 시안(pipeline/poster.py). 기본 꺼짐 — off 면 어떤 모델도 부르지 않고 화면은 구성안만 받는다.
# vertex: model_client.client() 와 같은 Vertex 접속(MODEL_PROVIDER=vertex·MODEL_REQUESTS_ENABLED=true·GCP_PROJECT_ID) /
# api: AI Studio 키(GEMINI_API_KEY, .env 에만)로 — 이것도 MODEL_REQUESTS_ENABLED=true 여야 부른다. 무료 키는 이미지 몫이 0 이다(10-06).
IMAGE_BACKEND = os.getenv("IMAGE_BACKEND", "off").strip().lower()
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-3.1-flash-image")
IMAGE_DAILY = int(os.getenv("IMAGE_DAILY", "30"))   # 하루 이미지 생성 호출 상한 — 이용자 요청 장부와 따로 센다
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")     # IMAGE_BACKEND=api 일 때만 읽는다
# 이미지 모델 단가 '입력,출력'(USD / 100만 토큰). GEMINI_MONTHLY_USD 가 켜져 있으면 단가가 없는 모델은 부르지 않으므로 운영에서는 이것도 넣는다
if _image_price := os.getenv("IMAGE_PRICE_USD", ""):
    GEMINI_PRICES[IMAGE_MODEL] = tuple(float(x) for x in _image_price.split(",")[:2])  # type: ignore[assignment]
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
# 위키미디어·위키·KYM 에 보내는 User-Agent. 위키미디어는 연락처(주소) 없는 UA 를 묶어서 막는다 — 연락처를 넣자 429 가 나던
# 위키백과 검색·위키데이터가 그대로 200 이 됐다(2026-10-01 실측). 개인 메일은 넣지 않는다.
BOT_UA = os.getenv("BOT_UA", "trend-agents/0.1 (+https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup) httpx")

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
