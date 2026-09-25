# Mac 개발 도구 설치

[공통 설치·실행 가이드](처음-설치.md) | [Windows 설치 가이드](Windows-설치.md)

팀의 기본 개발 환경입니다. **Git과 Docker Desktop만 설치**하면 됩니다.
Node 24.21.0, Python 3.12, npm, uv와 테스트 도구는 컨테이너에서 실행합니다.
이미 로컬에 설치된 Node·Python을 삭제하거나 버전을 바꿀 필요는 없습니다.

## 1. Git 준비

Spotlight에서 터미널을 열고 실행합니다.

```bash
git --version
```

버전이 표시되면 준비된 것입니다. Command Line Tools 설치 창이 뜨면 설치를 완료하세요.
도구가 없고 설치 창도 뜨지 않으면 다음 명령을 실행합니다.

```bash
xcode-select --install
```

이미 설치되어 있다는 메시지는 오류가 아니므로 다음 단계로 넘어갑니다.
Homebrew나 Make를 별도로 설치할 필요는 없습니다.

## 2. Docker Desktop 준비

1. Apple 메뉴의 **이 Mac에 관하여**에서 칩 종류를 확인합니다.
2. [Docker 공식 Mac 설치 안내](https://docs.docker.com/desktop/setup/install/mac-install/)에서
   Apple Silicon 또는 Intel에 맞는 설치 파일을 받습니다.
3. Docker를 응용 프로그램 폴더에 설치한 뒤 실행합니다.
4. 초기 설정과 권한 안내를 완료하고 엔진이 실행될 때까지 기다립니다.

단순히 앱을 설치하는 것과 엔진을 실행하는 것은 별개입니다. 개발을 시작할 때 Docker Desktop도 켜져 있어야 합니다.
공식 안내의 지원 macOS 버전과 시스템 요구사항도 확인하세요.

## 3. 설치 확인

새 터미널에서 실행합니다.

```bash
git --version
docker compose version
docker info
```

모두 오류 없이 실행되면 도구 준비가 끝났습니다. `docker info`가 연결 실패를 표시하면
Docker Desktop을 먼저 켜고, 초기 설정을 완료했는지 확인합니다.

이제 [공통 가이드의 저장소 받기](처음-설치.md#2-저장소-받기)로 이어가세요.
클론 위치는 본인이 정하면 되며 다른 팀원과 사용자명이나 홈 경로를 맞추지 않아도 됩니다.

로컬 검증은 Apple Silicon Mac에서 완료했습니다. Intel Mac은 같은 명령과 x64 이미지를 사용하지만
실제 Intel 기기에서 직접 실행한 결과로 간주하지는 않습니다.

## 4. 문제가 생겼을 때 준비 상태 확인

저장소를 받은 뒤 터미널에서 먼저 다음을 확인합니다. 값을 채팅이나 문서에 붙여넣을 때 개인 경로는 필요에 따라 가리세요.

```bash
pwd
git rev-parse --show-toplevel
git branch --show-current
docker context show
docker compose version
docker info --format '{{.ServerVersion}}'
docker compose ps -a
```

`pwd`와 저장소 루트가 다르면 루트로 이동하고, 작업 브랜치가 `develop`인지 확인합니다.
특히 다른 checkout을 여러 개 열었거나 `-p`를 사용했다면 같은 Compose 프로젝트를 보고 있는지 확인하세요.
프로젝트·checkout 연결은 `docker compose ls`의 이름과 설정 파일 경로로 확인할 수 있습니다.
Docker 명령 자체가 실패하면 아래 컨테이너 진단보다 엔진과 현재 context를 먼저 확인합니다.

```bash
docker compose run --rm --build doctor
```

이 명령은 의존 서비스를 자동으로 시작하지 않습니다. 처음 이미지 빌드는 도구 설치와 이미지 캐시를 만들고,
실행 시 임시 진단 컨테이너·필요한 네트워크가 만들어질 수 있지만 기존 서비스·DB·모델을 변경하지 않습니다.
소스와 컨테이너 파일시스템은 읽기 전용이며 Docker 소켓·DB 비밀번호·호스트 `.env`를 전달하지 않습니다.

| 출력 또는 증상 | 의미와 다음 행동 |
| --- | --- |
| `PASS Container toolchain` | 진단 이미지의 Node·Python 버전 확인. 호스트 버전과 별개 |
| `FAIL API` / `FAIL Web and API proxy` | 해당 프로젝트 서비스가 꺼졌거나 Mock 설정·연결에 문제가 있음. `docker compose up -d --wait` 후 재확인 |
| `PASS API`, `FAIL DB history read` | API 생존과 DB 연결은 별개. `docker compose logs --tail 50 db-init api` 확인 |
| `OPTIONAL Ollama server` | Docker에서 서버 접근 불가. 기본 Mock 개발에는 영향 없음 |
| `OPTIONAL Local model` | 서버는 있지만 실습 모델 미설치. 실제 추론을 원할 때만 모델 다운로드 |
| `NOT TESTED Inference and answer quality` | 이 진단은 추론·품질 검사를 수행하지 않음 |
| 기동 시 포트 사용 중 오류 | 아래 `lsof`로 현재 소유 프로세스를 확인하고 종료하거나 포트를 바꿀지 판단 |

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
command -v ollama
```

`lsof`에 기존 개발 서비스가 보이는 것은 정상일 수 있습니다. 출력만 보고 다른 프로세스를 강제로 종료하지 마세요.
`command -v ollama`는 호스트 CLI 경로를 확인할 뿐, 서버 실행이나 모델 설치를 보장하지 않습니다.
CLI가 PATH에 없더라도 GUI 앱이 설치됐을 수 있습니다. 기본 개발에는 Ollama가 필요하지 않습니다.
서버가 켜져 있을 때 `ollama list`로 다운로드 목록을 확인하고,
실제 추론을 원하면 [Ollama 실습 안내](개발-명령어.md#실제-로컬-모델-비교)를 따릅니다.

## 5. 별도 checkout을 독립적으로 검증하기

**다른 경로에 새로 clone한 저장소**에서 실행하세요. 아래 이름과 포트가 기존 프로젝트와 겹치지 않는지 먼저 확인합니다.

```bash
export COMPOSE_PROJECT_NAME=builder-cup-onboarding
export DEV_API_PORT=18000
export DEV_WEB_PORT=15173
docker compose up -d --build --wait
docker compose run --rm --build doctor
docker compose run --rm --build db-check
docker compose run --rm --build check
```

이 터미널에서는 http://localhost:15173 와 http://localhost:18000/docs 를 사용합니다.
서비스 간 통신은 내부 포트를 그대로 사용하며 다른 프로젝트의 컨테이너나 볼륨을 재사용하지 않습니다.
`db-check`의 `Open` 주소도 설정한 API 포트를 사용합니다.
종료할 때도 같은 터미널의 프로젝트 설정을 유지합니다.

```bash
docker compose down
unset COMPOSE_PROJECT_NAME DEV_API_PORT DEV_WEB_PORT
```

일반 `down`은 해당 검증 볼륨을 보존합니다. 이 안내는 기존 개발 DB나 모든 Docker 볼륨을 삭제하는 절차가 아닙니다.
다른 팀원 Mac의 확인 결과는 [계획 01 검증 기록](../plans/archive/01-environment-reproducibility.md)에 환경 정보와 함께 추가합니다.
