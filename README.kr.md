# AI Builder Cup 2026

[English](README.md) | 한국어 | [처음 설치하는 팀원을 위한 가이드](docs/setup.md)

Google AI Builder Cup 팀의 공통 개발 저장소입니다. React·TypeScript 화면과 Python·FastAPI 서버,
Gemini 및 별도 Gemma/vLLM 연결 구조가 준비되어 있습니다. `prototype/`은 독립적인 주제 후보이며
최종 주제가 정해진 것은 아닙니다.

## 처음 시작하기

**Git과 Docker만 설치하면 됩니다.** 로컬 Node·Python·uv·Make 설치는 필요하지 않습니다.
Docker Desktop을 켠 뒤 실행하세요. 처음이라면 [상세 설치 가이드](docs/setup.md)를 참고하세요.

```bash
git clone --branch develop https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup.git
cd 2026-google-ai-builder-cup
docker compose up -d
```

브라우저에서 **http://localhost:5173**을 엽니다.
첫 실행은 이미지를 내려받고 의존성을 설치하므로 몇 분 걸릴 수 있습니다.
`docker compose ps`에서 `api`, `web` 상태를 확인하세요.

- **화면 코드 수정** — `apps/web/src/`를 저장하면 Vite가 열린 브라우저에 자동 반영합니다.
- **API 코드 수정** — `apps/api/src/`를 저장하면 API가 자동 재시작됩니다.
- **개발 도구** — Node 24.21.0, Python 3.12와 의존성이 컨테이너 안에 설치됩니다.
- **모델** — 기본 개발 환경은 Mock이며 실제 AI를 호출하지 않습니다.
- **인증과 설정** — `.env` 없이 시작합니다. 호스트의 `.env`나 클라우드 인증정보를 읽지 않습니다.

`Analyze text →`를 눌러 결과와 `Demo data · no AI model was called` 표시가 보이면 정상입니다.
`Team access code`는 비워 두세요. API 문서는 http://localhost:8000/docs 에서 볼 수 있습니다.

## 이제 명령어는 Docker Compose로 통일합니다

Makefile은 제거했습니다. 다른 명령 관리 도구를 추가로 설치할 필요도 없습니다.
아래 명령은 모두 `compose.yaml`이 있는 저장소 루트에서 실행합니다.
**상황별 명령, 실행 결과, 옵션 뜻은 [개발 명령어 모음](docs/commands.md)에 정리했습니다.**

| 할 일 | 명령어 |
| --- | --- |
| 개발 환경 켜기 | `docker compose up -d` |
| 실행 상태 확인 | `docker compose ps` |
| 로그 보기 | `docker compose logs -f` |
| 개발 환경 끄기 | `docker compose down` |
| 의존성·이미지 설정 변경 반영 | `docker compose up -d --build` |
| 코드 검사·테스트·Mock 평가·웹 빌드 | `docker compose run --rm --build check` |
| 브라우저 연동 테스트 | `docker compose run --rm --build e2e` |
| 인프라 설정 로컬 검증 | `docker compose run --rm infra-check` |
| 배포 형태 미리보기 | `docker compose up -d --build preview` |
| 미리보기 종료 | `docker compose stop preview` |

`up -d`는 `api`, `web`만 켭니다. 검사·브라우저 테스트·미리보기는 명령으로 지정할 때만 실행됩니다.
E2E는 필요한 개발 서버를 자동으로 시작합니다. 첫 E2E 빌드에서는 테스트용 Chromium도 컨테이너에 설치합니다.
Mock 평가는 입출력 규칙을 확인하며 실제 AI 답변 품질을 평가하는 것은 아닙니다.

## 무엇을 바꾸면 다시 빌드하나요?

`apps/web/src/`와 `apps/api/src/` 내부 파일은 새로 추가해도 자동 반영됩니다.
패키지 목록·lockfile·Dockerfile·Python 도구 설정을 변경했거나 그런 변경을 pull했다면 다음을 실행하세요.

```bash
docker compose up -d --build
```

최상위에 새로운 소스·정적 파일 폴더를 만들면 Docker 이미지와 Compose 연결 설정도 추가해야 합니다.
호스트의 `node_modules`나 `.venv`는 컨테이너와 공유하지 않습니다.

## 개발 화면과 배포 미리보기의 차이

| 구분 | 개발 | 배포 미리보기 |
| --- | --- | --- |
| 실행 명령 | `docker compose up -d` | `docker compose up -d --build preview` |
| 화면 주소 | http://localhost:5173 | http://localhost:8080 |
| 소스 수정 자동 반영 | 지원 | 미지원, 다시 빌드 필요 |
| 실행 방식 | 웹·API 별도 개발 서버 | 빌드된 웹·API를 한 컨테이너에서 제공 |

두 환경은 동시에 실행할 수 있습니다. 미리보기까지 모두 끄려면 `docker compose --profile preview down`을 실행합니다.

## scripts 폴더는 무엇인가요?

Compose는 **팀원이 사용하는 실행 방법**, `scripts/`는 **그 명령이나 CI가 호출하는 내부 구현**입니다.
예를 들어 `check`가 `scripts/evaluate.py`를 실행하므로 팀원이 해당 파일을 직접 실행할 필요는 없습니다.
배포·롤백 스크립트는 운영 담당자가 명시적으로 실행합니다. [파일별 역할](scripts/README.md)을 정리했습니다.

## 폴더 구성

```text
compose.yaml                 개발 실행과 검사·미리보기 명령
Dockerfile.dev               개발 도구와 브라우저 테스트 이미지
Dockerfile                   배포용 앱 이미지
apps/web/                    웹 화면과 브라우저 테스트
apps/api/src/builder_cup/     API, 입력 검증, 모델 연결
models/vllm/                 별도 GPU 서버용 Gemma 설정
infra/gcp/                   GCP 인프라 설정
.github/workflows/           자동 검증과 배포
scripts/                     평가와 운영 작업의 구현
tests/                       API와 오류 처리 테스트
evaluation-cases/            평가용 입력 데이터
prototype/                   팀에서 검토할 후보 프로젝트
docs/                        설치, 구조, 운영, 협업 문서
```

## 협업과 배포

공통 개발 브랜치는 `develop`이고 push하면 CI가 실행됩니다.
**GCP 배포와 과금 활성화는 보류 중입니다.** 기본 개발 Compose는 실제 모델 호출용 환경이 아닙니다.
실제 Gemini 연결은 프로젝트 권한·인증 주입·모델 접근·할당량·과금 준비를 별도로 합의한 뒤 진행합니다.

`release/gcp` push는 실제 배포를 실행합니다. 배포 재개 전에는 해당 브랜치에 push하거나
`scripts/bootstrap-gcp.sh`를 실행하지 마세요. `.env`, 인증정보, 모델 파일, Terraform 상태,
생성된 평가 결과는 Git에 올리지 않습니다.

## 문서와 팀 링크

- [팀원용 처음 설치 가이드](docs/setup.md)
- [이전 작업과 남은 일](docs/session-handoff.md)
- [아키텍처](docs/architecture.md)
- [운영 안내](docs/operations.md)
- [팀 협업 방식](docs/team-workflow.md)
- [Gemma/vLLM 안내](models/vllm/README.md)

- [GitHub 프로젝트 보드](https://github.com/users/Sihyeon-Ji/projects/1)
