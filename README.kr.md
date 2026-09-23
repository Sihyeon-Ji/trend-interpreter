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
`docker compose ps`에서 `db`, `api`, `web` 상태를 확인하세요.
`db-init`은 실습 테이블 초기화 후 `Exited (0)`으로 끝나는 정상적인 일회성 작업입니다.

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
| 서비스·선택적 모델 준비 상태 진단 | `docker compose run --rm --build doctor` |
| 로그 보기 | `docker compose logs -f` |
| 개발 환경 끄기 | `docker compose down` |
| 의존성·이미지 설정 변경 반영 | `docker compose up -d --build` |
| 코드 검사·테스트·Mock 평가·웹 빌드 | `docker compose run --rm --build check` |
| PostgreSQL 실습 기록 생성·조회 | `docker compose run --rm --build db-check` |
| DB 마이그레이션 재실행·실패 롤백 검사 | `docker compose run --rm --build db-migration-check` |
| 로컬 DB 백업 생성 | `docker compose run --rm db-backup` |
| 병렬 작업·Join·Router 실습 | `docker compose run --rm --build workflow-check` |
| 실행·단계별 이력 저장·조회 검사 | `docker compose run --rm --build history-check` |
| Mock 오류·취소·재시도 실습 | `docker compose run --rm --build failure-check` |
| 실제 로컬 모델과 Mock 비교 | `docker compose run --rm --build ollama-check` |
| 평가 사례·수동 검토·보고서 비교 | `docker compose run --rm --build model-eval validate-suite` |
| Gemma 4 보고서와 실행 이력 연결 | `docker compose run --rm --build ollama-history-check` |
| 브라우저 연동 테스트 | `docker compose run --rm --build e2e` |
| 인프라 설정 로컬 검증 | `docker compose run --rm infra-check` |
| 배포 형태 미리보기 | `docker compose up -d --build preview` |
| 미리보기 종료 | `docker compose stop preview` |

`up -d`는 PostgreSQL과 초기화 작업을 거쳐 `api`, `web`을 켭니다. 검사·브라우저 테스트·미리보기는 명령으로 지정할 때만 실행됩니다.
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

## 패키지를 추가하거나 업데이트할 때

`docker compose run --rm --build npm install 패키지명` 또는
`docker compose run --rm --build uv add 패키지명`을 사용하면 목록과 lockfile이 로컬 저장소에 함께 기록됩니다.
호스트에 Node·Python을 설치하지 않아도 됩니다. 재빌드와 검증 후 두 파일을 같은 커밋에 포함하세요.
제거·개발용 패키지·업데이트 예시는 [명령어 모음](docs/commands.md)에 정리했습니다.

## PostgreSQL 첫 실습

`docker compose run --rm db-check`를 실행하면 합성 기록을 하나 생성하고 같은 ID로 조회합니다.
출력된 `Read again` 명령은 기존 기록만 조회하며, `Open` 주소는 브라우저에서 열 수 있습니다.
DB 재시작 후 같은 ID·이름·생성 시각이 유지되는지 [실습 기록](docs/ai-lab-plan.md)에서 확인하세요.
합성 기록은 API로 조회하며, 5173 화면에서는 별도로 그래프 실행 이력을 볼 수 있습니다.

DB 데이터와 자동 생성된 접속 비밀번호는 별도 Docker 볼륨에 남습니다. 일반 `down`은 보존하지만
볼륨 삭제 옵션은 실습 기록과 비밀번호를 지웁니다. DB는 호스트 포트를 공개하지 않으며
앱에는 합성 기록의 조회·추가 권한과 실행 이력 테이블의 조회·추가·수정 권한을 부여합니다.
배포 미리보기에서는 실습 API가 비활성화됩니다.
스키마 변경은 체크섬이 기록되는 순차 SQL 마이그레이션으로 관리합니다.
백업·새 DB 복원 절차는 [Plan 04 결과](docs/plans/04-database-recovery.md)에 정리했습니다.

## 작은 그래프 워크플로우 실습

