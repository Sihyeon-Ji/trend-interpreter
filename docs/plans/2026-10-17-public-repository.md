# 10-17 저장소 공개 전환과 배포 승인

실행일 **2026-10-17** · 담당 **shji(지시현)** · 상태 **준비 중** · 선행 [10-16 운영 DB 갱신](2026-10-16-final-db-refresh.md) · 제출 **10-18**

[계획 목록](README.md) · [GCP 운영](../운영/GCP-운영.md) · [WIF 배포 계정 분리](../운영/WIF-배포-계정-분리.md) · 경위 [옛 Plan 11](archive/11-public-repository-release-protection.md)

## 미리 할 일 (10-17 전)

- 1의 WIF 배포 계정 분리는 GCP IAM 적용·GitHub 변수 등록이 먼저라 미리 해 둘 수 있다.
- 거부·승인 경로 확인에 쓸 외부 계정과 collaborator 계정을 준비한다.

## 절차

전체 이력 재검사는 10-06에 마쳤다(오탐 3건). 공개 직전에 그 뒤 커밋까지 다시 검사한다. 순서는 아래와 같다. 상세는 [옛 Plan 11](archive/11-public-repository-release-protection.md#공개-직후-보호-설정)에 있다.

1. WIF 배포 계정 분리(`security/wif-environment`)를 적용한다. GCP IAM 적용과 GitHub 변수 등록이 코드 병합보다 먼저다([적용 순서](../운영/WIF-배포-계정-분리.md#적용-순서)).
2. 이력 재검사 → 공개 전환.
3. `gcp` environment 보호(required reviewer, self-review 금지, `release/gcp` 한정, 관리자 우회 금지).
4. Actions 기본 `GITHUB_TOKEN` read-only, fork PR의 secret·OIDC 차단 확인.

완료 기준

- 외부 사용자는 fork와 PR만 가능하고 직접 push할 수 없다. collaborator는 기존처럼 직접 push한다.
- `release/gcp` 배포에는 별도 Environment 승인이 필요하다.
- fork PR에 GitHub secret과 GCP OIDC가 노출되지 않는다.
- 실제 외부 계정과 collaborator 계정으로 거부·승인 경로를 각각 확인했다.
