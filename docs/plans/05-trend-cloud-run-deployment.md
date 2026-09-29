# Plan 05. Trend 앱 Cloud Run 배포

작성일 **2026-09-28** · 변경일 **2026-10-01** · 상태 **Cloud SQL 체험 인스턴스 생성 완료(콘솔에서 만듦, Terraform 밖), 앱 배포 구현 대기 — 코드 쪽(PostgreSQL·마이그레이션·JSON 로그·연결 풀, 유지보수 작업·운영 신호 — 10-01 develop)만 끝났고, GCP 자원 생성·배포는 제출 직전 사용자 확인 뒤** · 선행 [Plan 04](04-target-regions-and-keyword-dashboard.md) · 목표일 **2026-10-09** · 인프라 작업은 Plan 02부터 병행 가능

[계획 목록](README.md) · [Plan 13: Cloud SQL 유료 전환](13-cloud-sql-trial-to-paid-transition.md) · [아키텍처](../운영/시스템-아키텍처.md) · [AI 호출 제어](../운영/AI-호출-제어.md) · [GCP 운영](../운영/GCP-운영.md) · [Gemma 로컬 편집 결정](../AI-개발/Gemma-로컬-편집-엔진-결정.md)

> **변경 결정:** Cloud Run에는 웹·API와 PC 독립 운영에 필요한 작은 유지보수 작업만 두고, 영속 DB는 Cloud SQL에 둔다. 전체 수집·해석 파이프라인을 Cloud Run Job과 Scheduler로 이전하는 계획은 철회했다. Gemma 4 기반 사전·국가별 해석 편집은 [Plan 06](06-gemma-on-cloud-run-gpu.md)에 따라 Kaggle 노트북 GPU에서 오프라인 배치로 실행하고, 검수 후 별도 게시 도구로 반영한다.

## 배경

`prototype/trend`를 메인 앱으로 확정해 `apps/trend-api`와 `apps/trend-web`으로 옮겼습니다. 로컬 Compose,
CI 검사, 배포 이미지 빌드와 smoke 검사까지 통과했지만 **GCP 배포는 일부러 열지 않았습니다.**
`release/gcp`의 application job은 제거했고 `scripts/release_scope.py`는 Trend 변경을 공통 검사로만 보냅니다.
이전 실습 앱의 `builder-cup` Cloud Run 서비스는 Trend 릴리스가 대체할 때까지 그대로 둡니다.

배포를 열지 않은 이유는 두 가지입니다.

1. Trend API는 2026-09-28까지 SQLite(`data/trend.db`)에 저장했고, Cloud Run 인스턴스의 파일시스템은 재시작·스케일
   아웃 시 사라집니다. 같은 날 저장소를 PostgreSQL로 옮겼고, 2026-09-29에 Cloud SQL 체험 인스턴스를 만들었습니다.
   데이터베이스·사용자·접속 경로와 데이터 게시는 아직 준비해야 합니다.
2. Trend는 화면과 API가 별도 서비스입니다. API는 외부에 공개하지 않고 웹 서버 라우트만 호출하는 경로가 필요합니다.

## 이미 준비된 것

| 항목 | 상태 |
| --- | --- |
| Gemini 호출 경로 | `model_client.py`에서 Vertex AI + 런타임 service account. API key 없음. 런타임 계정에 `roles/aiplatform.user` 부여됨 |
| 호출 차단 | `MODEL_PROVIDER=vertex`와 `MODEL_REQUESTS_ENABLED=true`가 모두 켜져야 호출. 하루 예산 `GEMINI_DAILY_BUDGET` |
| 배포 이미지 | `apps/trend-api/Dockerfile`(uvicorn, 비root, 8080), `apps/trend-web/Dockerfile`(Next.js standalone, 8080) |
| 이미지 검증 | CI가 두 이미지를 빌드하고 `scripts/container-smoke.sh`로 health·첫 화면 확인 |
| 저장소 | PostgreSQL. `storage/db.py` 어댑터, `DATABASE_URL` 하나로 연결. 로컬 Compose `db`와 CI 검증 완료, SQLite 이관 스크립트 `scripts/migrate_sqlite_to_postgres.py` |
| Cloud SQL | `stunning-crane-508614-c1`의 `trend-project`, 도쿄(`asia-northeast1`), PostgreSQL 18. 2026-09-29 `gcloud sql instances describe` 결과 `RUNNABLE`. 콘솔에서 30일 무료 체험 문구 확인. DB·사용자·앱 연결은 미완료 |
| 웹 설정 | `DATA_MODE`, `TREND_API_URL`, `FRONTEND_API_TOKEN`, `SESSION_SECRET`은 런타임 환경변수. 빌드 시 박히지 않음 |
| 인프라 | Artifact Registry, 런타임·배포 service account, Workload Identity, 모니터링·알림·예산이 Terraform에 있음 |

