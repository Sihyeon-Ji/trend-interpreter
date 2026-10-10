# Plan 20. Trend 운영 일정 등록

작성일 **2026-10-05** · 상태 **완료(10-05) – GitHub Project 일정 등록·검증 완료** · 연계 [Plan 05](05-trend-cloud-run-deployment.md), [Plan 13](13-cloud-sql-trial-to-paid-transition.md), [Plan 17](17-hybrid-infrastructure.md), [Plan 19](19-production-data-refresh.md)

[계획 목록](../README.md) · [GCP 운영](../../운영/GCP-운영.md)

## 완료 범위

2026-10-05에 확정 일정 8개와 날짜 미정 후속 작업 4개를 기존 GitHub Project에 등록하고 검증해 보관했다. 사용자 결정에 따라 담당자는 모두 미정이다. 이후 운영 작업 실행과 후속 작업의 담당자·날짜 확정은 각 이슈 및 Plan 05·06·13·17·19에서 계속 추적한다.

## 목적

운영 서비스(`trend-production-web`·`trend-production-api`, Cloud SQL `trend-project`)에는 날짜가 정해진 운영 작업이 여러 계획에 흩어져 있다. 이 문서는 그 작업을 일정 도구(팀 캘린더나 프로젝트 보드)에 한 번에 옮기기 위한 등록 목록이다. 등록은 이 저장소 밖에서 하고, 등록을 마치면 아래 '등록 기록'에 도구 이름과 날짜를 적는다.

공모전 제출 마감은 **2026-10-18**, Cloud SQL 무료 체험 종료 예상일은 **2026-10-29경**이다. 체험 종료일은 생성일로 계산한 예상일이므로 10-20~22에 콘솔에서 다시 확인하고, 더 이르면 아래 일정을 모두 앞당긴다.

## 등록할 일정

