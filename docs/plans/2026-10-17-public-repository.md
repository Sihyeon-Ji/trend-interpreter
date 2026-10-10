# 10-17 저장소 공개 전환과 배포 승인

실행일 **2026-10-17** · 담당 **shji(지시현)** · 상태 **준비 중** · 선행 [10-16 운영 DB 갱신](2026-10-16-final-db-refresh.md) · 제출 **10-18**

[계획 목록](README.md) · [GCP 운영](../운영/GCP-운영.md) · [WIF 배포 계정 분리](../운영/WIF-배포-계정-분리.md) · 경위 [옛 Plan 11](archive/11-public-repository-release-protection.md)

## 미리 할 일 (10-17 전)

- **이력 재검사(10-10 실행).** `gitleaks 8.30.1 git --log-opts=--all --redact=100`(노트북 diff는 `cat`으로, [공개 전 보안 점검](../운영/공개-전-보안-점검.md)). 473개 커밋 중 줄이 더해진 457개를 검사, 3건 – 10-06에 오탐으로 판별한 것과 같은 파일·커밋(이미지 digest, 빈 `.env.example` 값, 공개 프로젝트 ID)이다. 공개 당일에는 10-10 뒤 커밋만 다시 본다.
- **WIF 배포 계정 분리 준비(10-10).** `security/wif-environment`(925948c)는 지금 develop과 충돌 없이 합쳐진다. `infra/gcp` plan은 문서대로 4개 추가·1개 교체에, develop에 이미 있던 경보 정책 변경 1개(게시 Job 실패도 경보)가 더해진다. 적용은 ① Terraform apply → ② 저장소 변수 `GCP_IMAGE_SERVICE_ACCOUNT` 등록 → ③ 병합·`release/gcp` 배포를 한 번에, 팀에 알리고 한다. ①과 ③ 사이에 누가 `release/gcp`에 push하면 이미지 job이 인증에 실패한다. 이 PC에 `gh`가 없어 ②는 GitHub 웹(Settings → Secrets and variables → Actions → Variables)에서 사용자가 한다.
- **검사용 계정.** 외부 GitHub 계정 하나(저장소 권한 없음)와 collaborator 계정 하나(예: ktwoo)가 필요하다. 외부 계정으로 직접 push 거부·fork PR에 secret이 없음을, collaborator 계정으로 develop push와 `release/gcp` 배포가 승인을 기다리는 것을 확인한다.

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
