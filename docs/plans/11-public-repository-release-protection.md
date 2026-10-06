# Plan 11. 공개 저장소와 GCP 배포 승인

작성일 **2026-09-23** · 상태 **공개·보호 설정 대기 – 전체 이력 재검사 완료(10-06, 오탐 3건). 개인정보 처리 결정(10-06). WIF 배포 계정 분리 코드 준비(10-06, 미적용)·실제 계정 검증 남음** · 선행 [Plan 09](09-generation-quality-evaluation.md) · 목표일 **2026-10-17**(제출 1~3일 전, 마지막 단계)

[현재 계획](README.md) · [GitHub Actions](../../.github/workflows/)

## 2026-10-06 WIF 배포 계정 분리 (코드 준비, 미적용)

배포 계정을 environment 없는 job(`trend_images`)도 쓸 수 있던 경계를 좁히는 변경을 브랜치 `security/wif-environment`에 준비했다. 배포 계정은 `gcp` environment job만, 이미지 push는 새 전용 계정으로 나눈다. 문제·바꾼 파일·적용 순서·확인·되돌리기는 [WIF 배포 계정 분리](../운영/WIF-배포-계정-분리.md)에 있다. GCP 적용(`terraform apply`)과 변수 등록은 아직 하지 않았다.

## 2026-10-06 전체 이력 재검사

공개 전 전체 이력 비밀 검사를 다시 했다(로컬의 모든 ref, `gitleaks 8.30.1 --log-opts=--all --redact=100`). 값은 터미널·문서에 남기지 않고 건수와 판별만 적는다.

**검사가 절반만 돌던 것을 먼저 고쳤다.** 이 저장소의 로컬 `.git/config`는 노트북 diff를 개발 PC의 `models/lora/.venv/bin/python -m nbstripout`으로 돌린다(`diff.ipynb.textconv`). 컨테이너 안에는 그 경로가 없어 `git log -p`가 노트북이 든 오래된 커밋에서 실패하고, gitleaks는 오류 없이 앞 185개 커밋만 검사하고 끝났다. 검사할 때만 `GIT_CONFIG_COUNT`로 `diff.ipynb.textconv`·`filter.nbstripout.clean`을 `cat`으로 바꿔 368개 커밋(줄이 더해진 커밋 전부)을 검사했다. 저장소 설정은 바꾸지 않았다. 명령은 [공개 전 보안 점검](../운영/공개-전-보안-점검.md)에 적었다.

| 발견 | 판별 |
| --- | --- |
| `manifests/gpu-cloud-run-probe-gemma4-12b-20261003-r2.json` `runtime` | 오탐. 컨테이너 이미지 digest(64자 hex)가 일반 키 규칙에 걸렸다 |
| `prototype/trend/.env.example`(09-23, 지금은 없음) | 오탐. `BLUESKY_APP_PASSWORD=`는 빈 값이고 규칙이 다음 줄까지 읽었다 |
| `docs/operations.md`(09-21, 지금은 없음) | 오탐. `gcloud ... --project=<프로젝트 ID>`. 프로젝트 ID는 워크플로에도 있는 공개 값이다 |

- 이력의 모든 `.env.example` 판(8개 경로)에서 PASS·SECRET·TOKEN·KEY 칸에 값이 있는 것은 둘이다. `VLLM_API_KEY`는 'local-…-only' 꼴의 자리표시값, `JIRA_PROJECT_KEY`는 4자 프로젝트 코드다. 비밀이 아니다.
- 이력의 파일 이름 1,298개 가운데 `.env`·개인 키·인증서·서비스 계정 JSON·Terraform state·`kaggle.json` 후보는 없다.
- **개인정보 처리(10-06 결정).** `docs/운영/GCP-운영.md` 콘솔 주소의 결제 계정 ID는 파일에서 뺐다(이력은 다시 쓰지 않음). 문서 3개의 팀원 개인 이메일과 커밋 작성자 이메일 4개는 그대로 둔다.

## 2026-10-03 점검

