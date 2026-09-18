# 팀원용 처음 설치 가이드

[프로젝트 소개로 돌아가기](../README.kr.md) | [English README](../README.md)

개발 도구가 없는 PC에서 저장소를 받아 공통 앱의 첫 화면을 확인하는 안내입니다.
**필수 도구 설치 → 저장소 클론 → Node 선택 → `make setup` → 검증 → 실행** 순서로 진행합니다.

이 가이드는 `apps/web`과 `apps/api`를 대상으로 합니다. `prototype/disease` 등 후보 프로젝트는
여기서 설치하거나 실행하지 않습니다. 기본 Mock 모드에서는 실제 AI를 호출하지 않으므로
GCP 계정, 결제 등록, API 키, GPU 없이 시작할 수 있습니다.

## 시작 전에

- 인터넷이 연결되어 있어야 합니다. 최초 설치에서는 개발 도구와 패키지, 테스트용 브라우저를 받습니다.
- GitHub에서 저장소 페이지를 열 수 있는지 확인하세요. 비공개 저장소라면 초대 수락과 Git 인증이 필요합니다.
- 검증한 환경은 Apple Silicon macOS입니다. Ubuntu와 Windows의 WSL2는 아래 절차를 제공하지만
  이 저장소의 전체 실행을 해당 환경에서 직접 검증하지는 않았습니다.
- 명령어 블록은 위에서부터 차례로 실행하세요. `#` 뒤는 설명이며 함께 복사해도 됩니다.
- `~`는 **본인의 홈 폴더**입니다. 다른 팀원과 사용자명이나 경로를 맞출 필요가 없습니다.

| 도구 | 역할 | 준비 방법 |
| --- | --- | --- |
| Git | 저장소 다운로드와 변경 이력 관리 | 운영체제별 설치 |
| Make | 프로젝트 명령어 실행 | macOS Command Line Tools 또는 Ubuntu 패키지 |
| uv | Python과 Python 패키지 관리 | 운영체제별 설치 |
| fnm | 프로젝트에 맞는 Node 버전 선택 | 이미 nvm을 쓰면 대체 가능 |
| Node.js 24.21.0·npm | 웹 개발 도구 실행과 패키지 설치 | 저장소를 받은 뒤 fnm으로 설치 |
| Python 3.12 | API 실행 | `make setup`에서 uv가 자동 설치 |

Docker, Terraform, gcloud, GitHub CLI는 처음 실행할 때 필수가 아닙니다.
이미 nvm을 사용하는 팀원은 아래에서 fnm 설치·셸 설정을 건너뛰고 3단계의 nvm 명령을 사용하세요.

## 1. 내 운영체제의 도구 설치

아래에서 **본인 운영체제에 해당하는 부분만** 진행하세요.

### macOS

Spotlight에서 `터미널`을 찾아 엽니다.

먼저 아래 명령을 실행하고 설치 창이 나타나면 완료될 때까지 기다립니다.
이미 설치되어 있다는 메시지는 정상이며 다음으로 넘어가면 됩니다.

```bash
xcode-select --install
```

다음으로 Homebrew가 있는지 확인합니다.

```bash
brew --version
```

