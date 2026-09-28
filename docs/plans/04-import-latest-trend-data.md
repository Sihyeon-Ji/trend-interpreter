# Plan 04. 최신 수집 데이터 받아서 한 번에 이관

작성일 **2026-09-28** · 상태 **대기(원작자에게 파일 요청 필요)** · 선행 작업 **PostgreSQL 전환 완료**

[계획 목록](README.md) · [개발 명령어의 이관 절차](../개발환경/개발-명령어.md#sqlite-시절-데이터-옮기기) · [Plan 03 배포](03-trend-cloud-run-deployment.md)

## 배경

이 저장소에 있던 `trend.db`(2026-09-23자, 용어 613개, 약 21만 행)는 이미 로컬 PostgreSQL로 옮겨 검증했습니다.
그러나 [인수인계 기록](../트렌드/인수인계-2026-09-15.md)에 따르면 그 뒤로도 다른 Linux PC(`/home/cytur/trend`)에서
파이프라인이 cron으로 계속 돌았으므로, 그쪽 파일이 더 최신일 가능성이 큽니다. 사전 뜻은 version으로 갱신되기 때문에
이미 있는 행을 건너뛰는 방식으로는 갱신된 뜻이 반영되지 않습니다. 그래서 **로컬 DB를 비운 뒤 최신 파일 하나로 다시 이관**합니다.

## 원작자에게 요청할 것

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

4. 이전 파일 세 개(`trend.db`, `trend.db.bak-*`)는 이관이 끝나면 지웁니다. 필요하면 로컬 PostgreSQL에서 `pg_dump`로 다시 내보낼 수 있습니다.

## 완료 기준

- 로컬 PostgreSQL의 용어·근거·검수 기록이 원작자 파일과 같은 시점이다.
- `docker compose exec api python scripts/health_check.py`에 경고가 없다.
- 이후 수집은 Compose `db`에만 쌓이고 SQLite 파일은 더 이상 만들어지지 않는다.

이 데이터는 나중에 Cloud SQL이 준비되면 `pg_dump`·`pg_restore`로 옮깁니다(Plan 03).