합성 회의록의 그래프 실습은 `docker compose run --rm workflow-check`로 실행합니다.
정상·필수 항목 누락·빈 항목의 세 입력에 대해 Mock 결과, 규칙 판단, 노드 실행 순서를 출력합니다.
`accepted`는 실습의 형식 규칙 통과를 뜻하며 사실성이나 AI 품질 판정이 아닙니다.
http://localhost:5173 의 **Workflow history**에서 `Run workflow`를 누르고 실행 항목을 선택하면
단계별 상태·시간·모델·토큰·오류 코드를 확인할 수 있습니다. 최근 20개를 조회하며 원문과 생성 결과는 저장하지 않습니다.
이력은 DB에 남지만 중단된 작업을 자동 재개하지는 않습니다. [실습 기록](docs/ai-lab-plan.md)을 참고하세요.

같은 화면의 **Practice scenario**에서 모델 시간 초과, 잘못된 JSON, 병렬 분기 실패, 재시도 복구를 선택할 수 있습니다.
기본 문서로 실행한 뒤 예상 결과와 실제 단계별 상태를 비교하세요. 이 실습에서 의도한 오류는 정상적인 재현 결과입니다.
터미널에서는 `docker compose run --rm --build failure-check`로 전체 시나리오를 검증합니다.

## 실제 모델 실습

Mac 호스트에 Ollama와 Google `gemma4:e4b` 모델을 준비한 뒤 `docker compose run --rm --build ollama-check`를 실행합니다.
버전이 있는 합성 문서 10개를 같은 그래프로 처리하고, 결과·토큰·시간을 `artifacts/`의 JSON과 Markdown 파일에 남깁니다.
같이 생성되는 수동 검토 양식은 원문/출력 근거와 평가자·시각을 기록하며, `model-eval`로 누락 없는지 확인합니다.
기본 웹 화면과 실행 이력 실습은 계속 Mock이며, 실제 모델 비교는 이 명령으로 따로 실행합니다.
연결 실패를 Mock 성공으로 바꾸지 않습니다. 설치·실행 순서는 [명령어 안내](docs/commands.md#실제-로컬-모델-비교),
관찰한 품질 문제와 성능 수치는 [5단계 실습 기록](docs/ai-lab-plan.md)에 있습니다.
평가 체계와 최신 10개 사례 결과는 [Plan 02 결과](docs/plans/02-model-evaluation.md)에 있습니다.
실제 모델 실행을 PostgreSQL 메타데이터 이력과 연결하려면 [Plan 03 결과](docs/plans/03-local-model-history.md)를 참고하세요.

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

공통 개발 브랜치는 `develop`이며 이 브랜치의 push는 GitHub Actions를 실행하지 않습니다.
기본 개발 Compose는 mock을 사용합니다. GCP 과금 계정이 연결됐고 Cloud Run에서 Vertex AI Gemini를
사용하는 릴리스가 운영 중이지만, 실제 모델 사용량과 할당량·비용은 계속 확인해야 합니다.

`release/gcp` push는 전체 검증을 한 번 실행한 뒤 이미지 게시와 실제 배포를 수행합니다.
필요하면 GitHub Actions에서 CI를 수동 실행할 수도 있습니다. `.env`, 인증정보, 모델 파일,
Terraform 상태, 생성된 평가 결과는 Git에 올리지 않습니다.

## 문서와 팀 링크

- [전체 문서 색인](docs/README.md)
- [1~5단계 종합 보고서 — 준비된 역량·한계·다음 과제](docs/ai-lab-report.md)
- [주제 선정 전에 진행할 공통 개발 기반 계획](docs/plans/README.md)
- [로컬 LLM·그래프 워크플로우·DB 이해하기](docs/ai-development-guide.md)
- [5단계 AI 실습 계획과 준비물](docs/ai-lab-plan.md)
- [팀원용 처음 설치 가이드](docs/setup.md)
- [아키텍처](docs/architecture.md)
- [GCP 설정·비용 절감·삭제·복구와 웹 화면 사용법](docs/operations.md)
- [팀 협업 방식](docs/team-workflow.md)
- [Gemma/vLLM 안내](models/vllm/README.md)

- [GitHub 프로젝트 보드](https://github.com/users/Sihyeon-Ji/projects/1)
