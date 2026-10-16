# 10-20 Cloud SQL 체험 종료 전 전환 – 작은 새 인스턴스로 이전

실행일 **2026-10-20 밤**(늦어도 10-26, 체험 종료 10-30경) · 담당 **shji(지시현)** · 상태 **결정 완료(10-16) – 10-20에 실행** · 다음 [10-27 청구 확인](2026-10-27-billing-check.md)

[계획 목록](README.md) · [GCP 운영](../운영/GCP-운영.md) · 경위·비용 비교 [옛 Plan 13](archive/13-cloud-sql-trial-to-paid-transition.md)

`trend-project`는 무료 체험 인스턴스다(종료 10-30경, 10-10 콘솔 확인). 만료 전에 업그레이드하지 않으면 요청 처리를 멈춘다. 자동 유료 전환 설정은 없고 콘솔의 **지금 업그레이드**로 사람이 실행한다. 비용 비교와 대안은 [옛 Plan 13](archive/13-cloud-sql-trial-to-paid-transition.md#비용과-서비스-연속성-비교)에 있다.

## 10-16 결정

- **경로 B – 작은 새 인스턴스를 만들어 운영 DB를 옮긴다.** 지금 인스턴스를 그대로 유료로 바꾸는 A(8 vCPU·64GB Enterprise Plus, 월 수백 달러)와, 바꾼 뒤 그 자리에서 줄이는 C(디스크 100GB가 줄지 않아 +월 $22)는 하지 않는다.
- **크기는 `db-g1-small`**(공유 코어, RAM 1.7GB), PostgreSQL 18, Enterprise 등급, 단일 영역 `asia-northeast1`, SSD 10GB(자동 증가 켬), 삭제 보호 켬. 월 $30 상한을 지키려면 `db-f1-micro`로 시작하고 느리면 올린다(크기 변경은 몇 분 중단).
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

## 10-20 실행 순서

1. 새 인스턴스 만들기(위 사양). Terraform `infra/gcp/hybrid`의 `sql_connection_name`을 새 인스턴스로 바꿀 준비.
2. 지금 운영 DB 백업: `pg_dump` 사본을 `artifacts/backups/`에 두고 로컬 복원으로 확인.
3. 새 인스턴스에 DB·역할 만들기: `trend_app`(소유자)과 게시 역할 `trend_publisher`(`configure_publisher_role.py --role trend_publisher`, `GRANT CONNECT`).
4. 덤프를 새 인스턴스에 복원하고, 운영과 표 행 수를 대조한다(`refresh_production.py compare`와 같은 기준 – 사람 결정·기록 누락 0).
5. Secret Manager에 새 연결 주소 version 추가: `trend-production-database-url`, `trend-production-publisher-database`.
6. API(Cloud Run v2 REST로 secret 버전·Cloud SQL 연결 바꾸기), 백업·유지보수·게시 Job을 새 secret·인스턴스로. Terraform과 운영을 맞춘다(`TF_DATA_DIR=.terraform/production`).
7. 확인: 웹 첫 화면·사전·둘러보기·만들기 200, API health, 검수 로그인, 백업·유지보수 Job 한 번 실행 성공.
8. 문제가 있으면 secret 버전을 이전 것으로 되돌려 옛 인스턴스로 돌아간다(옛 인스턴스는 10-30까지 그대로).

## 10-10 확인

- 인스턴스 `trend-project`: PostgreSQL 18, Enterprise Plus `db-perf-optimized-N-8`, SSD 100GB(자동 증가 꺼짐), 단일 영역, 백업 꺼짐, 삭제 보호 꺼짐. 생성 09-29. 콘솔 표시 '무료 체험 기간이 20일 후에 종료'(10-10 확인) – **10-30경 끝난다.** API에는 만료 시각이 나오지 않는다.
- DB 크기: `trend_20261009`(운영) 404MB, `trend_20261005` 323MB, `trend` 283MB. 셋을 합쳐도 1GB가 안 된다. 연결은 16개(최대 800).
- 실제 사용량에 비해 사양이 매우 크다(체험용 기본값). 유료 전환보다 작은 인스턴스(공유 코어 소형·월 상한 약 $30, [Plan 17 실행 기록](archive/17-hybrid-infrastructure-실행기록.md)의 사용자 결정)로 옮기는 쪽이 맞다. 옮길 때 지금 운영 DB 하나만 옮기고, 이전 DB들은 `pg_dump` 사본을 Git 밖에 둔 뒤 지운다.

## 처음 세운 절차(참고)

1. 10-20~22: 콘솔의 정확한 만료 시각, DB 크기·연결 수·부하를 확인하고 견적을 다시 만든다.
2. 10-24까지: 월 비용 상한과 경로(유료 전환 또는 작은 인스턴스로 이전)를 정한다. `pg_dump` 사본을 Git 밖에 두고 복원을 확인한다.
3. 10-26까지: 실행하고 API·웹·DB 연결, 게시·백업 Job을 확인한다. 새 인스턴스로 옮기면 [10-16 운영 DB 갱신](archive/2026-10-16-final-db-refresh.md)의 전환 절차와 게시 역할 준비를 그대로 거친다.

만료 전 전환을 확인할 때까지 종료 알림을 일정에서 지우지 않는다. 미리 할 수 있는 것: 콘솔의 정확한 만료 시각 확인은 지금도 된다.
