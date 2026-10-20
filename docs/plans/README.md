# 계획

작성일 **2026-09-23** · 최종 갱신 **2026-10-20** · 제출 완료 **사용자 확인**

[운영 명령](../개발환경/개발-명령어.md) · [승인 배치 게시](../개발환경/승인-배치-게시.md) · [결정 기록](../adr/README.md) · [완료 계획과 지난 점검](archive/README.md)

인프라는 [Plan 17](archive/17-hybrid-infrastructure.md)의 구성(웹·API는 Cloud Run, DB는 Cloud SQL)으로 운영 중이다. Gemma는 수집 서버·Kaggle의 배치 단계에서 쓰고, 배포본에서 도는 모습은 [Gemma 실시간 분류(ejchoi)](archive/ejchoi-gemma-live-classify.md)에서 다룬다. Gemma 실행 위치가 바뀐 경위는 [Plan 06](archive/06-gemma-on-cloud-run-gpu.md)과 [Gemma 로컬 편집 엔진 결정](../AI-개발/Gemma-로컬-편집-엔진-결정.md)에 남아 있다.

## 지금 상태 (10-10)

운영 웹·API·Cloud SQL·예약 백업·유지보수·게시 Job이 돈다. 10-10에 Plan 07·09·14·17·20을 마무리해 보관하고, 남은 일을 담당자별 계획으로 나눴다. 

- **품질:** 같은 12사례 9차 측정(사람 검토) – 어울리는 추천 91%, 위험한데 '없음' 0, 카피 즉시 사용성 2.50/3([Plan 09](archive/09-generation-quality-evaluation.md)). AI 초안을 지시현이 검토한 값이라 독립된 사람 판정으로 세지 않는다.
- **운영 데이터(10-10):** 추천 후보 36개 리스크 사람 판정, 드림코어·Meme coin·草·The cake is a lie 쓰임 낱말 고정, 草·도도독 뜻 수정.
- **배포(10-10):** 해시태그 중복 수정, 만들기 결과물의 언어 섞임 차단, 되돌리기 점검의 secret 별칭 수정. release 되돌리기 훈련 실행.
- **남은 문제:** 일본 화장품·러닝화·가계부와 한국 화장품은 추천 후보가 없다([밈 추천 남은 일](archive/ktwoo-meme-recommendation-remaining.md)). → 10-14 갱신·일본 보강으로 풀렸다(아래).

