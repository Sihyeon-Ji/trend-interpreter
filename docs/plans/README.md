# 계획

작성일 **2026-09-23** · 최종 갱신 **2026-10-10** · 제출 마감 **2026-10-18**

[운영 명령](../개발환경/개발-명령어.md) · [승인 배치 게시](../개발환경/승인-배치-게시.md) · [결정 기록](../adr/README.md) · [완료 계획과 지난 점검](archive/README.md)

인프라는 [Plan 17](archive/17-hybrid-infrastructure.md)의 구성(웹·API는 Cloud Run, DB는 Cloud SQL)으로 운영 중이다. Gemma는 수집 서버·Kaggle의 배치 단계에서 쓰고, 배포본에서 도는 모습은 [Gemma 실시간 분류(ejchoi)](ejchoi-gemma-live-classify.md)에서 다룬다. Gemma 실행 위치가 바뀐 경위는 [Plan 06](archive/06-gemma-on-cloud-run-gpu.md)과 [Gemma 로컬 편집 엔진 결정](../AI-개발/Gemma-로컬-편집-엔진-결정.md)에 남아 있다.

## 지금 상태 (10-10)

운영 웹·API·Cloud SQL·예약 백업·유지보수·게시 Job이 돈다. 10-10에 Plan 07·09·14·17·20을 마무리해 보관하고, 남은 일을 담당자별 계획으로 나눴다. 

- **품질:** 같은 12사례 9차 측정(사람 검토) – 어울리는 추천 91%, 위험한데 '없음' 0, 카피 즉시 사용성 2.50/3([Plan 09](archive/09-generation-quality-evaluation.md)). AI 초안을 지시현이 검토한 값이라 독립된 사람 판정으로 세지 않는다.
- **운영 데이터(10-10):** 추천 후보 36개 리스크 사람 판정, 드림코어·Meme coin·草·The cake is a lie 쓰임 낱말 고정, 草·도도독 뜻 수정.
- **배포(10-10):** 해시태그 중복 수정, 만들기 결과물의 언어 섞임 차단, 되돌리기 점검의 secret 별칭 수정. release 되돌리기 훈련 실행.
- **남은 문제:** 일본 화장품·러닝화·가계부와 한국 화장품은 추천 후보가 없다([밈 추천 남은 일](ktwoo-meme-recommendation-remaining.md)).

## 다음 순서

계획 문서 이름은 두 가지다. 정해진 날에 하는 일은 실행일(`2026-10-16-` 등), 마감까지 하는 일은 담당자(`shji-`·`ejchoi-`·`ktwoo-`·`sng_j-`)로 시작한다.

1. **10-14 코드 동결까지** – [Gemma 실시간 분류](ejchoi-gemma-live-classify.md)(ejchoi), [문구 흐름과 일본어 화면](ktwoo-copy-flow-and-japanese-ui.md)·[밈 추천 남은 일](ktwoo-meme-recommendation-remaining.md)(ktwoo).
2. **10-15 밤** – [수집 서버 스냅숏](2026-10-15-collection-server-snapshot.md)(ktwoo). 그때까지 서버 파이프라인은 fit 단계를 뺀다.
3. **10-16** – [마지막 운영 DB 갱신](2026-10-16-final-db-refresh.md)(shji).
4. **10-16 ~ 10-17** – 녹화([데모 영상](sng_j-demo-video.md), sng_j)와 [발표 자료](ejchoi-submission-deck.md)(ejchoi).
5. **10-17** – [저장소 공개 전환과 배포 승인](2026-10-17-public-repository.md)(shji). 10-18 제출.
6. **10-20 ~ 10-26** – [Cloud SQL 체험 종료 전 전환](2026-10-20-cloud-sql-transition.md), **10-27 ~ 10-28** [청구 확인](2026-10-27-billing-check.md)(shji).

GCP 리소스 생성·배포·결제와 운영 데이터 변경은 사용자 확인 뒤에 한다(`apps/trend-api/AGENTS.md`). 로컬 검사 통과는 운영 반영이나 AI 품질의 근거가 아니다.

## 현재 계획

### 날짜에 하는 일

| 실행일 | 계획 | 담당 | 할 일 | 완료 증거 |
| --- | --- | --- | --- | --- |
| 10-15 밤 | [2026-10-15-collection-server-snapshot](2026-10-15-collection-server-snapshot.md) | ktwoo | fit 단계 빼기(10-12 완료), 일본 후보 보강(진행 중), `db/latest` 업로드 | 업로드 시각 |
| 10-16 | [2026-10-16-final-db-refresh](2026-10-16-final-db-refresh.md) | shji | 마지막 운영 DB 갱신, 새 후보 쓰임 낱말·리스크, 12사례 재측정, 이전 DB 되돌리기 | 사람 결정 유지, 새 snapshot 시각으로 웹 열림 |
| 10-17 | [2026-10-17-public-repository](2026-10-17-public-repository.md) | shji | WIF 계정 분리, 이력 재검사, 공개, `gcp` environment 보호 | 외부·collaborator 계정의 거부·승인 확인 |
| 10-20 ~ 26 | [2026-10-20-cloud-sql-transition](2026-10-20-cloud-sql-transition.md) | shji | 체험 종료 전 유료 전환 또는 이전 | 체험 표시 소멸, 서비스 확인 |
| 10-27 ~ 28 | [2026-10-27-billing-check](2026-10-27-billing-check.md) | shji | 실제 청구 확인 | 항목별 예상치와 차이 |

