# Windows·WSL2 개발 도구 설치

[공통 설치·실행 가이드](처음-설치.md) | [Mac 설치 가이드](macOS-설치-진단.md)

Windows 사용자를 위한 보조 안내입니다. **WSL2의 Ubuntu에 저장소를 두고 Docker Desktop으로 실행**합니다.
Windows용 Node·Python·Make는 설치하지 않습니다. 이 설치 과정은 실제 Windows PC에서 아직 검증하지 않았습니다.

## 1. WSL2 Ubuntu 설치

관리자 PowerShell에서 실행합니다.

```powershell
wsl --install -d Ubuntu
```

안내가 나오면 Windows를 재부팅합니다. 시작 메뉴에서 Ubuntu를 열고 Linux 사용자명과 비밀번호를 만듭니다.
이미 설치한 경우 PowerShell에서 아래 명령으로 Ubuntu의 VERSION이 `2`인지 확인합니다.

```powershell
wsl --list --verbose
```

오류가 나거나 VERSION이 1이라면 [Microsoft 공식 WSL 설치 안내](https://learn.microsoft.com/en-us/windows/wsl/install)를
따라 설치·변환을 완료하세요. 이 단계의 PowerShell 명령과 이후 Ubuntu 명령을 구분해서 실행합니다.

## 2. Docker Desktop 설치와 연결

1. [Docker 공식 Windows 설치 안내](https://docs.docker.com/desktop/setup/install/windows-install/)를 따라 설치합니다.
2. Docker Desktop을 실행하고 WSL2 기반의 Linux 컨테이너 환경을 사용합니다.
3. Docker Desktop의 **Settings → Resources → WSL Integration**에서 사용할 Ubuntu를 활성화합니다.
4. Ubuntu 터미널을 새로 엽니다.

Docker Desktop이 WSL에 엔진을 연결하므로 Ubuntu 안에 별도의 Docker Engine을 중복 설치하지 않습니다.
공식 문서의 Windows·WSL 버전과 하드웨어 요구사항도 확인하세요.

## 3. Ubuntu 안에서 Git 설치

**아래부터는 PowerShell이 아니라 Ubuntu 터미널에서 실행합니다.**

```bash
sudo apt update
sudo apt install -y git
git --version
docker compose version
docker info
```

Docker 명령이 없거나 엔진에 연결되지 않으면 Docker Desktop 실행 상태와 Ubuntu의 WSL Integration을 확인합니다.
모두 정상이라면 [공통 가이드의 저장소 받기](처음-설치.md#2-저장소-받기)로 이어갑니다.

## 4. 저장소와 편집기 위치

저장소는 공통 가이드처럼 Ubuntu 홈의 `~/workspace`에 클론합니다.
자동 반영과 파일 접근을 위해 `/mnt/c/...` 대신 Linux 파일시스템을 사용하세요.
VS Code를 쓴다면 WSL 확장을 통해 **그 Ubuntu 저장소 폴더**를 열어 편집합니다.
Windows에 별도로 클론한 다른 폴더를 수정하면 실행 중인 컨테이너에 반영되지 않습니다.

앱을 켠 뒤 Windows 브라우저에서 http://localhost:5173 에 접속합니다.
접속이 안 되면 [Microsoft WSL 네트워크 안내](https://learn.microsoft.com/en-us/windows/wsl/networking)를 참고하세요.

이후 실행·검사·패키지 관리 명령은 Mac과 같습니다. [개발 명령어 모음](개발-명령어.md)을 사용하세요.
