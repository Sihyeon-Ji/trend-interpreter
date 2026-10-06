# WIF 배포 계정 분리: 배포 계정은 gcp environment job만

작성일 **2026-10-06** · 상태 **코드 준비 완료, GCP 미적용 – 브랜치 `security/wif-environment`(`2b8f474`)** · 관련 [Plan 11 공개 저장소와 GCP 배포 승인](../plans/11-public-repository-release-protection.md) · [GCP 운영](GCP-운영.md)

저장소를 공개하기 전에 GitHub Actions가 GCP 권한을 받는 경계를 좁힌다. 이 문서는 문제, 바꾼 것, 적용 순서, 확인과 되돌리기를 한곳에 적는다.

## 문제

- 배포 계정 `builder-cup-deploy`는 Cloud Run 관리(`roles/run.admin`), 로그 보기, 런타임 서비스 계정 사용, 이미지 쓰기 권한을 가진다.
- 이 계정의 WIF 바인딩(`roles/iam.workloadIdentityUser`)은 `attribute.repository_id` 전체였다. WIF provider 조건(저장소 ID·소유자 ID·`refs/heads/release/gcp`·`push`)을 지나는 job이면 environment가 없어도 배포 계정을 쓸 수 있었다.
- 실제로 `release-gcp.yml`의 `trend_images` job은 environment 없이 배포 계정으로 인증해 이미지를 올린다.
- 공개 뒤 `gcp` environment에 required reviewer를 걸어도, 승인을 거치지 않는 job이 같은 배포 권한을 가진다. Plan 11은 "environment가 없는 job이 같은 배포 계정을 사용할 수 없는지 검증한다"를 공개 전 조건으로 둔다.

2026-10-06 GitHub 상태(읽기만 함): 저장소 private, `gcp` environment 있음(보호 규칙 0개, private 무료 요금제라 켤 수 없음), 변수 `GCP_WORKLOAD_IDENTITY_PROVIDER`·`GCP_DEPLOY_SERVICE_ACCOUNT`는 저장소 변수.

## 바꾼 것