### 마감까지 하는 일

| 계획 | 담당 | 작업 | 상태 | 다음 완료 증거 | 마감 |
| --- | --- | --- | --- | --- | --- |
| [ktwoo-copy-flow-and-japanese-ui](ktwoo-copy-flow-and-japanese-ui.md) | ktwoo | 문구 흐름 남은 일(승인 기록·재검사)과 일본어 화면(Plan 20) | 코드 완료 – develop 반영(10-12), 배포 전 | 승인 기록 서버 저장, 日本語 전환 | 10-14 |
| [ktwoo-meme-recommendation-remaining](ktwoo-meme-recommendation-remaining.md) | ktwoo | 밈 추천 남은 일 – 빈 시장, 실사진, 분야 구분(Plan 07) | 진행 중 – 결정 반영(10-12), 일본 보강 | 10-16 갱신본 12사례 재측정 | 10-14·10-16 |
| [ejchoi-gemma-live-classify](ejchoi-gemma-live-classify.md) | ejchoi | 배포본에서 Gemma가 도는 모습 – 실시간 분류·관리자 수동 실행(Plan 14 1·2단계, Plan 17 GCE) | 진행 중 – 1·2단계 로컬 구현 | 운영 GPU VM(지시현 확인), 버튼 실행 한 번과 청구 확인 | 10-14 |
| [ejchoi-submission-deck](ejchoi-submission-deck.md) | ejchoi | 제출 발표 자료 | 초안 파일 있음 | 양식 완성, 숫자마다 출처 | 10-17 |
| [sng_j-demo-video](sng_j-demo-video.md) | sng_j | 데모 시나리오와 영상 | 시나리오 초안 v3 | 배포본 녹화 3분 미만 | 10-17 |

## 완료 계획

구현과 검증을 마친 계획은 [archive](archive/)에 보관한다. 과거 계획은 번호가 같아도 현재 계획과 별개다. 지난 점검 보고서(09-29~10-06)와 변경 공유(10-05)도 [archive](archive/README.md)에 있다.

| ID | 완료 작업 |
| --- | --- |
| [Plan 07](archive/07-meme-recommendation.md) | 사진·문구 기반 밈 추천 – 규칙·쓰임 낱말 고정까지(10-10). 남은 일은 [밈 추천 남은 일](ktwoo-meme-recommendation-remaining.md) |
| [Plan 09](archive/09-generation-quality-evaluation.md) | 추천·생성 품질 평가 – 같은 12사례 9차 측정·사람 검토(10-10). 데모는 [데모 영상](sng_j-demo-video.md) |
| [Plan 14](archive/14-gemma-visible-in-deployment.md) | 배포본 Gemma 기록 표시(0단계)에서 마무리(10-10). 1·2단계는 [Gemma 실시간 분류](ejchoi-gemma-live-classify.md) |
| [Plan 17](archive/17-hybrid-infrastructure.md) | 하이브리드 인프라 – 운영·승인 게시·거부 경로·되돌리기 확인(10-10) |
| [Plan 20](archive/20-copy-check-localization-flow.md) | 문구 검사·현지화 흐름 – 방향·무대 화면(10-10). 남은 일은 [문구 흐름과 일본어 화면](ktwoo-copy-flow-and-japanese-ui.md)·[문구 흐름과 일본어 화면](ktwoo-copy-flow-and-japanese-ui.md) |
| [Archive 01](archive/01-environment-reproducibility.md) | 개발환경 재현성과 진단 |
| [Plan 02](archive/02-lifecycle-stages.md) | 쓰임 근거 있는 검증 용어의 생애주기·확산 판정과 화면 표시(10-06) |
| [Plan 04](archive/04-target-regions-and-keyword-dashboard.md) | 목표 지역 선택·키워드 대시보드, 10개국 검색어 수집 확인(10-08) |
| [Plan 03](archive/03-term-risk.md) | 용어별 리스크 판정, 표본 20개 일치율(10-09). 근거 문장 분류 품질은 Plan 06 |
| [Plan 08](archive/08-content-generation.md) | SNS 카피·숏폼 대본·썸네일 생성, 밈 소개 문구·짤 이름 처리(10-09). 품질 평가는 Plan 09 |
| [Plan 12](archive/12-dictionary-crosscheck.md) | 확인된 사전 항목의 위키 대조와 '문서 대조' 단계(10-09). 확대 사전 대조는 제출 뒤 |
| [Plan 15](archive/15-overseas-generation-signals.md) | 해외 세대의 실측·추정 구별과 검색 관심 분리(10-09). 계정 기반 2·3단계는 제출 뒤 |
| [Plan 06](archive/06-gemma-on-cloud-run-gpu.md) | Kaggle 학습·DVC/GCS – **중단**(10-09). 전체 QLoRA·사람 정답 봉인·영어 뜻 첫 승인 게시까지. 팀 재현·모델 비교는 하지 않음 |
| [옛 Plan 11·13·19](archive/19-production-data-refresh.md) | 공개 저장소·Cloud SQL 유료 전환·운영 DB 갱신 – 새 [10-16 운영 DB 갱신](2026-10-16-final-db-refresh.md)에 합침(10-09) |
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
