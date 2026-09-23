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
| 준비 상태 읽기 전용 진단 | `docker compose run --rm --build doctor` | 서비스 자동 기동 없이 Mock·DB 읽기·선택적 Ollama 상태 확인 |
| 최근 로그부터 계속 보기 | `docker compose logs -f --tail 100` | 최근 100줄부터 실시간 로그 표시 |
| API 로그만 보기 | `docker compose logs -f --tail 100 api` | API 오류·재시작 상태 확인 |
| 웹 로그만 보기 | `docker compose logs -f --tail 100 web` | Vite 오류·화면 변경 감지 확인 |
| 개발 환경 종료 | `docker compose down` | 개발 컨테이너와 네트워크 제거, 소스·이미지는 유지 |

개발 화면은 **http://localhost:5173**, API 문서는 **http://localhost:8000/docs**입니다.
로그를 보다가 `Ctrl+C`를 누르면 로그 보기만 끝납니다. 서버 종료는 `down`을 사용하세요.

## 준비 상태 진단

Docker 엔진이 켜져 있고 저장소 루트에 있는지 먼저 확인한 뒤 실행합니다.

```bash
docker compose run --rm --build doctor
```

`doctor`는 의존 서비스를 자동 시작하지 않고 GET 요청으로 현재 프로젝트의 API·웹 프록시·DB 이력 조회를 확인합니다.
Ollama 서버·다운로드 목록을 조회하지만 설치·모델 다운로드·추론은 실행하지 않습니다.
기본 Mock 서비스가 준비되지 않았으면 종료 코드 1, 준비됐다면 0입니다. Ollama 미준비는 선택 항목이므로 종료 코드를 바꾸지 않습니다.
HTTP 요청 자체는 서비스 접근 로그에 남을 수 있으며 처음 실행 시 이미지·임시 컨테이너·네트워크는 생성될 수 있습니다.