GitHub OIDC 토큰의 subject(`sub`)는 job에 environment가 있으면 `repo:<소유자>/<저장소>:environment:<이름>`, 없으면 `repo:<소유자>/<저장소>:ref:<ref>`다([GitHub OIDC subject 규칙](https://docs.github.com/en/actions/reference/security/oidc)). 이 값으로 계정마다 쓸 수 있는 job을 나눈다.

| 계정 | 쓰는 job | 바인딩 subject | 권한 |
| --- | --- | --- | --- |
| `builder-cup-deploy`(기존) | `trend_app`·`alert_relay`(둘 다 `environment: gcp`) | `repo:Sihyeon-Ji/2026-google-ai-builder-cup:environment:gcp` | 그대로 |
| `builder-cup-image-push`(새로) | `trend_images`(environment 없음) | `repo:Sihyeon-Ji/2026-google-ai-builder-cup:ref:refs/heads/release/gcp` | Artifact Registry `builder-cup` 저장소 쓰기만 |

- WIF provider 조건(저장소·소유자·`release/gcp`·push)은 그대로 둔다. 두 subject 모두 이 조건을 먼저 지나야 한다.
- `trend_images`는 지금처럼 검사와 나란히 이미지를 만든다. 배포 시간은 그대로다.
- `alert_relay`의 alert-relay 이미지 push는 배포 계정의 기존 쓰기 권한으로 된다.

바뀐 파일:

| 파일 | 내용 |
| --- | --- |
| `infra/gcp/main.tf` | `google_service_account.image_push`, `google_artifact_registry_repository_iam_member.image_push_writer`, `google_service_account_iam_member.github_image_push` 추가. `google_service_account_iam_member.github`의 member를 `principalSet://…/attribute.repository_id/…`에서 `principal://…/subject/…:environment:gcp`로 |
| `infra/gcp/outputs.tf` | `image_push_service_account` output 추가 |
| `.github/workflows/release-gcp.yml` | `trend_images`의 `service_account`를 `vars.GCP_IMAGE_SERVICE_ACCOUNT`로 |
| `scripts/bootstrap-gcp.sh` | 저장소 변수 `GCP_IMAGE_SERVICE_ACCOUNT` 설정 추가 |
| `docs/운영/GCP-운영.md` | 변수 표에 `GCP_IMAGE_SERVICE_ACCOUNT` 추가 |

검증한 것: `docker compose run --rm infra-check`(두 Terraform 루트의 fmt·validate, hybrid 테스트 8개 통과), `tests/test_deploy_safety.py`·`tests/test_release_scope.py` 통과. **GCP에서의 실제 토큰 교환은 적용 전이라 확인하지 않았다.**

## 적용 순서

배포가 없는 때 한 번에 한다. 1을 하고 3을 하기 전에 누가 `release/gcp`에 push하면 `trend_images`가 인증에 실패한다(배포 계정을 더 쓸 수 없어서). 시작 전에 팀에 알린다.

1. **Terraform 적용.** 브랜치 `security/wif-environment`를 받아 `terraform -chdir=infra/gcp plan`으로 아래 변화만 있는지 확인하고 `apply`한다.
   - 추가: 서비스 계정 `builder-cup-image-push`, 그 계정의 Artifact Registry 쓰기 권한, 그 계정의 WIF 바인딩
   - 교체: 배포 계정의 WIF 바인딩(저장소 전체 → `environment:gcp` subject)
2. **GitHub 변수 등록.**
   ```bash
   gh variable set GCP_IMAGE_SERVICE_ACCOUNT --repo Sihyeon-Ji/2026-google-ai-builder-cup \
     --body "$(terraform -chdir=infra/gcp output -raw image_push_service_account)"
   ```
3. **합치고 배포.** 브랜치를 `develop`에 합치고 `release/gcp`로 push한다. `trend_images`(이미지 계정)와 `trend_app`(배포 계정)이 모두 성공하는지 Actions에서 본다. 그 뒤 운영 사이트가 정상인지 확인한다.
4. **IAM 확인.**
   ```bash
   gcloud iam service-accounts get-iam-policy \
     builder-cup-deploy@stunning-crane-508614-c1.iam.gserviceaccount.com
   ```
   `roles/iam.workloadIdentityUser`의 member가 `…/subject/repo:Sihyeon-Ji/2026-google-ai-builder-cup:environment:gcp` 하나인지 본다. `builder-cup-image-push`의 정책에는 `…:ref:refs/heads/release/gcp` 하나만 있어야 한다.

## 공개 뒤

저장소를 public으로 바꾼 직후 `gcp` environment에 required reviewer와 prevent self-review를 건다(Plan 11 '공개 직후 보호 설정'). 그러면 승인 전에는 `trend_app`·`alert_relay`가 시작되지 않아 배포 계정 토큰도 나오지 않는다. 이미지 계정은 승인 없이도 쓰이지만 이미지를 올리는 일만 할 수 있고, 이미지는 승인된 `trend_app`이 배포할 때만 서비스된다.

## 되돌리기

1. 브랜치 이전의 `infra/gcp/main.tf`·`outputs.tf`로 `terraform apply`한다. 배포 계정 바인딩이 저장소 전체로 돌아간다.
2. `release-gcp.yml`의 `trend_images`를 `vars.GCP_DEPLOY_SERVICE_ACCOUNT`로 되돌려 push한다.
3. 필요하면 `gh variable delete GCP_IMAGE_SERVICE_ACCOUNT`.

## 남은 결정

- 적용할 사람과 시각(인프라 담당이 하거나, 이 PC의 gcloud 계정에 프로젝트 IAM 권한이 있으면 그 계정으로).
- Plan 11의 '변수를 `gcp` environment 변수로 옮기기'와 함께 할지. 옮긴다면 `GCP_IMAGE_SERVICE_ACCOUNT`는 environment 없는 job이 읽어야 하므로 저장소 변수로 남긴다.