**10-16 갱신.** 운영 DB 갱신을 10-14 에 앞당겨 했다(`trend_20261014`, [실행 기록](archive/2026-10-16-final-db-refresh.md#10-14-실행-기록)). 10-15 에 비밈 14개 제외·요청 제한 180/150초·`reviewer` 계정을 더했고, 같은 12사례 10차를 운영에서 쟀다(11/12 완료, 위험 누락 0, AI 채점만). ktwoo 가 마친 계획 넷 – [10-16 운영 DB 갱신](archive/2026-10-16-final-db-refresh.md)·[수집 서버 스냅숏](archive/2026-10-15-collection-server-snapshot.md)·[밈 추천 남은 일](archive/ktwoo-meme-recommendation-remaining.md)·[문구 흐름과 일본어 화면](archive/ktwoo-copy-flow-and-japanese-ui.md) – 을 보관했다.

**10-16 결정(지시현).** 운영 GPU VM은 만들지 않는다(Gemma 실시간 분류는 코드만 운영에, [보관](archive/ejchoi-gemma-live-classify.md)). 저장소 이름을 `Sihyeon-Ji/trend-interpreter`로 바꾸고 오래된 원격 브랜치를 지웠다. 덱·영상 숫자는 4~9차(사람 검토)를 그대로 쓴다. 이전 DB 되돌리기 훈련은 하지 않는다.

**10-19 비용 결정(지시현).** Cloud SQL 월 $30은 상한이 아니며, 심사 기간의 운영 안정성을 비용 절감보다 우선한다. 계획대로 `db-g1-small`을 선택하고 전환 뒤 응답 시간·메모리·연결 수를 확인한다([10-20 전환](archive/2026-10-20-cloud-sql-transition.md)).

**10-20 전환 완료.** 운영 DB·API·Job을 `trend-production-sql`로 옮기고 복원·조회·검수 로그인을 확인했다. 옛 체험 인스턴스는 삭제됐다([실행 기록](archive/2026-10-20-cloud-sql-transition.md)). 실제 청구는 10-27에 확인하고, 게시 신선도 경보는 수집 중단에 맞춰 유지보수 Job 기준을 1488시간으로 올려 해소했다([#16](https://github.com/Sihyeon-Ji/trend-interpreter/issues/16), [운영 문서](../운영/GCP-운영.md#유지보수-job)).

**10-20 제출 확인.** 사용자가 최종 제출 완료를 확인했고 포털의 `Submitted` 상태와 평가 진행 화면을 공유했다. 화면은 Git 제외 경로에 보관했다. 정확한 접수 시각과 양식 입력 세부는 보이지 않는다([제출 기록](archive/2026-10-18-final-submission.md), [체크리스트](../대회/제출/제출-준비-체크리스트.md)).

## 다음 순서

1. **10-27 ~ 10-28** – [청구 확인](2026-10-27-billing-check.md)(shji).

GCP 리소스 생성·배포·결제와 운영 데이터 변경은 사용자 확인 뒤에 한다(`apps/trend-api/AGENTS.md`). 로컬 검사 통과는 운영 반영이나 AI 품질의 근거가 아니다.

## 현재 계획

### 날짜에 하는 일

| 실행일 | 계획 | 담당 | 할 일 | 완료 증거 |
| --- | --- | --- | --- | --- |
| 10-27 ~ 28 | [2026-10-27-billing-check](2026-10-27-billing-check.md) | shji | 실제 청구와 옛 인스턴스 삭제 후 과금 확인 | 항목별 예상치와 차이 |

## 완료 계획

구현과 검증을 마친 계획은 [archive](archive/)에 보관한다. 최종 제출 상태 화면도 10-20에 비공개로 보관하고 계획을 archive로 옮겼다. 과거 계획은 번호가 같아도 현재 계획과 별개다. 지난 점검 보고서(09-29~10-06)와 변경 공유(10-05)도 [archive](archive/README.md)에 있다.

| ID | 완료 작업 |
| --- | --- |
| [Cloud SQL 전환](archive/2026-10-20-cloud-sql-transition.md) | `trend-production-sql`로 운영 DB·서비스·Job 이전, 로컬·GCS 복원 검증, 옛 인스턴스 삭제(10-20). 청구는 10-27. 게시 경보는 10-20 기준 상향으로 해소(#16) |
| [최종 제출](archive/2026-10-18-final-submission.md) | 최종 제출 완료(10-19 사용자 확인, 10-20 `Submitted` 화면 확인·비공개 보관). 정확한 접수 시각과 양식 세부는 화면에 없음 |
| [제출 발표 자료](archive/ejchoi-submission-deck.md) | 제출용 PDF·링크·GPU 문장 정리 완료(10-17). 이번 PDF 검수의 후속 수정과 실제 제출은 별도 확인 |
| [제출 데모 영상](archive/sng_j-demo-video.md) | 2분 53초 영상 업로드 완료(10-17). 실제 제출은 [최종 제출 기록](archive/2026-10-18-final-submission.md) |
| [ejchoi 작업 인수인계](archive/ejchoi-작업-인수인계.md) | 인수인계 종료(10-17). 남은 수정·실제 제출은 [최종 제출 기록](archive/2026-10-18-final-submission.md)으로 이관 |
| [ejchoi 확인 요청](archive/ejchoi-확인-요청.md) | 10-16 결정·10-17 제작 완료로 요청 기록 종료. GPU는 미구축 결정이며 실행 완료가 아님 |
| [저장소 공개 전환](archive/2026-10-17-public-repository.md) | `Sihyeon-Ji/trend-interpreter` 공개, 배포는 `release/gcp`에서만(승인 없음), 외부 계정 push 거부 확인(10-16, 하루 앞당김) |
| [Gemma 실시간 분류](archive/ejchoi-gemma-live-classify.md) | 1·2단계 코드 운영 반영, 심사용 읽기 전용 계정. 운영 GPU는 만들지 않음(10-16 보관) |
| [10-16 운영 DB 갱신](archive/2026-10-16-final-db-refresh.md) | 스냅숏 `20261014T134313-8887867` → `trend_20261014`, 사람 결정 누락 0, API·Job 전환(10-14, ktwoo 마무리). 복원 검증·되돌리기 훈련은 하지 않음(10-16 보관) |
| [수집 서버 스냅숏](archive/2026-10-15-collection-server-snapshot.md) | 마지막 스냅숏 `20261014T134313-8887867`, fit 빼기, 일본 보강(카드 46 → 124)(10-16 보관) |
| [밈 추천 남은 일](archive/ktwoo-meme-recommendation-remaining.md) | 빈 시장 해소, 10차 재측정(운영, 11/12·위험 누락 0, AI 채점)(10-16 보관) |
| [문구 흐름과 일본어 화면](archive/ktwoo-copy-flow-and-japanese-ui.md) | 승인 기록·재검사·일본어 화면 운영 확인(승인 2건)(10-16 보관). ⑥ 조사 요청 등은 제출 뒤 과제 |
| [Plan 07](archive/07-meme-recommendation.md) | 사진·문구 기반 밈 추천 – 규칙·쓰임 낱말 고정까지(10-10). 남은 일은 [밈 추천 남은 일](archive/ktwoo-meme-recommendation-remaining.md) |
| [Plan 09](archive/09-generation-quality-evaluation.md) | 추천·생성 품질 평가 – 같은 12사례 9차 측정·사람 검토(10-10). 데모는 [데모 영상](archive/sng_j-demo-video.md) |
| [Plan 14](archive/14-gemma-visible-in-deployment.md) | 배포본 Gemma 기록 표시(0단계)에서 마무리(10-10). 1·2단계는 [Gemma 실시간 분류](archive/ejchoi-gemma-live-classify.md) |
| [Plan 17](archive/17-hybrid-infrastructure.md) | 하이브리드 인프라 – 운영·승인 게시·거부 경로·되돌리기 확인(10-10) |
| [Plan 20](archive/20-copy-check-localization-flow.md) | 문구 검사·현지화 흐름 – 방향·무대 화면(10-10). 남은 일은 [문구 흐름과 일본어 화면](archive/ktwoo-copy-flow-and-japanese-ui.md) |
| [Archive 01](archive/01-environment-reproducibility.md) | 개발환경 재현성과 진단 |
| [Plan 02](archive/02-lifecycle-stages.md) | 쓰임 근거 있는 검증 용어의 생애주기·확산 판정과 화면 표시(10-06) |
| [Plan 04](archive/04-target-regions-and-keyword-dashboard.md) | 목표 지역 선택·키워드 대시보드, 10개국 검색어 수집 확인(10-08) |
| [Plan 03](archive/03-term-risk.md) | 용어별 리스크 판정, 표본 20개 일치율(10-09). 근거 문장 분류 품질은 Plan 06 |
| [Plan 08](archive/08-content-generation.md) | SNS 카피·숏폼 대본·썸네일 생성, 밈 소개 문구·짤 이름 처리(10-09). 품질 평가는 Plan 09 |
| [Plan 12](archive/12-dictionary-crosscheck.md) | 확인된 사전 항목의 위키 대조와 '문서 대조' 단계(10-09). 확대 사전 대조는 제출 뒤 |
| [Plan 15](archive/15-overseas-generation-signals.md) | 해외 세대의 실측·추정 구별과 검색 관심 분리(10-09). 계정 기반 2·3단계는 제출 뒤 |
| [Plan 06](archive/06-gemma-on-cloud-run-gpu.md) | Kaggle 학습·DVC/GCS – **중단**(10-09). 전체 QLoRA·사람 정답 봉인·영어 뜻 첫 승인 게시까지. 팀 재현·모델 비교는 하지 않음 |
| [옛 Plan 11·13·19](archive/19-production-data-refresh.md) | 공개 저장소·Cloud SQL 유료 전환·운영 DB 갱신 – 새 [10-16 운영 DB 갱신](archive/2026-10-16-final-db-refresh.md)에 합침(10-09) |
| [Plan 05](archive/05-trend-cloud-run-deployment.md) | 웹·API·Cloud SQL 배포와 백업·유지보수·승인 게시(10-09 보관, 완료 기준 8개 중 5개). Job 이미지·Gemini 0회 확인은 Plan 17, 체험 결정은 Plan 13 |
| [Plan 01](archive/01-import-latest-trend-data.md) | 고정 스냅숏의 Cloud SQL 이관(10-09 보관). 운영 이관·갱신은 Plan 19, 게시는 승인 게시가 이어받음. 수집 서버 PostgreSQL 전환은 수집 서버 담당 |
| [Plan 16](archive/16-wiki-meme-catalog-and-tendency.md) | 위키 밈 분류 등재와 성향 분석 – 뜬 해 있는 용어 3,006개까지 하고 **보류**(10-09). 재시도·뜻 품질 검수는 제출 뒤 |
| [Plan 10](archive/10-term-relation-graph.md) | 용어 관계 그래프 – 미착수로 **보류**(10-09) |
| [Archive 02](archive/02-model-evaluation.md) | 모델 평가와 비교 보고서 |
| [Archive 03](archive/03-local-model-history.md) | 실제 모델 실행 이력 연결 |
| [Archive 04](archive/04-database-recovery.md) | DB 변경과 백업·복구 |
| [운영 Archive 01](archive/01-production-alerting.md) | Discord 운영 알림 중계기 |
| [운영 Archive 03](archive/03-alert-delivery-hardening.md) | 알림 유지와 전달 검증 보완 |
| [운영 Archive 04](archive/04-ci-change-routing.md) | 변경 범위에 따른 CI와 배포 |
| [운영 Archive 05](archive/05-model-request-controls.md) | AI 요청량 제어와 결과 형식 검증 |
| [운영 Archive 06](archive/06-release-recovery.md) | 배포 기록과 안전 복구 경로 |
| [Archive 18](archive/18-ci-parallelization.md) | CI 병렬화와 배포 시간 단축(16분 → 약 6분, 10-05) |
| [Archive 20](archive/20-trend-operations-schedule.md) | 운영 일정 8개·후속 작업 4개 GitHub Project 등록(10-05) |

## 공통 원칙

- `develop`에서 작업하고 `release/gcp` push만 실제 GCP 배포를 시작한다.
- 배포 전에 Compose 전체 검사와 인프라 검증을 통과시키고, 배포 뒤 서비스를 확인한다.
- 운영 로그와 알림에 원문, 생성 결과, API key를 넣지 않는다.
- GitHub와 GCP 설정을 바꾸면 해당 계획의 상태와 검증 결과도 갱신한다.
