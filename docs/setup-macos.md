# Mac 개발 도구 설치

[공통 설치·실행 가이드](setup.md) | [Windows 설치 가이드](setup-windows.md)

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

이제 [공통 가이드의 저장소 받기](setup.md#2-저장소-받기)로 이어가세요.
클론 위치는 본인이 정하면 되며 다른 팀원과 사용자명이나 홈 경로를 맞추지 않아도 됩니다.

로컬 검증은 Apple Silicon Mac에서 완료했습니다. Intel Mac은 같은 명령과 x64 이미지를 사용하지만
실제 Intel 기기에서 직접 실행한 결과로 간주하지는 않습니다.
