# Plan 03. Trend 앱 Cloud Run 배포

작성일 **2026-09-28** · 상태 **설계 대기(영속 저장소 결정 필요)** · 선행 작업 **로컬 통합 완료**

[계획 목록](README.md) · [아키텍처](../운영/시스템-아키텍처.md) · [AI 호출 제어](../운영/AI-호출-제어.md) · [GCP 운영](../운영/GCP-운영.md)

## 배경

`prototype/trend`를 메인 앱으로 확정해 `apps/trend-api`와 `apps/trend-web`으로 옮겼습니다. 로컬 Compose,
CI 검사, 배포 이미지 빌드와 smoke 검사까지 통과했지만 **GCP 배포는 일부러 열지 않았습니다.**
`release/gcp`의 application job은 제거했고 `scripts/release_scope.py`는 Trend 변경을 공통 검사로만 보냅니다.
이전 실습 앱의 `builder-cup` Cloud Run 서비스는 Trend 릴리스가 대체할 때까지 그대로 둡니다.

배포를 열지 않은 이유는 두 가지입니다.

1. Trend API는 SQLite(`data/trend.db`)에 사전·수집 데이터·검수 기록을 저장합니다. Cloud Run 인스턴스의
   파일시스템은 재시작·스케일 아웃 시 사라지므로 그대로 배포하면 데이터가 유실됩니다.
2. Trend는 화면과 API가 별도 서비스입니다. API는 외부에 공개하지 않고 웹 서버 라우트만 호출하는 경로가 필요합니다.

## 이미 준비된 것

| 항목 | 상태 |
| --- | --- |
| Gemini 호출 경로 | `model_client.py`에서 Vertex AI + 런타임 service account. API key 없음. 런타임 계정에 `roles/aiplatform.user` 부여됨 |
| 호출 차단 | `MODEL_PROVIDER=vertex`와 `MODEL_REQUESTS_ENABLED=true`가 모두 켜져야 호출. 하루 예산 `GEMINI_DAILY_BUDGET` |
| 배포 이미지 | `apps/trend-api/Dockerfile`(uvicorn, 비root, 8080), `apps/trend-web/Dockerfile`(Next.js standalone, 8080) |
| 이미지 검증 | CI가 두 이미지를 빌드하고 `scripts/container-smoke.sh`로 health·첫 화면 확인 |
| 웹 설정 | `DATA_MODE`, `TREND_API_URL`, `FRONTEND_API_TOKEN`, `SESSION_SECRET`은 런타임 환경변수. 빌드 시 박히지 않음 |
| 인프라 | Artifact Registry, 런타임·배포 service account, Workload Identity, 모니터링·알림·예산이 Terraform에 있음 |

## 결정할 것

### 1. 영속 저장소

| 후보 | 장점 | 부담 |
| --- | --- | --- |
| Cloud SQL PostgreSQL | SQL 그대로 이식, 트랜잭션·백업 표준 | `sqlite_store.py`·`dictionary_store.py`의 SQLite 전용 문법 이식, 최소 instance 비용 |
| Firestore | 서버리스, 비용 0에서 시작 | 저장소 계층 재작성, 집계 쿼리 제한 |
| Spanner Graph(사전) + BigQuery(시계열) | [방향 문서](../트렌드/방향.md)의 원래 설계, 무료 체험 90일 | 두 저장소 동시 이식, 체험 종료 후 비용 |

결정 기준은 제출까지 남은 기간과 팀의 SQL 익숙함입니다. 어느 쪽이든 저장소 접근은 `storage/` 아래 한 계층으로
모아 두었으므로 파이프라인·API 코드는 바뀌지 않아야 합니다.

### 2. 서비스 구성

| 서비스 | 공개 범위 | 역할 |
| --- | --- | --- |
| `builder-cup-trend-web` | public invoker | Next.js 화면과 서버 라우트 |
| `builder-cup-trend-api` | private (웹 서비스 계정만 invoker) | FastAPI 읽기 API와 검수 기록 |
| `builder-cup-trend-pipeline` | Cloud Run Job | `scripts/run_pipeline.py`를 Cloud Scheduler로 6시간마다 실행 |

웹 서버 라우트는 `TREND_API_URL`로 API를 부르고 Cloud Run ID token을 붙입니다. `FRONTEND_API_TOKEN`은 API가
쓰기 요청을 받을 때 추가로 확인하는 값으로 유지합니다.

### 3. Secret Manager 항목

값은 Terraform state에 넣지 않고 bootstrap에서 넣습니다. 이름은 다음 규칙으로 만듭니다.

| Secret | 사용하는 서비스 | 환경변수 |
| --- | --- | --- |
| `trend-frontend-api-token` | web, api | `FRONTEND_API_TOKEN` |
| `trend-session-secret` | web | `SESSION_SECRET` |
| `trend-accounts` | api | `ACCOUNTS` (PBKDF2 해시 JSON) |
| `trend-youtube-api-key` | api, pipeline | `YOUTUBE_API_KEY` |
| `trend-naver-client-id`, `trend-naver-client-secret` | api, pipeline | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |

Gemini는 secret이 필요 없습니다. Reddit·Bluesky 키는 수집기를 쓰기로 정할 때 추가합니다. 각 secret은
읽는 서비스 계정에만 `secretmanager.secretAccessor`를 부여하고, 배포 스크립트는 숫자 version을 고정해 참조합니다.

## 구현 순서

1. 영속 저장소를 정하고 `storage/`를 이식한 뒤 `docker compose run --rm --build check`와 파이프라인 한 바퀴를 로컬에서 통과시킵니다.
2. `infra/gcp/main.tf`에 Trend용 service account, secret metadata, IAM을 추가하고 `terraform fmt -check`·`validate`·`plan`으로 확인합니다.
3. `scripts/deploy-trend.sh`를 만듭니다. 후보 revision 배포 → API health와 웹 첫 화면·인증 거부 확인 → 트래픽 전환 → `release_summary.py` 기록 순서를 relay 배포 스크립트와 같게 맞춥니다.
4. `.github/workflows/release-gcp.yml`에 application job을 다시 추가하고, `scripts/release_scope.py`의 `app` 판정이 그 job을 켜도록 연결합니다. `scripts/release_recovery.py`의 `SECRETS`에 새 서비스를 추가합니다.
5. `infra/gcp/main.tf`의 uptime check 경로(`/health`), 로그 기반 오류 지표, 대시보드 필터를 새 서비스 이름으로 바꿉니다.
6. Trend 서비스가 정상 운영되면 이전 `builder-cup` 서비스를 삭제하고 `builder-cup-demo-key` secret과 관련 IAM을 Terraform에서 제거합니다.
7. [AI 호출 제어](../운영/AI-호출-제어.md)의 "운영 배포 뒤 조정 방법"과 [배포 복구](../운영/배포-복구.md)에 실제 명령을 채웁니다.

## 완료 기준

- `release/gcp` push 한 번으로 Trend API·웹·파이프라인 Job이 검증 후 배포되고, 이전 revision이 실패한 후보에 영향을 받지 않는다.
- 웹 공개 URL에서 사전·지구본·메시지 해석이 실데이터로 열리고, API URL은 익명 호출을 거부한다.
- 서비스 재시작 뒤에도 사전·검수 기록이 유지된다.
- `MODEL_REQUESTS_ENABLED=false`로 재배포하면 Gemini 호출이 0회가 되는 것을 로그 지표로 확인한다.
- 문서의 현재 상태와 검증 결과가 갱신되어 있다.
