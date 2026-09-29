# 계획

작성일 **2026-09-23** · 최종 갱신 **2026-09-29** · 상태 **계획별 진행 상황 상이** · 제출 마감 **2026-10-18**

[구현·완료도 실측 점검](구현-완료도-실측-점검-2026-09-29.md) · [현재 준비 상태 조사](../AI-개발/개발-준비-점검.md) · [운영 명령](../개발환경/개발-명령어.md) · [결정 기록](../adr/README.md) · [완료 계획](archive/)

## 현재 계획 (진행 순서)

번호는 **시작할 순서**입니다. [서비스 방향](../adr/0001-서비스-방향.md)과 [고도화 방안](../adr/0002-고도화-방안.md)의 기능 계획과
배포 계획을 한 줄로 세웠습니다. 목표일은 마감 사흘 전까지 데모를 마치는 기준입니다.

| ID | 구분 | 작업 | 선행 | 목표일 |
| --- | --- | --- | --- | --- |
| [01](01-import-latest-trend-data.md) | 데이터 | 원작자 PC의 최신 `trend.db`로 로컬 DB 재이관 | — | 10-01 (파일을 받는 즉시) |
| [02](02-lifecycle-stages.md) | 기반 | 생애주기 데이터 보강과 출처 순서 판정 | 01 | 10-02 |
| [03](03-term-risk.md) | 기반 | 용어별 리스크 필드와 근거 기반 판정 | 02 | 10-04 |
| [04](04-target-regions-and-keyword-dashboard.md) | 흐름 1 살펴보기 | 목표 지역 조정과 키워드 대시보드 | 02, 03 | 10-07 |
| [05](05-trend-cloud-run-deployment.md) | 배포 | Trend 웹·API와 Cloud SQL 배포, PC 독립 유지보수 | 04 | 10-09 |
| [06](06-gemma-on-cloud-run-gpu.md) | 데이터·AI | 로컬 Gemma 4로 사전·국가별 해석 편집 후 운영 DB 게시 | 05 | 10-10 |
| [07](07-meme-recommendation.md) | 흐름 2 추천받기 | 사진·홍보 문구 기반 밈 추천 | 02, 03, 04 | 10-12 |
| [08](08-content-generation.md) | 흐름 3 만들기 | SNS 카피·숏폼 대본·썸네일 구성안 생성 | 07, 06 | 10-14 |
| [09](09-generation-quality-evaluation.md) | 전체 | 추천·생성 품질 평가와 제출 데모 준비 | 07, 08 | 10-15 |
| [10](10-term-relation-graph.md) | 선택 | 용어 간 관계 그래프 | 07 | 여유 시 |
| [11](11-public-repository-release-protection.md) | 제출 | 공개 저장소 전환과 GCP 배포 승인 | 09 | 10-17 |
| [12](12-dictionary-crosscheck.md) | 데이터 | 확인된 사전 항목의 참고 위키 전수 대조와 새 말의 '문서 대조' 단계 | — | 10-04 (문서 없는 항목은 사용자 확인 뒤) |

순서를 정한 기준은 다음과 같습니다.

- 대시보드·추천이 쓰는 생애주기와 리스크 데이터를 먼저 만듭니다(01~03).
- 첫 화면(04)이 생기면 바로 배포해, 인프라 문제를 마감 직전이 아니라 중간에 발견합니다(05).
- 추천·생성이 참조할 검증된 사전과 국가별 해석 게시 경계를 먼저 마련합니다(06). 요청 시 검사는 운영 데이터·규칙 코드로 처리합니다.
- 공개 저장소 전환(11)은 제출 1~3일 전 마지막에 합니다. Collaborator 목록 정리는 이미 끝나 다시 하지 않습니다.
- 사람이 둘 이상이면 05의 Cloud SQL·배포와 06의 로컬 편집·게시 검증을 02부터 병행할 수 있습니다.
- 12는 [사전 등재 기준](../adr/0003-사전-등재-기준.md)(2026-09-29)으로 더한 데이터 작업입니다. 번호는 마지막이지만 다른 계획을 기다리지 않고 바로 시작할 수 있습니다.

2026-09-28에 전체 파이프라인 Cloud Run Job과 Gemma 전용 GPU 배포를 계획에서 철회했습니다. 근거·비용·실시간 요청의 처리 경계는 [Gemma 로컬 편집 엔진 결정](../AI-개발/Gemma-로컬-편집-엔진-결정.md)을 봅니다.

2026-09-28에 `prototype/trend`를 메인 앱(`apps/trend-api`, `apps/trend-web`)으로 승격했고, 이전 실습 앱의 배포 job은 제거했습니다.
아래 archive의 계획은 **번호가 같아도 현재 계획과 별개**이며 구현과 운영 검증을 마친 기록입니다.

## 완료 계획

다음 계획은 구현과 검증을 마쳐 [archive](archive/)에 보관했습니다.

| ID | 완료 작업 |
| --- | --- |
| [Archive 01](archive/01-environment-reproducibility.md) | 개발환경 재현성과 진단 |
| [Archive 02](archive/02-model-evaluation.md) | 모델 평가와 비교 보고서 |
| [Archive 03](archive/03-local-model-history.md) | 실제 모델 실행 이력 연결 |
| [Archive 04](archive/04-database-recovery.md) | DB 변경과 백업·복구 |
| [운영 Archive 01](archive/01-production-alerting.md) | Discord 운영 알림 중계기 |
| [운영 Archive 03](archive/03-alert-delivery-hardening.md) | 알림 유지와 전달 검증 보완 |
| [운영 Archive 04](archive/04-ci-change-routing.md) | 변경 범위에 따른 CI와 배포 |
| [운영 Archive 05](archive/05-model-request-controls.md) | AI 요청량 제어와 결과 형식 검증 |
| [운영 Archive 06](archive/06-release-recovery.md) | 배포 기록과 안전 복구 경로 |

## 공통 원칙

- `develop`에서 작업하고 `release/gcp` push만 실제 GCP 배포를 시작합니다.
- 배포 전에 Compose 전체 검사와 인프라 검증을 통과시킵니다.
- 운영 로그와 알림에 원문, 생성 결과, API key를 포함하지 않습니다.
- GitHub와 GCP 설정을 바꾸면 문서의 현재 상태와 검증 결과도 함께 갱신합니다.
