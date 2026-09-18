# 개발 명령어 모음

[한국어 README](../README.kr.md) | [처음 설치하기](setup.md)

**평소에는 이 문서를 보고 필요한 명령만 실행하면 됩니다.**
Docker를 켠 뒤 `compose.yaml`이 있는 저장소 루트에서 실행하세요.
아래 명령은 공통 웹·API용이며 `prototype/`과 별도 GPU 서버는 포함하지 않습니다.

## 가장 자주 쓰는 명령

| 하고 싶은 일 | 실행할 명령 | 결과 |
| --- | --- | --- |
| 개발 시작 | `docker compose up -d` | 웹·API를 백그라운드로 실행 |
| 준비 완료까지 기다리며 시작 | `docker compose up -d --wait` | 웹·API가 정상 상태가 될 때까지 대기 |
| 실행 상태 확인 | `docker compose ps` | 서비스 상태와 연결 포트 표시 |
| 최근 로그부터 계속 보기 | `docker compose logs -f --tail 100` | 최근 100줄부터 실시간 로그 표시 |
| API 로그만 보기 | `docker compose logs -f --tail 100 api` | API 오류·재시작 상태 확인 |
| 웹 로그만 보기 | `docker compose logs -f --tail 100 web` | Vite 오류·화면 변경 감지 확인 |
| 개발 환경 종료 | `docker compose down` | 개발 컨테이너와 네트워크 제거, 소스·이미지는 유지 |

개발 화면은 **http://localhost:5173**, API 문서는 **http://localhost:8000/docs**입니다.
로그를 보다가 `Ctrl+C`를 누르면 로그 보기만 끝납니다. 서버 종료는 `down`을 사용하세요.

## 수정한 내용을 반영할 때

| 변경한 내용 | 해야 할 일 |
| --- | --- |
| `apps/web/src/`의 React·CSS | 저장만 하면 브라우저에 자동 반영 |
| `apps/api/src/`의 Python | 저장만 하면 API 자동 재시작 |
| 패키지 목록·lockfile·Dockerfile·Python 도구 설정 | `docker compose up -d --build` |
| Compose 서비스 설정 | `docker compose up -d --build` |
| 코드는 그대로이고 API 프로세스만 재시작 | `docker compose restart api` |
| 코드는 그대로이고 웹 프로세스만 재시작 | `docker compose restart web` |

`restart`는 이미지를 다시 빌드하거나 바뀐 Compose 설정을 적용하지 않습니다.
의존성이나 설정이 바뀌었다면 `up -d --build`를 사용하세요.
기본 개발 서비스는 Mock을 사용하며 호스트 `.env`를 컨테이너에 전달하지 않습니다.

## 검사와 테스트

| 확인할 것 | 실행할 명령 | 실행 조건 |
| --- | --- | --- |
| 코드 스타일·타입·Python 테스트·Mock 평가·웹 빌드 | `docker compose run --rm --build check` | 개발 서버가 꺼져 있어도 가능 |
| 브라우저에서 화면과 API 연동 | `docker compose run --rm --build e2e` | 필요한 개발 서버를 자동 시작 |
| Terraform 설정 | `docker compose run --rm infra-check` | 클라우드 리소스를 생성하지 않음 |
| Compose 설정 문법 | `docker compose config --quiet` | 설정 내용을 출력하지 않고 검사 |

`check`는 검사 중 하나라도 실패하면 중단합니다. E2E는 개발 화면인 5173에 연결합니다.
첫 브라우저 테스트는 이미지에 Chromium을 설치하므로 시간이 더 걸릴 수 있습니다.
검사 컨테이너는 `--rm`으로 종료 후 제거되지만, E2E가 시작한 개발 서버는 남아 있습니다.
Mock 평가 통과는 실제 Gemini 연결이나 AI 품질을 확인한 결과가 아닙니다.

이미 실행 중인 API 컨테이너에서 Python 테스트만 빠르게 다시 실행할 수도 있습니다.

```bash
docker compose exec api pytest -q
```

