# 계획

작성일 **2026-09-23** · 최종 갱신 **2026-10-09** · 제출 마감 **2026-10-18**

[운영 명령](../개발환경/개발-명령어.md) · [승인 배치 게시](../개발환경/승인-배치-게시.md) · [결정 기록](../adr/README.md) · [완료 계획과 지난 점검](archive/README.md)

인프라는 [Plan 17](17-hybrid-infrastructure.md)의 하이브리드 구성(웹·API는 Cloud Run, DB는 Cloud SQL, Gemma 서빙은 GCE GPU, 학습·데이터 공유는 Kaggle + DVC/GCS)을 따른다. Gemma 실행 위치가 바뀐 경위는 [Plan 06](06-gemma-on-cloud-run-gpu.md)과 [Gemma 로컬 편집 엔진 결정](../AI-개발/Gemma-로컬-편집-엔진-결정.md)에 남아 있다.

## 지금 상태 (10-09)

운영 웹·API·Cloud SQL·예약 백업·유지보수 Job은 돌고 있다. 제출 전에 남은 핵심은 추천 품질, 승인 게시의 운영 적용, 데이터 갱신 두 번(10-10·10-16)과 공개 전환(10-17)이다.

- **배포:** 10-09에 `release/gcp`로 여러 번 배포했다. 실측 세대만 표시(Plan 15), 리스크 민감 소재 오탐 수정(Plan 03), 만들기 프롬프트 개선(Plan 09), 사용 자제·욕설 표제어의 공개 숨김(Plan 03), 웹 의존성 보안 수정(`next` 16.3.8)이 들어갔고 migration 018~021이 운영 DB에 적용됐다([Plan 05](05-trend-cloud-run-deployment.md#2026-10-09-배포-네-번과-운영-확인)).
- **판정:** 리스크 표본 20개(Plan 03), 추천·만들기 네 차례(Plan 09), 밈 여부 라벨 116개, 추천 후보 쓰임 낱말 170개 검토를 받았다. 모두 AI 초안을 지시현이 검토한 값이라 독립된 사람 판정으로 세지 않는다. 같은 12사례에서 추천 어울림 40 → 85%, 카피 즉시 사용성 2.0 → 2.75/3이다.
- **운영 데이터:** Know Your Meme·relatable·거시기를 사람 결정으로 사전에서 뺐다. 관리 화면 리스크 표에서 8건을 사람이 정했다(アヘ顔·2 Girls 1 Cup 등 사용 자제, 표제어 오탐 1건 해제, [Plan 03](03-term-risk.md#2026-10-09-공개-숨김과-운영-리스크-사람-결정)). 리스크 규칙 수정은 다음 갱신(Plan 19)에서 운영 수준에 반영된다.
- **추천의 남은 문제:** 일본 화장품·러닝화·가계부와 한국 화장품은 추천이 0이다(알맞은 후보가 사전에 없다). 한국 카드 101개 중 56개가 식어 가는 밈, 31개가 친근한 톤에 맞지 않는 말투라 빠진다. 이름뿐인 밈(Wojak)이 해시태그로만 들어간다. 같은 문구라도 실행마다 제품 이해가 달라 추천이 바뀐다.

## 다음 순서

1. 10-10 운영 데이터 갱신(Plan 19)과 리스크 재판정. 사람·Gemini가 붙인 쓰임 낱말은 이어지는지 확인하고, 새로 들어온 후보만 `fit_backfill.py --gemini`로 붙인 뒤 같은 12사례 재측정.
2. 이름뿐인 밈(meme_name)을 해시태그 대신 썸네일·짤 구성안에 넣기, 제품 이해를 고정해 같은 문구에 같은 추천이 나오게 하기(Plan 07·08).
3. 승인 게시의 운영 로그인·secret·Job 적용(Plan 05·06·17).
4. 데모 시나리오 3개를 배포본에서 재현하고 영상·덱을 만든다(Plan 09). 시나리오는 새 화면 기준 v3. 화면에 나올 말의 영어 뜻 60개를 승인 배치로 운영에 준비했고(`draft`) 승인·게시가 남았다(Plan 06).
5. 10-16 마지막 갱신, 10-17 공개 전환(Plan 11). Cloud SQL 유료 전환 판단은 10-26 전(Plan 13).

GCP 리소스 생성·배포·결제와 운영 데이터 변경은 사용자 확인 뒤에 한다(`apps/trend-api/AGENTS.md`). 로컬 검사 통과는 운영 반영이나 AI 품질의 근거가 아니다.

## 현재 계획

| ID | 작업 | 상태 | 다음 완료 증거 | 목표일 |
| --- | --- | --- | --- | --- |
| [01](01-import-latest-trend-data.md) | 고정 스냅숏의 Cloud SQL 이관 | Cloud SQL 적재·첫 운영 갱신 완료 | 수집 서버 PostgreSQL 전환, 같은 입력 이관 재현, 승인 게시 운영 기록 | 10-01 |
| [03](03-term-risk.md) | 용어별 리스크 판정 | verified 7,655개 판정. 검토 표본 20/20(AI 초안 검토 · 뽑을 때 규칙과 14/20, 현행 규칙 보정 뒤 13/20). 민감 소재 오탐 82개 수정 | 근거 문장 분류 품질 개선(e4b 재분류 흔들림이 큼), 분류 공급 갱신 | 10-04 |
| [05](05-trend-cloud-run-deployment.md) | 웹·API·Cloud SQL 배포와 백업·유지보수 | 운영 배포·release 경로·예약 백업/유지보수 운영 중 | 승인 게시, 복구·경보 실측 | 10-09 |
| [06](06-gemma-on-cloud-run-gpu.md) | Kaggle 학습·DVC/GCS·승인 게시 | 전체 QLoRA 실행·사람 정답 20건 봉인·번역 시험 | 팀 재현, 봉인 정답 모델 비교, 실제 승인 게시 | 10-10 |
| [07](07-meme-recommendation.md) | 사진·문구 기반 밈 추천 | 추천·사진 흐름 구현. 쓰임 낱말에 밈 종류·사용층을 더하고 인물·작품·특정 팬덤·분야 밖 일반 낱말을 거름, 후보 170개 사람 검토(10-09) | 빈 시장 후보 보강, 제품 이해 흔들림 줄이기, 실사진 평가 | 10-12 |
| [08](08-content-generation.md) | SNS 카피·숏폼 대본·썸네일 생성 | 생성·호출 한도 구현, 밈 소개 문구 거르기(`meta_meme`) 추가 | 브랜드와 맞지 않는 이름을 해시태그에서도 빼기, 뜻 충실도 평가 | 10-14 |
| [09](09-generation-quality-evaluation.md) | 추천·생성 품질 평가와 데모 | 7차 측정·검토 판정 네 차례(어울림 85% · 사용성 2.75/3) | 사진 평가, 배포본 데모 3개·영상·덱 | 10-15 |
| [10](10-term-relation-graph.md) | 용어 관계 그래프(선택) | 미착수 | 근거 있는 용어 관계와 원조 추적 5사례 | 여유 시 |
| [11](11-public-repository-release-protection.md) | 공개 저장소 전환과 배포 승인 | 전체 이력 재검사 완료, WIF 분리는 별도 브랜치 | 코드 적용, 공개·보호 설정, 실제 계정 검증 | 10-17 |
| [12](12-dictionary-crosscheck.md) | 확인된 사전 항목의 위키 대조 | 과거 165개 처리, verified 대조 170/7,654 | 확대 사전 대조와 팀 DB 반영 | 10-04 |
| [13](13-cloud-sql-trial-to-paid-transition.md) | Cloud SQL 체험 종료 전 유료 전환 | 계획 | 만료·비용 확인 뒤 전환 또는 이전 결정 | 10-26 |
| [14](14-gemma-visible-in-deployment.md) | 배포본에서 Gemma 활용 보이기 | 모델 기록 표시 구현 | 배포본 확인, GPU 관리자 실행·중단 검증 | 10-12 |
| [15](15-overseas-generation-signals.md) | 해외 세대·관심 신호 | 비한국어 검색 관심 260/386개, 실측 세대 0개. 모델 추정 세대는 공개 화면에서 숨김(10-09 배포) | 해외 연령 실측 자료와 외부 계정 확장 | 10-10 |
| [16](16-wiki-meme-catalog-and-tendency.md) | 위키 밈 분류 등재와 성향 분석 | 뜬 해 있는 용어 3,006개 | 조사 중 28개·카탈로그 실패 189건 재시도, 뜻 품질 사람 검수 | 10-06 |
| [17](17-hybrid-infrastructure.md) | 하이브리드 인프라 통합 | 운영 웹/API·Cloud SQL·GCE 추론 시험·예약 운영 | 팀 재현, 모델 승격, 승인 게시, 최종 평가 | 10-12 |
| [19](19-production-data-refresh.md) | 사람의 결정을 지키는 운영 DB 갱신 | 첫 전환(10-05, `trend_20261005`) | 10-10 갱신·보호 데이터 보존·복구 검증, 10-16 마지막 갱신 | 10-10 |
| [20](20-copy-check-localization-flow.md) | 문구 검사·현지화·승인 흐름 | '무대' 화면 개편 반영(시장은 한국·일본·영어권), 포스터 backend 일부 | 일본어 화면, 승인/공유 결정과 구현 | 10-14 |

## 완료 계획

구현과 검증을 마친 계획은 [archive](archive/)에 보관한다. 과거 계획은 번호가 같아도 현재 계획과 별개다. 지난 점검 보고서(09-29~10-06)와 변경 공유(10-05)도 [archive](archive/README.md)에 있다.

| ID | 완료 작업 |
| --- | --- |
| [Archive 01](archive/01-environment-reproducibility.md) | 개발환경 재현성과 진단 |
| [Plan 02](archive/02-lifecycle-stages.md) | 쓰임 근거 있는 검증 용어의 생애주기·확산 판정과 화면 표시(10-06) |
| [Plan 04](archive/04-target-regions-and-keyword-dashboard.md) | 목표 지역 선택·키워드 대시보드, 10개국 검색어 수집 확인(10-08) |
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
