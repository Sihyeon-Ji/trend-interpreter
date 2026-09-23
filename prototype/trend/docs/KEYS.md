# 필요한 키·계정 정리 (2026-09-14)

> **현황 (09-14 21:15)** — 계정 `ktw251908@gmail.com`, 프로젝트 **`trend-agents-2026`** (사용자 결정: AI Studio 가 만든 'Gemini API' 프로젝트는 다른 계정 소유라 새로 만듦). 결제 계정 **미연결**(사용자 결정: 필요해질 때 붙임). gcloud 584 설치, `gcloud auth login --update-adc` 완료, ADC quota project 설정. `gcloud services enable` 로 BigQuery·YouTube·Generative Language·API Keys 켬. **YouTube 키·Gemini 키는 `gcloud services api-keys create --api-target=service=...` 로 API 별 제한을 걸어 발급해 `.env` 에만 저장** (콘솔 클릭 없이 재발급 가능). BigQuery 공개 데이터셋 조회 실측 성공(결제 없이 샌드박스). **09-15: Bluesky 앱 비밀번호·네이버(API HUB) 키 입력 완료, Reddit 은 Data API 신청 대기.**

전부 `.env` 에만 넣는다 (`.env.example` 참고). 코드·문서·커밋에 절대 넣지 않는다.
원칙: **GCP 프로젝트 하나**에 Gemini·YouTube·BigQuery·Spanner·Cloud Run 을 전부 묶는다. 결제 계정은 그 프로젝트에 한 번만 연결.

## 0. 전제 — Google Cloud 프로젝트 + 결제 계정

| 무엇 | 어디서 | 비용 | 메모 |
|---|---|---|---|
| GCP 프로젝트 생성 | console.cloud.google.com | 무료 | 프로젝트 ID 를 `GOOGLE_CLOUD_PROJECT` 에 |
| 결제 계정 연결 | 콘솔 > 결제 | 신규 계정이면 $300 크레딧 | Gemini 유료 티어 · Spanner 체험(과금 없음이지만 결제 계정 필수) · Cloud Run 에 필요. **09-15 실측: 무료 등급은 모델당 하루 20회**(quota `GenerateRequestsPerDayPerProjectPerModel-FreeTier`=20) — 파이프라인 한 바퀴도 못 돈다. 결제는 선택이 아니라 필수 |
| gcloud CLI | `brew install --cask google-cloud-sdk` → `gcloud auth application-default login` | 무료 | BigQuery·Spanner 클라우드·배포는 키가 아니라 이 로그인(ADC)으로 접근. 이 맥에 아직 없음 |

## 1. 지금 바로 필요 (1주차, 실측 막힌 것)

| 키 | 발급 | 비용 | 여는 기능 | .env |
|---|---|---|---|---|
| **Gemini API 키** | aistudio.google.com/apikey → 위 GCP 프로젝트 선택 → AI Studio 에서 결제 등록(Tier 1) | 3.8 Flash 입력 $0.75/1M, 출력 $3.75/1M. 쇼츠 300개/일 ≈ $2.3/일. 무료 티어는 하루 20요청 수준이라 개발 불가 | 쇼츠 영상 해석 · Google Search grounding 리서치(월 5,000회 무료) · 임베딩(gemini-embedding-001) · 분류 | `GEMINI_API_KEY` |
| **YouTube Data API 키** | 같은 프로젝트 > API 및 서비스 > 라이브러리 > "YouTube Data API v3" 사용 설정 > 사용자 인증 정보 > API 키 만들기 > **API 제한: YouTube Data API v3 만** | 무료, 10,000 unit/일 (프로젝트 단위) | 27개국 인기 영상(1 unit) · 8개 집중 국가 검색(100 unit) | `YOUTUBE_API_KEY` |

Gemini 키와 YouTube 키는 같은 프로젝트의 별도 키로 만드는 걸 권한다(제한 범위가 다름).

## 2. 곧 필요 (2~3주차)

| 키·설정 | 발급 | 비용 | 여는 기능 | .env |
|---|---|---|---|---|
| **ADC 로그인** | `gcloud auth application-default login` (또는 서비스 계정 JSON) | 무료 | BigQuery(GDELT 공개 데이터셋 · 시계열) · Spanner 클라우드 인스턴스 | `GOOGLE_CLOUD_PROJECT`, (선택) `GOOGLE_APPLICATION_CREDENTIALS` |
| **Spanner 무료 체험 인스턴스** | 콘솔 > Spanner > "무료 체험 인스턴스 만들기" (리전: asia-northeast3 서울 권장) | 90일 무료, 10GB, Graph·벡터 포함. 과금 없음 | 사전 지식 그래프 클라우드 이전 (지금은 로컬 에뮬레이터) | `SPANNER_INSTANCE_ID`, `SPANNER_DATABASE_ID` |
| **네이버 데이터랩** | **2026-07-30 부터 개발자센터 신규 등록 불가("신규로 등록할 수 없는 API").** 대신 네이버 클라우드 콘솔 console.ncloud.com > Services > Application Services > **NAVER API HUB** > 이용 신청 > Application 등록 > 데이터랩 **검색어 트렌드 + 쇼핑인사이트** 선택 > 인증 정보(Client ID/Secret). 계정 생성 시 결제수단(카드) 등록이 필요하지만 HUB 는 한시 무료(데이터랩 API 각 월 5만 회) | 무료(한시) | 한국 연령대별 검색 곡선 + 쇼핑 분야(패션의류·화장품/미용·식품…)×연령·성별 클릭 추세 (**한국 한정** 세대 신호, `docs/research/05`) | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| Reddit API (선택) | reddit.com/prefs/apps > "script" 앱 생성 | 무료, 100 QPM | 급증 원인 조사의 커뮤니티 근거(공개 JSON 은 403 — OAuth 필수) | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` |
| Bluesky 앱 비밀번호 (선택) | bsky.app > 설정 > 앱 비밀번호 | 무료 | 글로벌 커뮤니티 검색(공개 검색 엔드포인트는 403) | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` |