로컬 Terraform의 WIF 조건에 gcp environment 제약이 없음을 확인했다. GitHub 공개 여부·reviewer·브랜치 설정은 이번에 재조회하지 않았으므로 과거 원격 확인 날짜를 유지한다. 최초 의존성 검사는 실패했으나 후속 13건 수정·개발 도구 1건 기한부 예외 후 재검사에서 통과했다. 공개·설정 변경·외부 계정 검증은 실행하지 않았다.

근거·검증 범위와 구현 적절성은 [10-03 점검 보고서](구현-완료도-실측-점검-2026-10-03.md)를 따른다. 아래 날짜별 결과는 당시 기록으로 보존한다.

## 목적

제출을 위해 저장소를 public으로 전환해도 외부 사용자가 배포 브랜치에 push하거나 GCP 배포를 실행할 수 없게 합니다. collaborator의 평소 Git 사용 방식은 유지하고, 실제 GCP 배포만 GitHub Environment 승인으로 통제합니다.

## GitHub 권한 구조

개인 계정 소유 public 저장소에서 외부 사용자는 코드를 읽고 fork하거나 PR을 만들 수 있지만 직접 push할 수 없습니다. 소유자와 write 권한이 있는 collaborator만 push할 수 있습니다. 따라서 public 전환 자체가 모든 사용자에게 write 권한을 주지는 않습니다.

개인 계정 소유 저장소에서는 collaborator가 write 권한 경계입니다. 현재 팀원은 직접 push할 수 있게 두고, `gcp` Environment 승인자를 통해 실제 GCP credential 접근과 배포만 제한합니다.

## 현재 상태

2026-09-23 기준 상태입니다(09-29 실측으로 확인한 것은 아래 '현재 상태와 남은 일').

- 저장소는 private이며 GitHub Free를 사용합니다.
- private 저장소에서는 현재 요금제의 branch protection API를 사용할 수 없습니다.
- `release/gcp` push가 변경 범위에 따라 `Release GCP`의 검사·배포 job을 실행합니다.
- 배포 job은 `gcp` environment와 OIDC를 사용합니다.
- `gcp` environment에는 required reviewer와 deployment branch 제한이 아직 없습니다.

## 공개 전 준비

### 공개 이력 검사

Git 전체 이력에 `.env`, API key, 서비스 계정 키, 사용자 원문, 모델 출력이 포함되지 않았는지 검사합니다. 현재 파일만 지우는 것으로는 과거 커밋의 비밀정보가 제거되지 않으므로 이력 검사 결과를 공개 전 확인해야 합니다.

2026-09-26에 [사전 보안 점검](../운영/공개-전-보안-점검.md)을 수행했습니다. 당시 알려진 경고 2건은 오탐으로 판별됐습니다. 저장소 공개 직전에 그 이후 commit까지 포함해 이력 검사를 다시 실행합니다.

Repository collaborator 목록은 현재 팀원 기준으로 이미 정리되어 있으므로 이 계획의 실행 항목에서 제외합니다.

## 공개 직후 보호 설정

### 1. `gcp` environment 보호

- required reviewer에 배포 승인 담당자 지정
- prevent self-review 활성화
- deployment branch를 `release/gcp`로 제한
- environment secret과 variable 접근은 승인 이후에만 허용
- 관리자에 의한 보호 규칙 우회 비활성화

