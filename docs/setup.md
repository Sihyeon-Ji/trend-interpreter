# 팀원용 처음 설치 가이드

[한국어 README](../README.kr.md) | [English README](../README.md)

이미 설치를 마쳤다면 [개발 명령어 모음](commands.md)에서 필요한 명령만 찾아 실행하세요.

**Git과 Docker 설치 → 저장소 클론 → `docker compose up -d` → 화면 확인**이면 시작할 수 있습니다.
Node, Python, uv, Make를 PC에 따로 설치하거나 터미널 두 개를 켤 필요가 없습니다.
개발 도구와 의존성은 컨테이너 안에 준비됩니다.

이 가이드는 공통 앱인 `apps/web`과 `apps/api`를 실행합니다.
`prototype/`의 주제 후보, GPU 모델 서버, GCP 배포는 기본 실행에 포함되지 않습니다.
기본 모델은 Mock이므로 계정·API 키·결제 등록 없이 동작합니다.

## 1. 운영체제별로 도구 설치

팀의 기본 환경은 Mac입니다. 혹시 Windows에서 작업할 경우를 위해 설치 절차를 따로 준비했습니다.
**본인 운영체제의 문서 하나만 따라 한 뒤**, 이 문서의 도구 확인부터 이어가세요.

| 운영체제 | 설치 가이드 | 이후 명령을 실행할 곳 |
| --- | --- | --- |
| Mac | [Mac 설치 가이드](setup-macos.md) | macOS 터미널 |
| Windows | [Windows·WSL2 설치 가이드](setup-windows.md) | Ubuntu 터미널 |

Mac에서는 Apple Silicon과 Intel에 맞는 Docker Desktop을 선택합니다. 실제 검증한 로컬 환경은
Apple Silicon Mac이며, Windows 전체 설치 과정과 Intel Mac은 별도 기기에서 직접 검증하지 않았습니다.
기본 앱 컨테이너는 Linux ARM64에서, GitHub CI는 Linux x64에서 검증됩니다.

### 도구 확인

```bash
git --version
docker compose version
docker info
```

세 명령이 오류 없이 실행되어야 합니다. Compose는 v2 이상의 `docker compose` 명령을 사용합니다.
`docker info`에서 엔진 연결 오류가 나면 먼저 Docker Desktop을 실행하세요.

## 2. 저장소 받기

터미널에서 다음을 순서대로 실행합니다.

```bash
mkdir -p ~/workspace
cd ~/workspace
git clone --branch develop https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup.git
cd 2026-google-ai-builder-cup
```

`~`는 본인의 홈 폴더입니다. `/Users/sean` 같은 다른 사람의 경로를 맞출 필요가 없습니다.
이미 클론했다면 다시 클론하지 말고 해당 폴더로 이동하세요.
이후 모든 명령은 **`compose.yaml`이 있는 저장소 루트**에서 실행합니다.

```bash
pwd
git branch --show-current
```

현재 브랜치가 `develop`인지 확인합니다.
`Repository not found`나 인증 오류가 나오면 GitHub에서 저장소 초대를 수락했는지,
해당 계정으로 저장소를 열 수 있는지 확인하세요. 비공개 저장소는 별도 Git 인증이 필요합니다.
[GitHub 인증 안내](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)를 참고하고,
토큰을 저장소 URL이나 공유 로그에 넣지 마세요.

## 3. 개발 환경 켜기

```bash
docker compose up -d
```

첫 실행에서는 Node 24.21.0, Python 3.12 기반 개발 이미지를 빌드하고 패키지를 설치합니다.
인터넷 속도와 PC에 따라 몇 분 걸릴 수 있습니다. 이후 실행에서는 만들어 둔 이미지를 재사용합니다.
`-d`는 백그라운드 실행이라는 뜻이므로 명령이 끝나도 서버는 계속 켜져 있습니다.

```bash
docker compose ps
```

`db`, `api`, `web` 세 서비스가 `Up` 상태이고 준비가 완료되면 `healthy`로 표시됩니다.
`docker compose ps -a`에 보이는 `db-init`의 `Exited (0)`은 실습 테이블 초기화가 완료됐다는 뜻입니다.
아직 준비 중이면 다음 명령으로 로그를 보세요.

```bash
docker compose logs -f
```

로그를 그만 보려면 `Ctrl+C`를 누릅니다. 서버는 종료되지 않습니다.
이전 버전의 `app` 컨테이너가 남았다는 경고가 뜨면 이 저장소의 예전 컨테이너인지 확인한 뒤
한 번만 `docker compose up -d --remove-orphans`로 정리할 수 있습니다.

## 4. 첫 화면 확인

브라우저에서 **http://localhost:5173**을 엽니다.

1. `AI BUILDER CUP / 2026` 화면이 나타납니다.
2. `Your text`에 기본 문장을 그대로 두거나 간단한 문장을 입력합니다.
3. `Team access code`는 비워 둡니다.
4. `Analyze text →`를 누릅니다.
5. `Summary`, `Key points`, `Demo data · no AI model was called`가 나타나면 성공입니다.

