# AI Builder Cup 2026

[English](README.md) | 한국어 | [처음 설치하는 팀원을 위한 가이드](docs/개발환경/처음-설치.md)

**트렌드 통역(Trend Interpreter)** 서비스의 팀 공통 저장소입니다. 세대와 나라를 건너 유행어·밈을
해석해 주는 서비스로, Next.js 화면(`apps/trend-web`), FastAPI API와 수집·사전 파이프라인
(`apps/trend-api`), Discord 운영 알림 중계기(`apps/alert-relay`), GCP 인프라(`infra/gcp`)로 구성됩니다.
`prototype/`의 다른 후보 프로젝트는 참고용으로만 남겨 두었습니다.

## 처음 시작하기

**Git과 Docker만 설치하면 됩니다.** 로컬 Node·Python·uv 설치는 필요하지 않습니다.
Docker Desktop을 켠 뒤 실행하세요. 처음이라면 [상세 설치 가이드](docs/개발환경/처음-설치.md)를 참고하세요.

```bash
git clone --branch develop https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup.git
cd 2026-google-ai-builder-cup
docker compose up -d
```

브라우저에서 **http://localhost:3000**을 엽니다.
첫 실행은 이미지를 내려받고 의존성을 설치하므로 몇 분 걸릴 수 있습니다.
`docker compose ps`에서 `db`, `api`, `web` 상태를 확인하세요.

- **화면 코드 수정** — `apps/trend-web/`의 `app`, `components`, `lib`, `public`을 저장하면 Next.js가 자동 반영합니다.
- **API 코드 수정** — `apps/trend-api/src/`를 저장하면 API가 자동 재시작됩니다.
- **개발 도구** — Node 24.21.0(pnpm은 Corepack), Python 3.12(uv)와 의존성이 컨테이너 안에 설치됩니다.
- **모델** — 기본 개발 환경은 `MODEL_PROVIDER=mock`, `MODEL_REQUESTS_ENABLED=false`라 유료 모델을 호출하지 않습니다.
- **데이터베이스** — 관계형 데이터는 모두 PostgreSQL(`db` 서비스, `postgres_data` 볼륨)에 저장합니다. 개발용 계정은 고정값이고 포트는 호스트에 공개하지 않습니다.
- **인증과 설정** — `.env` 없이 시작합니다. 호스트의 `.env`나 클라우드 인증정보를 읽지 않습니다.

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

## 협업과 배포

공통 개발 브랜치는 `develop`이며 이 브랜치의 push는 GitHub Actions를 실행하지 않습니다.
`release/gcp` push는 변경 범위를 판정해 전체 검증을 한 번 실행하고, 알림 중계기가 바뀌었을 때만 중계기를 배포합니다.

**Trend 앱의 배포 job은 일부러 꺼 두었습니다.** Cloud SQL PostgreSQL 인스턴스와 비공개 API 경로를 준비한 뒤
[Plan 05](docs/plans/05-trend-cloud-run-deployment.md)에 따라 다시 켭니다. 그전까지는 이전에 배포한
`builder-cup` Cloud Run 서비스가 그대로 운영됩니다. `.env`, 인증정보, 모델 파일, Terraform 상태,
수집 데이터는 Git에 올리지 않습니다.

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
