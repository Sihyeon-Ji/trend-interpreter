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
3. 운영 URL과 `/api/health`를 확인합니다.
4. 검증된 GitHub 저장소 URL과 배포 URL을 제출합니다.

공개 이력 검사는 public 전환 전에 수행합니다. 현재 요금제에서 활성화할 수 없는 Environment 보호 규칙은 저장소를 public으로 바꾼 직후 적용하고, 승인 대기 동작을 검증할 때까지 새 운영 배포를 완료하지 않습니다.
