# Plan 19. 운영 DB 데이터 갱신 경로

작성일 **2026-10-04** · 변경일 **2026-10-05** · 상태 **첫 전환 완료(10-05) – 다음 갱신 10-10·10-16** · 연계 [Plan 01](archive/01-import-latest-trend-data.md), [Plan 05](archive/05-trend-cloud-run-deployment.md), [Plan 13](13-cloud-sql-trial-to-paid-transition.md), [Plan 17](17-hybrid-infrastructure.md) · 목표일 **첫 갱신 2026-10-10, 제출 전 마지막 갱신 10-16**

[계획 목록](README.md) · [운영 DB 백업](../운영/GCP-운영.md#운영-db-백업) · [Cloud SQL 복원 리허설](../개발환경/Cloud-SQL-복원-리허설.md)

## 2026-10-07 승인 배치 게시 기반 구현

불변 배치·항목 해시, 검수자 계정 승인, 뜻 판·사람 결정 충돌 검사, 뜻과 파생 출력·캐시의 원자적 게시, 활성 `publication_id`를 로컬 구현했다. Plan 19 overlay는 성공 게시된 항목과 게시 기록을 보존하고 새 표가 없는 이전 DB도 받는다. 웹 배치 목록·비교·승인/거절도 연결했다. Cloud Run Job·전용 DB 역할·운영 migration/게시·API 모드 실제 흐름·복구 검증은 남는다. 이 기록으로 Plan 17의 최종 승인 게시 기준을 완료 처리하지 않는다. [도구와 검증 범위](../개발환경/승인-배치-게시.md)를 따른다.

## 1. 문제

운영 `trend` DB는 10-01 22:45 KST snapshot `20261001T224511-e56b90d`를 빈 DB에 적재한 뒤 그대로다. 수집 서버는 계속 돌고 GCS `db/latest/`는 하루 두 번(12:45·22:45 KST) 갱신되지만, 운영으로 가져오는 경로가 없다.

지금 있는 도구는 **빈 DB에만** 적재한다(`scripts/load-cloud-sql.sh`, `migrate_sqlite_to_postgres.py --fresh`). 운영 DB에 다시 적재하면 운영에서만 생긴 아래 자료가 사라진다.

| 운영에서만 생기는 자료 | 표 | 10-04 백업 기준 |
| --- | --- | --- |
| 검수 결정과 그 기록 | `review_history`, `review_queue`의 결정 열 | `review_history` 107행 |
| 사람이 승인·수정한 뜻 | `meanings`(`verified_human`·`rejected`, 수정안 새 판과 닫힌 이전 판) | `verified_human` 121개 |
| 사람이 정한 표제어 상태·리스크 | `terms`(`retired`, `json`의 `risk_human`·`risk_decided_by`) | – |
| Gemini 월 사용액 장부 | `gemini_calls`(`usd:YYYY-MM` 등) | 37행 |
| 계정 설정·못 답한 질문·해석 캐시 | `reader_prefs`, `lookups`, `explain_cache` | 0행 / 보존 기간 적용 |

`gemini_calls`를 잃으면 월 $15 상한이 그달 처음부터 다시 세어져 **비용 상한이 사실상 풀린다.** 검수 기록을 잃으면 감사·검수 흐름(심사 기준의 사람 승인 지점)이 비게 된다.

## 2. 원칙

- **사람의 결정은 운영 DB가 원본이다.** 수집 서버는 자동 자료(후보·근거·언급·생애주기·자동 뜻)의 원본이다. 겹치면 사람의 결정이 이긴다. 이는 앱의 기존 규칙(`verified_human`은 자동 조사가 덮지 않는다, 자동 저장은 리스크·제외 결정을 저장된 쪽에서 가져온다)과 같다.
- **운영 DB에 직접 덮어쓰지 않는다.** 새 DB를 옆에 만들고 검증한 뒤 연결을 바꾼다. 실패하면 연결만 되돌린다.
- 갱신 전에는 반드시 [운영 DB 백업](../운영/GCP-운영.md#운영-db-백업)을 수동으로 한 번 실행하고 성공을 확인한다.

## 3. 선택지

| 경로 | 방법 | 장점 | 단점 |
| --- | --- | --- | --- |
| **A. 새 DB 구성 후 전환 (권장)** | 같은 인스턴스에 `trend_<snapshot>` DB를 만들어 새 snapshot을 적재하고, 운영 DB의 사람 결정을 **표제어 단위로 덮어 얹은(overlay)** 뒤 `DATABASE_URL` secret 새 version으로 API를 재배포한다 | 기존 적재·검증 도구를 그대로 쓴다. 되돌리기는 이전 secret version으로 재배포하면 끝난다. Plan 13 B 경로(10-26 새 인스턴스 이전)에 같은 도구를 대상만 바꿔 쓴다 | 전환 직전 몇 분 동안 검수 쓰기를 멈춰야 한다. 인스턴스에 DB가 잠시 두 벌 있다(100GB 디스크 중 일부) |
| B. 운영 DB에 증분 반영 | snapshot과 운영의 차이를 앱 저장 함수(`human=False`)로 운영 DB에 직접 반영한다 | 전환이 필요 없다 | 실패하면 중간 상태가 공개된다. 되돌리려면 백업 복원뿐이고 그 사이 검수가 사라진다. 이관 도구와 다른 두 번째 적재 경로가 생긴다 |
| C. Plan 17 승인 변경 배치 게시 | `batch_id`·`publication_id` 단위로 검수된 변경만 게시하고 활성 게시본을 마지막에 바꾼다 | 장기적으로 가장 정확하다 | migration·게시 Job·화면이 모두 새로 필요해 10-18 제출 전에 끝내기 어렵다. 제출 뒤 과제로 둔다 |

## 4. 권장안 A의 절차

도구는 `scripts/refresh-production-db.sh`(단계별 하위 명령)와 `scripts/refresh_production.py`(덮어 얹기·재계산·대조)다. 단계마다 건수만 담은 보고서를 남기고 행 내용·접속 정보는 남기지 않는다. 실행 명령은 [운영 DB 갱신](../운영/GCP-운영.md#운영-db-갱신)에 있다.

**10-05 변경:** 생애주기 재계산(track)은 표제어마다 뉴스 전체를 읽어 수집 PC에서도 7,500개에 37분이 걸린다. Cloud SQL proxy 너머로는 몇 시간이 걸려 리허설 중 멈췄다. 그래서 3~4단계와 재계산을 로컬 임시 PostgreSQL에서 끝낸 뒤 덤프를 새 Cloud SQL DB에 올린다(`build` → `create` → `upload`). 전환 직전 덮어 얹기만 Cloud SQL에서 다시 실행한다.

1. **입력 고정.** Plan 17 도구로 GCS `db/latest/`의 새 snapshot을 manifest와 함께 고정하고 해시를 확인한다.
2. **백업.** Scheduler로 백업을 한 번 실행하고 `scripts/verify-production-backup.sh`로 복원을 확인한다.
3. **새 DB 적재.** `trend_<snapshot 날짜>` DB를 만들고 `trend_app`에 소유권을 준다. 기존 `restore_rehearsal.py load`로 사용자 표를 뺀 적재와 표별 건수 대조를 한다.
4. **사람 결정 덮어 얹기.** 운영 DB에서 읽어 새 DB에 쓴다.
   - 대상 표제어 = `review_history`의 표제어 ∪ 현재 뜻이 `verified_human`·`rejected`인 표제어 ∪ `risk_decided_by`가 있는 표제어.
   - 대상 표제어의 `terms`·`meanings`(모든 판)·`review_queue`는 운영 값으로 **바꾼다.** 새 snapshot의 같은 표제어 자동 뜻은 버린다. 근거(`evidences`)는 합친다(운영에만 있는 행 추가).
   - `review_history`·`gemini_calls`·`reader_prefs`·`lookups`·`explain_cache`는 운영 행을 그대로 옮긴다. `gemini_calls`는 운영 값이 이긴다.
   - `terms` 행을 통째로 바꾸면 그 행의 자동 리스크 판정도 운영의 옛 값이 된다. 그래서 덮어 얹기는 끝에서 대상 표제어의 리스크만 규칙으로 다시 판정한다(`rejudge_risk`, 모델 없음, 사람이 정한 `risk_human`은 그대로). 전환 직전 덮어 얹기에도 같이 적용된다.
   - 끝나면 `track`·`risk`·`board`·`dashboard` 단계를 새 DB에서 다시 계산한다. 수집 PC의 판정이 끝나지 않은 채 snapshot이 만들어지면 생애주기·리스크가 빠진 표제어가 생긴다(10-01 사본에서 746개, [Plan 02](archive/02-lifecycle-stages.md) 10-05 진단).
5. **검증.** 새 DB에서 사람 결정 건수(`review_history`, `verified_human` 뜻, 사람 리스크)가 운영과 같고, `gemini_calls`의 이번 달 `usd:` 값이 같은지 확인한다. 로컬 웹·API를 새 DB의 복원 사본에 붙여 사전·지도·검수 화면을 확인한다.
6. **전환.** 검수자에게 알리고 검수 쓰기를 멈춘다(아래 결정 2). 4단계의 덮어 얹기를 한 번 더 실행해 그 사이 결정을 반영한다. 새 DB를 가리키는 secret version을 만들고 `production.tfvars.json`의 `database_secret_version`을 바꿔 API를 새 revision으로 배포한다. 백업 Job도 같은 secret을 쓰므로 함께 바뀐다.
7. **확인과 정리.** 운영 URL의 사전·지도·해석, 검수 한 건, `/meta`의 갱신 시각을 확인한다. 이전 DB는 다음 갱신까지 남겨 두고(되돌리기 대상), 그다음 갱신 때 지운다.

되돌리기는 이전 secret version으로 6단계를 반대로 실행한다. 전환 뒤 새 DB에서 생긴 검수가 있으면 같은 덮어 얹기로 이전 DB에 옮긴 뒤 되돌린다.

## 2026-10-05 운영 리허설 (전환 제외)

snapshot `20261005T124512-e56b90d`(10-05 12:45 KST, 표제어 11,356개)로 전환 직전까지 실행했다. 운영 서비스는 계속 `trend` DB를 썼다.

| 단계 | 결과 | 시간 |
| --- | --- | --- |
| `capture` | manifest 고정, 표제어 11,356개 | 1분 미만 |
| `build` | 사람 결정 표제어 139개 덮어 얹기, 판정 재계산(track 11,279·risk 7,655·board 82·dashboard 7,318), 대조 통과, 덤프 61.8MB | 14분 |
| `create` | `trend_20261005`, 소유자 `trend_app`, PUBLIC 접속 회수, 임시 관리자 삭제 확인 | 1분 미만 |
| `upload` | 표 48개 | 30초 |
| `overlay`(전환 직전) | 빠진 결정 0 – 검수 기록 107·사람 승인 뜻 121·제외 28·Gemini 장부 40행 모두 일치 | 25초 |

생애주기 재계산 뒤 verified의 `unknown`은 7,020개에서 6,663개로 줄었다. 처음 build는 재계산에 73분이 걸렸고, 그 사이 proxy access token(1시간)이 만료돼 대조 단계가 실패했다. 뉴스를 표제어마다 다시 읽던 track을 한 번 읽어 재사용하도록 고친 뒤 결과 분포가 같고 build가 14분이 됐다. proxy는 운영 DB를 읽는 단계마다 새로 띄운다.

## 2026-10-05 첫 전환

사용자 결정으로 리허설 DB를 그대로 운영에 올렸다. 검수 작업이 없는 시간이라 중지 공지는 생략했다.

| 순서 | 결과 |
| --- | --- |
| 전환 전 백업 | `trend-20261005T081948Z.dump` 성공 |
| 직전 덮어 얹기 | 빠진 결정 0, 검수 기록 107·사람 승인 뜻 121 |
| secret | `trend-production-database-url` version 2 → `trend_20261005`. `production.tfvars.json`(Git 제외)을 version 2로 바꿨다 |
| API | 새 revision `trend-production-api-00010-t9s`(이미지·과금 설정은 이전과 같음)로 트래픽 100%. 이전 revision `trend-production-api-00016-bif`는 version 1(`trend` DB) |
| 확인 | 웹 `/`·`/map`·`/dictionary`·`/explain`·`/briefing` 200, API 익명 403, 2017년 위키 밈 항목에 '유행 시기 2017년'과 '최근 쓰임 자료 없음' 표시, 오류 로그 0건 |
| 전환 뒤 백업 | `trend-20261005T082334Z.dump` 61.8MB 성공 |

되돌리기는 `gcloud run services update-traffic trend-production-api --region=asia-northeast1 --to-revisions=trend-production-api-00016-bif=100`이다. 이전 `trend` DB(283MB)는 다음 갱신까지 남긴다.

## 2026-10-09 두 번째 전환

10-10 예정이던 갱신을 사용자 결정으로 앞당겼다. 수집 PC가 10-09 12:45 KST에 올린 snapshot `20261009T124515-8b2a19c`(표제어 11,471개)를 썼다. 다른 세션의 커밋하지 않은 변경이 갱신 이미지에 섞이지 않게 `origin/develop`의 별도 worktree에서 실행했다.

| 순서 | 결과 |
| --- | --- |
| `build` | 사람 결정 표제어 146개 덮어 얹기, 사람·Gemini 쓰임 낱말 170개 이어 받기, 재계산(track 11,393·risk 7,554·board 79·dashboard 7,220), 대조 빠진 결정 0, 덤프 79MB |
| `create`·`upload` | `trend_20261009`, 표 54개 |
| 새 후보 쓰임 낱말 | 추천 후보가 170 → 279개로 늘어 꼬리표 없는 124개를 `gemini-3.5-flash`(묶음 25개, 5회)로 붙였다 |
| 전환 전 백업 | `trend-20261009T123411Z.dump`, 복원 검증 표 54개·739,348행 |
| 직전 덮어 얹기 | 빠진 결정 0 |
| secret | version 3 → `trend_20261009`, `production.tfvars.json` 갱신·`terraform-vars.sh save` |
| 백업 Job | Terraform으로 version 3 |
| API | Terraform이 409로 실패(아래). 서비스 중이던 revision의 정의에서 DB secret만 3으로 바꾼 `trend-production-api-db20261009`를 Cloud Run v2 API로 만들고 트래픽 100% |
| 확인 | 웹 `/`·`/map`·`/dictionary`·`/explain`·`/briefing`·사전 항목 200, 전환 뒤 API 오류 로그 0, 이전 DB(`trend_20261005`)와 새 DB 대조 빠진 결정 0, 전환 뒤 백업 `trend-20261009T130214Z.dump` 79MB, Terraform plan 변경 없음 |

**절차에서 드러난 것.**

- **Terraform 상태 위치.** `infra/gcp/hybrid/.terraform`은 staging 상태(`hybrid/staging`)에 붙어 있다. production은 `TF_DATA_DIR=.terraform/production`으로 실행해야 한다. 기본값으로 계획하면 production 변수로 staging 상태를 비교해 생성 10·삭제 8이 나온다(적용하지 않았다).
- **API는 Terraform으로 전환할 수 없다.** API의 revision 이름은 배포 스크립트가 정하고 Terraform은 무시한다(`ignore_changes`). 그래서 Terraform이 지금 revision 이름 그대로 설정을 바꾸려다 409(`Revision ... with different configuration already exists`)가 난다. `gcloud run services update --update-secrets`는 v2 secret 경로를 읽지 못해 멈추고, `gcloud run services replace`는 cloudresourcemanager API를 켤지 묻다 멈춘다. Cloud Run v2 API로 template의 secret 버전과 revision 이름만 바꾸는 것이 통했다.
- **다른 세션의 배포.** 전환 중에 다른 세션이 `release/gcp`를 배포했다. 서비스 정의는 전환 직전에 다시 읽어야 한다(먼저 읽은 정의를 적용하면 이전 이미지로 돌아간다).
- **직전 덮어 얹기는 secret을 만들기 전에.** secret이 새 DB를 가리킨 뒤에는 도구가 덮어 얹기를 거부한다. 그래서 전환 뒤 두 DB를 직접 대조해 빠진 결정 0을 확인했다.

되돌리기: `gcloud run services update-traffic trend-production-api --region=asia-northeast1 --to-revisions=trend-production-api-00052-kab=100`(이전 DB `trend_20261005`를 가리킨다). 백업 Job은 `production.tfvars.json`을 version 2로 되돌리고 Terraform으로 맞춘다. `trend_20261005`는 다음 갱신까지 남기고 그 전 DB `trend`는 이번에 지울 수 있다.

## 5. 결정 (2026-10-05 사용자)

1. **경로** – A. 새 DB를 꾸민 뒤 연결을 바꾼다. B·C는 쓰지 않으며, C는 제출 뒤 과제로 둔다.
2. **전환 중 쓰기 중지** – 검수자에게 알리고 5분 동안 검수를 멈춘다. 도구는 전환 직후 두 DB의 `review_history` 건수를 비교해 다르면 덮어 얹기를 다시 실행한다.
3. **갱신 주기** – 제출 전 두 번 수동으로 한다. 10-10은 실제 데이터 리허설, 10-16은 제출 최종본이다.
4. **수집 서버로 사람 결정 돌려보내기** – 제출 뒤에 수집 서버 소유자와 형식을 맞춘다. 그때까지 운영 화면은 4단계의 덮어 얹기로 보호한다.

## 6. 완료 기준

- 새 snapshot이 반영된 뒤에도 운영의 `review_history`·`verified_human` 뜻·사람 리스크·`gemini_calls`가 전환 전과 같다.
- 전환 전 백업과 그 복원 검증 보고서가 있고, 이전 DB로 되돌리는 명령을 한 번 실행해 본 기록이 있다.
- 운영 웹의 사전·지도·해석이 새 snapshot 시각으로 열리고, 오류 경보가 없다.

## 2026-10-05 전환 뒤 리스크 보정

전환 직전 덮어 얹기가 재계산 뒤에 사람이 손댄 표제어 106개의 `terms` 행을 이전 DB 값으로 다시 바꿔, 이 106개의 리스크가 09-30 판정으로 남았다. 나머지 7,549개는 10-05 판정이었다. 그 결과 10-05 리스크 규칙(위험 근거가 쓰임의 절반 이하이면 주의)이 gaslighting·懶人包에 적용되지 않았다.

| 순서 | 결과 |
| --- | --- |
| 보정 전 백업 | `trend-20261005T092309Z.dump` 61.8MB 성공 |
| 다시 판정 | 배포 커밋 `56eb0d1`로 만든 이미지에서 106개에 `risk.apply`만 실행. 사람이 정한 리스크 0개. 사용 자제 → 주의 2개(gaslighting·懶人包), 나머지 104개는 같은 수준 |
| 확인 | 사용 자제 53 → 51, 주의 821 → 823, 09-30 판정 0개. 대시보드는 요청마다 현재 리스크를 읽으므로 캐시는 다시 만들지 않았다 |

다음 갱신부터는 덮어 얹기가 같은 판정을 스스로 한다(4단계).