## 결정할 것

### 1. 영속 저장소 — PostgreSQL (결정됨)

관계형 데이터는 모두 PostgreSQL로 통일했습니다(2026-09-28). 공모전 배포에는 이미 콘솔에서 생성한 **Cloud SQL for PostgreSQL**
`trend-project`를 사용합니다. 이 인스턴스는 도쿄 리전의 PostgreSQL 18, Enterprise Plus 체험 사양(8 vCPU·64 GB·100 GB)입니다.
콘솔에서 **30일 무료 체험** 표시를 확인했고, API 조회에서는 `RUNNABLE`입니다. 체험 종료 예상일은 생성일로부터 30일 뒤인
**2026-10-29경**이며 정확한 시각은 콘솔의 남은 일수 표시로 확인합니다. 인스턴스 자체의 체험 요금과 별도로 리전 밖·공용
인터넷 연결의 데이터 전송 비용은 발생할 수 있습니다([Cloud SQL 무료 체험 공식 안내](https://docs.cloud.google.com/sql/docs/postgres/free-trial-instance)).

Cloud Run API와 별도 유지보수 작업은 Cloud SQL 커넥터(Unix socket) 또는 private IP로 붙습니다. `DATABASE_URL`은
Secret Manager에 둡니다. 콘솔에서 자동 생성한 관리자 비밀번호는 Git·Terraform state·로그에 넣지 않고, 앱에는 별도
최소 권한 DB 사용자를 사용합니다. **이번 공모전 범위에서는 자동 백업과 시점 복구를 켜지 않습니다.** 체험 인스턴스는
백업·복원을 지원하지 않으므로, 게시 데이터가 생기면 성공한 게시본을 `pg_dump`로 별도 보관하고 로컬 PostgreSQL에서
복원할 수 있는지 확인합니다. 덤프에는 자격증명이나 사용자 입력이 포함될 수 있으므로 Git에 넣지 않고 접근을 제한합니다.
체험 종료 전에 유료 전환·소형 인스턴스로의 이전·서비스 종료 중 하나를 결정합니다. 전환 시에는 체험 사양 그대로 과금하지
않도록 요금과 크기를 먼저 확인하고, 필요한 경우 백업 정책을 다시 결정합니다.

현재 인스턴스는 **Terraform 외부에서 만든 체험 자원**으로 취급합니다. 이번 계획의 Terraform에는 동일 이름의 Cloud SQL
인스턴스 생성 리소스를 추가하지 않습니다. 기존 인스턴스를 참조해 서비스 계정·IAM·Secret 메타데이터 등 앱 인프라를
관리하며, 향후 유료 전환과 Terraform 편입은 별도 변경으로 검토합니다. 체험 종료 뒤 전환하지 않으면 인스턴스가 요청을
처리하지 않으므로, 공모전 시연 일정과 남은 일수를 함께 점검합니다.
Spanner Graph는 이번 제출 범위에서 제외합니다. 기존 BigQuery 공개 시계열 조회는 PostgreSQL 운영 DB 결정과 별개입니다.

### 2. 서비스 구성

| 서비스 | 공개 범위 | 역할 |
| --- | --- | --- |
| `builder-cup-trend-web` | public invoker | Next.js 화면과 서버 라우트 |
| `builder-cup-trend-api` | private (웹 서비스 계정만 invoker) | FastAPI 읽기 API와 검수 기록 |

전체 파이프라인은 Cloud Run에 배포하지 않습니다. 개발자 PC의 수집 결과와 Kaggle의 편집 초안을 검수한 뒤 별도 게시 도구로 Cloud SQL에 반영합니다.
PC가 멈춰도 공개 읽기 기능은 마지막 성공 게시본으로 동작해야 합니다. 단, 사용자 입력의 보존 기간 정리와 운영 건강 점검은 PC에 의존하지 않는 작은 예약 작업으로 따로 구현합니다.

웹 서버 라우트는 `TREND_API_URL`로 API를 부르고 Cloud Run ID token을 붙입니다. `FRONTEND_API_TOKEN`은 API가
쓰기 요청을 받을 때 추가로 확인하는 값으로 유지합니다.

### 3. Secret Manager 항목

값은 Terraform state에 넣지 않고 bootstrap에서 넣습니다. 이름은 다음 규칙으로 만듭니다.

| Secret | 사용하는 서비스 | 환경변수 |
| --- | --- | --- |
| `trend-database-url` | api, 유지보수 작업 | `DATABASE_URL` (Cloud SQL 연결 문자열) |
| `trend-frontend-api-token` | web, api | `FRONTEND_API_TOKEN` |
| `trend-session-secret` | web | `SESSION_SECRET` |
| `trend-accounts` | api | `ACCOUNTS` (PBKDF2 해시 JSON) |

YouTube·Naver 수집 자격증명은 로컬 편집 파이프라인에만 필요하며 Cloud Run secret으로 복제하지 않습니다. 로컬 운영 자격증명과 운영 DB 게시 권한의 경계는 Plan 06에서 정합니다.

Gemini는 secret이 필요 없습니다. Reddit·Bluesky 키는 수집기를 쓰기로 정할 때 추가합니다. 각 secret은
읽는 서비스 계정에만 `secretmanager.secretAccessor`를 부여하고, 배포 스크립트는 숫자 version을 고정해 참조합니다.

## 운영 전 결정 사항 (2026-09-28 확정)

| 항목 | 결정 | 상태 |
| --- | --- | --- |
| Gemma 4 사용 | Kaggle의 사전·국가별 해석 편집 배치, PC 대체 경로 | [Plan 06](06-gemma-on-cloud-run-gpu.md)에서 진행. 운영 Cloud Run GPU 배치 여부는 [Plan 14](14-gemma-visible-in-deployment.md)에서 협의 중(미정) |
| 계정 관리 | 현행 `ACCOUNTS` 해시 유지. 비밀번호를 파일에 남기지 않음 | 완료. `set_account.py`는 비밀번호를 출력에 한 번만 보여 주고 `data/accounts.txt`는 삭제 |
| 사용자 입력 문장 | 해석 캐시 **7일**, 미해결 질문 **30일** 뒤 삭제 | PC와 독립적으로 돌 `scripts/maintenance.py` 구현(2026-09-29). 예약 실행(Cloud Run Job·Scheduler)은 남음 |
| 스키마 변경 | 번호가 붙은 SQL 파일 + `schema_migrations` 적용 기록 표 | 완료. `storage/migrations/NNN_설명.sql`, 적용된 파일이 바뀌면 시작을 거부 |
| 별칭 조회 | `term_aliases` 표와 기본키 인덱스 | 완료. 마이그레이션 001 |
| DB 연결 | `psycopg_pool` 풀 + Cloud Run 동시성 제한 | 완료. `DB_POOL_SIZE`(기본 8)와 Cloud Run `--concurrency`를 같은 값으로 배포 |
| Spanner Graph | 제출 범위에서 제외 | 그래프 조회는 PostgreSQL `edges` 표로 동작. 코드는 유지 |
| 로그 | 표준 출력, Cloud Run에서는 JSON | 완료. `logging_setup.py`, `LOG_FORMAT`으로 형식 지정 |

## 구현 순서

1. 기존 `trend-project`가 `RUNNABLE`이고 콘솔에 남은 체험 일수가 표시되는지 확인합니다. 별도 앱 DB와 최소 권한 사용자를 준비하고, 런타임 service account에 `roles/cloudsql.client`를 부여합니다. 기존 로컬 데이터는 `scripts/migrate_sqlite_to_postgres.py` 또는 `pg_dump`로 옮깁니다. 스크립트는 빈 DB에 `--fresh --skip-user-data`로, `pg_dump`는 `--exclude-table-data=explain_cache --exclude-table-data=reader_prefs`로 이용자 문장과 계정별 설정을 뺍니다(리허설 결과는 [Plan 01](01-import-latest-trend-data.md)). 인스턴스나 DB 비밀번호를 Terraform에 다시 생성하거나 기록하지 않습니다.
2. `infra/gcp/main.tf`에 Trend용 service account, secret metadata, IAM을 추가하고 `terraform fmt -check`·`validate`·`plan`으로 확인합니다.
3. `scripts/deploy-trend.sh`를 만듭니다. 후보 revision 배포 → API health와 웹 첫 화면·인증 거부 확인 → 트래픽 전환 → `release_summary.py` 기록 순서를 relay 배포 스크립트와 같게 맞춥니다.
   API 서비스는 **`--concurrency`와 `DB_POOL_SIZE`를 같은 값(기본 8)으로** 배포하고 `--max-instances 2`로 둡니다. 두 값을 스크립트의 한 변수에서 함께 넘겨 따로 바뀌지 않게 합니다.
   Cloud SQL 연결 총량은 `max-instances × DB_POOL_SIZE`에 유지보수 작업과 로컬 게시 연결 수를 더해 인스턴스의 허용 연결 수보다 작게 설계합니다.
4. **전체 파이프라인 Job은 만들지 않습니다.** 로컬 파이프라인의 게시 방법과 중복 실행 방지는 Plan 06에서 구현합니다. 대신 해석 캐시 7일·미해결 질문 30일 보존 정리와 마지막 게시 시각 건강 점검을 PC 없이 실행하는 최소 권한 예약 작업을 설계·구현합니다. 예약 작업이 실행할 `scripts/maintenance.py`는 구현했습니다([구현 기록](#구현-기록)). Job·Scheduler·경보 연결이 남았습니다. 운영 로그에 사용자 원문·생성 결과를 남기지 않습니다.
5. `.github/workflows/release-gcp.yml`에 application job을 다시 추가하고, `scripts/release_scope.py`의 `app` 판정이 그 job을 켜도록 연결합니다. `scripts/release_recovery.py`의 `SECRETS`에 새 서비스를 추가합니다.
6. `infra/gcp/main.tf`의 uptime check 경로(`/health`), 로그 기반 오류 지표, 대시보드 필터를 새 서비스 이름으로 바꿉니다.
7. Trend 서비스가 정상 운영되면 이전 `builder-cup` 서비스를 삭제하고 `builder-cup-demo-key` secret과 관련 IAM을 Terraform에서 제거합니다.
8. [AI 호출 제어](../운영/AI-호출-제어.md)의 "운영 배포 뒤 조정 방법"과 [배포 복구](../운영/배포-복구.md)에 실제 명령을 채웁니다.
9. 데이터 게시 후 Git 밖의 제한된 위치에 `pg_dump` 사본을 남기고, 로컬 PostgreSQL 복원 검증 결과와 체험 종료 전 처리 결정을 기록합니다. 자동 백업·시점 복구는 이번 범위에 포함하지 않습니다.

## 완료 기준

- `release/gcp` push 한 번으로 Trend API·웹과 필수 유지보수 작업이 검증 후 배포되고, 이전 revision이 실패한 후보에 영향을 받지 않는다. 전체 파이프라인 Job은 배포되지 않는다.
- 웹 공개 URL에서 사전·지구본·메시지 해석이 실데이터로 열리고, API URL은 익명 호출을 거부한다.
- 서비스 재시작 뒤에도 사전·검수 기록이 Cloud SQL에 유지된다.
- 콘솔에서 체험 남은 일수를 확인하고, 게시 데이터의 `pg_dump` 사본을 로컬 PostgreSQL에 복원해 확인한다. 체험 종료 전 유료 전환·이전·종료 중 하나를 결정한다.
- PC가 꺼져도 마지막 성공 게시본을 읽을 수 있고, 갱신 시각·오래된 자료 상태가 표시된다. 보존 기간 정리와 건강 점검은 PC와 독립적으로 실행되며 경고가 Discord로 온다.
- API의 Cloud Run 동시성과 `DB_POOL_SIZE`가 같은 값으로 배포되어 있다.
- 새 revision이 시작할 때 `schema_migrations`에 없는 마이그레이션만 적용되고, 로그가 Cloud Logging에 JSON으로 남는다.
- `MODEL_REQUESTS_ENABLED=false`로 재배포하면 Gemini 호출이 0회가 되는 것을 로그 지표로 확인한다.
- 문서의 현재 상태와 검증 결과가 갱신되어 있다.

## 현재 상태와 남은 일 (2026-09-29 실측)

완료 기준 8개 중 충족한 것은 없고, 코드가 준비된 것이 일부 있다.

| 완료 기준 | 상태 | 근거 |
| --- | --- | --- |
| `release/gcp` 한 번으로 웹·API·유지보수 작업 배포 | 미충족 | `release-gcp.yml` 은 scope·checks·infrastructure·alert_relay job 뿐이다. `release_scope.py` 가 계산하는 `app` 출력을 읽는 job 이 없고 `scripts/deploy-trend.sh` 도 없다 |
| 웹 URL 실데이터·API 익명 거부 | 미충족 | `infra/gcp/main.tf` 에 Trend 서비스 계정·secret·서비스가 없고, 웹 서버가 Cloud Run ID 토큰을 붙이지 않는다(웹 서버 fetch 14곳에 Authorization 없음) |
| 재시작 뒤에도 Cloud SQL 에 유지 | 미충족 | 코드(`storage/db.py`, `DATABASE_URL`)는 준비. Terraform 에 `google_sql_database_instance` 가 없고 `sqladmin.googleapis.com` 이 API 목록에 없다 |
| PC 없이 게시본 읽기·정리·건강 점검·Discord 경고 | 미충족 | 보존 정리는 파이프라인 단계 `collect.retention` 안에만 있고, `scripts/health_check.py` 는 경고를 출력만 한다 |
| Cloud Run 동시성 = `DB_POOL_SIZE` | 미충족 | `DB_POOL_SIZE` 기본 8(`config.py`)만 있고 배포 스크립트가 `--concurrency` 를 넘기지 않는다 |
| 마이그레이션 적용·JSON 로그 | 일부 | `apply_migrations` 와 `logging_setup.py`(`K_SERVICE` 가 있으면 JSON)는 있고 테스트가 있으나 Cloud Run 에서 검증하지 않았다 |
| `MODEL_REQUESTS_ENABLED=false` 로 호출 0회 확인 | 미충족 | 차단 게이트(`model_client.py`)는 있으나 호출마다 남기는 로그 이벤트와 Trend 용 로그 지표가 없다 |
| 문서 갱신 | 미충족 | [AI 호출 제어](../운영/AI-호출-제어.md) 의 실제 명령은 배포 뒤 채우기로 남아 있고, [배포 복구](../운영/배포-복구.md) 는 builder-cup 과 알림 중계기만 다룬다 |

남은 일(구현 순서 1~9 와 같은 순서, 아래는 실측으로 보탠 구체 항목):

1. Cloud SQL Terraform(인스턴스·DB, 명시한 에디션·사양, 백업·PITR, `deletion_protection`), `sqladmin.googleapis.com` 활성화, 서비스 계정 `roles/cloudsql.client`. 지금 인스턴스는 콘솔에서 만든 것이라 Terraform 과 어긋난다([Plan 13](13-cloud-sql-trial-to-paid-transition.md)).
2. Trend 서비스 계정(웹·API·유지보수)과 secret 메타데이터(`trend-database-url`·`trend-frontend-api-token`·`trend-session-secret`·`trend-accounts`), 서비스 계정별 `secretAccessor`. secret 값은 Terraform 상태에 넣지 않고 부트스트랩이 만든다.
3. 웹 서버 전용 헬퍼 하나로 메타데이터 서버에서 Cloud Run ID 토큰을 받아(audience = `TREND_API_URL`, 약 55분 캐시, Cloud Run 밖에서는 아무것도 안 함) fetch 14곳에 붙인다.
4. `scripts/deploy-trend.sh`: 후보 revision `--no-traffic --tag=candidate`, API `--no-allow-unauthenticated`·`--concurrency` 와 `DB_POOL_SIZE` 를 한 변수로·`--max-instances 2`·`--add-cloudsql-instances`. `release-gcp.yml` 에 application job 추가, `release_recovery.py` 를 Trend 서비스용으로 일반화.
5. PC 독립 유지보수 작업(`apps/trend-api/scripts/maintenance.py`): `prune_user_text` 실행, 마지막 성공 갱신의 나이 확인, 사용자 원문 없는 JSON 로그 한 줄. 임계값은 12시간 이상(`health_check` 의 8시간과 다르게).
6. 호출마다 `gemini_call` 구조화 로그(모델·장부·결과, 내용 없음)와 로그 기반 지표.
7. 감시를 Trend 서비스로 옮긴다: 가동 확인은 Trend 웹 URL(웹에는 `/api/health` 경로가 없다 — `app/api` 는 auth·chat·explain·generate·prefs·recommend·review 뿐), 오류 지표는 Cloud Run 요청 로그(`httpRequest.status>=500`)로.
8. 다중 인스턴스 대비: `apply_migrations` 에 `pg_advisory_xact_lock`, 마이그레이션은 expand-only, 풀에 `check=ConnectionPool.check_connection`.
9. **사용자/팀 결정 대기:** Cloud SQL 사양·에디션·버전·네트워크(공개 IP + Auth Proxy 만, 또는 비공개 IP + VPC), 월 비용 수용과 지출 상한(기존 상한은 Vertex AI·Gemini API 만 덮는다).
10. **사용자 확인 뒤(제출 직전) 실행:** `terraform apply`·부트스트랩, 원작자 서버 `trend.db` 를 Auth Proxy 로 Cloud SQL 에 초기 적재([Plan 01](01-import-latest-trend-data.md) 선행), 첫 `release/gcp` push, 익명 403·재시작 유지 확인, Trend 가 서비스되면 `builder-cup` 서비스·`builder-cup-demo-key` secret·IAM 정리, 운영 문서의 실제 명령·검증 결과 기록.

## 구현 기록

### 2026-09-29 유지보수 작업과 운영 신호 (`feat/ops-signals`)

- **`apps/trend-api/scripts/maintenance.py`.** 해석 캐시 7일·미해결 질문 30일 정리(`prune_user_text`)와 마지막 정상 게시 점검을 한 번 하고
  이벤트 한 줄(`event=maintenance`: 지운 건수·게시 시각·경과 시간·오류 종류)을 남긴다. 종료 코드는 0 정상, 1 정리·점검 실패, 2 게시본이 오래됨.
  표를 만들거나 마이그레이션하지 않으므로 DB 역할에는 `explain_cache`·`lookups`의 SELECT·DELETE와 `pipeline_runs`의 SELECT만 주면 된다.
  로컬 Compose PostgreSQL에서 그 권한만 가진 역할로 실행해 확인했다(수집 기록만 → 2, 게시 1시간 전 → 0, 틀린 비밀번호 → 1이며 로그에는 `OperationalError`만).
  같은 역할로 `db.connect()`를 부르면 `permission denied for schema public`으로 실패한다. 오래됨은 다시 돌려도 풀리지 않으므로 Job 재시도는 0으로 둔다.
- **게시 신선도.** `/meta`의 `last_run`은 이제 지도(`board`)·대시보드(`dashboard`) 게시가 모두 성공한 마지막 때이고 `stale`은 그게 12시간보다 오래됐는지다.
  전에는 어느 단계든 끝난 때(0건·건너뜀 포함)였다. 원작자 서버 `trend.db`(읽기 전용 조회)에서 잰 값:
  - 09-17~09-28 밤마다 23:2x 게시 → 다음 날 09:2x 게시 간격이 10.0~10.5시간이다. 8시간 한계(`health_check.py`)는 매일 밤 울리고 12시간은 울리지 않는다.
  - 09-28 19:33·23:33(한국 시각) 지도 단계가 `KeyError: 'namu_rank'`로 실패해 지도가 14:27 것으로 19.1시간 남았다. 그동안 옛 계산은 23:33:06을 냈고,
    새 계산은 14:27을 내며 09-29 02:27에 `stale`이 된다.
  - 화면(사전·최근 변화의 '갱신' 시각, 관리 화면 머리의 '마지막 실행')은 코드 변경 없이 새 `last_run`을 보인다. `stale` 표시는 프론트 결정 뒤에 붙인다.
- **Gemini 호출 이벤트.** `pipeline/gemini.py`가 Vertex에 요청을 보낼 때마다 `event=gemini_call`(`model`·`ledger`·`outcome`·`code`) 한 줄을 남긴다.
  Cloud Run 서비스와 Job은 JSON 로그라 `jsonPayload.event="gemini_call"`로 로그 기반 지표를 만들 수 있다([AI 호출 제어](../운영/AI-호출-제어.md)).
  호출이 꺼져 있으면(`MODEL_REQUESTS_ENABLED=false`) 장부를 깎기 전에 끝나 이벤트가 0이다. 전에는 보내지 않은 요청이 호출마다 장부를 1씩 깎았다(시험에서 36→35, 12→11).
- **보존 기간 실측.** 원작자 서버 `trend.db`에는 사용자 문장 정리가 없어 해석 캐시 66건 중 59건이 7일을 넘겼다(가장 오래된 것 09-14, 미해결 질문은 0건).
  그 서버에 이 정리를 옮기면 첫 실행에서 지워진다.
- 남은 일: Job·Scheduler와 실패 경보(Discord), `gemini_call` 로그 지표, 배포 뒤 `MODEL_REQUESTS_ENABLED=false`에서 0회 확인은 인프라 작업에서 한다.
