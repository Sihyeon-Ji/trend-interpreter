# AI Builder Cup 2026

[English](README.md) | 한국어 | [처음 설치하는 팀원을 위한 가이드](docs/개발환경/처음-설치.md)

**트렌드 통역(Trend Interpreter)** 서비스의 팀 공통 저장소입니다. 세대와 나라를 건너 유행어·밈을
해석해 주는 서비스로, Next.js 화면(`apps/trend-web`), FastAPI API와 수집·사전 파이프라인
(`apps/trend-api`), Discord 운영 알림 중계기(`apps/alert-relay`), GCP 인프라(`infra/gcp`)로 구성됩니다.
`prototype/`의 다른 후보 프로젝트는 참고용으로만 남겨 두었습니다.

Google Cloud AI Builder Cup 2026 (JAPAC) · 테마 **Media, Content & Digital Experiences** · 팀 **COPYBARA**

| | |
| --- | --- |
| 배포본 | 제출 양식에 적는다(Cloud Run, 주소 뒤에 `?lang=ko`·`en`·`ja` 를 붙이면 화면 언어가 바뀐다) |
| 데모 영상(2분 53초) | [YouTube](https://youtu.be/KHXkWvGHFx4) |
| 평가 | [EVALUATION.md](EVALUATION.md)(영어) · 회차별 집계 [`evals/`](evals/recommend-rounds.csv) |
| 구조 | [그림](#구조) · [시스템 아키텍처](docs/운영/시스템-아키텍처.md) |

![만들기 화면: 시장마다 규칙이 지금 써도 되는 밈을 고르고, AI가 문구를 쓰고, 규칙이 다시 확인하고, 사람이 승인한다](docs/images/create.png)

## 무엇을 하나요

브랜드 마케터와 크리에이터가 밈에 대해 묻는 것은 하나입니다. 지금, 이 시장에서, 문제없이 써도 되나?
트렌드 통역은 수집한 공개 자료로 시장마다(아시아·태평양 10개국과 글로벌) 이 물음에 답합니다.

**왜 필요한가.** 브랜드는 이미 밈으로 말합니다. Morning Consult 조사(2024년 9–10월, Z세대 1,002명)에서 Z세대 소셜미디어
이용자의 71%가 지난 한 달 사이 브랜드가 인터넷 유행어나 밈을 쓰는 것을 봤고, 반응은 좋다 42%·싫다 32%로 갈렸습니다
([Morning Consult, 2024-12-09](https://intel.morningconsult.com/mc-content/analysis/brands-social-media-trends)).
뜻이나 기원을 잘못 알면 공개적으로 문제가 됩니다. 2023년 10월 위메프는 사기 전과자의 말투에서 나온 밈으로 특가 알림을
보냈다가 범죄를 희화화한다는 비판을 받았습니다([이투데이, 2023-10-30](https://www.etoday.co.kr/news/view/2297322)).
2026년 5월 스타벅스 코리아는 5·18 기념일에 '탱크데이' 텀블러 행사를 열었다가 몇 시간 만에 중단했고, 대표가 경질됐으며 모회사 이마트
주가는 다음 날 6% 떨어졌습니다([The Korea Herald, 2026-05-19](https://www.koreaherald.com/article/10741050)).
신조어 자체에도 비용이 있습니다. 2025년 Journal of Marketing Research 연구는 소비자가 브랜드의 신조어를 진정성 없게 보고, 젊은 층도
나이 든 층만큼 부정적이었다고 보고했습니다([BakeryandSnacks, 2026-08-21](https://www.bakeryandsnacks.com/Article/2026/08/21/why-internet-slang-can-damage-food-and-drink-brands/)).
같은 몸짓이나 말도 시장마다 다르게 읽힙니다. 스와치는 2025년 중국에서 광고 사진 속 몸짓이 비하로 읽혀 사진을 내렸습니다
([PBS NewsHour](https://www.pbs.org/newshour/amp/world/swatch-apologizes-for-ad-showing-gesture-seen-as-derogatory-and-racist)).
마케터는 올리기 전에 뜻, 쓰이는 곳, 식고 있는지, 어디서 왔는지를 알아야 합니다.

| 기능 | 이용자가 얻는 것 |
| --- | --- |
| 트렌드 대시보드 | 지금 쓰이는·식어 가는·주의가 필요한 밈과 단계·리스크·12주 언급, 바로 써도 되는 밈을 보여 주는 한눈에 보기 |
| 밈 사전 | 출처를 단 뜻(판 관리)·쓰이는 지역·나라별 차이·이력 |
| 트렌드 브리핑 | PDF로 저장하거나 공유하는 시장 보고서 한 장. 요약은 목록의 사실만으로 쓴다 |
| 캠페인 키트 | 제품 사진이나 문구에 맞는 밈 추천과 SNS 카피·숏폼 대본·썸네일 구성안, 사전 대조 검사 |
| 카피 검사 | 내 문구의 밈이 위험하거나 식었거나 그 시장 말이 아닌지 알리고, 뜻에 맞게 썼는지 AI 의견 |
| 메시지 해석·사전 챗봇 | 붙여 넣은 메시지를 쉬운 말로 풀고, 사전에만 근거해 답하는 읽기 전용 도구 호출 챗봇 |
| 세계 지도·최근 변화 | 밈이 쓰이는 곳과 최근에 바뀐 것 |
| 검수 화면 | 새 뜻·고칠 뜻·리스크 결정을 사람이 승인하는 대기열 |


### 화면

| 둘러보기: 쓰이는 말·식어 가는 말·조심할 말(영어권 시장) | 사전 항목: 써도 되나, 뜻과 출처(“cooked”) |
| --- | --- |
| ![둘러보기](docs/images/explore-en.png) | ![사전 항목](docs/images/entry-en.png) |
| **트렌드 브리핑: 시장 보고서 한 장** | **세계 지도: 시장별·나라를 건넌 밈** |
| ![트렌드 브리핑](docs/images/briefing.png) | ![세계 지도](docs/images/map.png) |

배포본 화면이고, 자료는 2026년 10월 9일에 모은 것입니다(영어 화면).

## AI를 어떻게 쓰나요

판정은 규칙, 서술은 모델입니다. 등재·생애주기·검증 상태·리스크 수준·목록 거르기·추천 순위는 결정론적 코드가 정하고,
모델이 상태를 정하지 않습니다.

- **Vertex AI의 Gemini** (런타임 service account, API key 없음, 월 금액 상한): 새 말의 grounding 조사, 인기 쇼츠 해석,
  제품 사진·문구의 제품 설명, 캠페인 카피 생성, 브리핑 요약, 카피가 밈을 뜻에 맞게 썼는지 의견.
- **Gemma 4** (로컬·Kaggle, 배치 파이프라인): 새로 실린 말의 표제어 읽기·뜻 언어판 초안, 근거 문장의 리스크 분류, 사전 뜻을 출처와 대조하는 감사관.
  감사관 QLoRA 파인튜닝은 판정 형식은 배웠지만 판단이 나아졌다는 근거가 없어 기본 모델을 씁니다([EVALUATION.md](EVALUATION.md)).
- **Agent Development Kit(ADK)**: 네 에이전트 팀(수집 → 조사 → 사전 편집 → 게시)이 같은 결정론 단계를 도구로 부르고 실행 보고서를 남깁니다.
  에이전트는 상태를 정하지 않습니다([`agents/team.py`](apps/trend-api/src/trend_agents/agents/team.py)).
- 수집 서버는 Gemini API(Google AI Studio 키)로 Gemini 를 하루 호출 예산 안에서 부릅니다.
- 모델 결과는 화면에 나가기 전에 규칙이 검사합니다. 뜻은 맞는 참고 문서가 있어야 하고, 생성한 카피는 고른 밈·욕설·길이를
  다시 확인하며, 비었거나 메모 같은 뜻은 내보내지 않습니다.

배포된 화면에서 보이는 곳:

- 사전 항목마다 'Gemma 가 분류한 실제 문장으로 규칙이 리스크를 정했다' 고 밝히고, 둘러보기 상세에 그 요약('문장 12개 중 긍정 12')과
  '이렇게 만들었어요' 설명을 둡니다. 커뮤니티 글은 건수만 세고 인용하지 않습니다.
- [`/about`](apps/trend-web/app/about/page.tsx)은 Gemini·Gemma·규칙·사람이 각각 무엇을 하는지 쉬운 말로 설명합니다.
  다른 이용자 화면에는 모델 이름을 두지 않습니다.
- 검수자용 상태 화면은 파이프라인 단계마다 모델별 공개 결과 수와, 최근 24시간의 모델 호출 수·걸린 시간을 보입니다.
- 검수자 도구는 용어의 최신 기사 제목이나 고른 용어(5개까지)를 GPU VM 의 Gemma 에게 보내 공개 판정과 나란히 보일 수 있게
  만들어 두었습니다(같은 규칙으로 매기고 저장하지 않음). L4 VM 은 Terraform([`infra/gcp/hybrid/gpu.tf`](infra/gcp/hybrid/gpu.tf))에
  정의돼 있지만 비용 때문에 배포하지 않아, 두 버튼은 'GPU 꺼짐'을 바로 알립니다.
  Gemma 의 배치 작업 실적은 검수자 상태 화면의 모델 기록에 있습니다.

심사위원은 제출 양식에 적은 읽기 전용 검수 계정으로 로그인할 수 있습니다. 관리 화면은 모두 열리고, 승인·제외·리스크 결정은 막힙니다.

무엇을 어떻게 쟀는지, 수치와 한계, 남은 과제는 [EVALUATION.md](EVALUATION.md)(영어)에 있습니다.

## 구조

![구조: 배치에서 사전을 만들고, 요청 때는 규칙이 고르고 Gemini가 쓰고 규칙이 검사하고 사람이 승인한다](docs/images/architecture.png)

실선 칸은 코드·규칙, 점선 칸은 모델이고, 파란 아이콘은 사람이 승인하는 곳입니다.

## Google Cloud 사용

| 서비스 | 용도 |
| --- | --- |
| Cloud Run | 웹·비공개 API·알림 중계기. 새 revision을 검사한 뒤 트래픽을 옮긴다 |
| Cloud SQL for PostgreSQL | 게시된 사전·근거·대시보드 데이터 |
| Vertex AI (Gemini) | 요청 때 조사·생성·요약 |
| Cloud Storage | 수집 서버가 넘기는 고정 데이터 스냅숏 |
| Cloud Logging·Monitoring·Pub/Sub | 팀 Discord 채널로 가는 운영 알림 |
| Secret Manager | 런타임 비밀값 |

수집은 별도 팀 서버에서 돌고, 검증한 스냅숏만 Cloud SQL에 게시합니다. 자세한 것은 [시스템 아키텍처](docs/운영/시스템-아키텍처.md)에 있습니다.

## 처음 시작하기

**Git과 Docker만 설치하면 됩니다.** 로컬 Node·Python·uv 설치는 필요하지 않습니다.
Docker Desktop을 켠 뒤 실행하세요. 처음이라면 [상세 설치 가이드](docs/개발환경/처음-설치.md)를 참고하세요.

```bash
git clone --branch develop https://github.com/Sihyeon-Ji/trend-interpreter.git
cd trend-interpreter
docker compose up -d
```

브라우저에서 **http://localhost:3000**을 엽니다.
첫 실행은 이미지를 내려받고 의존성을 설치하므로 몇 분 걸릴 수 있습니다.
`docker compose ps`에서 `db`, `api`, `web` 상태를 확인하세요.

- **화면 코드 수정** – `apps/trend-web/`의 `app`, `components`, `lib`, `public`을 저장하면 Next.js가 자동 반영합니다.
- **API 코드 수정** – `apps/trend-api/src/`를 저장하면 API가 자동 재시작됩니다.
- **개발 도구** – Node 24.21.0(pnpm은 Corepack), Python 3.12(uv)와 의존성이 컨테이너 안에 설치됩니다.
- **모델** – 기본 개발 환경은 `MODEL_PROVIDER=mock`, `MODEL_REQUESTS_ENABLED=false`라 유료 모델을 호출하지 않습니다.
- **데이터베이스** – 관계형 데이터는 모두 PostgreSQL(`db` 서비스, `postgres_data` 볼륨)에 저장합니다. 개발용 계정은 고정값이고 포트는 호스트에 공개하지 않습니다.
- **인증과 설정** – `.env` 없이 시작합니다. 호스트의 `.env`나 클라우드 인증정보를 읽지 않습니다.

첫 화면은 **예시 데이터 모드**입니다. 지구본, 사전, 메시지 해석 화면이 내장 예시로 열립니다.
로컬 API의 실데이터를 보려면 `DATA_MODE=api docker compose up -d`로 다시 켭니다.
API 문서는 http://localhost:8000/docs, 상태 확인은 http://localhost:8000/health 입니다.

## 명령어는 Docker Compose로 통일합니다

아래 명령은 모두 `compose.yaml`이 있는 저장소 루트에서 실행합니다.
**상황별 명령, 실행 결과, 옵션 뜻은 [개발 명령어 모음](docs/개발환경/개발-명령어.md)에 정리했습니다.**

| 할 일 | 명령어 |
| --- | --- |
| 개발 환경 켜기 | `docker compose up -d` |
| 실행 상태 확인 | `docker compose ps` |
| 로그 보기 | `docker compose logs -f` |
| 개발 환경 끄기 (DB 볼륨은 유지) | `docker compose down` |
| 의존성·이미지 설정 변경 반영 | `docker compose up -d --build` |
| API 테스트·릴리스 테스트·웹 lint·웹 빌드 | `docker compose run --rm --build check` |
| 서비스 lockfile 취약점 검사 | `docker compose run --rm security-check` |
| 브라우저 연동 테스트 | `docker compose run --rm --build e2e` |
| 인프라 설정 로컬 검증 | `docker compose run --rm infra-check` |
| Python 패키지 추가 | `docker compose run --rm --build uv add 패키지명` |
| 웹 패키지 추가 | `docker compose run --rm --build pnpm add 패키지명` |

`up -d`는 `db`, `api`, `web`을 켭니다. 검사·브라우저 테스트·도구는 명령으로 지정할 때만 실행되며, `check`는 API 테스트를 위해 `db`를 함께 켭니다.
E2E는 필요한 개발 서버를 자동으로 시작하며, 첫 E2E 빌드에서는 테스트용 Chromium도 컨테이너에 설치합니다.
검사 통과는 코드 계약과 빌드를 확인한 것이지 AI 답변 품질을 평가한 것은 아닙니다.

## 무엇을 바꾸면 다시 빌드하나요?

연결된 소스 폴더 안의 파일은 새로 추가해도 자동 반영됩니다.
패키지 목록·lockfile·Dockerfile·Compose 설정을 변경했거나 그런 변경을 pull했다면 다음을 실행하세요.

```bash
docker compose up -d --build
```

호스트의 `node_modules`나 `.venv`는 컨테이너와 공유하지 않습니다.

## 패키지를 추가하거나 업데이트할 때

`docker compose run --rm --build uv add 패키지명`(API) 또는
`docker compose run --rm --build pnpm add 패키지명`(웹)을 사용하면 목록과 lockfile이 로컬 저장소에 함께 기록됩니다.
재빌드와 검증 후 `pyproject.toml`·`uv.lock` 또는 `package.json`·`pnpm-lock.yaml`을 같은 커밋에 포함하세요.

## 모델 호출은 어떻게 제어하나요?

| 설정 | 로컬 기본값 | 운영 의도 |
| --- | --- | --- |
| `MODEL_PROVIDER` | `mock` | `vertex` |
| `MODEL_REQUESTS_ENABLED` | `false` | 비용을 쓸 때만 `true` |
| `GCP_PROJECT_ID`, `GOOGLE_CLOUD_LOCATION` | 비움 | Vertex AI 프로젝트·위치 |
| `GEMINI_DAILY_BUDGET` | `36` | DB에 기록하는 하루 호출 상한 |

Gemini 클라이언트는 `apps/trend-api/src/trend_agents/model_client.py` 한 곳에서만 만들며, API 키 대신
Cloud Run 런타임 서비스 계정으로 Vertex AI에 접속합니다. 저장소 어디에도 Gemini API 키는 없습니다.
로컬 Gemma는 Ollama 또는 OpenAI 호환 서버(`LOCAL_LLM_BASE_URL`)로 연결합니다.
수집기 키(YouTube, Naver)는 `apps/trend-api/.env`에만 둡니다. 자세한 내용은 [AI 호출 제어](docs/운영/AI-호출-제어.md)를 보세요.

## 폴더 구성

```text
compose.yaml                 개발 실행과 검사 명령
Dockerfile.dev               개발 도구와 브라우저 테스트 이미지
apps/trend-web/              Next.js 화면, 브라우저 테스트, 배포용 Dockerfile
apps/trend-api/              FastAPI API, PostgreSQL 기반 수집·사전 파이프라인, 배포용 Dockerfile
apps/alert-relay/            Pub/Sub 알림을 Discord로 보내는 비공개 Cloud Run 중계기
models/vllm/                 별도 GPU 서버용 Gemma 설정
infra/gcp/                   GCP 인프라 설정
.github/workflows/           자동 검증과 배포
scripts/                     릴리스·smoke 검사·운영 작업의 구현
tests/                       릴리스 분류·복구 테스트
prototype/                   이전 후보 프로젝트(빌드·검사 대상 아님)
docs/                        설치, 운영, 트렌드 설계 기록, 계획 문서
```

## 문서와 팀 링크

- [전체 문서 색인](docs/README.md)
- [트렌드 방향·파이프라인·조사 기록](docs/트렌드/방향.md)
- [현재 계획과 완료 계획 archive](docs/plans/README.md)
- [팀원용 처음 설치 가이드](docs/개발환경/처음-설치.md)
- [운영 AI 호출 중지·예산 조정](docs/운영/AI-호출-제어.md)
- [아키텍처](docs/운영/시스템-아키텍처.md)
- [GCP 설정·비용·삭제·복구](docs/운영/GCP-운영.md)
- [팀 협업 방식](docs/개발환경/팀-작업-방식.md)
- [Gemma/vLLM 안내](models/vllm/README.md)
- [GitHub 프로젝트 보드](https://github.com/users/Sihyeon-Ji/projects/1)

## 라이선스

[Apache License 2.0](LICENSE). 외부 라이브러리는 각자의 라이선스를 따릅니다.
