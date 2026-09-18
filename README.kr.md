# AI Builder Cup 2026

한국어 | [English](README.md) | [처음 설치하는 팀원을 위한 가이드](docs/setup.md)

Google AI Builder Cup에 참가하는 팀의 공통 개발 저장소입니다. 최종 주제가 정해지기 전에도
화면과 API를 실행하고, 모델 연결과 테스트를 준비할 수 있도록 기본 환경을 구성했습니다.

**처음 클론했다면 [팀원용 설치 가이드](docs/setup.md)를 순서대로 따라 주세요.**
필수 도구 설치부터 첫 화면 확인까지 설명되어 있습니다.

## 현재 상태

- 공통 앱은 React·TypeScript·Vite 화면과 Python·FastAPI 서버로 구성되어 있습니다.
- Node.js는 **24.21.0**, Python은 **3.12**를 사용합니다. Python은 uv가 준비합니다.
- 기본 실행 모드는 **Mock**입니다. 실제 AI를 호출하지 않고 정해진 규칙으로 응답하므로
  로컬 실행에 GCP 계정, 결제 설정, API 키, GPU가 필요하지 않습니다.
- 실제 Gemini와 별도 Gemma/vLLM 서버를 연결할 수 있는 구조가 준비되어 있습니다.
- `prototype/`은 주제 검토용 후보 프로젝트입니다. 공통 앱과 별도로 실행하며,
  현재 최종 주제가 정해진 것은 아닙니다.
- **GCP 배포와 과금 활성화는 보류 중입니다.**

## 빠른 시작

Git, Make, uv, fnm 설치와 fnm 셸 설정이 끝났다는 전제입니다. 아직 준비하지 않았다면
[상세 설치 가이드](docs/setup.md)를 먼저 확인하세요. 이미 nvm을 사용한다면 아래의
`fnm install` / `fnm use`를 `nvm install` / `nvm use`로 바꾸면 됩니다.

### 1. 저장소 받기와 Node 선택

```bash
mkdir -p ~/workspace
cd ~/workspace
git clone --branch develop https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup.git
cd 2026-google-ai-builder-cup
fnm install
fnm use
node --version
```

마지막 출력이 `v24.21.0`이면 됩니다. 이미 클론했다면 해당 저장소 폴더로 이동한 뒤
`fnm install`부터 실행하세요. 특정 사용자명이나 `/Users/sean` 경로는 필요하지 않습니다.

### 2. 프로젝트 설치

```bash
make setup
```

Python 환경과 앱 의존성을 설치하고, `.env`가 없으면 예제에서 생성합니다.
기존 `.env`는 덮어쓰지 않습니다. 처음에는 `MODEL_PROVIDER=mock`을 유지하세요.

### 3. 정상 설치 확인

서버를 켜기 전에 실행하세요.

```bash
make check test build eval
(cd apps/web && npx playwright install chromium)
make e2e
```

Ubuntu·WSL에서 브라우저 시스템 라이브러리가 부족하면
[설치 가이드의 검증 단계](docs/setup.md#verify)를 확인하세요.
`make eval`은 Mock 기반 입출력 검증이며 실제 AI 품질 평가가 아닙니다.

### 4. 실행

터미널 두 개를 열고, **각각 저장소 루트 폴더에서** 실행하세요.

터미널 1 — API 서버

```bash
make api
```

터미널 2 — 웹 화면

```bash
fnm use
make web
```

브라우저에서 **http://127.0.0.1:5173**을 여세요. `Analyze text →` 버튼을 누른 뒤 결과와
`Demo data · no AI model was called` 표시가 보이면 기본 연결이 정상입니다.
처음 생성한 `.env`에서는 `Team access code`를 비워 둬도 됩니다.
서버를 종료하려면 각 터미널에서 `Ctrl+C`를 누르세요.

## 자주 쓰는 명령어

아래 명령어는 모두 저장소 루트, 즉 `Makefile`이 있는 폴더에서 실행합니다.

| 명령어 | 하는 일 |
| --- | --- |
| `make` | 사용 가능한 명령 안내 |
| `make setup` | Node 버전 확인, 의존성 설치, 최초 `.env` 생성 |
| `make api` | API 개발 서버 실행, 포트 8000 |
| `make web` | 웹 개발 서버 실행, 기본 포트 5173 |
| `make check` | 코드 스타일과 타입 검사 |
| `make test` | API 등 Python 테스트 |
| `make build` | 배포용 웹 파일 생성 |
| `make eval` | 실제 모델을 호출하지 않는 Mock 계약 검증 |
| `make e2e` | 웹 빌드 후 브라우저 연동 테스트 |
| `make docker` | Docker로 Mock 앱 빌드·실행, 포트 8080 |
| `make infra-check` | Terraform 설정 로컬 검증, 클라우드 리소스 생성 없음 |

E2E는 자체 서버를 띄우므로 포트 8000이 비어 있어야 합니다.
Docker와 Terraform은 해당 기능을 사용할 때만 설치하면 됩니다.

## 폴더 구성

```text
apps/web/                    공통 웹 화면과 브라우저 테스트
apps/api/src/builder_cup/     공통 API, 입력 검증, 모델 연결
models/vllm/                 별도 GPU 서버용 Gemma 실행 설정
infra/gcp/                   GCP 인프라 설정
.github/workflows/           자동 검증과 배포 워크플로
scripts/                     배포, 롤백, 평가 스크립트
tests/                       API와 오류 처리 테스트
evaluation-cases/            평가용 입력 데이터
prototype/                   팀에서 검토할 후보 프로젝트
docs/                        설치, 구조, 운영, 협업 문서
```

## 협업과 배포

공통 개발 기준 브랜치는 `develop`입니다. `develop` push와 PR에서는 자동 검증을 실행합니다.
`release/gcp`에 push하면 실제 GCP 배포 워크플로가 실행되므로, 배포를 재개하기로 결정하기 전에는
해당 브랜치에 push하거나 `make infra-apply`를 실행하지 마세요.

`.env`, 인증정보, 모델 파일, 생성된 평가 결과는 Git에 올리지 않습니다.
실제 모델 연결이 필요할 때는 [영문 모델 연결 안내](README.md#real-gemini)와
[운영 문서](docs/operations.md)를 확인하고 담당자와 설정을 맞춰 주세요.
`make eval-live`는 실제 모델을 호출할 수 있어 비용이 발생할 수 있습니다.

## 문서와 팀 링크

- [팀원용 처음 설치 가이드](docs/setup.md) — 운영체제별 준비, 실행, 문제 해결
- [이전 작업과 남은 일](docs/session-handoff.md) — 영문 인수인계 기록
- [아키텍처](docs/architecture.md) — 공통 앱의 구조와 역할 분리
- [운영 안내](docs/operations.md) — GCP, 비용, 인증, 로그, 롤백
- [팀 협업 방식](docs/team-workflow.md)
- [Gemma/vLLM 안내](models/vllm/README.md)

- [GitHub 프로젝트 보드](https://github.com/users/Sihyeon-Ji/projects/1)
- [GitHub 저장소](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup)

외부 서비스 링크는 참고용입니다. 저장소를 클론한다고 해당 서비스 인증까지 설정되지는 않습니다.