이 명령은 전체 `check`의 대체가 아닙니다. 실패한 브라우저 테스트의 파일을 보관하는 방법은
[설치 가이드](setup.md#verify)를 참고하세요.

## 패키지 추가·제거·업데이트

실행 중인 컨테이너에 `exec`로 설치하면 저장소의 목록·lockfile이 바뀌지 않습니다.
아래 전용 명령은 **호스트 저장소에 두 파일을 함께 기록**합니다. 로컬 Node·Python 설치는 필요 없습니다.
Mac과 Windows·WSL2에서 동일하며, 반드시 저장소 루트에서 실행하세요.

| 대상 | 함께 커밋할 파일 |
| --- | --- |
| 프런트엔드 | `apps/web/package.json`, `apps/web/package-lock.json` |
| Python | `pyproject.toml`, `uv.lock` |

다음 패키지명은 사용법 예시입니다. 실제 필요한 패키지로 바꿔 실행하세요.
아직 필요하지 않은 패키지를 미리 추가할 필요는 없습니다.

| 할 일 | 명령어 예시 |
| --- | --- |
| 프런트엔드 패키지 추가 | `docker compose run --rm --build npm install zod` |
| 프런트엔드 개발용 패키지 추가 | `docker compose run --rm --build npm install --save-dev prettier` |
| 프런트엔드 패키지 제거 | `docker compose run --rm npm uninstall zod` |
| 프런트엔드 패키지의 허용 범위 내 업데이트 | `docker compose run --rm npm update react` |
| 프런트엔드 목록을 직접 수정한 뒤 lockfile 갱신 | `docker compose run --rm npm install` |
| Python 패키지 추가 | `docker compose run --rm --build uv add httpx` |
| Python 개발용 패키지 추가 | `docker compose run --rm --build uv add --dev pytest` |
| Python 패키지 제거 | `docker compose run --rm uv remove httpx` |
| Python 개발용 패키지 제거 | `docker compose run --rm uv remove --dev pytest` |
| Python 패키지의 허용 범위 내 업데이트 | `docker compose run --rm uv lock --upgrade-package httpx` |
| Python 목록을 직접 수정한 뒤 lockfile 갱신 | `docker compose run --rm uv lock` |

`npm` 작업은 lockfile만 갱신하고 설치 스크립트를 실행하지 않습니다. `uv add/remove`도 로컬 가상환경을
설치하지 않습니다. 따라서 작업 컨테이너를 지워도 두 설정 파일의 변경은 저장소에 남고,
호스트에 `node_modules`나 `.venv`를 만들지 않습니다. 전용 도구 이미지는 현재 앱의 의존성 설치에
의존하지 않으므로 목록과 lockfile이 일시적으로 맞지 않아도 복구 명령을 실행할 수 있습니다.

`npm` 서비스는 `apps/web`용입니다. `prototype/`의 패키지를 수정하지 않습니다.
여러 패키지 수정 명령을 동시에 실행하지 말고 하나씩 완료하세요. 패키지 제거는 사용처도 수정해야 합니다.

변경 후에는 차이를 확인하고 이미지를 재빌드합니다.

```bash
git diff -- pyproject.toml uv.lock apps/web/package.json apps/web/package-lock.json
docker compose up -d --build
docker compose run --rm --build check
docker compose run --rm --build e2e
```

검증이 통과하면 변경한 목록과 lockfile을 **같은 커밋**에 포함하세요.
lockfile의 버전이나 해시는 손으로 편집하지 않습니다. 빌드는 `npm ci`와 `uv sync --locked`로
목록·lockfile 불일치를 거부합니다. 명령 실패 시 일부 파일이 바뀌었을 수 있으므로 `git diff`를 확인하세요.

## 배포 형태 미리보기

| 하고 싶은 일 | 실행할 명령 |
| --- | --- |
| 최신 코드로 미리보기 빌드·실행 | `docker compose up -d --build preview` |
| 미리보기만 종료 | `docker compose stop preview` |
| 개발·미리보기 컨테이너 모두 제거 | `docker compose --profile preview down` |

미리보기 주소는 **http://localhost:8080**입니다. 개발 서버와 동시에 실행할 수 있습니다.
미리보기에는 자동 반영이 없으므로 수정 후에는 첫 번째 명령으로 다시 빌드하세요.
`preview`는 로컬 Mock 앱이며 GCP 배포가 아닙니다.

## 자주 쓰는 작업 순서

다음 날 작업을 시작할 때는 Docker를 켜고 저장소 루트에서 실행합니다.

```bash
docker compose up -d
```

팀의 최신 변경을 받을 때는 먼저 `git status`로 본인의 수정 내역을 확인합니다.
수정한 파일을 정리한 뒤 다음을 실행하세요.

```bash
git pull --ff-only
docker compose up -d --build
```

코드 변경을 공유하기 전에는 다음을 실행합니다. 첫 번째 명령이 실패하면 원인을 해결한 뒤 진행하세요.

```bash
docker compose run --rm --build check
docker compose run --rm --build e2e
```

작업이 끝나면 `docker compose down`으로 종료합니다.
미리보기도 켰다면 `docker compose --profile preview down`을 사용하세요.

## 옵션과 파일 역할

| 항목 | 의미 |
| --- | --- |
| `-d` | 터미널을 점유하지 않고 백그라운드 실행 |
| `--build` | 실행 전에 이미지 빌드, 바뀌지 않은 단계는 캐시 재사용 |
| `--rm` | 일회성 작업 컨테이너를 종료 후 제거 |
| `--wait` | 서비스가 실행·정상 상태가 될 때까지 대기 |
| `-f` (`logs`에서) | 새 로그를 계속 표시 |
| `compose.yaml` | 팀원과 CI가 실행하는 서비스·검증 명령 정의 |
| `apps/web/package.json` | 컨테이너 내부의 프런트엔드 도구 명령 |
| `scripts/` | 평가·배포·롤백 등의 내부 구현, [파일별 역할](../scripts/README.md) |

GCP 배포와 과금 활성화는 현재 보류 중입니다. `scripts/bootstrap-gcp.sh`, 배포·롤백 스크립트,
`release/gcp` push는 평소 개발 명령이 아닙니다. 재개가 결정되면 [운영 문서](operations.md)를 따릅니다.

## GitHub CI는 언제 실행되나요?

- `develop`에 코드·설정 변경을 push하면 전체 검증을 실행합니다.
- 변경 파일이 Markdown 문서뿐인 `develop` push는 실행하지 않습니다.
- `develop`, `release/gcp` 대상 PR은 문서 변경이어도 검증을 실행합니다. 필수 PR 검사 상태가 대기 상태로 남는 것을 피하기 위해서입니다.
- 같은 브랜치나 PR에 새 변경이 들어오면 이전 검증을 취소하고 최신 변경을 검증합니다.
- GitHub Actions의 CI 화면에서 `Run workflow`로 수동 실행할 수도 있습니다.
- `release/gcp` 배포에서 호출하는 검증은 문서 필터로 생략하지 않고, 새 실행 때문에 취소하지 않습니다.

`verify`는 작업 이름입니다. 그 안에서 코드 검사·Python 테스트·Mock 평가·브라우저 테스트·Terraform
검증·배포 이미지 빌드·컨테이너 smoke test를 실행합니다. `develop`은 실제 GCP 배포를 하지 않습니다.

팀원의 PC가 Mac이어도 CI는 Docker의 Linux 실행 환경을 확인하므로 Ubuntu runner를 사용합니다.
공개 저장소의 표준 runner는 무료이고, 비공개 저장소는 소유자 계정의 요금제별 무료 시간을 사용합니다.
GitHub Free 기준 월 2,000분이며 다른 비공개 저장소 사용량과 공유됩니다.
[공식 Actions 과금 안내](https://docs.github.com/en/billing/concepts/product-billing/github-actions)를 기준으로,
GitHub 계정의 Billing and licensing에서 실제 사용량과 예산·초과 사용 차단 설정을 확인하세요.
이 저장소의 CI 설정만으로 계정 전체의 과금을 막지는 못합니다.
