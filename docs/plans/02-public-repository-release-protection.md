# Plan 02 공개 저장소와 배포 브랜치 보호

작성일 **2026-09-23** · 상태 **실행 준비**

[현재 계획](README.md) · [GitHub Actions](../../.github/workflows/)

## 목적

제출을 위해 저장소를 public으로 전환해도 외부 사용자가 배포 브랜치에 push하거나 GCP 배포를 실행할 수 없게 합니다. 팀 collaborator도 코드 검증과 승인을 거쳐야 `release/gcp`를 변경할 수 있게 합니다.

## GitHub 권한 구조

개인 계정 소유 public 저장소에서 외부 사용자는 코드를 읽고 fork하거나 PR을 만들 수 있지만 직접 push할 수 없습니다. 소유자와 write 권한이 있는 collaborator만 push할 수 있습니다. 따라서 public 전환 자체가 모든 사용자에게 write 권한을 주지는 않습니다.

다만 개인 계정 소유 저장소는 특정 collaborator만 브랜치에 push하도록 제한하는 세밀한 규칙이 부족합니다. collaborator 일부만 배포 후보를 만들게 해야 한다면 organization 저장소로 이전해 팀 권한을 나누거나, GitHub Environment 승인자를 통해 실제 배포를 제한해야 합니다.

## 현재 상태

2026-09-23 기준 상태입니다.

- 저장소는 private이며 GitHub Free를 사용합니다.
- private 저장소에서는 현재 요금제의 branch protection API를 사용할 수 없습니다.
- `release/gcp` push가 `Deploy GCP` workflow를 실행합니다.
- 배포 job은 `gcp` environment와 OIDC를 사용합니다.
- `gcp` environment에는 required reviewer와 deployment branch 제한이 아직 없습니다.
- `CI` workflow는 `workflow_call`과 수동 실행만 지원해 PR의 required check로 바로 지정할 수 없습니다.

## 공개 전 준비

### 1. 접근 권한 정리

1. repository collaborator 목록을 확인합니다.
2. 현재 팀원이 아닌 계정을 제거합니다.
3. 남은 collaborator가 모두 write 권한을 가져도 되는지 확인합니다.
4. GitHub Actions secret, variable, GCP IAM 주체를 함께 점검합니다.

### 2. 공개 이력 검사

Git 전체 이력에 `.env`, API key, 서비스 계정 키, 사용자 원문, 모델 출력이 포함되지 않았는지 검사합니다. 현재 파일만 지우는 것으로는 과거 커밋의 비밀정보가 제거되지 않으므로 이력 검사 결과를 공개 전 확인해야 합니다.

### 3. PR용 CI 실행 조건 추가

`CI` workflow에 `develop`과 `release/gcp` 대상 `pull_request` trigger를 추가합니다. fork PR에서는 secret과 GCP OIDC를 제공하지 않고 Mock과 로컬 인프라 검사만 실행합니다.

CI가 실제 PR에서 성공한 뒤에만 required status check로 지정합니다. 존재하지 않거나 한 번도 실행되지 않은 check를 먼저 필수로 설정하면 병합할 수 없습니다.

## 공개 직후 보호 설정

### 1. `develop` 보호

- pull request 필수
- 승인 1명 이상
- 새 commit이 추가되면 이전 승인 무효화
- 모든 대화 해결 필수
- CI required status check 필수
- force push와 branch deletion 금지
- 관리자 우회 금지

### 2. `release/gcp` 보호

- 직접 push 금지
- pull request 필수
- 승인 1명 이상
- 새 commit이 추가되면 이전 승인 무효화
- 모든 대화 해결 필수
- CI required status check 필수
- force push와 branch deletion 금지
- 관리자 우회 금지

평상시에는 검증된 `develop` commit을 `release/gcp`로 올리는 PR만 허용합니다.

### 3. `gcp` environment 보호

- required reviewer에 배포 승인 담당자 지정
- prevent self-review 활성화
- deployment branch를 `release/gcp`로 제한
- environment secret과 variable 접근은 승인 이후에만 허용

브랜치 변경 권한과 실제 GCP credential 접근을 분리하므로 collaborator 계정이 실수로 배포 PR을 만들더라도 승인 전에는 배포가 진행되지 않습니다.

### 4. Actions 기본 권한 축소

- repository의 기본 `GITHUB_TOKEN` 권한을 read-only로 설정
- workflow별 필요한 권한만 명시
- fork PR에서 secret과 OIDC 발급 금지 상태 확인
- 외부 action은 commit SHA 고정 유지

## 검증 절차

1. 외부 계정 또는 fork에서 직접 push가 거부되는지 확인합니다.
2. 외부 PR에서 CI는 실행되지만 secret과 OIDC를 읽을 수 없는지 확인합니다.
3. collaborator의 `develop` 직접 push가 거부되는지 확인합니다.
4. 승인 없는 `release/gcp` 변경과 배포가 거부되는지 확인합니다.
5. 승인된 PR만 CI 통과 후 병합되는지 확인합니다.
6. `release/gcp` 병합 후 `Deploy GCP`가 실행되고 environment 승인 전 대기하는지 확인합니다.
7. 승인 후 배포가 성공하고 Cloud Run 상태 검사를 통과하는지 확인합니다.

## 완료 기준

- collaborator 목록에 현재 팀원만 남아 있습니다.
- 외부 사용자는 fork와 PR만 가능하며 직접 push할 수 없습니다.
- `develop`과 `release/gcp`에 동일한 기본 보호 규칙이 적용되어 있습니다.
- `release/gcp` 배포에는 별도 environment 승인이 필요합니다.
- fork PR에 GitHub secret과 GCP OIDC가 노출되지 않습니다.
- 실제 외부 계정과 collaborator 계정으로 거부·승인 경로를 각각 검증했습니다.

## 적용 시점

PR용 CI trigger와 공개 이력 검사는 public 전환 전에 준비합니다. 현재 요금제에서 활성화할 수 없는 branch protection과 environment 보호 규칙은 저장소를 public으로 바꾼 직후 적용하고, 보호 검증이 끝날 때까지 새 배포를 만들지 않습니다.
