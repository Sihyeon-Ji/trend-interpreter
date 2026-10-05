# Plan 18. CI 병렬화와 배포 시간 단축

작성일 **2026-10-04** · 상태 **완료(10-05) – 16분에서 약 6분으로 단축, 완료 기준 세 가지 확인** · staging은 두지 않음(10-04 결정) · 연계 [Plan 05](../05-trend-cloud-run-deployment.md), [Plan 17](../17-hybrid-infrastructure.md) · 목표일 **2026-10-08**

[현재 계획](../README.md) · [Cloud Run 서비스 준비](../../개발환경/Cloud-Run-서비스-준비.md) · [GCP 운영](../../운영/GCP-운영.md)

## 1. 배경

`release/gcp` push 한 번에 약 16분이 걸린다. Trend 앱이 바뀔 때마다 비슷하게 걸리고, 문서만 바뀌면 `scripts/release_scope.py`가 검사와 배포를 건너뛴다. 10-04 성공 실행(run 37165654584, push부터 끝까지 15분 38초)의 실제 단계별 시간은 아래와 같다.

| job | 단계 | 시간 |
| --- | --- | --- |
| `checks / verify` (10분 44초) | `check` – 개발 이미지 빌드 약 95초 + Python·웹 테스트·lint·build 약 105초 | 210초 |
| | `audit-check` · `gateway-check` | 58초 · 8초 |
| | `security-check` · 개발 스택 기동 | 11초 · 14초 |
| | `e2e` – 브라우저 이미지 빌드 약 45초 + 예열 41초 + 테스트 43개 118초 | 228초 |
| | `infra-check` | 15초 |
| | API·웹·relay 이미지 빌드 + smoke | 19초 + 59초 + 8초 + 4초 + 2초 |
| `trend_app` (4분 40초) | API·웹 이미지 빌드·push | 61초 + 101초 |
| | 후보 검사·트래픽 전환(`deploy-trend.sh`) | 79초 |

모든 단계가 job 하나에서 차례로 돈다. 서로 기다릴 이유가 없는 검사가 대부분이다. 같은 API·웹 이미지를 CI와 배포 job이 두 번 빌드하고, 배포 job의 빌드(약 2분 40초)는 검사가 끝난 뒤에야 시작한다.

## 2. 목표와 지켜야 할 조건

- `release/gcp` push부터 production 전환까지 **8분 이내**(벽시계 시간).
- 검사가 하나라도 실패하면 배포하지 않는다. 지금의 안전 조건(후보 검사 실패 시 트래픽 유지, 이미지 digest 고정)은 그대로 둔다.
- 로컬 명령(`docker compose run --rm --build check` 등)은 바꾸지 않는다. CI는 같은 Compose 서비스를 나눠 부르기만 한다.

## 3. 설계

### 3.1 CI를 병렬 job으로 나누기

`ci.yml`의 `verify`를 서로 독립적인 job으로 나눈다. `release-gcp.yml`의 `checks`는 지금처럼 `ci.yml`을 부르고, 배포 job은 모든 job이 성공해야 시작한다.

| job | 실행 | 비고 |
| --- | --- | --- |
| `app` | `check` | Python·웹 단위 테스트, lint, build |
| `models` | `audit-check`, `gateway-check` | 모델 쪽 독립 lockfile |
| `static` | `security-check`, `infra-check` | 빌드가 거의 없어 가장 빠르다 |
| `e2e` | 개발 스택 기동 → `e2e` | 가장 길다. 실패 artifact 수집은 이 job으로 옮긴다 |
| `images` | API·웹·relay 이미지 빌드 → smoke | 아래 3.2의 캐시를 쓴다 |

벽시계 시간은 가장 긴 `e2e`(개발·브라우저 이미지 빌드 약 2분 20초 + 기동 + 예열·테스트 약 2분 40초, 합 약 5분 20초)로 정해진다.

### 3.2 배포 이미지 선빌드와 빌드 캐시 공유

- **배포 이미지는 검사와 동시에 만든다(10-05 적용).** `release-gcp.yml`의 `trend_app`을 둘로 나눴다. `trend_images`는 `scope`만 기다려 API·웹 이미지를 빌드해 Artifact Registry에 push하고 digest를 output으로 넘긴다. `trend_app`은 `checks`와 `trend_images`가 모두 성공해야 시작하고, 넘겨받은 digest로 `deploy-trend.sh`만 실행한다. push된 이미지는 트래픽을 받지 않으므로 "검사 실패 시 배포하지 않는다"는 조건은 그대로다. 빌드 약 2분 40초가 검사 뒤의 임계 경로에서 빠진다. 인증은 release workflow 안에서만 하므로 `ci.yml`은 GCP 인증 없이 수동 실행할 수 있다.
- `images` job은 `docker build` 대신 `docker/build-push-action`(`load: true`)으로 빌드하고 배포와 같은 GitHub Actions 캐시 scope(`trend-api`·`trend-web`·`alert-relay`)를 읽고 쓴다. 같은 실행 안에서는 두 job이 동시에 돌아 서로의 캐시를 쓰지 못하지만, 다음 실행부터는 lockfile이 그대로면 의존성 층을 다시 만들지 않는다.
- **개발 이미지(`Dockerfile.dev`) 캐시는 보류한다.** 병렬 job들은 같은 실행 안에서 동시에 빌드하므로 서로의 캐시를 쓸 수 없다. 다음 실행을 위해 GitHub Actions 캐시에 남기려면 `docker-container` builder가 필요하고, 이 builder는 1GB 이상의 개발 이미지를 서비스마다 docker로 다시 옮겨(load) 빌드 시간 절약분(약 1분)을 상당 부분 잃는다. 개발·브라우저·audit 이미지 층이 저장소 캐시 한도(10GB)를 채워 배포 이미지 캐시를 밀어낼 위험도 있다. 실측에서 8분을 넘기면 다시 검토한다.