공개 전에는 GCP WIF 신뢰 조건도 함께 점검합니다. 현재 Terraform 조건은 repository ID, owner ID,
`release/gcp`, push event만 확인합니다. GitHub Environment 승인에 배포를 묶으려면 `gcp` environment를
나타내는 OIDC subject 조건도 요구하고, environment가 없는 job이 같은 배포 계정을 사용할 수 없는지
검증합니다. 단순히 workflow YAML에 `environment: gcp`가 있다는 사실만으로 이 클라우드 경계를
검증했다고 표시하지 않습니다. [GitHub OIDC subject 규칙](https://docs.github.com/en/actions/reference/security/oidc)

`release/gcp` push가 발생하면 기존 `checks` job은 먼저 실행되지만, 실제 배포 job은 Environment 승인 전까지 시작되지 않습니다. 따라서 collaborator가 실수로 배포 브랜치를 갱신해도 승인 전에는 GCP OIDC credential을 발급받거나 Cloud Run을 변경할 수 없습니다.

### 2. collaborator 직접 push 유지

- `develop`과 `release/gcp`에 PR 또는 코드 리뷰를 강제하지 않음
- 현재 collaborator는 기존처럼 직접 push 가능
- 외부 사용자는 public 전환 후에도 직접 push 불가
- 실제 배포의 최종 통제 지점은 `gcp` Environment 승인으로 한정

이 선택은 collaborator가 branch를 force push하거나 삭제하는 위험까지 막지는 않습니다. 현재 팀 규모에서는 Git 작업 절차를 단순하게 유지하고, 제출 서비스에 영향을 주는 배포 권한만 보호합니다.

### 3. Actions 기본 권한 축소

- repository의 기본 `GITHUB_TOKEN` 권한을 read-only로 설정
- workflow별 필요한 권한만 명시
- fork PR에서 secret과 OIDC 발급 금지 상태 확인
- 외부 action은 commit SHA 고정 유지

## 검증 절차

1. 외부 계정 또는 fork에서 직접 push가 거부되는지 확인합니다.
2. 외부 PR에서 secret과 OIDC를 읽을 수 없는지 확인합니다.
3. collaborator가 `develop`과 `release/gcp`에 직접 push할 수 있는지 확인합니다.
4. `release/gcp` push 후 검사는 실행되지만 배포 job은 Environment 승인 전 대기하는지 확인합니다.
5. 승인 전에는 GCP OIDC credential이 발급되지 않고 Cloud Run 리비전이 바뀌지 않는지 확인합니다.
6. 지정된 reviewer의 승인 후 배포가 성공하고 Cloud Run 상태 검사를 통과하는지 확인합니다.
7. `gcp` environment를 사용하지 않는 job은 GCP WIF 교환에서 거부되는지 확인합니다.

## 완료 기준

- 외부 사용자는 fork와 PR만 가능하며 직접 push할 수 없습니다.
- collaborator는 기존처럼 직접 push할 수 있습니다.
- `release/gcp` 배포에는 별도 Environment 승인이 필요합니다.
- fork PR에 GitHub secret과 GCP OIDC가 노출되지 않습니다.
- 실제 외부 계정과 collaborator 계정으로 거부·승인 경로를 각각 검증했습니다.

## 적용 시점

이 계획은 GitHub 저장소 URL을 제출하기 **1~3일 전**에 실행하는 것이 적절합니다. 제출 당일에 처음 적용하면 공개 이력 문제나 Environment 승인 설정 오류를 고칠 시간이 부족합니다.

### 제출 1~3일 전

1. 제출 후보 commit을 정하고 Compose 전체 검사와 실제 배포 상태를 확인합니다.
2. Git 전체 이력에서 credential과 공개하면 안 되는 데이터를 검사합니다.
3. 저장소를 public으로 전환합니다.
4. `gcp` Environment reviewer, prevent self-review, `release/gcp` branch 제한을 즉시 설정합니다.
5. 외부 사용자 권한과 collaborator 직접 push를 확인합니다.
6. 승인 전 배포 대기와 승인 후 배포 성공을 실제로 한 번 검증합니다.

### 제출 당일

1. 저장소가 public 상태인지 확인합니다.
2. 제출 URL을 로그아웃 상태나 시크릿 창에서 열어 README와 source가 보이는지 확인합니다.
3. 공개 웹 URL의 실제 사용자 흐름과 인증된 API `/health`, 익명 API 접근 거부를 배포 검사로 확인합니다. 현재 Trend 웹에는 `/api/health`가 없습니다.
4. 검증된 GitHub 저장소 URL과 배포 URL을 제출합니다.

공개 이력 검사는 public 전환 전에 수행합니다. 현재 요금제에서 활성화할 수 없는 Environment 보호 규칙은 저장소를 public으로 바꾼 직후 적용하고, 승인 대기 동작을 검증할 때까지 새 운영 배포를 완료하지 않습니다.

## 현재 상태와 남은 일 (2026-09-29 실측)

완료 기준 5개 중 충족한 것은 없다. 셋은 실제 계정과 공개 전환이 있어야 확인할 수 있다.

| 완료 기준 | 상태 | 근거 |
| --- | --- | --- |
| 외부 사용자는 fork·PR 만 가능 | 사용자 실행 대기 | 저장소는 아직 private(익명 조회 404). 공개 전환과 외부 계정 확인이 필요하다 |
| collaborator 직접 push 유지 | 사용자 실행 대기 | 지금은 직접 push 가 되고(develop 작성자 4명) 브랜치 보호는 설정하지 않았다. 공개 뒤 collaborator 계정으로 다시 확인한다 |
| `release/gcp` 배포에 Environment 승인 | 미충족 | `gcp` environment 에 검토자가 없고 `bootstrap-gcp.sh` 가 빈 `PUT` 으로 만든다. WIF 신뢰 조건(`infra/gcp/main.tf`)은 repository ID·owner ID·`release/gcp` ref·push 이벤트만 보고 `environment` 를 보지 않는다 |
| fork PR 에 secret·OIDC 미노출 | 일부 | 구조상 안전하다: `pull_request`·`pull_request_target` 트리거가 없고(`ci.yml` 은 workflow_call·dispatch, `release-gcp.yml` 은 `release/gcp` push) 최상위 권한이 `contents: read` 다. 공개 뒤 실험으로 확인하지 않았다 |
| 외부·collaborator 계정으로 거부·승인 검증 | 사용자 실행 대기 | 실제 계정·공개 전환·승인 대기 실행이 필요하다. 지금 배포 job 은 알림 중계기뿐이라 `ops: 알림 중계기 재배포` 로 시험할 수 있다 |

남은 일:

1. WIF 조건에 `&& assertion.environment == 'gcp'` 를 더한다(알림 중계기 job 은 이미 `environment: gcp` 를 선언한다). `infra-check` 로 검증하고 plan/apply 는 사용자 확인 뒤 한다.
2. 부트스트랩이 `GCP_WORKLOAD_IDENTITY_PROVIDER`·`GCP_DEPLOY_SERVICE_ACCOUNT` 를 저장소 변수가 아니라 `gcp` environment 변수(`--env gcp`)로 두게 하고, environment 는 없을 때만 만들게 한다(빈 `PUT` 이 보호 규칙을 되돌릴 수 있다).
3. 공개 직전 전체 이력 비밀 재검사(예: `gitleaks --log-opts=--all --redact=100`, 건수만 기록). 09-26 검사 이후 develop 에 134개 커밋이 더 쌓였다(09-29 기준).
4. 공개 전 개인정보 검토: 문서 세 곳에 개인 이메일 주소가 있고(`docs/트렌드/인수인계-2026-09-15.md`, `docs/트렌드/조사/05-카테고리-트렌드-소스.md`, `docs/트렌드/키-계정-정리.md`), `docs/운영/GCP-운영.md` 의 콘솔 주소에 결제 계정 ID 가 들어 있다. 파일에서 지우는 것과 이력에서 지우는 것(이력 재작성)은 별개이므로 **사용자 결정 대기**다. 값은 이 문서에 적지 않는다.
5. 제출 당일 절차의 `/api/health` 는 Trend 웹에 없다(`apps/trend-web/app/api` 는 auth·chat·explain·generate·prefs·recommend·review 뿐). 웹 주소 확인과 배포 검사로 대신하거나 health 경로를 더한다.
6. **사용자 실행:** 공개 전환 직후 GitHub 설정 – 필수 검토자, 자기 승인 방지, 배포 브랜치 `release/gcp`, 관리자 우회 끄기, 저장소 기본 `GITHUB_TOKEN` 읽기 전용(이미 read), fork PR 워크플로 승인. 그리고 WIF plan/apply.
7. **사용자 실행:** 검증 – 외부·collaborator 계정, 승인을 기다리는 배포(중계기 재배포 또는 [Plan 05](05-trend-cloud-run-deployment.md) 의 Trend 앱 job), environment 없는 job 이 WIF 토큰 교환에서 거부되는 것.