| 날짜 | 작업 | 완료 증거 | 근거 |
| --- | --- | --- | --- |
| 10-10 | 운영 DB 2차 갱신. 끝나면 이전 `trend` DB를 지운다 | 갱신 보고서의 `differences` 비어 있음, 운영 화면 확인, `trend` DB 삭제 | Plan 19, [운영 DB 갱신](../../운영/GCP-운영.md#운영-db-갱신) |
| 10-16 | 제출 전 마지막 운영 DB 갱신. 전환 뒤 백업을 받아 로컬에도 보관한다 | 갱신 보고서, 전환 뒤 백업 검증 보고서 | Plan 19 |
| 10-20~22 | Cloud SQL 체험 종료 시각을 콘솔에서 확인하고 새 소형 인스턴스(공유 코어, 월 약 $30 상한) 견적을 만든다 | 종료 시각, 견적 링크와 월 비용 기록 | Plan 13 |
| 10-24 | 이전 경로와 비용을 확정한다. 새 인스턴스의 자동 백업·PITR 사용 여부도 정한다(삭제 보호는 켠다) | 결정 기록 | Plan 13 |
| 10-24 | 이날부터 갱신이 8일을 넘어 유지보수 Job이 매일 '오래됨' 경보를 낸다. 10-26 이전 때 갱신을 함께 하면 멈춘다 | 경보 확인 | [유지보수 Job](../../운영/GCP-운영.md#유지보수-job) |
| 10-26 | 새 인스턴스를 만들고 갱신 도구(`create`·`upload`·`overlay`)로 운영 DB를 옮긴 뒤 연결을 바꾼다. Terraform의 `sql_connection_name`과 secret version을 함께 바꾼다 | 운영 화면·검수 쓰기·재시작 확인, 백업·유지보수 Job 성공 | Plan 13, Plan 19 |
| 10-27~28 | 실제 청구액과 Cloud SQL SKU를 확인하고 예상치와 비교한다. 체험 인스턴스는 새 인스턴스가 검증된 뒤 지운다 | 청구 기록, 체험 인스턴스 정리 | Plan 13 |
| 2026-12 중 | GPU gateway TLS 인증서를 교체한다(`scripts/rotate-gpu-tls.sh staging`). 현재 인증서는 2027-01-01 전에 만료된다 | 새 인증서 version, 검증 기록 | Plan 17 |

## 날짜를 정해야 하는 작업

아래는 아직 날짜가 없다. 2026-10-05 사용자 결정으로 담당자는 모두 미정으로 두고 후속 작업으로 등록했다. 실행 전 담당자와 날짜를 확정한다.

| 작업 | 내용 | 권장 시기 |
| --- | --- | --- |
| 복원 사본의 보존 기간 정리 검증 | 백업을 복원한 사본에서 보존 기간이 지난 사용자 문장이 `prune_user_text`로 지워지는지 확인한다(Plan 05 9번의 남은 부분) | 10-10 갱신 때 함께 |
| 수집 서버로 사람 결정 돌려보내기 | 운영의 검수 결과를 수집 서버에 알려 같은 제안이 다시 올라오지 않게 한다. 수집 서버 소유자와 형식을 맞춰야 한다 | 제출 뒤 |
| 승인 게시 | 검수한 변경만 묶어 게시하고 활성 게시본을 마지막에 바꾸는 방식(Plan 17)으로 수동 갱신을 대신한다 | 제출 뒤 |
| 수집 파이프라인의 클라우드 이전 | 원작자 PC의 cron 수집을 팀 코드·PostgreSQL로 옮긴다(Plan 06) | 제출 뒤 |

## 등록 방법

1. 위 표의 작업마다 일정 항목을 하나씩 만들고, 제목에 계획 번호를 붙인다(예: `[Plan 19] 운영 DB 2차 갱신`).
2. 본문에는 '작업'·'완료 증거'·'근거' 칸을 그대로 옮기고, 이 문서의 저장소 경로를 함께 적는다.
3. 같은 날 두 작업이 있으면 따로 만든다. 10-24의 경보 항목은 알림용이다.
4. 체험 종료일을 콘솔에서 확인해 일정이 바뀌면 이 문서와 Plan 13을 먼저 고친 뒤 일정 도구를 고친다.

## 등록 기록

- 등록일: **2026-10-05**
- 도구: 기존 [GitHub Project – 2026 Google AI Builder Cup](https://github.com/users/Sihyeon-Ji/projects/1)
- 등록 경로: GitHub MCP 연결 오류로 인증된 GitHub CLI를 사용했다.
- 담당자: 사용자 결정에 따라 **모두 미정**(Assignees 비움).
- 상태: 모든 항목 **Todo**. 일정 등록 완료이며 운영 작업 실행 완료를 뜻하지 않는다.
- 확정 일정 8개는 `Start date`·`Target date`에 반영했다. 10-24 작업은 각각 등록했고, 12월 인증서 교체는 12-01~12-31 범위로 등록했다(정확한 실행일 미정).
- 후속 작업 4개는 날짜 필드를 비우고 본문에 권장 시기를 남겼다. 담당자·날짜 확정은 대기 중이다.
- 검증: GitHub에서 다시 읽어 12개 항목의 Project 연결·Todo 상태·날짜·담당자 미지정·이슈 본문을 확인했다.
- Project의 날짜는 작업 추적용이다. 자동 알림은 설정하지 않았다.

| 일정 | 등록 항목 |
| --- | --- |
| 10-10 | [#12 [Plan 19] 운영 DB 2차 갱신](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/12) |
| 10-16 | [#13 [Plan 19] 제출 전 마지막 운영 DB 갱신 및 백업](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/13) |
| 10-20~22 | [#14 [Plan 13] Cloud SQL 체험 종료 확인 및 소형 인스턴스 견적](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/14) |
| 10-24 | [#15 [Plan 13] 이전 경로·비용·백업 정책 확정](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/15) |
| 10-24 | [#16 [Plan 05] 유지보수 Job 오래됨 경보 확인](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/16) |
| 10-26 | [#17 [Plan 13·19] 새 Cloud SQL 인스턴스로 운영 DB 이전](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/17) |
| 10-27~28 | [#18 [Plan 13] 실제 청구액 확인 및 체험 인스턴스 정리](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/18) |
| 2026-12 중 | [#19 [Plan 17] GPU gateway TLS 인증서 교체](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/19) |
| 미정 | [#20 [Plan 5] 복원 사본의 보존 기간 정리 검증](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/20) |
| 미정 | [#21 [Plan 19] 수집 서버로 사람 결정 돌려보내기](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/21) |
| 미정 | [#22 [Plan 17] 승인 게시](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/22) |
| 미정 | [#23 [Plan 6] 수집 파이프라인의 클라우드 이전](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/issues/23) |