### 3.3 그 밖의 단축

- **E2E는 production 이미지를 대상으로 돈다(10-05 적용).** `e2e`는 개발 서버(`api`·`web`) 대신 `apps/trend-api`·`apps/trend-web` Dockerfile로 만든 `e2e-api`·`e2e-web`을 연다. 개발 서버 첫 컴파일 때문에 필요했던 예열(`e2e/global-setup.ts`)은 지웠다. `browser-tests` 이미지는 개발 이미지 위가 아니라 `tooling` 위에 웹 패키지와 Chromium만 올린다. 그래서 `e2e` job은 큰 개발 이미지를 만들지 않고, api·web 이미지를 두 번 내보내지도 않는다. CI는 세 이미지를 `docker compose build` 한 번으로 병렬 빌드한 뒤 `run`한다. 로컬 명령 `docker compose run --rm --build e2e`는 그대로다.
- 바뀐 경로에 따라 job을 건너뛰는 방식(예: 웹만 바뀌면 `models` 생략)은 검사 누락 위험이 있어 이번 범위에서 제외한다.

## 4. staging – 두지 않음 (10-04 결정)

`release/gcp`는 production만 배포한다. 10-03에 만든 staging 웹·API는 작업자가 로컬에서 직접 배포했고 자동 경로가 없었다. 공모전 제출물 하나를 팀이 함께 고치는 상황이라 사용자는 staging을 두지 않기로 했다. production 배포에는 이미 같은 역할의 안전장치가 있다. CI 전체 검사를 통과해야 배포가 시작되고, 새 revision을 트래픽 없이 띄워 검사한 뒤에만 전환하며, `scripts/rollback-gcp.sh`로 이전 revision에 바로 되돌릴 수 있다.

10-04에 staging 웹·API 서비스, `trend_staging` DB와 사용자, staging 앱 secret 4개, staging 로그 제외 규칙을 삭제했다. GPU 검증에 쓴 staging 네트워크·서비스 계정·GPU gateway token·TLS/CA secret은 감사관 모델 시험용으로 남겼다.

## 5. 구현 순서

1. ~~최근 실행의 단계별 실제 시간을 Actions 기록에서 확인해 1장의 추정치를 바꾼다.~~ (10-05 완료)
2. ~~`ci.yml`을 3.1의 job으로 나누고, 실패 artifact 수집을 `e2e` job으로 옮긴다.~~ (10-05 완료)
3. ~~3.2의 배포 이미지 선빌드와 이미지 캐시를 적용한다.~~ (10-05 완료, 개발 이미지 캐시는 보류)
4. `release/gcp`로 실제 배포해 시간과 안전 조건을 확인한다.

### 5.1 첫 측정(10-05)

run 37270366058(c125871): push부터 production 전환까지 **7분 5초**(이전 15분 38초). 새 web revision `trend-production-web-00008-duf`가 트래픽 100%를 받고 `/`·`/map`·`/api/health`가 200으로 응답하는 것을 확인했다.

| job | 시간 | 비고 |
| --- | --- | --- |
| `checks / e2e` | 309초 | 임계 경로. 같은 날 수동 CI 실행에서는 293초·379초로 편차가 크다 |
| `checks / app` | 253초 | |
| `checks / images` | 100초 | 캐시 없는 develop 첫 실행은 288초 |
| `checks / models` · `static` | 65초 · 27초 | |
| `trend_images` | 94초 | 검사와 동시에 끝나 임계 경로 밖 |
| `trend_app` | 102초 | 후보 검사·트래픽 전환만 |

같은 날 배포를 막은 두 실패는 병렬화와 무관하다. 10-04의 화면별 페이지 제목 변경 뒤 E2E(`sample-flow.spec.ts`, 팀원이 수정)와 `scripts/container-smoke.sh`의 제목 검사가 `Trend Interpreter`만 기대해 실패했다. smoke 검사는 한국어·영어 사이트 이름 중 하나를 확인하도록 고쳤다.

### 5.2 배포 차단과 두 번째 측정(10-05)