| 주소 | 용도 |
| --- | --- |
| http://localhost:5173 | 개발 화면, 파일 수정 자동 반영 |
| http://localhost:8000/api/health | API 응답 확인 |
| http://localhost:8000/docs | API 요청을 살펴보는 자동 문서 |

PostgreSQL 실습은 `docker compose run --rm db-check`로 시작합니다.
합성 기록을 생성·조회한 뒤 재조회 명령과 브라우저 주소를 출력합니다.
문서나 모델 API 키는 필요하지 않습니다. 자세한 과정은 [실습 기록](ai-lab-plan.md)에 있습니다.

`.env` 생성이나 인증정보 복사가 필요하지 않습니다. 개발 서비스는 호스트 `.env`를 읽지 않고
Compose에 정의한 Mock 설정으로 실행합니다. 기존 `.venv`나 `node_modules`가 있어도 공유하지 않습니다.

## 5. 코드를 수정하면 어떻게 반영되나요?

웹과 API가 별도 컨테이너에서 실행되며, 로컬 소스 폴더가 컨테이너에 연결되어 있습니다.

| 수정한 것 | 반영 방식 |
| --- | --- |
| `apps/web/src/`의 React·TypeScript·CSS | 저장하면 열린 브라우저에 자동 반영 |
| `apps/api/src/`의 Python | 저장하면 API 자동 재시작, 다음 요청부터 변경 적용 |
| 연결된 소스 폴더 안의 새 파일 | 자동 감지 |
| `apps/web/index.html`, Vite 설정 | Vite가 변경 감지, 필요 시 개발 서버 자동 재시작 |
| 패키지 목록·lockfile·Dockerfile·Python 도구 설정 | 아래 명령으로 다시 빌드 |
| 새로운 최상위 소스·정적 파일 폴더 | Docker 이미지와 Compose 연결 설정 추가 필요 |

```bash
docker compose up -d --build
```

새 라이브러리는 [명령어 모음의 패키지 관리 절차](commands.md)를 따라 추가하세요.
전용 `npm`·`uv` 서비스가 패키지 목록과 lockfile을 호스트 저장소에 함께 갱신합니다.
재빌드는 lockfile에 기록된 패키지를 설치하며 새로운 버전을 임의로 선택하지 않습니다.
Compose 설정을 수정했을 때도 위 명령을 실행해 컨테이너를 갱신하세요.

API 자동 재시작 중에는 잠깐 요청이 실패할 수 있습니다. 로그에서 시작 완료를 확인한 뒤 다시 요청하세요.
실제 AI 호출이나 공유 환경 배포는 개발용 자동 반영 설정과 별개입니다.

<a id="verify"></a>

## 6. 검사와 테스트

기본 검사·테스트·Mock 평가·웹 빌드를 한 번에 실행합니다.

```bash
docker compose run --rm --build check
```

