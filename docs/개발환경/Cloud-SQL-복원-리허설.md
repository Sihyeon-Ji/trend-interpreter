# Cloud SQL staging 인수와 복원 리허설

Plan 17 3단계와 [Plan 13](../plans/13-cloud-sql-trial-to-paid-transition.md)의 선행 검증이다. 고정 snapshot을 PostgreSQL에 이관하고, `pg_dump`로 만든 사본을 빈 DB에 복원해 원본과 같은지 확인한다. 개발 DB와 Cloud SQL에는 쓰지 않는다.

## 실행

```sh
scripts/restore-rehearsal.sh 20261001T224511-e56b90d \
  manifests/restore-rehearsal-20261001T224511-e56b90d.json
```

스크립트는 별도 Compose 프로젝트 `trend-restore-rehearsal`에서 `postgres:18.6`을 띄우고 아래 순서로 실행한다. 종료 시 컨테이너·볼륨·작업 디렉터리를 지운다. dump 파일은 DB 컨테이너 밖으로 나오지 않는다.

1. `manifests/<snapshot>.json`의 SHA-256으로 압축 DB를 검증한다.
2. 빈 `rehearsal_source` DB에 `migrate_sqlite_to_postgres.py --fresh --skip-user-data`와 같은 이관을 실행한다. 원본 행 수에서 이관 규칙으로 빠지는 행을 뺀 값과 표별로 대조하고, 사용자 표 3개가 0행인지 확인한다.
3. `pg_dump --format=custom --no-owner --no-privileges`로 dump를 만들고 빈 `rehearsal_restored` DB에 `pg_restore --exit-on-error`로 복원한다.
4. 두 DB의 표 목록, 표별 행 수와 행 순서와 무관한 내용 checksum, 컬럼·제약·색인·sequence 정의를 비교한다. 하나라도 다르면 실패한다.

보고서에는 표 이름·건수·checksum·시간·dump 크기만 남기며 행 내용과 접속 정보는 남기지 않는다.

## 2026-10-03 결과

[보고서](../../manifests/restore-rehearsal-20261001T224511-e56b90d.json) 기준이다.

| 항목 | 결과 |
| --- | --- |
| 입력 | snapshot `20261001T224511-e56b90d`, 압축 DB SHA-256 manifest 일치 |
| 이관 | 41개 표 일치. `news` 51,632행 중 기본키 길이 정책으로 6행 제외, 나머지 표 제외 없음 |
| 사용자 자료 | `explain_cache`·`lookups`·`reader_prefs` 0행 |
| 복원 대조 | 표 48개(이관 41개 + 앱이 만드는 빈 표·별칭·migration 기록), 659,707행, 컬럼 291·제약 125·색인 45 모두 원본과 동일 |
| 크기·시간 | custom dump 52.9MB, 이관 15초, dump+복원 8초(로컬 Docker, PostgreSQL 18.6) |

이 결과는 **로컬 PostgreSQL 18.6에서 이관·논리 백업·복원 절차가 데이터를 잃지 않는다**는 근거다. Cloud SQL의 관리형 백업·PITR·실제 소켓 접속·권한 분리를 검증한 것은 아니다.

## 원격 Cloud SQL 현황

2026-10-03 읽기 전용 조회 결과다.

| 항목 | 상태 |
| --- | --- |
| 인스턴스 | `trend-project`, `RUNNABLE`, PostgreSQL 18, 도쿄, Enterprise Plus `db-perf-optimized-N-8` |
| 보호 | 자동 백업·PITR·삭제 보호 꺼짐, 백업 0건, 공개 IP 사용, private network 미설정 |
| DB·사용자 | DB는 기본 `postgres` 하나, `trend` 등 앱 DB 없음. 사용자는 기본 `postgres` 하나, IAM DB 사용자 없음 |
| 사용량 | Cloud Monitoring의 디스크 사용량 약 100MB, `postgres` DB 연결 0 |

디스크 사용량이 빈 인스턴스 수준이고 앱 DB가 없으므로 **원격에는 보존할 앱 데이터가 없다**고 판단한다. 따라서 Cloud SQL `postgres` DB의 내용을 읽기 위한 SQL 인증 정보는 지금 필요하지 않다. staging과 production은 위 리허설과 같은 절차로 새 DB에 처음부터 적재한다.

