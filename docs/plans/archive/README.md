# 완료 계획 Archive

다음 계획은 구현과 검증을 마쳐 보관한 문서입니다. 현재 실행할 계획은 [상위 계획 목록](../README.md)을 확인합니다.

## 2026-10-03 재점검

과거 계획 9개의 당시 완료 기록과 현재 코드 적용 범위를 [진척도·구현 적절성 보고서](구현-완료도-실측-점검-2026-10-03.md)에서 점검했다. 이곳의 옛 Compose 서비스·제거된 파일·실습 앱 명령은 현재 실행 절차가 아니다. 최신 실행은 [개발 명령어](../../개발환경/개발-명령어.md)를 따른다.

다른 팀원 Mac, 실제 과거 revision으로의 traffic 복구, 현재 운영 알림 전달은 이번에 검증하지 않았다. 과거 완료를 현재 Trend 앱의 Cloud SQL 복원·모델 품질·실배포 완료로 합산하지 않는다.

| ID | 완료 작업 |
| --- | --- |
| [01](01-environment-reproducibility.md) | 개발환경 재현성과 진단 |
| [현행 Plan 02](02-lifecycle-stages.md) | 쓰임 근거가 있는 검증 용어의 생애주기·확산 판정(10-06 완료 기준 충족) |
| [현행 Plan 04](04-target-regions-and-keyword-dashboard.md) | 지역 선택·예시/API 흐름·10개국 검색어 수집 확인(10-08 완료 기준 충족) |
| [02](02-model-evaluation.md) | 모델 평가와 비교 보고서 |
| [03](03-local-model-history.md) | 실제 모델 실행 이력 연결 |
| [04](04-database-recovery.md) | DB 변경과 백업·복구 |
| [운영 01](01-production-alerting.md) | Discord 운영 알림 중계기 |
| [운영 03](03-alert-delivery-hardening.md) | 알림 유지와 전달 검증 보완 |
| [운영 04](04-ci-change-routing.md) | 변경 범위에 따른 CI와 배포 |
| [운영 05](05-model-request-controls.md) | AI 요청량 제어와 결과 형식 검증 |
| [운영 06](06-release-recovery.md) | 배포 기록과 안전 복구 경로 |
| [18](18-ci-parallelization.md) | CI 병렬화와 배포 시간 단축(16분→약 6분, 10-05) |
| [현행 Plan 03](03-term-risk.md) | 용어별 리스크 판정, 표본 20개 일치율(10-09) |
| [현행 Plan 08](08-content-generation.md) | SNS 카피·숏폼 대본·썸네일 생성(10-09) |
| [현행 Plan 12](12-dictionary-crosscheck.md) | 확인된 사전 항목의 위키 대조(10-09) |
| [현행 Plan 15](15-overseas-generation-signals.md) | 해외 세대의 실측·추정 구별(10-09) |
| [현행 Plan 06](06-gemma-on-cloud-run-gpu.md) | Kaggle 학습·DVC/GCS – 하지 않기로 하고 중단(10-09). 완료가 아니다 |
| [현행 Plan 11](11-public-repository-release-protection.md)·[13](13-cloud-sql-trial-to-paid-transition.md)·[19](19-production-data-refresh.md) | 새 [Plan 11](../11-submission-operations.md)에 합침(10-09). 남은 일은 그쪽에서 관리 |
| [현행 Plan 07](07-meme-recommendation.md) | 사진·문구 기반 밈 추천 – 규칙·쓰임 낱말 고정까지(10-10). 남은 일은 [Plan 24](../24-meme-recommendation-remaining.md) |
| [현행 Plan 09](09-generation-quality-evaluation.md) | 추천·생성 품질 평가 – 9차 측정·사람 검토(10-10). 데모는 [Plan 25](../25-submission-demo-and-deck.md) |
| [현행 Plan 14](14-gemma-visible-in-deployment.md) | 배포본 Gemma 기록 표시(0단계)에서 마무리(10-10). 1·2단계는 [Plan 21](../21-gemma-live-classify.md) |
| [현행 Plan 17](17-hybrid-infrastructure.md)·[실행 기록](17-hybrid-infrastructure-실행기록.md) | 하이브리드 인프라 – 운영·승인 게시·거부 경로·되돌리기 확인(10-10). GCE 추론은 Plan 21, 이전 DB 되돌리기는 [Plan 11](../11-submission-operations.md) |
| [현행 Plan 20](20-copy-check-localization-flow.md) | 문구 검사·현지화 흐름 – 방향·무대 화면(10-10). 남은 일은 [Plan 22](../22-copy-flow-remaining.md), 일본어는 [Plan 23](../23-japanese-ui.md) |
| [현행 Plan 05](05-trend-cloud-run-deployment.md) | 웹·API·Cloud SQL 배포와 백업·유지보수·승인 게시(10-09). 남은 두 가지는 Plan 17로 넘김 |
| [현행 Plan 01](01-import-latest-trend-data.md) | 고정 스냅숏의 Cloud SQL 이관(10-09). 수집 서버 PostgreSQL 전환은 그 담당자에게 넘김 |
| [현행 Plan 16](16-wiki-meme-catalog-and-tendency.md) | 위키 밈 분류 등재 – 용어 3,006개까지 하고 보류(10-09). 완료가 아니다 |
| [현행 Plan 10](10-term-relation-graph.md) | 용어 관계 그래프 – 미착수로 보류(10-09). 완료가 아니다 |
| [20](20-trend-operations-schedule.md) | 운영 일정 8개·후속 작업 4개 GitHub Project 등록 및 검증(10-05) |

## 종료된 점검 보고서

| 점검일 | 기록 | 보관 이유 |
| --- | --- | --- |
| 2026-09-29 | [구현·완료도 점검](구현-완료도-실측-점검-2026-09-29.md) | 점검 종료, 10-01·10-03 후속 점검으로 갱신 |
| 2026-10-01 | [구현·완료도 점검](구현-완료도-실측-점검-2026-10-01.md) | 점검 종료, 10-03 후속 점검으로 갱신 |
| 2026-10-03 | [진척도·구현 적절성 점검](구현-완료도-실측-점검-2026-10-03.md) | 점검 종료, 10-06 재점검으로 갱신 |
| 2026-10-05 | [변경 공유](변경-공유-2026-10-05.md) | 공유 종료, 내용은 각 계획에 반영 |
| 2026-10-06 | [구현·완료도 재점검](구현-완료도-실측-점검-2026-10-06.md) | 점검 종료, 계획 목록(10-09)으로 갱신 |
| 2026-10-08 | 계획 대비 진행 상태 | 계획 목록(10-09)에 합쳐 지웠다(git 기록에 남음) |

점검 종료는 해당 보고서에 등장하는 실행 계획의 완료를 뜻하지 않는다. 현행 Plan 02·04는 명시된 완료 기준을 충족해 10-08에 보관했다. 다른 현행 계획은 데이터·품질·운영 또는 사람 확인 조건이 남아 상위 목록에 유지한다.