현재 Python 테스트 84개와 Mock 평가 2개가 있으며 이후 개발에 따라 개수는 바뀔 수 있습니다.
실행 이력 실습은 http://localhost:5173 의 `Workflow history`에서 시작합니다.
단계별 상태·시간과 DB 저장 확인 방법은 [명령어 모음](commands.md#실행-이력-조회)에 있습니다.
실제 모델 실습을 원할 때만 [Ollama 준비와 비교](commands.md#실제-로컬-모델-비교)를 진행하세요.
기본 설치·검사에는 Ollama나 모델 다운로드가 필요하지 않습니다.
앞 단계가 실패하면 중단됩니다. 이 명령은 개발 서버를 켜지 않아도 실행할 수 있습니다.

브라우저에서 실제 화면과 API 연결을 검사하려면 다음을 실행합니다.

```bash
docker compose run --rm --build e2e
```

필요한 `api`, `web`을 자동으로 시작하고, 별도 테스트 컨테이너에서 Chromium 테스트를 실행합니다.
호스트에 Playwright나 Chrome을 따로 설치할 필요는 없습니다. 최초 브라우저 이미지 빌드에는 시간이 걸립니다.
기존 개발 서버를 종료할 필요도 없습니다. 현재 브라우저 테스트는 7개입니다.

`--rm`은 끝난 **검사 컨테이너만** 제거합니다. 개발 서버는 계속 실행됩니다.
검사 컨테이너 안의 평가 JSON·실패 추적 파일도 제거되므로, 실패 증거를 보관하려면 다음처럼 실행합니다.

```bash
docker compose run --build --name builder-cup-debug e2e
```

실패했다면 다른 터미널에서 파일을 꺼낸 뒤 검사 컨테이너를 지울 수 있습니다.

```bash
mkdir -p artifacts
docker cp builder-cup-debug:/workspace/apps/web/test-results ./artifacts/browser-test-results
docker rm builder-cup-debug
```

같은 이름의 이전 검사 컨테이너가 있으면
먼저 결과를 확인하고 제거한 뒤 새 검사를 실행합니다. CI에서는 실패 파일을 자동 보관합니다.
Mock 검증은 실제 Gemini 연결이나 AI 답변 품질을 증명하지 않습니다.

## 7. 종료와 다음 날 시작

개발 환경을 끄려면 다음을 실행합니다. 소스 파일과 빌드 이미지는 삭제하지 않습니다.
PostgreSQL 데이터와 접속 비밀번호 볼륨도 유지됩니다. 실습 중에는 볼륨 삭제 옵션을 추가하지 마세요.

```bash
docker compose down
```

다음 날에는 Docker Desktop을 켜고 저장소 루트에서 다시 실행하면 됩니다.

```bash
docker compose up -d
```

최신 코드를 받을 때는 `git status`로 본인이 수정한 파일이 있는지 먼저 확인하세요.
변경을 정리한 뒤 다음을 실행합니다.

```bash
git pull --ff-only
docker compose up -d --build
```

pull이 충돌이나 브랜치 분기로 멈추면 강제로 덮어쓰지 말고 개발 담당자에게 확인하세요.

## 8. 배포할 형태로도 확인하고 싶다면

```bash
docker compose up -d --build preview
```

**http://localhost:8080**에서 배포용 이미지의 Mock 앱을 확인합니다.
이 컨테이너는 빌드된 화면과 API를 함께 제공하고 소스 자동 반영은 하지 않습니다.
코드를 수정한 뒤에는 같은 명령으로 다시 빌드하세요. 개발 서버와 동시에 실행할 수 있습니다.

```bash
docker compose stop preview
```

개발과 미리보기 컨테이너까지 모두 제거하려면 `docker compose --profile preview down`을 실행합니다.
클라우드 리소스를 생성하거나 GCP에 배포하는 명령은 아닙니다.

## 9. Makefile과 scripts는 어떻게 달라졌나요?

Makefile은 제거했습니다. 별도 `just`나 `task`도 설치하지 않습니다.

- **`compose.yaml`** — 팀원과 CI가 사용하는 실행·검증 명령의 진입점
- **`apps/web/package.json`** — 컨테이너가 호출하는 Vite·TypeScript·Playwright 명령
- **`scripts/`** — 평가·컨테이너 검증·배포·롤백 작업의 구현

예를 들어 `check`가 평가 스크립트를 호출하므로, 평소에는 스크립트 이름을 기억할 필요가 없습니다.
파일별 역할은 [scripts 안내](../scripts/README.md)에 정리했습니다.

## 자주 만나는 문제

| 증상 | 확인과 해결 |
| --- | --- |
| Docker 엔진에 연결할 수 없음 | Docker Desktop이 실행 중인지 확인하고 `docker info`를 다시 실행합니다. |
| `no configuration file provided` | `compose.yaml`이 있는 저장소 루트로 이동합니다. |
| 이미지·패키지 다운로드 실패 | 네트워크·프록시와 처음 발생한 오류를 확인한 뒤 `docker compose up -d --build`를 다시 실행합니다. |
| 포트 5173 또는 8000이 이미 사용 중 | 예전에 실행한 호스트 Vite·API 서버를 해당 터미널에서 종료합니다. 모르는 프로세스는 임의로 종료하지 마세요. |
| 수정해도 화면이 그대로임 | 8080 미리보기가 아닌 5173 개발 화면인지 확인합니다. 실제로 열린 저장소와 Compose를 실행한 폴더가 같은지도 확인합니다. |
| 새 라이브러리가 없다는 오류 | lockfile 갱신 후 `docker compose up -d --build`로 의존성을 다시 설치합니다. |
| 분석 요청 실패 | `docker compose ps`, `docker compose logs api web`로 상태를 확인합니다. API 재시작 중이면 잠시 뒤 다시 요청합니다. |
| Windows에서 변경 감지가 느리거나 안 됨 | WSL의 Linux 홈에 클론하고 그 폴더를 편집하고 있는지, Docker Desktop WSL Integration이 켜져 있는지 확인합니다. |
| 예전 `make` 명령을 찾을 수 없음 | 이번 설정부터 Compose 명령으로 바뀌었습니다. README의 명령 표를 확인합니다. |

해결되지 않으면 운영체제, 실행한 명령, 첫 오류, `docker compose version`, `docker compose ps` 결과를
개발 담당자에게 전달하세요. `.env`, 토큰, 인증정보는 첨부하지 마세요.

## 선택 사항과 배포 제한

Terraform도 컨테이너로 검증할 수 있습니다.

```bash
docker compose run --rm infra-check
```

설정을 검사할 뿐 클라우드 리소스를 생성하지 않습니다.
실제 Gemini·Gemma 연결은 [운영 문서](operations.md)와 [모델 안내](../models/vllm/README.md)를 참고해
담당자와 별도로 준비합니다. GCP 배포는 운영 담당자가 [운영 문서](operations.md)에 따라
`scripts/bootstrap-gcp.sh`와 `release/gcp` 브랜치로 수행합니다.