**배포 차단 – 확인.** `apps/trend-api/tests`에 일부러 실패하는 테스트를 넣어 push했다(run 37271542571, da201f4). `trend_images`는 이미지를 push했지만 `checks / app`이 그 테스트 하나로 실패했고, `trend_app`·`alert_relay`는 건너뛰었다. 운영 web·API revision은 바뀌지 않았다. 이 테스트는 1c1e2df에서 되돌렸다. 그 사이 force-push가 한 번 있었는데, 이전 SHA가 어느 브랜치에도 없으면 `release_scope.py`가 바뀐 파일을 계산하지 못해 전체 검사로 분류한다. 이 실행(run 37272181080)도 같은 테스트로 배포를 막았다.

**8분 이내 두 번 연속 – 미달.**

| run | 커밋 | push → 전환 | `e2e` job | 비고 |
| --- | --- | --- | --- | --- |
| 37270366058 | c125871 | 7분 5초 | 309초 | |
| 37272196364 | 1c1e2df | 15분 7초 | 409초 | 앞 실행이 끝날 때까지 `ci.yml` concurrency로 6분 30초 대기. 대기를 빼도 8분 37초 |
| 37273522294 | 03191e1 | 8분 58초 | 427초 | 빈 재배포 커밋(`ops: 메인 서비스 재배포`) |

임계 경로는 늘 `e2e` job이고, 시간 대부분은 2코어 runner의 속도 편차에서 나온다. private 저장소의 기본 runner가 2코어라 Playwright도 worker 1개로 돈다. 03191e1의 `e2e` job을 나누면 다음과 같다.

| 단계 | 시간 |
| --- | --- |
| 개발 이미지 빌드·내보내기(`up --build`) | 131초 |
| `run --build e2e`가 api·web 이미지를 다시 내보냄 | 약 22초(중복) |
| 브라우저 이미지 빌드 | 약 51초 |
| 예열 | 53초 |
| 테스트 43개 | 약 150초(첫 지도 테스트만 46초) |

같은 코드에서도 테스트가 2.1분에서 3.4분까지 오간다. 그래서 지금 구성으로는 8분을 안정적으로 지키기 어렵다. 후보는 다음과 같다.

1. **중복 내보내기 제거**(약 20초): api·web은 앞 단계에서 빌드하고, 브라우저 이미지만 따로 빌드한 뒤 `--build` 없이 `run`한다.
2. **E2E를 2개 job으로 나누기**(Playwright `--shard`, 약 1.5~2분): job마다 이미지 빌드와 예열이 반복되므로 Actions 사용 시간은 한 번에 약 5분 늘어난다.
3. **production 빌드 대상 E2E**(3.3, 약 1분): 예열이 필요 없고 개발 서버의 첫 컴파일도 사라지지만 Compose 구성이 바뀐다.
4. **더 큰 runner**: 4코어 이상 runner는 유료 플랜이 필요하다.

1·3을 합쳐 적용했다(3.3).

### 5.3 production 이미지 E2E 적용 뒤 측정(10-05)

| run | 커밋 | push → 전환 | `e2e` job | `app` job | `trend_app` |
| --- | --- | --- | --- | --- | --- |
| 37278062702 | 352a8a2 | **6분 5초** | 192초 | 246초 | 102초 |
| 37278688570 | 56eb0d1 | **5분 48초** | 240초 | 213초 | 92초 |

두 번 연속 8분 이내를 확인했다. 운영 web·API revision 00016이 트래픽 100%를 받고 `/`·`/map`·`/dictionary`·`/api/health`가 200으로 응답한다. E2E 테스트 43개는 로컬에서 예열 포함 약 80초 걸리던 것이 12초로 줄었다. CI에서는 약 1.5분으로, 그중 지구본을 그리는 지도 테스트 두 개가 약 46초다(2코어 runner, GPU 없음).

이제 임계 경로는 `app` job(약 3.5~4분)과 `e2e` job이 번갈아 맡는다. 더 줄이려면 `app` job 안의 개발 이미지 빌드(약 95초)나 웹 build가 대상이다. 지금 목표에는 필요 없다.

## 6. 완료 기준

- `release/gcp` push부터 production 전환까지 8분 이내를 두 번 연속 확인한다.
- 검사 job 하나를 일부러 실패시켰을 때 배포 job이 시작되지 않는다.
- 로컬 Compose 명령과 문서의 검사 절차가 그대로 동작한다.

## 7. 비용과 위험

- 비공개 저장소의 Actions 사용 시간은 **job 시간의 합**으로 센다. 병렬화는 벽시계 시간을 줄이지만 job마다 준비·빌드가 반복돼 사용 시간은 늘 수 있다. 캐시 적용 전후로 월 사용량을 확인한다.
- 병렬 job은 runner마다 디스크가 따로라 10-04의 디스크 여유 문제는 줄어든다. 각 job의 개발 스택 기동은 독립적이어야 한다.
- 캐시가 오래된 층을 쓰는 문제를 막기 위해 lockfile·Dockerfile이 바뀌면 캐시 키가 바뀌는지 확인한다.
