# Plan 02 공개 저장소와 GCP 배포 승인

작성일 **2026-09-23** · 상태 **실행 준비**

[현재 계획](README.md) · [GitHub Actions](../../.github/workflows/)

## 목적

제출을 위해 저장소를 public으로 전환해도 외부 사용자가 배포 브랜치에 push하거나 GCP 배포를 실행할 수 없게 합니다. collaborator의 평소 Git 사용 방식은 유지하고, 실제 GCP 배포만 GitHub Environment 승인으로 통제합니다.

## GitHub 권한 구조

개인 계정 소유 public 저장소에서 외부 사용자는 코드를 읽고 fork하거나 PR을 만들 수 있지만 직접 push할 수 없습니다. 소유자와 write 권한이 있는 collaborator만 push할 수 있습니다. 따라서 public 전환 자체가 모든 사용자에게 write 권한을 주지는 않습니다.

개인 계정 소유 저장소에서는 collaborator가 write 권한 경계입니다. 현재 팀원은 직접 push할 수 있게 두고, `gcp` Environment 승인자를 통해 실제 GCP credential 접근과 배포만 제한합니다.

## 현재 상태

2026-09-23 기준 상태입니다.

- 저장소는 private이며 GitHub Free를 사용합니다.
- private 저장소에서는 현재 요금제의 branch protection API를 사용할 수 없습니다.
- `release/gcp` push가 `Deploy GCP` workflow를 실행합니다.
- 배포 job은 `gcp` environment와 OIDC를 사용합니다.
- `gcp` environment에는 required reviewer와 deployment branch 제한이 아직 없습니다.

## 공개 전 준비

### 1. 접근 권한 정리

1. repository collaborator 목록을 확인합니다.
2. 현재 팀원이 아닌 계정을 제거합니다.
3. 남은 collaborator가 모두 write 권한을 가져도 되는지 확인합니다.
4. GitHub Actions secret, variable, GCP IAM 주체를 함께 점검합니다.

### 2. 공개 이력 검사

Git 전체 이력에 `.env`, API key, 서비스 계정 키, 사용자 원문, 모델 출력이 포함되지 않았는지 검사합니다. 현재 파일만 지우는 것으로는 과거 커밋의 비밀정보가 제거되지 않으므로 이력 검사 결과를 공개 전 확인해야 합니다.

## 공개 직후 보호 설정

### 1. `gcp` environment 보호

- required reviewer에 배포 승인 담당자 지정
- prevent self-review 활성화
- deployment branch를 `release/gcp`로 제한
- environment secret과 variable 접근은 승인 이후에만 허용

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

## 완료 기준

- collaborator 목록에 현재 팀원만 남아 있습니다.
- 외부 사용자는 fork와 PR만 가능하며 직접 push할 수 없습니다.
- collaborator는 기존처럼 직접 push할 수 있습니다.
- `release/gcp` 배포에는 별도 Environment 승인이 필요합니다.
- fork PR에 GitHub secret과 GCP OIDC가 노출되지 않습니다.
- 실제 외부 계정과 collaborator 계정으로 거부·승인 경로를 각각 검증했습니다.

## 적용 시점

공개 이력 검사는 public 전환 전에 수행합니다. 현재 요금제에서 활성화할 수 없는 Environment 보호 규칙은 저장소를 public으로 바꾼 직후 적용하고, 승인 대기 동작을 검증할 때까지 새 운영 배포를 완료하지 않습니다.
