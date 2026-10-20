# 10-20 Cloud SQL 체험 종료 전 전환 – 작은 새 인스턴스로 이전

실행일 **2026-10-20 오전**(체험 종료 10-30경) · 담당 **shji(지시현)** · 상태 **DB·서비스 전환 완료·보관, 청구 확인·게시 경보는 후속** · 다음 [10-27 청구 확인](../2026-10-27-billing-check.md)

[계획 목록](../README.md) · [GCP 운영](../../운영/GCP-운영.md) · 경위·비용 비교 [옛 Plan 13](13-cloud-sql-trial-to-paid-transition.md)

`trend-project`는 무료 체험 인스턴스다(종료 10-30경, 10-10 콘솔 확인). 만료 전에 업그레이드하지 않으면 요청 처리를 멈춘다. 자동 유료 전환 설정은 없고 콘솔의 **지금 업그레이드**로 사람이 실행한다. 비용 비교와 대안은 [옛 Plan 13](13-cloud-sql-trial-to-paid-transition.md#비용과-서비스-연속성-비교)에 있다.

## 10-16 결정

- **경로 B – 작은 새 인스턴스를 만들어 운영 DB를 옮긴다.** 지금 인스턴스를 그대로 유료로 바꾸는 A(8 vCPU·64GB Enterprise Plus, 월 수백 달러)와, 바꾼 뒤 그 자리에서 줄이는 C(디스크 100GB가 줄지 않아 +월 $22)는 하지 않는다.
- **크기는 `db-g1-small`**(공유 코어, RAM 1.7GB), PostgreSQL 18, Enterprise 등급, 단일 영역 `asia-northeast1`, SSD 10GB(자동 증가 켬), 삭제 보호 켬.
- **옮기는 것은 운영 DB(`trend_20261014`) 하나.** 이전 DB(`trend`·`trend_20261005`·`trend_20261009`)는 `pg_dump` 사본을 Git 밖(`artifacts/backups/`)에 두고 옮기지 않는다.
- **날짜는 10-20 밤.** 제출물은 PPT·영상이고 심사위원은 11월에 사이트를 본다. 녹화(10-17까지)가 끝난 뒤, 심사 전이라 보는 사람이 거의 없는 때에 한다. 몇 분 끊김이 있다.

**비용(도쿄, Cloud Billing Catalog API 단가, 10-16 조회).**

| 항목 | 단가 | 한 달(730시간) |
| --- | --- | --- |
| `db-g1-small` | $0.046/시간 | 약 $34 |
| `db-f1-micro`(대안) | $0.014/시간 | 약 $10 |
| SSD | $0.221/GB·월 | 10GB 약 $2.2 |
| 백업 | $0.104/GB·월 | 1GB 미만이라 $0.1 안팎 |

small이면 한 달 약 $36, 결선(12-04)까지 약 $55. 옛 체험 인스턴스는 10-30까지 무료라 옮기는 동안 함께 둬도 요금이 없다. 새 인스턴스가 검증되면 옛 인스턴스를 지운다(10-27 청구 확인 때).

**10-19 비용 결정(지시현).** 월 $30은 상한이 아니다. 월 약 $36인 `db-g1-small` 비용을 수용하고 심사 기간의 운영 안정성을 우선한다. 비용 절감만을 위해 `db-f1-micro`로 시작하지 않는다. 다만 `db-g1-small`도 공유 코어로 SLA 대상이 아니므로, 전환 직후 응답 시간·메모리·연결 수와 Job 실행을 확인하고 부족하면 더 큰 인스턴스를 별도 결정한다.

## 10-20 실행 순서

실행 전에 새 인스턴스의 자동 백업·PITR 사용 여부와 예상 비용을 확정한다. 기존 [#15 일정](https://github.com/Sihyeon-Ji/trend-interpreter/issues/15)의 미결정 항목이다.

1. 새 인스턴스 만들기(위 사양). Terraform `infra/gcp/hybrid`의 `sql_connection_name`을 새 인스턴스로 바꿀 준비.
2. 지금 운영 DB 백업: `pg_dump` 사본을 `artifacts/backups/`에 두고 로컬 복원으로 확인.
3. 새 인스턴스에 DB·역할 만들기: `trend_app`(소유자)과 게시 역할 `trend_publisher`(`configure_publisher_role.py --role trend_publisher`, `GRANT CONNECT`).
4. 덤프를 새 인스턴스에 복원하고, 운영과 표 행 수를 대조한다(`refresh_production.py compare`와 같은 기준 – 사람 결정·기록 누락 0).
5. Secret Manager에 새 연결 주소 version 추가: `trend-production-database-url`, `trend-production-publisher-database`.
6. API(Cloud Run v2 REST로 secret 버전·Cloud SQL 연결 바꾸기), 백업·유지보수·게시 Job을 새 secret·인스턴스로. Terraform과 운영을 맞춘다(`TF_DATA_DIR=.terraform/production`).
7. 확인: 웹 첫 화면·사전·둘러보기·만들기 200, API health, 검수 로그인, 백업·유지보수 Job 한 번 실행 성공. 응답 시간·메모리·DB 연결 수를 함께 기록한다.
8. 문제가 있으면 secret 버전을 이전 것으로 되돌려 옛 인스턴스로 돌아간다(옛 인스턴스는 10-30까지 그대로).

## 10-20 실행 기록

- 새 인스턴스 `trend-production-sql`을 PostgreSQL 18, Enterprise `db-g1-small`, 도쿄 단일 영역, SSD 10GB·자동 증가·삭제 보호로 만들었다. 자동 백업 7개와 PITR 로그 7일을 켰다. 운영 DB가 1GB 미만이라 백업 저장비는 소액으로 예상하며, 새 Enterprise 인스턴스의 Cloud Storage PITR 로그 보관에는 [인스턴스별 추가 요금이 없다](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/restore). 실제 청구액은 10-27에 확인한다.
- 옛 인스턴스의 DB 네 개를 각각 권한 600의 custom dump로 떠서 확인했다. 새 인스턴스에는 `trend_20261014`만 옮겼다. 운영 덤프를 로컬 PostgreSQL 18에 복원했고, 새 DB의 59개 표·1,365,134행은 원본과 일치했다. 사람 결정·게시·Gemini 장부 대조와 전환 직전 재대조에서 누락은 0건이었다. 이후 사용자 요청으로 운영 덤프와 과거 복원용 로컬 덤프를 삭제했다. 이전 DB 세 개의 덤프는 `artifacts/backups/cloud-sql-transition-20261020/`에 남아 있으며, 옛 인스턴스 삭제 후 이 DB들의 마지막 확인된 사본이다.
- 새 인스턴스에 `trend_app`과 제한된 `trend_publisher`를 만들고 게시 역할 검사를 통과했다. 임시 관리 계정은 삭제했다. Secret Manager의 운영 DB URL은 버전 5, 게시 DB URL은 버전 3으로 추가했다. 운영 API와 백업·유지보수·게시 Job은 모두 새 인스턴스와 해당 버전을 가리킨다. API 트래픽은 `trend-production-api-sql-20261020` revision에 100%다.
- 백업 Job을 실행해 성공했고, 생성된 GCS dump를 별도 PostgreSQL에 복원해 59개 표·1,365,134행·마이그레이션 27개를 확인했다. 복원 전에 생성된 자동 백업과 별도로, 복원 후 Cloud SQL 온디맨드 백업을 생성해 `SUCCESSFUL`을 확인했다. API health·보드·간결한 사전 응답과 웹 첫 화면·사전·둘러보기·만들기·로그인 화면은 200이었다. 첫 사전 화면은 약 20초, 재요청은 약 2.7초였다. 생성·복원·전환 중 관측한 20분간 Cloud SQL CPU 사용률 최대 51%, 메모리 사용률 최대 53%, 연결 최대 6개였다.
- 유지보수 Job은 DB에 연결해 보존 작업을 실행했으나 마지막 게시가 10-11이라 게시 경과 211.5시간이 설정된 192시간 한도를 넘어 의도대로 exit 2를 반환했다. 새 게시 또는 경보 기준의 별도 운영 판단이 필요하다. 이후 사용자 화면에서 `copybara` 검수 계정의 운영 `/admin` 로그인과 검수 목록 표시를 확인했다.
- 점검 중 지원하지 않는 `/terms?limit=1`을 두 번 호출했다. API 내부는 전체 응답을 200으로 만들었지만 Cloud Run이 응답 크기 초과로 외부에 500을 반환해 5xx 경보가 왔다. Cloud Monitoring의 해당 두 분 각 1건 외에 웹 5xx와 후속 분의 5xx는 없었다. 실제 사전 화면이 쓰는 `/terms?slim=true`는 200이었다.
- `docker compose run --rm --build check`와 `docker compose run --rm --build e2e`가 통과했고, production Terraform 전체 plan은 변경 0건이다. `production.tfvars.json`과 Secret Manager의 `trend-terraform-vars` 버전 7을 실제 배포 상태로 맞췄다. 이후 사용자가 옛 `trend-project`를 삭제했고, 재확인한 인스턴스 목록에는 `trend-production-sql`만 남았다. 옛 인스턴스로 트래픽을 되돌릴 수 없으며, 운영 복구에는 새 인스턴스의 Cloud SQL 백업·PITR 또는 GCS dump를 사용한다. 이전 secret 버전은 아직 남아 있다.

## 10-10 확인

- 인스턴스 `trend-project`: PostgreSQL 18, Enterprise Plus `db-perf-optimized-N-8`, SSD 100GB(자동 증가 꺼짐), 단일 영역, 백업 꺼짐, 삭제 보호 꺼짐. 생성 09-29. 콘솔 표시 '무료 체험 기간이 20일 후에 종료'(10-10 확인) – **10-30경 끝난다.** API에는 만료 시각이 나오지 않는다.
- DB 크기: `trend_20261009`(운영) 404MB, `trend_20261005` 323MB, `trend` 283MB. 셋을 합쳐도 1GB가 안 된다. 연결은 16개(최대 800).
- 실제 사용량에 비해 사양이 매우 크다(체험용 기본값). 유료 전환보다 작은 인스턴스(공유 코어 소형·월 상한 약 $30, [Plan 17 실행 기록](17-hybrid-infrastructure-실행기록.md)의 사용자 결정)로 옮기는 쪽이 맞다. 옮길 때 지금 운영 DB 하나만 옮기고, 이전 DB들은 `pg_dump` 사본을 Git 밖에 둔 뒤 지운다.

## 처음 세운 절차(참고)

1. 10-20~22: 콘솔의 정확한 만료 시각, DB 크기·연결 수·부하를 확인하고 견적을 다시 만든다.
2. 10-24까지: 월 비용 상한과 경로(유료 전환 또는 작은 인스턴스로 이전)를 정한다. `pg_dump` 사본을 Git 밖에 두고 복원을 확인한다.
3. 10-26까지: 실행하고 API·웹·DB 연결, 게시·백업 Job을 확인한다. 새 인스턴스로 옮기면 [10-16 운영 DB 갱신](2026-10-16-final-db-refresh.md)의 전환 절차와 게시 역할 준비를 그대로 거친다.

만료 전 전환을 확인할 때까지 종료 알림을 일정에서 지우지 않는다. 미리 할 수 있는 것: 콘솔의 정확한 만료 시각 확인은 지금도 된다.
