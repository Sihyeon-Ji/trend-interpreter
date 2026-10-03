# Trend Cloud Run 웹·API 준비

## 코드 상태

`infra/gcp/hybrid`의 `services=null`이 기본값이다. 이 상태에서는 웹·API Cloud Run 서비스를 만들지 않는다. `enabled=true`와 승인된 `services` 입력이 모두 있을 때만 서비스를 정의한다. 지금은 Terraform mock plan만 실행했으며 GCP 자원이나 IAM은 변경하지 않았다.

| 서비스 | Terraform 설정 | 확인할 것 |
| --- | --- | --- |
| API | IAM invoker 검사 필수, `allUsers` 바인딩 없음, API SA 사용 | 익명 요청 401/403, 웹 SA 허용 |
| 웹 | 공개 Cloud Run, 별도 웹 SA, 해당 API에만 `roles/run.invoker` | staging 웹의 production API 거부 |
| API 네트워크 | API /26 서브넷의 Direct VPC egress, private range만 VPC 경유 | 예약 GPU IP의 TLS 8443 연결 |
| API DB | 기존 Cloud SQL 인스턴스의 `/cloudsql` 소켓 mount, `DATABASE_URL` Secret Manager version | PostgreSQL staging 이관·역할·복원 |
| 실행 한도 | 웹·API 각각 min 0/max 2 인스턴스, API 동시 요청 8 | 실제 연결 수·지연·호출 예산 |

웹의 `DATA_MODE=api`, `TREND_API_AUTH=google-id-token`과 API URL은 서비스 설정으로 연결한다. Google ID token을 사용하는 웹 코드는 [웹 API 인증](Cloud-Run-웹-API-인증.md)에 있다. API는 기본 `MODEL_PROVIDER=mock`, `MODEL_REQUESTS_ENABLED=false`로 시작한다. 기존 운영 `builder-cup`을 대체하거나 release job을 활성화하지 않는다.

