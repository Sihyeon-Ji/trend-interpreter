# Plan 01. 최신 수집 데이터 받아서 한 번에 이관

작성일 **2026-09-28** · 변경일 **2026-10-01** · 상태 **기존 스냅숏 이관 검증 완료(09-29) · GCS 최신 고정 스냅숏의 staging 이관·대조는 남음 · 수집 서버는 SQLite 유지** · 선행 **없음** · 목표일 **2026-10-01**

[계획 목록](README.md) · [개발 명령어의 이관 절차](../개발환경/개발-명령어.md#sqlite-시절-데이터-옮기기) · [Plan 05 배포](05-trend-cloud-run-deployment.md)

## 배경

이 저장소에 있던 `trend.db`(2026-09-23자, 용어 613개, 약 21만 행)는 이미 로컬 PostgreSQL로 옮겨 검증했습니다.
그러나 [인수인계 기록](../트렌드/인수인계-2026-09-15.md)에 따르면 그 뒤로도 다른 Linux PC(`/home/cytur/trend`)에서
파이프라인이 cron으로 계속 돌았으므로, 그쪽 파일이 더 최신일 가능성이 큽니다. 사전 뜻은 version으로 갱신되기 때문에
이미 있는 행을 건너뛰는 방식으로는 갱신된 뜻이 반영되지 않습니다. 그래서 **빈 DB에 최신 파일 하나로 다시 이관**합니다.

2026-10-01부터 인수 원본은 [Plan 17](17-hybrid-infrastructure.md)의 `gs://copybara-team-shared-bucket/taewoo/trend-interpreter/`입니다. 수집 서버의 SQLite는 유지하고, 서비스용 PostgreSQL로 승인 자료를 별도 게시합니다. 수집 서버를 PostgreSQL로 바꾸는 것은 이 계획의 완료 조건이 아닙니다. 아래 09-29 결과는 당시 PC 사본의 검증 기록이며 최신 GCS 자료의 검증 결과가 아닙니다.

## 절차

1. **스냅숏 고정.** GCS `db/latest/`에서 선택한 객체 generation·해시·크기·표별 건수를 manifest로 고정하고 `snapshots/<snapshot-id>/` 사본을 검증합니다. manifest를 마지막에 게시하는 인수 도구는 Plan 17에서 구현합니다. 여러 최신 파일을 임의로 섞지 않습니다. 압축을 푼 SQLite 사본은 Git 제외 경로 `apps/trend-api/data/trend.db`에 두고, 사용자 표 `explain_cache`·`lookups`·`reader_prefs` 제외를 확인합니다. `.sql.gz`는 SQLite dump이므로 PostgreSQL에 직접 복원하지 않습니다.

2. **빈 DB.** 별도 Compose 프로젝트로 띄웁니다. 기본 프로젝트의 `postgres_data` 볼륨(`2026-google-ai-builder-cup_postgres_data`)은
   지우지 않습니다. 되돌릴 수 없으므로 바꿔야 하면 먼저 `pg_dump`로 보관합니다.

   ```bash
   docker compose -p abc-pgimport up -d --wait db
   ```

3. **이관.** `--fresh`는 대상 `terms`에 행이 있으면 아무것도 옮기지 않고 끝납니다. 이미 있는 행은 새 파일의 값으로 바뀌지 않기 때문입니다.

   ```bash
   docker compose -p abc-pgimport run --rm -v "$PWD/apps/trend-api/data:/import:ro" api \
     python scripts/migrate_sqlite_to_postgres.py --sqlite /import/trend.db --fresh --skip-user-data
   ```

4. **확인.** 표마다 원본과 건수를 비교하고, 건강 점검과 실데이터 화면을 봅니다. 포트는 다른 checkout과 겹치지 않게 고릅니다.
   e2e에는 예시 데이터를 전제한 단언이 있어 실데이터에서는 일부가 실패합니다(2026-09-29에는 10건, 아래 결과).

   ```bash
   docker compose -p abc-pgimport run --rm api python scripts/health_check.py
   DATA_MODE=api DEV_WEB_PORT=3518 DEV_API_PORT=8518 docker compose -p abc-pgimport up -d --wait
   DATA_MODE=api DEV_WEB_PORT=3518 DEV_API_PORT=8518 docker compose -p abc-pgimport --profile tools run --rm e2e
   ```

5. **정리와 게시.** 로컬 임시 사본만 정리하고, 원본 GCS 객체·고정 스냅숏·수집 서버 DB는 보존합니다. 초기 이관 이후 갱신은 Plan 17의 승인 변경 배치로 게시합니다. 운영 DB에 전체 이관을 반복하지 않습니다.

Cloud SQL로 보낼 사본에서는 이용자가 붙여 넣은 문장(`explain_cache`)과 계정별 설정(`reader_prefs`)을 뺍니다.
스크립트로 바로 옮기면 `--fresh --skip-user-data`, 로컬 DB에서 내보내면
`pg_dump -Fc --no-owner --exclude-table-data=explain_cache --exclude-table-data=lookups --exclude-table-data=reader_prefs`입니다([Plan 05](05-trend-cloud-run-deployment.md)).

현재 이관 스크립트의 `--skip-user-data`는 `explain_cache`·`reader_prefs`만 제외합니다. GCS 인수본에서 `lookups`도 없는지 확인하고, 향후 원본에 존재할 수 있는 `lookups`까지 제외하도록 스크립트를 보완해야 합니다. 이 세 표 제외 검증은 최초 이관의 필수 조건입니다.

## 완료 기준

- 선택한 GCS snapshot manifest와 staging PostgreSQL의 용어·뜻·근거·검수 기록을 대조하고, 호환성 때문에 제외한 항목을 건수와 사유로 기록한다. → 최신본은 미검증
- staging에서 `health_check.py`와 API 모드 실데이터 흐름을 검증한다. → 09-29 사본은 확인, 최신본은 남음
- 이용자 표 제외를 확인하고 Cloud SQL 최초 이관·복원 결과에 snapshot ID를 연결한다. → 남음
- 수집 서버의 SQLite를 유지하면서 이후 승인 배치를 중복·뜻 버전 충돌 없이 게시한다. → Plan 17의 게시 구현·검증과 연결

## 결과 (2026-09-29, 23:02 KST 스냅숏 · 19:15 회차 뒤)

원본은 32개 표 약 34만 행입니다. 용어 745 · 근거 15,807 · 뜻 767 · 검수 기록 592 · 근거 분류 1,237
(점검 때 본 19:02 사본은 737 · 15,703 · 755 · 582 · 1,219).

**이관에서 드러난 것.** 기존 스크립트로 옮기면 news 표에서 멈췄습니다.

| 문제 (실측) | 고친 것 |
| --- | --- |
| `index row size 2920 exceeds btree version 4 maximum 2704 for index "news_pkey"` – 2,901바이트짜리 Google 뉴스 주소 1건. news 30,000/42,776에서 끝나(exit 1) 별칭 표도 다시 만들지 못했다(0행). 파이프라인 수집(`store.upsert_news`)도 이런 주소가 하나 섞이면 그 나라 뉴스 묶음이 통째로 롤백됐다. PostgreSQL에서만 나는 문제 | 주소가 2,048바이트보다 긴 뉴스는 저장하지도 옮기지도 않는다(`store.NEWS_LINK_MAX`). 이번 파일에서 6건, 그중 근거로 쓰인 것 1건 |
| `terms.diffusion` 0/745. 마이그레이션 002의 보정은 처음 연결할 때 빈 표에서 돌고, SQLite `terms`에는 이 열이 없다 | 스크립트가 옮긴 뒤 용어 JSON에서 채운다: 247 (태동 152 · 식상 72 · 주류 21 · 확산 2) |
| 이미 있는 행은 `ON CONFLICT DO NOTHING`으로 건너뛰므로, 옛 DB에 새 파일을 옮기면 옛 값이 조용히 남는다 | `--fresh`. 실데이터가 든 DB(terms 745)에서 아무것도 옮기지 않고 exit 1로 끝나는 것을 확인 |
| 해석 캐시 66행·계정 설정 1행이 Cloud SQL 사본에 따라간다 | `--skip-user-data`. 실데이터로 새 DB에 옮겨 두 표 0행, 나머지는 같음을 확인 |

**고친 스크립트로 다시 옮긴 결과(`--fresh`).** 약 6초 걸렸습니다. 32개 표 중 31개가 건수와 행 내용까지 원본과 같고,
news만 42,770/42,776(뺀 6건)입니다. 별칭 표는 136행입니다.

| 확인 | 결과 |
| --- | --- |
| `health_check.py` | 경고 없음. 검증 153 · 검수 대기 559 · 내린 것 23, 화면에 나가는 뜻 중 쓸 수 없는 것 0, 번역 안 된 것 0, 열린 검수 182 |
| 규칙 단계(candidates·hunt·track·board·dashboard)를 PostgreSQL에서 다시 실행 | 오류 없음. track 212.6초(트윈 SQLite 188.1초). 용어 745개의 상태·생애주기·확산 단계가 트윈 결과와 모두 같고, 주간 언급이 다른 1칸(42→41)은 뺀 뉴스 1건 때문 |
| API 모드 웹 + e2e 전체 | 19 통과 · 10 실패 · 2 건너뜀(관리 화면, 세션 비밀값 없음). 그동안 API 로그에 5xx·오류 없음, 웹 로그에도 오류 없음 |
| Cloud SQL 사본 리허설 | `pg_dump`(두 표의 데이터 제외) 27 MB · 1.4초, 새 DB에 `pg_restore` 1.2초. 건수 같음, 두 표 0행. `schema_migrations` 6행이 그대로라 API가 마이그레이션을 다시 적용하지 않고, 건강 점검 경고 없음 |

e2e 실패 10건은 모두 예시 데이터를 전제한 단언입니다. 예시 건수(`전체 6`), 예시 주제(`오징어 게임`), 실데이터에서 내린 `t_crumbl`,
실데이터에는 있는 홍콩 밈, 예시 추천의 `럭키비키`(실데이터 순위 상위 5개에 없음, 5건), 사전이 50개씩 나뉘어 2쪽에 있는 `자만추`.
PostgreSQL 때문에 난 실패는 없었습니다.

PostgreSQL DB의 정렬 규칙은 `en_US.utf8`이라 `ORDER BY canonical` 결과가 SQLite(바이트 순)와 다릅니다.
사전 화면은 웹이 다시 정렬하므로 보이는 순서에는 영향이 없습니다.

남은 일: GCS 최신 고정 스냅숏으로 이관·대조를 다시 실행합니다. 기본 로컬 볼륨 교체는 필수 사항이 아니며, 교체할 때는 먼저 `pg_dump`로 보관합니다. 이관한 DB는 `abc-pgimport_postgres_data` 볼륨에 남겨
다른 계획의 실데이터 확인에 씁니다(`DATA_MODE=api docker compose -p abc-pgimport up -d`).