무료 체험 인스턴스는 **백업과 복원을 지원하지 않으며, 인스턴스 삭제 시의 최종 백업만 예외다.** 체험 기간이 끝나기 전에 업그레이드하지 않으면 요청 처리를 멈추고, 90일 유예 뒤 삭제 예정이 된다([무료 체험 안내](https://docs.cloud.google.com/sql/docs/postgres/free-trial-instance)). 그래서 관리형 백업·PITR·삭제 보호는 유료 전환 후에 켠다. 그 전까지의 복구 수단은 이 리허설의 `pg_dump` 절차다.

## 보호 설정안 – 유료 전환 직후 적용

아래는 Plan 13에서 경로 A(기존 인스턴스 유료 전환)를 선택했을 때의 변경안이다. 비용에 영향을 주므로 사용자 승인 전에는 실행하지 않는다.

```sh
gcloud sql instances patch trend-project --project=stunning-crane-508614-c1 \
  --backup-start-time=18:00 \
  --retained-backups-count=7 \
  --enable-point-in-time-recovery \
  --retained-transaction-log-days=7 \
  --deletion-protection
```

- 백업 시작 18:00 UTC는 한국 시각 03:00이다. 보존 7개·로그 7일은 시작값이며 실제 저장 비용을 보고 조정한다.
- 적용 후 `gcloud sql instances describe`로 네 설정과 첫 자동 백업 `SUCCESSFUL`을 확인한다. 이후 백업을 **새 임시 인스턴스**에 복원해 이 문서의 checksum 대조와 같은 방법으로 검증하고 임시 인스턴스를 지운다. 기존 인스턴스에 덮어쓰는 복원은 하지 않는다([백업](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/backups), [복원](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/restore)).
- 공개 IP는 Cloud Run의 Cloud SQL connector 소켓만 쓰도록 승인 네트워크를 비워 두고, `--connector-enforcement=REQUIRED`와 `--ssl-mode=ENCRYPTED_ONLY`를 함께 검토한다. Private IP 전환은 VPC peering과 재시작이 필요하므로 별도 변경으로 다룬다.

경로 B(새 소형 인스턴스)를 선택하면 새 인스턴스 생성 시 같은 설정을 처음부터 켜고, 이 리허설과 같은 적재 절차로 데이터를 넣는다.

## staging 연결안

| 항목 | 결정안 |
| --- | --- |
| DB | 같은 인스턴스에 `trend_staging`과 `trend` DB를 따로 만든다. 기본 `postgres` DB에는 앱 데이터를 두지 않는다 |
| 사용자 | 환경별 앱 사용자 `trend_staging_app`·`trend_app`을 만들고 자기 DB만 소유한다. 기본 `postgres` 사용자는 앱에서 쓰지 않는다 |
| 비밀번호 | 생성한 값을 바로 Secret Manager `trend-staging-database-url`·`trend-production-database-url`의 새 version으로 넣는다. 채팅·로그·Terraform state에 남기지 않는다 |
| 연결 문자열 | `postgresql://<user>:<password>@/<db>?host=/cloudsql/stunning-crane-508614-c1:asia-northeast1:trend-project` – `infra/gcp/hybrid`의 `/cloudsql` 소켓 mount와 맞춘다 |
| 적재 | 리허설과 같은 snapshot·`--fresh --skip-user-data` 이관을 staging DB에 실행하고 표별 건수를 이 보고서와 대조한다 |
| 분리 확인 | staging API SA가 production secret을 읽지 못하고, staging 사용자가 `trend` DB에 접속하지 못하는지 확인한다 |

DB·사용자 생성은 인스턴스 사양을 바꾸지 않아 추가 과금이 거의 없다. 다만 체험 인스턴스에 적재한 데이터는 백업되지 않으므로, 유료 전환 또는 이전 경로가 정해진 뒤 적재하는 것을 기본으로 한다.

## 남은 결정

- Plan 13의 전환 경로 A/B와 월 비용 상한, 실행 일자
- 보호 설정안의 백업 보존 수·PITR 로그 일수
- staging DB 적재 시점 – 유료 전환 전 시험 적재를 허용할지 여부