서비스를 만들기 전에 두 서비스의 자동 Cloud Run request log URL을 `_Default` sink에서 제외하도록 정의했다. URL에는 검색어 등이 포함될 수 있다. API의 Uvicorn access log도 끈다. 기존 `builder-cup` 로그는 이 필터에 포함하지 않는다. [Cloud Run 로깅 안내](https://docs.cloud.google.com/run/docs/logging)에 따라 실제 `_Default`와 추가 사용자 정의 sink를 확인해야 한다. 요청 수·상태 감시는 URL을 저장하지 않는 지표로 구성해야 한다.

## 필요한 고정 입력

`services`에는 웹·API의 Artifact Registry image digest, 기존 Cloud SQL connection name, 숫자로 고정된 `DATABASE_URL`·`ACCOUNTS`·`FRONTEND_API_TOKEN`·`SESSION_SECRET` 버전이 필요하다. Image는 같은 프로젝트·지역의 기존 `builder-cup` repository에서, Cloud SQL connection name도 같은 프로젝트·지역에서 가져온다. Secret 이름은 같은 프로젝트의 `trend-staging-*` 또는 `trend-production-*`로 분리한다. Terraform은 secret의 **이름과 버전만** 보관한다. 값은 state에 넣지 않는다. 웹 SA는 frontend token·session secret에, API SA는 DB URL·계정·frontend token에만 접근하도록 바인딩한다.

감사관 GPU 호출을 켜려면 `services.gpu`에 고정 모델 이름·Ollama manifest digest·VM release SHA-256·CA 전용 Secret Manager version을 입력한다. VM의 release SHA-256이 다르면 API 배포 계획을 거부한다. API는 그때만 gateway token과 CA를 주입받는다. CA secret에는 PEM 신뢰 인증서만 담고, GPU의 TLS 개인키 secret과 분리한다. `GPU_GATEWAY_REQUESTS_ENABLED`는 이 선택에 따라 설정된다. vision·tool·stream 작업은 gateway에서 거부하며 감사관 후보를 추천·카피 생성에 재사용하지 않는다.

설정 예시의 이미지 digest·secret version을 임의 값으로 채워 apply하지 않는다. 현재 승인된 모델 release, 서비스 이미지 digest, Secret Manager 값과 Cloud SQL staging 연결 문자열은 아직 준비되지 않았다.

## 적용 전 검증

1. 기존 root가 관리하는 Cloud Run API와 기존 Cloud SQL Admin API가 활성인지 확인한다. Plan 13의 Cloud SQL 보호·백업·PITR·staging 이관과 복원을 확인한다. 로컬 복원 리허설 결과와 보호 설정·staging 연결안은 [Cloud SQL 복원 리허설](Cloud-SQL-복원-리허설.md)에 있다. 현재 기존 인스턴스는 공개 IP이고 보호 설정이 완료되지 않았다. Cloud Run의 Cloud SQL connector는 기존 인스턴스만 참조한다. [공식 Cloud SQL 연결](https://docs.cloud.google.com/sql/docs/postgres/connect-run)을 기준으로 실제 소켓 접속을 검증한다.
2. 환경별 Terraform 원격 state·비용 상한·배포 이미지 digest·Secret Manager numeric version·IAM 권한을 검토한다. 공개 웹은 API invoker 바인딩 후에만 활성화되도록 의존성을 지정했다.
3. staging에서 웹 SA의 API 호출, 익명 API 차단, staging→production 거부, DB 읽기·검수 쓰기·사진 업로드·질문 스트림·취소를 실행한다. [공식 서비스 간 인증](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)의 audience를 사용한다.
4. GPU 실행이 승인됐을 때만 [VM 배포 계약](GPU-VM-배포-계약.md)의 image·모델·TLS·자동 중지를 검증한다. 브라우저 요청을 끊어도 동기 API worker의 이미 시작된 모델 호출이 즉시 취소된다고 보장하지 않는다.

실제 GCP 접속·Gemini 호출·GPU 품질·운영 비용은 이번 mock plan으로 입증되지 않는다. Plan 05 조건을 채우기 전까지 Trend 배포 job은 비활성이다.

## 로컬 검사

```bash
docker compose run --rm --build check
docker compose run --rm --build e2e
docker compose run --rm infra-check
```

`infra-check`는 기존 root와 새 root의 fmt/validate, 비활성·staging/production·GPU·웹/API·잘못된 GPU release 시나리오를 검사한다. 이 검사는 리소스를 생성하지 않는다.

## 2026-10-03 staging 배포

사용자 결정에 따라 staging만 Terraform으로 직접 배포했다. production은 계속 `release/gcp` 경로로만 배포하며, 그 job은 아직 꺼져 있다. 웹은 주소를 아는 사람만 들어오는 공개 상태이고 검수 기능은 로그인으로 보호한다. GPU는 연결하지 않았다(`services.gpu=null`, API는 `MODEL_PROVIDER=mock`).

| 항목 | 값 |
| --- | --- |
| 웹 | `https://trend-staging-web-7jftqxfz3q-an.a.run.app` |
| API | `https://trend-staging-api-7jftqxfz3q-an.a.run.app` (IAM 인증 필수) |
| 이미지 | `trend-api@sha256:9c279a4a…`, `trend-web@sha256:adbc4c38…` (`a3cb2bd`·`c499d6b` 기준) |
| DB | 체험 인스턴스의 `trend_staging`, `trend-staging-database-url` version 2 |
| secret | `trend-staging-accounts` 1(검수 계정 1개), `trend-staging-frontend-token` 1, `trend-staging-session-secret` 1 |

입력값은 로컬 `infra/gcp/hybrid/staging.tfvars.json`(Git 제외)에 있으며 위 값으로 다시 만들 수 있다. 적용 결과는 생성 12개였다.

웹 이미지는 Apple Silicon의 amd64 에뮬레이션에서 Next.js 빌드가 exit 139로 죽어 Cloud Build로 만들었다. 기본 Compute 계정으로는 빌드 생성이 거부돼, 로그 쓰기·`builder-cup` push·소스 버킷 읽기만 가진 `trend-cloud-build` SA를 지정했다.

검수 계정은 사용자가 직접 만들었다. 비밀번호를 터미널에서 입력받아 PBKDF2 해시만 secret에 넣는 일회성 명령을 썼다. 로컬 개발용 `set_account.py`는 `.env`·`.env.local`을 고치므로 쓰지 않았다.

| 확인 | 결과 |
| --- | --- |
| API 익명 요청 | `/health`·`/terms` 403 |
| API 인증 호출 | `/health` 200, 표제어 11,244개 |
| 잘못된 비밀번호 로그인 | 401 |
| 웹 → API → DB | `/briefing` 200, API 대시보드 표제어 14개가 화면에 표시, sample 표시 없음 |
| 웹 화면 | `/`·`/map`·`/updates`·`/graph`·`/check`·`/login` 200, `/trends` 307 |
| 관리자 화면 | `/admin` 비로그인 시 `/login?next=/admin`으로 이동 |
| URL 로그 제외 | 규칙 반영까지 몇 분 걸렸고, 이후 새 요청의 URL 로그는 저장되지 않음 |

남은 문제는 다음과 같다.

- `/dictionary` 504와 검수 목록 멈춤은 해결했다(아래 '목록 응답 시간 수정').
- API의 `/review/queue`·`/review/stats` 읽기에는 앱 수준 인증이 없다(기존 설계). API가 IAM으로 막혀 웹 SA와 관리자만 부를 수 있고, 쓰기는 검수 token이 필요하다. 공개 범위를 넓히기 전에 다시 검토한다.
- 로그인과 검수 권한은 사용자가 `copybara` 계정으로 확인했다(결정자 이름 표시).

### 목록 응답 시간 수정

배포 후 사전 화면이 504로 실패하고 검수 목록(1,599건)이 "불러오는 중"에서 멈췄다. 원인은 두 가지였다.

1. **표제어마다 DB를 따로 조회했다.** 표제어 하나를 만들 때 뜻·번역·사용층·주간 추이·근거·미디어·지역 등 8~9번 조회해 1만여 개에서 약 10만 번 왕복했다. 로컬 DB에서는 빨랐지만 Cloud SQL은 조회마다 네트워크 왕복이 붙는다. 목록을 만드는 동안만 표마다 한 번에 읽어 두는 `dictionary_store.batched`를 추가했다(`4299126`). 표제어별 함수와 호출부는 그대로이고, 블록 밖의 읽기와 쓰기는 영향이 없다. 결과가 표제어별 조회와 같고 조회 수가 표제어 수와 무관한지 테스트로 확인한다.
2. **응답이 Cloud Run 한도에 걸렸다.** 공개 사전 전체가 29MB, 관리자용 전체 목록은 32MiB 한도를 넘어 500이었다. API에 gzip 압축을 추가했다(`407c59e`). 질문 스트리밍(`text/event-stream`)은 Starlette 기본값대로 압축하지 않는다.

| 경로 | 수정 전 | 수정 후 |
| --- | --- | --- |
| API `/terms`(7,654개) | 90초 초과 504 | 8.2초, 전송 6.7MB |
| API `/terms?status=all`(11,120개) | 90초 초과 | 10.5초, 전송 10.2MB |
| API `/review/queue`(1,599건) | 응답 없음 | 1.8초, 전송 0.76MB |
| 웹 `/dictionary` | 504 | 첫 요청 9.7초, 웹 캐시 후 1.1초 |

현재 staging API 이미지는 `trend-api@sha256:5dce9697…`(`407c59e`)다. 사전 전체를 한 번에 내려보내는 구조라 첫 요청은 여전히 10초 안팎이다. 표제어가 더 늘면 페이지 단위 조회를 검토한다.

