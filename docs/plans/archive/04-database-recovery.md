# 04. DB 스키마 변경과 백업·복구

상태 **구현·현재 Mac 격리 복원 검증 완료** · [현재 계획](../README.md)

## 해결할 문제와 목표

현재는 반복 가능한 초기화와 추가 SQL로 실습 테이블을 준비합니다. 볼륨 보존은 확인했지만,
스키마 변경 이력 관리와 백업 파일에서 별도 DB로 복원하는 과정은 아직 검증하지 않았습니다.

목표는 **기존 기록을 유지하며 스키마를 바꾸고, 별도의 백업에서 기록을 복원할 수 있는 로컬 절차**를 만드는 것입니다.
클라우드 DB 운영이나 고가용성 구성을 미리 구축하지 않습니다.

## 구현 범위

- 기존 `database.initialize`와 `002`·`003` SQL의 적용 상태를 확인해 버전 관리 도입 방식을 정합니다.
- 새 DB와 이미 데이터가 있는 DB에서 같은 최종 스키마를 만들도록 명시적인 변경 경로를 제공합니다.
- 짧은 순차 SQL 관리와 기존 마이그레이션 도구 중 현재 변경 규모에 맞는 한 가지를 선택합니다.
- 적용 버전·중복 실행·실패 시 동작을 확인하고 두 가지 스키마 관리 체계를 동시에 유지하지 않습니다.
- `pg_dump`·`pg_restore` 기반의 백업·별도 대상 복원 절차를 Compose 진입점으로 제공합니다.
- 백업 파일은 Git에서 제외하고 관리자·앱 비밀번호는 파일이나 로그에 복사하지 않습니다.

## 진행 순서

1. 현재 테이블·제약·인덱스·앱 권한과 데이터 존재 여부를 기준 상태로 기록합니다.
2. 기존 DB를 보존하며 기준 버전을 등록하고, 실제 스키마와 버전 표시가 일치하는지 검증합니다.
3. 격리된 테스트 DB에서 성공·재실행·의도적 실패 변경을 시험합니다. 불필요한 제품 테이블은 추가하지 않습니다.
4. 로컬 합성 기록과 실행 이력을 백업하고 별도 Compose 프로젝트의 새 DB로 복원합니다.
5. 복원 후 앱 권한을 명시적으로 적용하고 ID·시각·노드 관계·조회 가능 여부를 대조합니다.
6. 백업 위치·확인 방법·복원 대상 선택·실패 시 대처를 문서화합니다.

## 완료 기준과 확인 방법

| 기준 | 확인 방법 |
| --- | --- |
| 새 DB와 기존 DB 모두 지원 | 빈 DB 및 현재 구조의 데이터가 있는 DB에서 같은 목표 버전으로 도달 |
| 실패한 변경을 성공 처리하지 않음 | 테스트용 실패 SQL 후 버전·실제 스키마·데이터 상태 확인 |
| 재실행 안전성 | 같은 변경을 다시 실행해 중복 적용·기록 손실이 없음을 확인 |
| 백업에서 복원 가능 | 별도 DB에서 실행 ID·생성 시각·노드 수와 관계 일치 |
| 복원 후 권한 유지 | 앱으로 필요한 조회·추가·이력 수정은 가능하고 테이블 생성·삭제는 불가 |
| 원본 개발환경 보존 | 기존 DB·볼륨·비밀번호를 삭제하거나 덮어쓰지 않고 복원 실습 완료 |
| 비밀정보 분리 | 명령행·로그·백업 산출물에 접속 비밀번호나 역할 비밀번호를 포함하지 않음 |

역할·비밀번호 자체를 전체 덤프하는 방식은 사용하지 않습니다. 소유자·권한 복원과 앱 계정 준비는
현재 초기화 정책에 맞춰 별도로 처리하고 결과를 검사합니다.
DB 버전 간 업그레이드나 대규모 무중단 변경까지 검증했다고 주장하지 않습니다.

## 산출물과 제외 범위

산출물은 선택한 스키마 변경 방식, 검증된 Compose 백업·복원 명령, 격리된 복원 검증 결과와 운영 안내입니다.
복원 명령은 대상으로 개발 원본을 자동 선택하지 않도록 설계합니다.
기존 볼륨 삭제, 실제 사용자 데이터 도입, 클라우드 백업, 암호화·보관 기간의 제품 정책 확정,
고가용성·시점 복구·상시 백업 스케줄러는 포함하지 않습니다.

## 구현 결정

현재 migration은 3개이고 DB도 로컬 실습 범위이므로 외부 migration framework를 추가하지 않았습니다.
`apps/api/src/builder_cup/migrations/NNN_name.sql`을 순서대로 실행하는 작은 runner를 사용합니다.
`lab.schema_migrations`에는 버전·이름·SHA-256·적용 시각을 저장합니다.

| 버전 | 파일 | 역할 |
| --- | --- | --- |
| `001` | `001_initial_records.sql` | 합성 record table |
| `002` | `002_workflow_history.sql` | 실행·node 이력과 index |
| `003` | `003_workflow_scenario.sql` | 실행 scenario 열과 제약 |