`command not found`가 나오면 [Homebrew 공식 홈페이지](https://brew.sh/)의 설치 명령을 실행하세요.
설치 마지막에 출력되는 **Next steps**의 명령도 실행해야 `brew`를 사용할 수 있습니다.
Apple Silicon과 Intel Mac의 Homebrew 경로는 다를 수 있으므로 설치 프로그램이 안내한 경로를 사용하세요.

이제 필요한 도구를 설치합니다.

```bash
brew install git uv fnm
```

macOS 기본 셸인 zsh에서 fnm을 사용할 수 있도록 설정합니다. 아래 명령은 설정 줄이 없을 때만
추가하므로 여러 번 실행해도 같은 줄을 중복 추가하지 않습니다.

```bash
touch ~/.zshrc
grep -Fqx 'eval "$(fnm env --use-on-cd --shell zsh)"' ~/.zshrc || \
  printf '\n%s\n' 'eval "$(fnm env --use-on-cd --shell zsh)"' >> ~/.zshrc
eval "$(fnm env --use-on-cd --shell zsh)"
```

이 설정은 새 터미널에서도 Node 버전을 선택할 수 있게 합니다.
[fnm 공식 셸 설정 안내](https://github.com/Schniz/fnm#shell-setup)를 기준으로 작성했습니다.
Bash 등 다른 셸을 사용하는 경우 공식 문서에서 해당 셸의 설정을 확인하세요.

### Windows

이 프로젝트의 명령은 Bash와 Make를 사용합니다. Windows에서는 **WSL2의 Ubuntu 안에서**
설치와 실행을 진행하세요. 일반 PowerShell이나 명령 프롬프트에서 `make setup`을 실행하는 절차가 아닙니다.

관리자 권한으로 PowerShell을 열어 다음을 실행합니다.

```powershell
wsl --install -d Ubuntu
```

재시작 안내가 나오면 재부팅하고, 시작 메뉴에서 Ubuntu를 실행해 Linux 사용자명과 비밀번호를 만듭니다.
기존 설치가 있다면 `wsl --list --verbose`에서 Ubuntu의 VERSION이 `2`인지 확인하세요.
설치가 지원되지 않거나 오류가 발생하면 [Microsoft 공식 WSL 설치 안내](https://learn.microsoft.com/en-us/windows/wsl/install)를 확인하세요.

**이후 모든 명령은 Ubuntu 터미널에서 실행합니다.** 도구도 Windows와 별개로 Ubuntu 안에 설치해야 합니다.
다음 Ubuntu 절차로 이어가세요. 저장소는 아래 예시처럼 Linux 홈의 `~/workspace`에 받습니다.

### Ubuntu / Windows의 WSL2 Ubuntu

Bash 터미널에서 실행합니다.

```bash
sudo apt update
sudo apt install -y git make curl unzip ca-certificates build-essential
```

uv와 fnm은 각각의 공식 설치 스크립트로 설치합니다.
스크립트 내용을 확인하고 싶다면 [uv 설치 문서](https://docs.astral.sh/uv/getting-started/installation/)와
[fnm 설치 문서](https://github.com/Schniz/fnm#installation)를 먼저 열어 보세요.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell
```

fnm의 경로와 Bash 초기화를 설정합니다. 기본 설치 경로를 사용하는 명령입니다.
설치 프로그램에 다른 경로가 표시되면 그 안내를 따르세요.

```bash
touch ~/.bashrc
grep -Fqx 'export PATH="$HOME/.local/bin:${XDG_DATA_HOME:-$HOME/.local/share}/fnm:$PATH"' ~/.bashrc || \
  printf '\n%s\n' 'export PATH="$HOME/.local/bin:${XDG_DATA_HOME:-$HOME/.local/share}/fnm:$PATH"' >> ~/.bashrc
grep -Fqx 'eval "$(fnm env --use-on-cd --shell bash)"' ~/.bashrc || \
  printf '\n%s\n' 'eval "$(fnm env --use-on-cd --shell bash)"' >> ~/.bashrc
source ~/.bashrc
```

다른 Linux 배포판은 패키지 설치 명령이 다르므로 위 `apt` 명령을 그대로 사용하지 마세요.

## 2. 설치 확인과 저장소 클론

먼저 아래 명령이 각각 버전을 출력하는지 확인합니다. nvm 사용자는 마지막 명령을 `nvm --version`으로 바꿉니다.

```bash
git --version
make --version
uv --version
fnm --version
```

이제 저장소를 받습니다.

```bash
mkdir -p ~/workspace
cd ~/workspace
git clone --branch develop https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup.git
cd 2026-google-ai-builder-cup
```

이미 클론했다면 `git clone`은 다시 실행하지 말고 해당 폴더로 이동하세요.
본인이 원하는 다른 경로에 받아도 됩니다. 이후 **저장소 루트**라는 표현은 `Makefile`, `README.md`,
`apps`가 들어 있는 이 폴더를 의미합니다.

```bash
pwd
git branch --show-current
```

현재 폴더가 저장소이고 브랜치가 `develop`인지 확인하세요.

`Repository not found` 또는 인증 오류가 나오면 브라우저에서 해당 GitHub 계정의 저장소 접근 권한을
먼저 확인하세요. 비공개 저장소의 HTTPS 인증에는 GitHub 비밀번호 대신 지원되는 Git 인증 방식이
필요합니다. [GitHub 인증 안내](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)를 참고하고,
접근 권한이 없으면 저장소 관리자에게 초대를 요청하세요. 토큰을 저장소 URL이나 공유 로그에 넣지 마세요.

## 3. 프로젝트의 Node 버전 선택

저장소 루트에서 실행합니다.

```bash
fnm install
fnm use
node --version
npm --version
```

fnm이 `.nvmrc`를 읽어 필요한 Node를 설치하고 선택합니다.
Node 출력은 **`v24.21.0`**이어야 합니다. npm은 Node와 함께 설치됩니다.
다른 버전이면 아직 `make setup`을 실행하지 말고 아래 문제 해결 항목을 확인하세요.

이미 nvm을 쓰는 팀원은 fnm 대신 아래 명령을 사용하면 됩니다.
이 가이드의 나머지 `fnm use`도 `nvm use`로 바꾸세요.

```bash
nvm install
nvm use
node --version
```

## 4. 프로젝트 설치 — make setup

```bash
make setup
```

다음 작업이 자동으로 진행됩니다.

1. 현재 Node가 `24.21.0`인지 확인합니다.
2. Python 3.12가 없으면 uv가 내려받고, `.venv`에 프로젝트 전용 환경을 구성합니다.
3. `uv.lock`과 `apps/web/package-lock.json`에 기록된 의존성을 설치합니다.
4. `.env`가 없으면 `.env.example`을 복사합니다. 기존 `.env`는 유지합니다.

최초 실행은 다운로드 때문에 시간이 걸릴 수 있습니다. 별도로 `pip install`을 하거나
`.venv`를 활성화할 필요는 없습니다. 명령이 오류 없이 끝나면 다음으로 진행합니다.

새로 생성한 `.env`는 이미 로컬 실행에 맞춰져 있습니다. GCP 프로젝트 ID나 모델 이름이 들어 있어도
`MODEL_PROVIDER=mock`인 동안 실제 모델을 호출하지 않습니다. 설정을 수정했다면 최초 검증에는
`MODEL_PROVIDER=mock`, 빈 `DEMO_API_KEY`를 사용하세요.

`.env`는 로컬 설정 파일이며 Git에서 제외됩니다. 팀원에게 실제 키가 들어 있는 `.env`를 보내지 마세요.

<a id="verify"></a>

## 5. 정상 설치 검증

개발 서버를 켜기 전에 실행합니다.

```bash
make check test build eval
```

코드 스타일·타입 검사, Python 테스트, 웹 빌드, Mock 평가를 순서대로 실행합니다.
앞 단계가 실패하면 중단되므로 오류를 해결한 뒤 다시 실행하세요.
현재 기준 Python 테스트는 7개, Mock 평가 사례는 2개이며 이후 개발에 따라 개수는 달라질 수 있습니다.

다음으로 테스트용 Chromium을 설치합니다. 평소 사용하는 Chrome과는 별개입니다.

macOS

```bash
(cd apps/web && npx playwright install chromium)
```

Ubuntu·WSL2 Ubuntu

```bash
(cd apps/web && npx playwright install --with-deps chromium)
```

Linux에서는 시스템 라이브러리 설치를 위해 관리자 비밀번호를 요청할 수 있습니다.
이후 저장소 루트에서 브라우저 테스트를 실행합니다.

```bash
make e2e
```

현재 테스트 2개가 통과하면 브라우저와 API의 기본 연결 검증이 완료됩니다.
테스트가 포트 8000에 자체 API 서버를 띄우므로 기존 `make api` 서버가 있다면 먼저 `Ctrl+C`로 종료하세요.
테스트 서버는 검증 후 자동으로 종료됩니다. 이 결과는 실제 Gemini 연결이나 AI 답변 품질을 검증한 것은 아닙니다.

## 6. 앱 실행과 첫 화면 확인

터미널을 **두 개** 엽니다. 아래 경로는 2단계의 예시 위치입니다.
다른 위치에 클론했다면 `cd` 경로를 본인의 저장소 위치로 바꿔 주세요.

터미널 1에서 API 서버를 실행합니다.

```bash
cd ~/workspace/2026-google-ai-builder-cup
make api
```

이 터미널은 서버가 실행되는 동안 그대로 열어 두세요. 명령 입력 상태로 돌아오지 않는 것이 정상입니다.

터미널 2에서 웹 서버를 실행합니다.

```bash
cd ~/workspace/2026-google-ai-builder-cup
fnm use
make web
```

브라우저에서 **http://127.0.0.1:5173**을 엽니다. WSL을 사용해도 Windows 브라우저에서 같은 주소로
접속을 시도할 수 있습니다. 포트가 이미 사용 중이면 웹 서버가 다른 주소를 안내할 수 있으므로
터미널에 출력된 `Local` 주소를 확인하세요.

1. `AI BUILDER CUP / 2026` 화면이 나타납니다.
2. `Your text`에 기본 문장을 그대로 두거나 간단한 문장을 입력합니다.
3. 기본 `.env`를 사용한다면 `Team access code`는 비워 둡니다.
4. `Analyze text →` 버튼을 누릅니다.
5. `Summary`, `Key points`, `Demo data · no AI model was called`가 보이면 성공입니다.

| 주소 | 용도 |
| --- | --- |
| http://127.0.0.1:5173 | 개발 중인 웹 화면 |
| http://127.0.0.1:8000/api/health | API 서버 응답 확인 |
| http://127.0.0.1:8000/docs | API 요청을 살펴볼 수 있는 자동 문서 |

종료할 때는 두 터미널에서 각각 `Ctrl+C`를 누릅니다.
`.env`를 변경한 경우에는 API 서버를 껐다가 다시 실행하세요.

## 7. 다음 날 다시 시작할 때

도구 설치나 `git clone`을 반복하지 않습니다. 저장소에 들어가 Node를 선택하고 서버 두 개를 실행하면 됩니다.

최신 변경을 받을 때는 먼저 개발 서버를 종료한 뒤 다음을 실행하세요.

```bash
cd ~/workspace/2026-google-ai-builder-cup
git status
```

본인이 수정한 파일이 있다면 변경을 정리한 뒤 다음 명령을 실행하세요.

```bash
git pull --ff-only
fnm install
fnm use
make setup
```

pull이 충돌이나 브랜치 분기로 중단되면 강제로 덮어쓰지 말고 개발 담당자에게 확인하세요.
Node 버전이나 의존성이 바뀌었을 수 있어 업데이트 후에는 위 설치 명령을 다시 실행합니다.
확인이 필요하면 5단계 검증을 다시 실행한 뒤 6단계처럼 서버를 켜세요.

## 자주 만나는 문제

| 증상 | 확인과 해결 |
| --- | --- |
| `brew`, `uv`, `fnm`을 찾을 수 없음 | 도구 설치와 셸 초기화가 완료되었는지 확인하고 새 터미널을 엽니다. Homebrew는 설치 마지막의 Next steps도 실행해야 합니다. |
| `Can't find the necessary environment variables` | fnm 셸 설정이 적용되지 않은 상태입니다. macOS zsh에서는 `eval "$(fnm env --use-on-cd --shell zsh)"`를 실행합니다. Ubuntu Bash에서는 `--shell bash`를 사용합니다. |
| `Select the Node version...` 또는 Node 버전 불일치 | 저장소 루트에서 `fnm install`, `fnm use`, `node --version`을 순서대로 실행합니다. 출력은 `v24.21.0`이어야 합니다. |
| `No rule to make target 'setup'` | 현재 폴더에 `Makefile`이 있는지 확인합니다. `apps/web` 안이 아니라 저장소 루트에서 실행해야 합니다. |
| `uv sync` 또는 `npm ci` 다운로드 실패 | 인터넷·프록시·패키지 서버 접근 상태와 첫 오류를 확인합니다. 연결 문제가 해결되면 `make setup`을 다시 실행합니다. |
| Chromium 실행 파일이 없음 | 5단계의 Playwright 브라우저 설치 명령을 실행합니다. Ubuntu·WSL은 `--with-deps`가 포함된 명령을 사용합니다. |
| `Address already in use` 또는 E2E 포트 충돌 | 포트 8000을 사용 중인 기존 개발 서버를 해당 터미널에서 `Ctrl+C`로 종료합니다. 모르는 프로세스를 임의로 종료하지 마세요. |
| 화면은 열리는데 분석 요청이 실패함 | 터미널 1의 `make api`가 실행 중인지, `/api/health`에 접속되는지 확인합니다. `.env`의 `MODEL_PROVIDER=mock`도 확인합니다. |
| `Enter the team access code to continue.` | 로컬 `.env`의 `DEMO_API_KEY`가 설정되어 있는지 확인합니다. 최초 Mock 실행이라면 비운 뒤 API를 재시작합니다. |
| 포트 8000에서 화면이 안 보이거나 예전 화면이 보임 | 개발 화면은 5173으로 접속합니다. 8000에서 웹 화면을 보려면 `make build`로 최신 파일을 생성해야 합니다. |
| WSL에서는 서버가 떴는데 Windows 브라우저가 연결되지 않음 | 먼저 `http://localhost:5173`을 시도하고 WSL 네트워크·방화벽 설정을 확인합니다. [공식 네트워크 안내](https://learn.microsoft.com/en-us/windows/wsl/networking)를 참고하세요. |

해결되지 않으면 **운영체제, 실행한 명령, 처음 발생한 오류, `node --version`, `uv --version` 출력**을
개발 담당자에게 전달하세요. `.env` 내용이나 토큰·인증정보는 첨부하지 마세요.

## 필요할 때만 준비하는 기능

| 기능 | 추가 준비 | 안내 |
| --- | --- | --- |
| 앱을 컨테이너로 실행 | Docker Desktop 또는 해당 OS의 Docker 환경 | 엔진 실행 후 `make docker`, 포트 8080 접속 |
| 인프라 설정 로컬 검증 | Terraform >=1.6, <2.0 | `make infra-check` |
| GitHub PR·Actions CLI 작업 | GitHub CLI와 별도 인증 | `gh auth login` |
| 실제 Gemini 호출 | Google Cloud CLI·ADC·프로젝트 권한·모델 접근·과금 준비 | [운영 문서](operations.md), 담당자와 먼저 협의 |
| Gemma/vLLM 실행 | 별도 Linux·NVIDIA GPU 환경 | [모델 실행 안내](../models/vllm/README.md) |

현재 GCP는 검증만 하는 상태입니다. 배포를 재개하기로 결정하기 전에는 과금을 활성화하거나
`make infra-apply`, `git push origin release/gcp`를 실행하지 마세요.
`make eval-live` 역시 실제 모델을 호출할 수 있으므로 설치 확인에는 `make eval`을 사용합니다.
