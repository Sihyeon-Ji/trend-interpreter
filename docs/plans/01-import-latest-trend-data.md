# Plan 01. 최신 수집 데이터 받아서 한 번에 이관

작성일 **2026-09-28** · 상태 **대기 — 원본은 원작자 PC(`/home/cytur/trend/data/trend.db`)에 그대로 있어 파일 요청은 필요 없고, 로컬 PostgreSQL 재이관과 기록은 아직 안 함 · 수집을 PostgreSQL 로 옮길지는 사용자/팀 결정 대기** · 선행 **없음** · 목표일 **2026-10-01**

[계획 목록](README.md) · [개발 명령어의 이관 절차](../개발환경/개발-명령어.md#sqlite-시절-데이터-옮기기) · [Plan 05 배포](05-trend-cloud-run-deployment.md)

## 배경

이 저장소에 있던 `trend.db`(2026-09-23자, 용어 613개, 약 21만 행)는 이미 로컬 PostgreSQL로 옮겨 검증했습니다.
그러나 [인수인계 기록](../트렌드/인수인계-2026-09-15.md)에 따르면 그 뒤로도 다른 Linux PC(`/home/cytur/trend`)에서
파이프라인이 cron으로 계속 돌았으므로, 그쪽 파일이 더 최신일 가능성이 큽니다. 사전 뜻은 version으로 갱신되기 때문에
이미 있는 행을 건너뛰는 방식으로는 갱신된 뜻이 반영되지 않습니다. 그래서 **로컬 DB를 비운 뒤 최신 파일 하나로 다시 이관**합니다.

## 원작자에게 요청할 것

(2026-09-29 확인: 이 파일은 원작자 PC 에 있고 그 PC 의 cron 이 계속 갱신하므로 별도 요청 없이 복사할 수 있다. 아래 표는 복사할 대상을 정리한 것이다.)

파일 하나면 됩니다. 실행 중인 파이프라인이 있으면 멈춘 상태에서 복사해 달라고 요청합니다.

| 요청 항목 | 경로 | 비고 |
| --- | --- | --- |
| SQLite 데이터 파일 | `~/trend/data/trend.db` (또는 옮긴 위치의 `apps/trend-api/data/trend.db`) | 필수. 수집 원본·사전·검수 기록 전부 |
| 마지막 실행 시각 | `logs/pipeline.log` 끝부분 | 선택. 어느 시점까지의 데이터인지 기록용 |

받은 파일은 Git에 넣지 않고 `apps/trend-api/data/`에 둡니다(`.gitignore` 제외 대상). 전달 경로는 팀 Discord 파일 첨부나
Google Drive 공유 링크면 충분하며, `.env`나 `data/accounts.txt`는 함께 받지 않습니다.

## 절차

1. 현재 로컬 DB를 비웁니다. 볼륨을 지우면 다음 `up`에서 빈 데이터베이스가 새로 만들어집니다.

   ```bash
   docker compose down
   docker volume rm 2026-google-ai-builder-cup_postgres_data
   docker compose up -d --wait
   ```

2. 받은 파일을 API 컨테이너에 넣고 이관합니다. 표마다 복사한 행 수가 출력되고, 마지막에 별칭 표(`term_aliases`)를 다시 만듭니다.

   ```bash
   docker compose cp apps/trend-api/data/trend.db api:/workspace/apps/trend-api/data/trend.db
   docker compose exec api python scripts/migrate_sqlite_to_postgres.py --sqlite data/trend.db
   ```

3. 결과를 확인합니다. `terms` 수가 원작자가 알려 준 값과 같고, 화면이 실데이터로 열려야 합니다.

   ```bash
   docker compose exec db psql -U trend -d trend -c 'SELECT status, COUNT(*) FROM terms GROUP BY status'
   docker compose exec api python scripts/health_check.py
   DATA_MODE=api docker compose up -d
   ```

4. `apps/trend-api/data/` 에 둔 복사본(`trend.db`, `trend.db.bak-*`)은 이관이 끝나면 지웁니다. 원작자 PC 의 원본 `/home/cytur/trend/data/trend.db` 와 그 `.bak-*` 는 지우지 않습니다. 필요하면 로컬 PostgreSQL에서 `pg_dump`로 다시 내보낼 수 있습니다.

## 완료 기준

- 로컬 PostgreSQL의 용어·근거·검수 기록이 원작자 파일과 같은 시점이다.
- `docker compose exec api python scripts/health_check.py`에 경고가 없다.
- 이후 수집은 Compose `db`에만 쌓이고 SQLite 파일은 더 이상 만들어지지 않는다.

## 현재 상태와 남은 일 (2026-09-29 실측)

완료 기준 셋 모두 아직 충족하지 않았다.

- **1. 같은 시점이 아님.** 팀 저장소 Compose 컨테이너는 떠 있지 않고, 로컬 PostgreSQL 볼륨은 09-28 16:06 에 만들어졌다. 원작자 PC 의 `trend.db` 는 09-29 14:36 실행분(용어 737, 근거 15,703)까지 갱신돼 있다(그 뒤에도 cron 이 하루 4회 계속 쓴다).
- **2. 건강 점검 미실행.** 컨테이너가 없어 돌리지 못했다. 원작자 PC 쪽 점검은 09-29 10:45 에 '경고 없음' 이었다.
- **3. 사용자/팀 결정 대기.** 팀 코드에는 SQLite 쓰기 경로가 없지만(`grep` 결과 `scripts/migrate_sqlite_to_postgres.py` 에만 sqlite 가 나온다), 실제 수집은 아직 원작자 PC 의 cron(9·14·19·23시 :15)과 SQLite 에서 돈다. 수집과 :8180 API 를 팀 코드 + PostgreSQL 로 옮길지는 사용자 결정이다.

남은 일:

1. cron 이 도는 시각(:15~:40)을 피해 `sqlite3 trend.db ".backup ..."` 로 일관된 사본을 떠서 `apps/trend-api/data/` 에 둔다. 현재 볼륨은 지우기 전에 `pg_dump` 한다.
2. 절차 1~3 을 실행하고, 표마다 복사한 행 수를 SQLite 와 대조한다. `terms.diffusion` 열은 마이그레이션 002 가 빈 표에서 먼저 채워지므로 이관 뒤 `UPDATE terms SET diffusion = json::jsonb->>'diffusion'` 로 다시 채운다.
3. 사본을 뜬 시각과 표별 행 수를 이 문서에 적는다.
4. `migrate_sqlite_to_postgres.py` 는 `ON CONFLICT DO NOTHING` 이라 비어 있지 않은 표에 다시 실행하면 낡은 행이 남는다. 비어 있을 때만 돌리도록 막거나 개발 문서의 '다시 실행해도 안전합니다' 를 고친다.

이 데이터는 나중에 Cloud SQL이 준비되면 `pg_dump`·`pg_restore`로 옮깁니다(Plan 05).