## 3. 키가 필요 없는 글로벌 소스 (이미 쓰거나 바로 쓸 수 있음)

| 소스 | 범위 | 비고 |
|---|---|---|
| **Google Trends "Trending now" RSS** `trends.google.com/trending/rss?geo=KR` | 나라별 지금 뜨는 검색어 10개 + 대략 검색량 + 관련 뉴스 | ✅ 2026-09-14 KR·JP·US·ID 실측. 카테고리 없음 → 로컬 모델이 분류 (`docs/research/05`) |
| **Google Trends BigQuery 공개 데이터셋** `bigquery-public-data.google_trends.international_top_*` | 약 50개국 일별 상위 25·급상승 25, 5년 백필 | ADC 만(무료 1TB/월). ✅ 09-14 실측: **42개국** — KR(하위지역 16)·JP(47)·ID(34)·TH·VN·TW·IN·AU·PH·MY 포함, **SG·HK 없음**, US 는 별도 `top_terms`(DMA). 어제 KR 급상승 1위 '홍삼 스파 참 숯가마 사우나', 나머지 연예·스포츠 |
| Google News RSS | 27개 로케일 (KR·JP·TW·HK·TH·VN·ID·PH·MY·SG·IN·AU·US·CA·GB·DE·FR·ES·IT·BR·MX·AR·TR·SA·EG·NG·ZA) | ✅ 실측. 키워드 검색도 로케일별 |
| Wikipedia / Wiktionary 페이지뷰 API | 전 언어판, 일별 | User-Agent 헤더만. ✅ 09-14 ko 상위 목록 실측. 밈·유행어 문서의 언어별 급상승 = 글로벌 관심 신호. 다음 수집기 후보 |
| GDELT (BigQuery 공개 데이터셋) | 100+ 언어, 15분 갱신 | ADC 만. 국가별 뉴스 톤·테마 |
| **Google 뉴스 RSS `site:` 검색** — 더쿠·디시·에펨·인스티즈·루리웹·클리앙·뽐뿌·레딧 (KR), togetter·girlschannel (JP), kaskus (ID), pantip (TH), ptt·dcard (TW) | 구글에 색인된 커뮤니티 글만 | ✅ 09-15 실측(디시 글 검색됨). 크롤링 없이 커뮤니티 근거를 얻는 길 |
| YouTube 댓글 (commentThreads) | 공식 API, 1 unit | ✅ 09-15 실측. 영상 상위 댓글을 커뮤니티 반응 근거로 |
| Hacker News Algolia | 키 없음 | ✅ 실측. 영어권 기술 커뮤니티 |
| Ollama Gemma 4 | 로컬 | 없음 |

## 4. 나중에 (앞문·배포 단계)

| 키 | 용도 |
|---|---|
| Slack Incoming Webhook 또는 Notion/CMS 토큰 | B2B 앞문의 "승인 → 발행" 데모 |
| Firebase 프로젝트 (같은 GCP 프로젝트에 연결) | 프론트 호스팅·Auth 를 쓸 경우 |
| Cloud Scheduler · Cloud Run | ADC 로 처리, 별도 키 없음 |

## 5. 제외·보류 (키를 받아도 쓰지 않음)

- **Google Trends API** — 2026-09 현재도 알파 심사제, 무응답 사례 많음. 신청만 해둘 것 (developers.google.com/search/apis/trends). 대신 위 RSS + BigQuery 공개 데이터셋을 쓴다 (`docs/research/05`).
- **X API** — 월 $100+. 유행어 속도 신호로는 최고지만 비용·약관. 다른 프로젝트의 미러 스크래핑은 내부 신호로만.
- **TikTok Research API** — 연구기관 심사 필요. 쇼츠로 대체.
- **Telegram** — 밈 유통 경로가 아님.

## 6. 글로벌 커버리지에서 정직하게 알아둘 한계

- **연령대별 공개 데이터는 한국(네이버)에만 있다.** 다른 나라의 세대 신호는 Gemini 가 영상·언어·커뮤니티 맥락에서 추정하고, 플랫폼(서브레딧·채널)과 뉴스 등장 지연으로 보강한다. 사전에는 `Segment(세대×국가)` 로 저장하되 근거 종류를 함께 남긴다.
- YouTube `mostPopular` 는 2025-07 이후 음악·영화·게임 차트 위주. 국가별 쇼츠 비율은 실측 후 검색 쿼리 비중 조절.
- 검색(100 unit) 쿼터 때문에 집중 국가는 8개(`REGIONS_FOCUS`)로 시작. 늘리려면 GCP 콘솔에서 YouTube 쿼터 증가 신청(무료, 심사 며칠).