호스트 경로·브랜치·Docker context·포트 소유 프로세스·CLI 설치 여부는 컨테이너에서 판단하지 않습니다.
[Mac 진단 명령과 결과별 대처](setup-macos.md#4-문제가-생겼을-때-준비-상태-확인)를 함께 사용하세요.

다른 checkout을 동시에 띄울 때는 `COMPOSE_PROJECT_NAME`과 `DEV_API_PORT`·`DEV_WEB_PORT`를 구분합니다.
기본 포트는 계속 8000·5173이며 모든 개발 공개 포트는 루프백에 바인딩합니다.
[격리 실행 예시](setup-macos.md#5-별도-checkout을-독립적으로-검증하기)와
[Compose 프로젝트 이름 규칙](https://docs.docker.com/compose/how-tos/project-name/)을 참고하세요.

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
| PostgreSQL 기록 저장·조회 | `docker compose run --rm --build db-check` | DB 초기화와 API 준비 후 실행 |
| DB migration 재실행·실패 rollback | `docker compose run --rm --build db-migration-check` | 데이터·버전 상태 유지 확인 |
| 그래프 워크플로우 실습 | `docker compose run --rm --build workflow-check` | 합성 문서로 병렬 실행·통합·규칙 분기 확인 |
| 실행 이력 저장·조회 검사 | `docker compose run --rm --build history-check` | 성공·실패 실행과 단계별 메타데이터 확인 |
| 오류·취소·재시도 재현 | `docker compose run --rm --build failure-check` | 예상 실패와 복구를 이력에서 검증 |
| 모델 평가 suite·검토·보고서 | `docker compose run --rm --build model-eval validate-suite` | 실제 모델 호출 없이 평가 구조 확인 |
| Gemma 4 보고서·DB 이력 연결 | `docker compose run --rm --build ollama-history-check` | 명시적 합성 사례 하나만 실제 모델 호출 |
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

## PostgreSQL 저장·조회 실습

```bash
docker compose run --rm db-check
```

합성 기록 한 개를 만들어 DB에 저장하고, 같은 ID로 조회해서 결과를 비교합니다.
`id`, `label`, `created_at`과 `PASS`가 나오면 성공입니다.
출력 하단의 `Read again` 명령을 복사하면 **기존 ID만 조회**할 수 있습니다.
`Open` 주소는 브라우저에서 같은 기록을 보는 주소입니다.

데이터 유지를 확인하려면 위에서 생성한 ID를 보관한 뒤 다음을 실행합니다.

```bash
docker compose restart db
```

DB가 다시 준비되면 보관한 `Read again` 명령을 실행합니다.
처음 `db-check`를 다시 실행하면 새 기록을 생성하므로, 반드시 기존 ID로 읽어야 합니다.
`docker compose down` 후 `docker compose up -d --wait`로 재생성해도 같은 방법으로 확인합니다.

| 서비스·볼륨 | 역할 |
| --- | --- |
| `db` | PostgreSQL 18.6, 호스트에 포트 공개하지 않음 |
| `db-init` | 실습 테이블·계정 초기화. `Exited (0)`은 정상 완료 |
| `db-check` | API를 통해 합성 기록 저장·조회 검증 |
| `postgres_data` | DB 데이터 유지 |
| `postgres_admin_password`, `postgres_app_password` | 자동 생성한 관리자·앱 접속 비밀번호 유지 |

일반 `down`은 볼륨을 보존합니다. 볼륨 삭제 옵션을 붙이거나 Docker Desktop에서 해당 볼륨을 삭제하면
기록이나 접속 비밀번호가 없어집니다. 비밀번호 볼륨도 데이터 볼륨과 함께 보존하세요.
DB 중단 시 실습 API는 `503 database_unavailable`을 반환합니다.
일반 `/api/health`는 앱 생존 상태이므로 DB 연결 성공을 뜻하지 않습니다.
실제 검증 결과는 [실습 계획과 기록](ai-lab-plan.md)에 있습니다.

## DB migration과 백업·새 DB 복원

`apps/api/src/builder_cup/migrations/`의 `NNN_name.sql` 파일을 번호순으로 적용합니다.
적용한 버전·이름·SHA-256·시각은 `lab.schema_migrations`에 저장됩니다.
이미 적용된 파일은 건너뛰고 checksum이 달라지면 실패합니다.

```bash
docker compose run --rm --build db-migration-check
```

이 검사는 migration을 두 번 적용해 데이터와 버전이 바뀌지 않는지 확인하고,
변경된 checksum 거부와 의도적 SQL 실패의 transaction rollback을 검사합니다.
실패 probe table과 가짜 버전은 rollback되므로 남지 않습니다.

현재 로컬 DB를 custom-format 파일로 백업합니다.

```bash
docker compose run --rm db-backup
```

출력된 `.dump`와 `.dump.sha256`은 권한 `0600`으로 Git 제외 `backups/`에 저장됩니다.
role·ACL·접속 비밀번호는 dump에 포함하지 않습니다. 기존 파일을 덮어쓰지 않습니다.

복원은 기존 DB가 아니라 **존재하지 않는 새 DB 이름**으로만 가능합니다.

```bash
export BACKUP_FILE=/backups/builder-cup-YYYYMMDDTHHMMSSZ.dump
export RESTORE_DATABASE=builder_cup_restore_YYYYMMDD
docker compose run --rm db-restore
docker compose run --rm --build db-recovery-check
unset BACKUP_FILE RESTORE_DATABASE
```

복원 명칭은 `builder_cup_restore_` 다음에 소문자·숫자·밑줄을 사용해야 합니다.
대상 DB가 이미 있거나 checksum 파일이 없거나 다르면 복원을 거부합니다.
새 DB 생성 뒤 `pg_restore`가 실패하면 자동 삭제하지 않고 부분 대상을 남깁니다.
오류를 확인한 뒤 다른 새 대상 이름으로 다시 시도하며, 기존 대상의 수동 삭제는 이 명령의 범위가 아닙니다.
`db-recovery-check`는 원본·복원의 record, workflow run/node, migration table을
row count와 정렬된 JSON fingerprint로 비교하고 앱 role의 제한된 권한도 확인합니다.
비교 출력에는 원문 row나 비밀번호가 포함되지 않습니다.

이 절차는 로컬 논리 백업·복원 실습입니다. 자동 백업 스케줄, 암호화 보관,
Cloud SQL, 시점 복구나 PostgreSQL major version upgrade를 검증한 것은 아닙니다.
검증 결과와 안전 범위는 [Plan 04](plans/archive/04-database-recovery.md)에 있습니다.

## 그래프 워크플로우 실습

그래프 실습은 다음 명령으로 실행합니다.

```bash
docker compose run --rm workflow-check
```

추가 문서를 준비할 필요가 없습니다. `evaluation-cases/workflow-lab.json`에 있는 합성 입력 3개를
실행하며 정상 문서는 `accepted`, 필수 항목이 없거나 비어 있으면 `needs_revision`을 출력합니다.
`EVENTS`는 실제 노드 시작·완료 순서입니다. Mock은 즉시 응답하므로 두 분기가 화면상 순서대로
끝날 수 있습니다. 병렬 스케줄링 자체는 한 분기가 다른 분기의 시작을 기다리는 테스트로 검증합니다.

직접 다른 문장을 보내려면 http://localhost:8000/docs 에서 `POST /api/lab/workflow`를 사용하세요.
`text`에는 `## 일정`, `## 준비`라는 제목과 각 제목 아래 내용이 있어야 형식 검사를 통과합니다.
일반 Markdown 전체를 파싱하거나 내용의 사실성을 판단하는 규칙은 아닙니다.
기본 개발 환경에서는 실행·단계별 메타데이터를 DB에도 저장합니다.

## 실행 이력 조회

1. `docker compose up -d --build --wait`로 개발 환경을 켭니다.
2. http://localhost:5173 에서 **Workflow history**로 내려갑니다.
3. 합성 문서를 그대로 두고 **Run workflow**를 누릅니다.
4. 최근 실행 목록에서 항목을 선택해 시간·모델·토큰·오류 코드와 5개 단계의 상태를 확인합니다.
5. 다른 터미널에서 실행했다면 **Refresh history**로 목록과 선택한 상세를 갱신합니다.

작은 화면에서는 단계별 표를 가로로 스크롤하세요. 목록은 최근 20개이며 실행 이력만으로
입력이나 생성 결과를 복원할 수는 없습니다. 두 텍스트 모두 이력 DB에 저장하지 않습니다.

| 표시 | 의미 |
| --- | --- |
| `completed` + `accepted` | 모든 단계 완료, 문서 형식 규칙 통과 |
| `completed` + `needs_revision` | 실행은 완료했지만 필수 제목·내용 보완 필요 |
| `failed` / `cancelled` | 실행 실패 / 비동기 작업 취소 |
| `skipped` | 앞 단계 실패 등으로 실행하지 않은 노드 |
| `Running / unfinished` | 실행 중이거나 종료 기록을 남기지 못한 실행 |
| `Not reported` | 공급자가 토큰 수를 제공하지 않음. Mock은 명시적으로 0을 기록 |

노드 정보는 실행 종료 시 한 번에 저장합니다. 실시간 진행 화면이 아니며 강제 종료나 DB 기록 실패로
미완료 상태가 남을 수 있습니다. **Refresh history는 자동 재개 명령이 아닙니다.**
`Attempts`는 모델 호출 시도 횟수입니다. 토큰 수는 공급자가 보고한 응답 기준이며 미보고 실패 호출까지 합산한 청구량이 아닙니다.

터미널에서 성공·실패 저장과 원문 미포함을 자동 확인하려면 다음을 실행합니다.

```bash
docker compose run --rm --build history-check
```

출력된 기존 실행 ID를 조회하려면 `history-check` 뒤에 해당 UUID를 붙입니다. 이 경우 새 실행을 만들지 않습니다.
DB 재시작 전후 같은 ID의 상태·시각·노드 정보가 유지되는지 비교할 수 있습니다.
일반 `docker compose down`은 이력을 보존하지만 볼륨 삭제는 데이터를 지웁니다.
API는 `GET /api/lab/runs`와 `GET /api/lab/runs/{id}`이며 http://localhost:8000/docs 에서 사용할 수 있습니다.

## 실패 실습

개발 환경을 켠 뒤 http://localhost:5173 의 **Workflow history → Practice scenario**에서
시나리오를 선택하고 **Run workflow**를 누릅니다. 우선 기본 합성 문서를 유지하세요.
예상 결과는 선택 상자 아래에 표시되며 실제 결과는 실행 상세의 `Scenario`, `Attempts`, 노드 상태로 비교합니다.

| 선택 | 시나리오 값 | 기본 문서의 예상 결과 |
| --- | --- | --- |
| Normal workflow | `normal` | 정상 완료, 1회 호출 |
| Model timeout | `timeout` | HTTP 504 `model_timeout`, 각 1초 제한으로 2회 시도 후 실패 |
| Invalid model JSON | `invalid_json` | HTTP 502 `invalid_model_response`, 1회 호출 후 재시도 없이 실패 |
| Parallel branch failure | `branch_failure` | HTTP 500 `document_check_failed`, 문서 검사 실패·추출 취소 |
| Transient error then recovery | `transient_error` | 첫 연결 실패 후 두 번째 성공, HTTP 200·2회 호출 |

실패하면 Join과 Router는 `skipped`입니다. 잘못된 JSON은 즉시 실패하므로 독립적인 문서 검사는
그때까지 끝났으면 `completed`, 끝나지 않았으면 `cancelled`일 수 있습니다.
각 요청은 독립적이며 실패 실습 후 `Normal workflow`로 바꾸면 정상 실행합니다.
선택한 실패보다 입력 검사가 먼저이므로 공백 등 잘못된 입력은 `invalid_input`으로 거부합니다.

```bash
docker compose run --rm --build failure-check
docker compose run --rm failure-check timeout
docker compose run --rm failure-check branch_failure
docker compose run --rm failure-check transient_error
```

첫 명령은 실패 3종·재시도 성공·정상 실행을 전부 확인합니다. `PASS`는 예상대로 실패하거나 복구했고
이력까지 올바르게 저장됐다는 뜻입니다. 출력된 `Read again` 명령으로 기존 실행을 다시 조회할 수 있습니다.
외부 모델·네트워크를 호출하지 않고 Mock 지연과 오류를 주입하며, DB나 컨테이너를 강제로 끄지 않습니다.
DB 저장 오류 정책은 자동 테스트에서 시작 쓰기 실패·종료 쓰기 실패로 별도 검증합니다.

## 실제 로컬 모델 비교

기본 `up -d`와 `check`는 계속 Mock입니다. 아래는 **Mac에서 실제 추론을 원할 때만** 실행합니다.
Ollama는 Mac 호스트에서 실행하고, 비교 코드는 Docker에서 실행합니다.

처음 한 번 Homebrew로 설치하고, 터미널 하나에서 로컬 전용 서버를 켭니다.

```bash
brew install ollama
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

이 터미널은 열어 두고 다른 터미널에서 모델을 받습니다.

```bash
ollama pull gemma4:e4b
ollama list
docker compose run --rm --build ollama-check
```

이미 Ollama가 실행 중이면 `ollama serve`를 중복 실행하지 마세요.
백그라운드 실행을 원하면 먼저 `~/.ollama/server.json`에 `"disable_ollama_cloud": true`를 설정하고
`brew services start ollama`를 사용합니다. 파일이 없다면 아래 내용으로 만들고, 기존 파일이 있으면 다른 설정을 유지해 병합합니다.

```json
{"disable_ollama_cloud": true}
```

이번 검증 PC에는 Homebrew Ollama 0.34.2, 모델과 위 설정을 준비하고 백그라운드 서비스를 시작했습니다.
다른 팀원은 각자 준비해야 합니다. 모델은 `~/.ollama/models`에 있으며 Git이나 Docker 이미지에 넣지 않습니다.
모델 파일은 약 9.6GB이며 실행 시 메모리와 추가 디스크 공간도 필요합니다.

비교 명령은 합성 문서 3개로 Mock 3회·Ollama 4회를 실행합니다. 첫 문서는 실제 모델로 두 번 실행해
초기 로딩이 포함된 요청과 후속 요청을 비교합니다. 모델이 이미 메모리에 있다면 첫 요청도 빠를 수 있습니다.
초기 로딩부터 다시 재려면 다른 추론 작업이 없는 때에 `ollama stop gemma4:e4b` 후 비교 명령을 실행하세요.

결과는 `artifacts/ollama-comparison-날짜.json`과 같은 이름의 `.md`로 남습니다.
**Markdown은 입력·기대 사실·금지할 주장·실제 응답을 읽는 용도**, JSON은 버전·모델 digest·토큰·노드·로딩 시간 확인용입니다.
원문과 생성 결과는 합성 평가 파일에만 남으며 운영 로그에는 출력하지 않습니다. 이 비교는 PostgreSQL 이력에 저장하지 않습니다.
Markdown에서 각 사실이 유지되는지 직접 비교하세요. `schema valid`는 내용이 정확하다는 뜻이 아닙니다.

| 상황 | 확인 방법 |
| --- | --- |
| 실행 중인 모델·GPU 사용 확인 | `ollama ps` |
| 모델만 메모리에서 내리기 | `ollama stop gemma4:e4b` — 다운로드 파일 유지 |
| 백그라운드 서버 중지 | `brew services stop ollama` |
| 서버 중단·모델 미설치 | 비교 명령 실패 및 실패 보고서 생성, Mock으로 대체하지 않음 |
| 일반 웹 화면의 모델 | http://localhost:5173 은 계속 Mock |

Ollama는 루프백에만 바인딩하고 Docker에서 `host.docker.internal`로 접근합니다. 이 Mac에서 연결을 검증했습니다.
Windows·WSL2의 Ollama 설치와 네트워크는 이번 검증 범위 밖이며, 기존 Mock 개발 흐름에는 영향이 없습니다.
공식 자료는 [Ollama FAQ](https://docs.ollama.com/faq), [Ollama Gemma 4](https://ollama.com/library/gemma4),
[Google Gemma 4 개요](https://ai.google.dev/gemma/docs/core)를 참고하세요.

### 평가 suite와 보고서 비교

실제 모델을 호출하지 않고 현재 평가 사례의 구조·버전·해시를 확인합니다.

```bash
docker compose run --rm --build model-eval validate-suite
```

`ollama-check` 보고서에는 커밋과 dirty 상태를 자동으로 알 수 없으므로 호스트에서 전달합니다.

```bash
export SOURCE_COMMIT="$(git rev-parse HEAD)"
export SOURCE_DIRTY=false
docker compose run --rm --build ollama-check
unset SOURCE_COMMIT SOURCE_DIRTY
```

변경 파일이 있으면 `SOURCE_DIRTY=true`로 기록합니다. `.review.json`은 자동 점수가 아니라 검토 양식입니다.
평가자와 시각을 기록하고 모든 기준에 상태·출력 근거를 작성한 뒤 보고서와 함께 검증합니다.

```bash
docker compose run --rm model-eval validate-review \
  artifacts/REPORT.review.json --report artifacts/REPORT.json
```

두 보고서의 suite SHA-256이 같을 때 출력 변화, 소요 시간과 토큰 차이를 비교합니다.
두 수동 검토를 함께 주면 기준별 상태 변화도 기록합니다.

```bash
docker compose run --rm model-eval compare \
  artifacts/BASE.json artifacts/CURRENT.json \
  --base-review artifacts/BASE.review.json \
  --current-review artifacts/CURRENT.review.json \
  --output artifacts/model-comparison.json
```

suite가 바뀌면 명령은 `suite_changed`를 기록하고 직접 비교하지 않습니다.
토큰이 보고되지 않은 실행의 차이는 `null`이며 0으로 추정하지 않습니다.
결과 파일은 계속 Git 제외 `artifacts/`에 보관합니다.

### Gemma 4 실행을 Workflow history에 연결

기본 웹·API는 Mock을 유지하면서 합성 사례 하나만 실제 Gemma 4로 실행하고 메타데이터를 PostgreSQL에 저장합니다.

```bash
export SOURCE_COMMIT="$(git rev-parse HEAD)"
export SOURCE_DIRTY=false
docker compose run --rm --build ollama-history-check
unset SOURCE_COMMIT SOURCE_DIRTY
```

기본 사례는 `meeting`입니다. 다른 합성 사례 ID를 사용하려면 명령 끝에 붙입니다.

```bash
docker compose run --rm ollama-history-check schedule_change
```

출력의 `Run ID`는 생성된 `artifacts/ollama-history-날짜.json`,
`GET /api/lab/runs/{id}`, http://localhost:5173 의 **Workflow history**에서 동일합니다.
보고서에는 고정 합성 원문과 생성 결과가 들어가지만 Git에서 제외됩니다.
PostgreSQL에는 Provider·모델·상태·시간·토큰·오류·노드 정보만 저장하고 원문·생성 결과는 저장하지 않습니다.

실패 이력 연결을 실제 외부 장애 없이 확인할 수 있습니다.

```bash
docker compose run --rm ollama-history-check meeting --failure model_unavailable
docker compose run --rm ollama-history-check meeting --failure model_timeout
```

두 명령은 의도적으로 종료 코드 1을 반환하고 `provider=ollama`, `model=gemma4:e4b`의 실패 이력을 남깁니다.
Mock으로 대체하지 않으며 보고서에 `simulation` 값을 기록합니다. 기본 API 프로세스의 Provider는 계속 Mock입니다.

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

`scripts/bootstrap-gcp.sh`, 배포·롤백 스크립트, `release/gcp` push는 운영 명령입니다.
평소 개발에서는 실행하지 말고 실제 배포 시 [운영 문서](operations.md)를 따릅니다.

## GitHub CI는 언제 실행되나요?

- `develop` push와 PR은 자동 검증을 실행하지 않습니다.
- `release/gcp` push가 배포 워크플로를 시작하고, 그 안에서 전체 CI를 한 번 실행합니다.
- GitHub Actions의 CI 화면에서 `Run workflow`로 수동 실행할 수도 있습니다.
- 릴리스 검증은 변경 파일 종류와 관계없이 실행하며 진행 중인 배포를 새 push로 취소하지 않습니다.

`verify`는 작업 이름입니다. 그 안에서 코드 검사·Python 테스트·Mock 평가·브라우저 테스트·Terraform
검증·배포 이미지 빌드·컨테이너 smoke test를 실행합니다. 실제 GCP 배포는 검증 성공 후에만 진행됩니다.

팀원의 PC가 Mac이어도 CI는 Docker의 Linux 실행 환경을 확인하므로 Ubuntu runner를 사용합니다.
공개 저장소의 표준 runner는 무료이고, 비공개 저장소는 소유자 계정의 요금제별 무료 시간을 사용합니다.
GitHub Free 기준 월 2,000분이며 다른 비공개 저장소 사용량과 공유됩니다.
[공식 Actions 과금 안내](https://docs.github.com/en/billing/concepts/product-billing/github-actions)를 기준으로,
GitHub 계정의 Billing and licensing에서 실제 사용량과 예산·초과 사용 차단 설정을 확인하세요.
이 저장소의 CI 설정만으로 계정 전체의 과금을 막지는 못합니다.