새 DB에서는 세 migration을 순서대로 적용합니다. 기존 table이 있는 DB에서는 `IF NOT EXISTS` 기반 SQL로
현재 구조를 보존한 뒤 버전과 checksum을 등록합니다. migration SQL과 버전 INSERT는 같은 transaction이며,
적용 후 파일 checksum이 바뀌면 시작 시 실패합니다. 기존 직접 초기화 경로는 제거해 두 체계를 병행하지 않습니다.

## 백업·복원 동작

`db-backup`은 PostgreSQL 18.6 `pg_dump --format custom --no-owner --no-acl`을 사용합니다.
덤프와 SHA-256 파일은 `0600` 권한으로 Git 제외 `backups/`에 생성되며 기존 경로를 덮어쓰지 않습니다.
role과 ACL을 dump하지 않고 접속 비밀번호는 임시 `PGPASSFILE`로만 전달합니다.

`db-restore`는 checksum을 먼저 확인하고 `builder_cup_restore_` 접두사의 **새 DB만** 생성합니다.
기존 대상이 있으면 실패하며 덮어쓰기·clean restore를 실행하지 않습니다. 복원 뒤 현재 초기화 정책의
앱 role 권한을 명시적으로 적용합니다. `db-recovery-check`는 원본과 복원본의 row count·fingerprint 및
앱 role의 사용 가능/금지 권한을 비교합니다.
새 DB 생성 뒤 restore가 실패하면 자동 삭제하지 않아 조사 가능한 부분 상태를 보존합니다.
재시도는 다른 새 대상 이름을 사용하며 삭제·덮어쓰기 자동화는 제공하지 않습니다.

## 직접 실행

```bash
docker compose run --rm --build db-migration-check
docker compose run --rm db-backup

export BACKUP_FILE=/backups/builder-cup-YYYYMMDDTHHMMSSZ.dump
export RESTORE_DATABASE=builder_cup_restore_YYYYMMDD
docker compose run --rm db-restore
docker compose run --rm --build db-recovery-check
unset BACKUP_FILE RESTORE_DATABASE
```

기존 DB 이름이나 기존 restore DB를 대상으로 지정하면 실패합니다. 자세한 출력과 옵션은
[명령어 문서](../../commands.md#db-migration과-백업새-db-복원)에 있습니다.

## 검증 기록 — 2026-09-23

`builder-cup-plan04-20260923` Compose 프로젝트와 새 데이터·비밀번호 볼륨,
별도 포트 28000·25173을 사용했습니다. 기존 개발 프로젝트는 대상으로 사용하지 않았습니다.

| 확인 항목 | 실제 결과 |
| --- | --- |
| 기존 개발 DB 기준선 | migration 적용 전후 `records=0`, `runs=32`, `nodes=160` 유지, 버전 3개 등록 |
| 새 DB 초기화 | 빈 격리 볼륨에서 `001~003` 적용, 합성 record·workflow 생성 성공 |
| 재실행 안전성 | initialize 두 번 실행 후 버전·checksum·데이터 수 동일 |
| checksum drift | 적용된 `001`의 다른 checksum을 거부하고 상태를 변경하지 않음 |
| 실패 transaction | probe table·가짜 `999` 버전·0 나누기를 한 transaction에서 실행, table과 버전 모두 rollback |
| 백업 | `plan04-20260923.dump` 9,186 bytes와 SHA-256 생성, role/password SQL 없음 |
| 새 DB 복원 | `builder_cup_restore_plan04` 생성·custom dump 복원·앱 권한 적용 성공 |
| 기존 대상 보호 | 같은 restore 이름 재실행과 원본 `builder_cup` 이름을 종료 코드 2로 거부 |
| 데이터 비교 | records 4, runs 5, nodes 25, migrations 3의 count·fingerprint 모두 일치 |
| 권한 비교 | 앱 role의 schema usage와 필요한 SELECT·INSERT·UPDATE 허용, CREATE·DELETE 불허 |
| 자동 검사 | Python 테스트 84개, Mock 계약 평가 2개, 타입 검사와 웹 빌드 통과 |

복원 검증 fingerprint는 records `edea13622b083be0c5168a0df256c42b`, runs
`17ef6f844d64f9c8fca54e0608c6808b`, nodes `7a7b030eeca0bd631ced998b776de1ec`,
migrations `4afa3df7d3c47de7c57226e24998e125`였습니다. 값은 이 로컬 합성 데이터에만 해당합니다.

검증 컨테이너와 네트워크는 종료했고 `builder-cup-plan04-20260923_*` 볼륨은 증거 보존을 위해 남겼습니다.
백업 파일도 Git에서 제외된 현재 PC 전용 산출물입니다. 다른 PC에서는 새 데이터와 fingerprint가 생성됩니다.

## 남은 범위

이 구현은 로컬 custom-format 논리 백업과 동일 PostgreSQL 18.6 cluster의 새 DB 복원을 검증합니다.
백업 암호화·외부 보관·보존 기간·스케줄·복구 시간 목표·시점 복구·major version upgrade·Cloud SQL은
제품 데이터와 운영 요구가 정해진 뒤 별도로 설계해야 합니다.
