# GCP 설정 및 운영

Project는 `stunning-crane-508614-c1`입니다. Cloud Run과 Artifact Registry는 도쿄
`asia-northeast1`을 사용합니다. Gemini location은 `global`이며 이는 한국 내 데이터 보관을
보장한다는 뜻이 아닙니다.

## 최초 1회 기반 인프라 구성

1. `gh auth login`, `gcloud auth login`, `gcloud auth application-default login`으로 인증합니다.
2. GitHub 계정에는 variable과 environment를 설정할 저장소 관리 권한이 필요합니다. Google 계정에는
   API 활성화, IAM/service account, federation, secret, storage, Artifact Registry, monitoring을
   관리할 project 권한이 필요합니다.
3. 배포 운영 장비에는 인증된 CLI와 함께 Bash, Python 3, Terraform 1.6 이상 2.0 미만이 필요합니다.
   현재 검증 version은 1.16.3입니다. Compose 개발 stack에는 이 host tool이 필요하지 않습니다.
4. Cloud 배포가 필요하고 결제가 활성화되어 있으면 `bash scripts/bootstrap-gcp.sh`를 실행합니다.
   Script는 준비된 인프라를 적용하기 전에 Terraform plan을 보여주며, 현재 gcloud project나 계정을
   임의로 바꾸지 않습니다.
5. GitHub의 기본 branch를 `develop`으로 설정합니다.
6. `release/gcp`에 push하면 CI와 배포가 실행됩니다.

Bootstrap은 다시 실행할 수 있습니다. 기존 demo secret version을 보존하며 remote state를 사용합니다.
API 활성화나 resource 생성 전에 project에 결제가 연결되어 있는지도 확인합니다. 공개 정보인 repository
ID만 무시 대상인 `infra/gcp/github.auto.tfvars.json`에 기록합니다.

GitHub environment 이름은 `gcp`입니다. 승인 gate를 설정하지 않았으므로 branch push가 배포를 자동으로
시작합니다. Bootstrap이 만드는 대상은 다음과 같습니다.

- Terraform state용 GCS bucket
- 필요한 project API
- Artifact Registry
- 배포·runtime service account와 IAM
- Workload Identity Federation
- Secret Manager metadata와 demo access code
- Log 기반 metric과 운영 dashboard
- GitHub 배포 variable과 `gcp` environment

Cloud Run 서비스에는 변경할 수 없는 application image digest가 필요하므로 bootstrap은 서비스를 만들지
않습니다. 첫 CD가 서비스를 만들고 이후 CD는 후보 revision을 만든 뒤 smoke check에 성공할 때까지 현재
revision의 traffic을 유지합니다. Domain mapping은 별도이며 팀 소유 domain이 생길 때까지 만들지 않습니다.

자동 검사와 배포는 `release/gcp` push에서만 실행됩니다. `develop` push는 CI를 시작하지 않습니다.
원격 검사가 미리 필요하면 CI workflow를 수동 실행합니다. 2026-09-21 첫 release는 약 4분 38초가
걸렸습니다. 전체 검사가 약 3분 15초, 인증·cache된 image 게시·Cloud Run 배포가 약 1분 16초였습니다.
중복 `develop` CI trigger를 없앤 다음 release는 약 4분 4초가 걸렸습니다. Warm build cache가 이후
실행을 줄일 수 있지만 전체 test suite가 release 시간의 대부분을 차지합니다.

Bootstrap이 설정하는 repository variable은 다음과 같습니다.

| Variable | 출처 |
| --- | --- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Terraform `workload_identity_provider` output |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | Terraform `deploy_service_account` output |
| `GEMINI_MODEL` | 선택 사항이며 기본값은 `gemini-3.5-flash` |

## 웹 화면과 팀 접근 코드 사용법

Cloud Run은 구매한 domain 없이도 HTTPS `run.app` URL을 제공합니다. 배포된 서비스 URL을 browser에서
열면 됩니다. Custom domain mapping은 팀이 소유하고 소유권을 확인할 수 있는 domain이 있어야 합니다.
Domain을 사거나 이전한 뒤에만 추가하며 현재 배포와 공개 web 접근에는 필요하지 않습니다.

화면의 `Team access code`는 Google 계정 비밀번호나 Gemini API key가 아닙니다. 공개된 Cloud Run
주소에서 팀원만 모델을 호출하도록 bootstrap이 무작위로 생성한 팀 공용 비밀번호입니다. 실제 값은
Secret Manager의 `builder-cup-demo-key` 최신 version에 있습니다.

```bash
gcloud secrets versions access latest \
  --secret=builder-cup-demo-key \
  --project=stunning-crane-508614-c1
```

출력된 값은 private channel로만 팀원에게 전달합니다. 문서, Git, issue, chat, screenshot에 남기지 않습니다.
Web 화면은 다음 순서로 사용합니다.

1. `Your text`에 요약할 개인정보 없는 테스트 문장을 입력합니다.
2. `Team access code`에 Secret Manager에서 복사한 값을 입력합니다.
3. `Analyze text`를 누릅니다.
4. 오른쪽 `RESULT`에서 요약, 핵심 내용, provider, model 정보를 확인합니다.

Access code는 frontend bundle이나 `localStorage`에 넣지 않고 현재 React memory에만 유지합니다. Page를
새로고침하거나 tab을 닫으면 다시 입력해야 합니다. 값이 없거나 틀리면 `401` 오류가 표시됩니다.

Release smoke test는 static UI, application health, anonymous request 거부를 검사합니다. 실제 Gemini
project 접근이나 quota까지 입증하지는 않습니다. 첫 release 후에는 team code를 넣어 실제 text를
제출하고 반환된 model, token, 결과를 확인합니다. 로컬에서도 실제 provider 평가를 실행합니다. 후보
revision의 smoke test가 실패하면 기존 revision에 traffic을 보내지 않습니다. 최초 배포에는 보존할
이전 revision이 없습니다.

조직 정책이 `allUsers`를 금지하면 public invoker 설정 단계가 명확하게 실패합니다. 이 경우 승인된
private access 구조를 사용해야 하며 인증을 제거해서 우회하면 안 됩니다.

## 예산과 리전

2026-09-21에 결제를 연결하고 배포를 재개했습니다. 실제 수요를 측정할 때까지 Cloud Run 최소 instance는
0, 최대 instance는 2로 유지합니다. 인증 성공만으로 model 접근, quota, 전체 운영 검증이 완료된 것은
아닙니다.

Cloud Run 기준 도쿄(`asia-northeast1`)와 오사카(`asia-northeast2`)는 Tier 1, 서울
(`asia-northeast3`)은 Tier 2 가격을 사용합니다. 애플리케이션과 Artifact Registry는 도쿄에 둡니다.
이 tier 구분은 Cloud Run 가격에만 해당하며 Gemini나 모든 GCP 서비스 가격을 뜻하지 않습니다. 최종
region을 정할 때 application dependency도 가능한 한 같은 region에 둡니다. 자세한 내용은
[Cloud Run location](https://docs.cloud.google.com/run/docs/locations)과
[가격](https://cloud.google.com/run/pricing)을 확인합니다.

Billing budget을 암묵적으로 설정하지 않습니다. 무시 대상인 `infra/gcp/terraform.tfvars`에 billing
account 통화와 일치하는 `billing_account`, `monthly_budget`, `budget_currency`를 설정한 뒤 plan/apply합니다.
그러면 account의 기본 billing 수신자에게 50%, 90%, 100% 알림을 보냅니다. Budget 생성에는 billing
account 권한이 필요합니다. **Budget 알림은 지출을 중단하지 않습니다.** 실제 account에서 model quota와
접근 권한, budget, 알림 수신자, 실제 model 가격을 확인해야 합니다. Cloud Run이 0으로 축소돼도 image
storage는 남습니다.

## 비용 절감을 위한 삭제 수준

목표에 맞는 가장 작은 삭제 범위를 선택합니다. Release workflow는 Terraform이나
`bootstrap-gcp.sh`를 실행하지 않으며 기반 인프라가 이미 있다고 가정합니다. Cloud Run 서비스가 없으면
새로 만들 수 있지만 Registry, identity, IAM binding, secret이 없으면 복구하지 못하고 실패합니다.

| 단계 | 삭제 대상 | 남는 대상 | 다음 `release/gcp` push만으로 배포 가능? |
| --- | --- | --- | --- |
| 그대로 유지 | 없음 | 서비스와 전체 기반 인프라 | 가능 |
| 서비스 중단 | Cloud Run 서비스 | Image, registry, identity, secret, monitoring, Terraform state | 서비스 삭제가 끝난 뒤 가능 |
| 서비스와 image 정리 | Cloud Run 서비스와 `app` image 묶음 | 비어 있는 registry와 나머지 기반 인프라 | 가능. CD가 새 image를 먼저 게시 |
| 기반 인프라 전체 제거 | Cloud Run, image, Terraform 관리 기반, state bucket | Project, 결제 연결, 활성 API | 불가능. CD 전에 bootstrap 필요 |

최소 instance 0인 요청 기반 서비스에는 유휴 Cloud Run instance 비용이 없지만 공개 request가 들어오면
instance가 시작될 수 있습니다. 서비스를 삭제하면 request를 막고 revision도 함께 삭제합니다. Artifact
Registry image는 자동으로 삭제되지 않습니다. Artifact Registry storage, Terraform state storage,
Gemini request, project의 다른 resource는 각각 별도 과금 기준을 가집니다. 공식 문서는
[Cloud Run 과금 설정](https://docs.cloud.google.com/run/docs/configuring/billing-settings),
[서비스 삭제 동작](https://docs.cloud.google.com/run/docs/managing/services#delete),
[Artifact Registry 가격](https://cloud.google.com/artifact-registry/pricing)을 참고합니다.

### 권장 방법: Cloud Run 서비스만 삭제

오랫동안 서비스를 공개하지 않을 때 권장하는 방법입니다. 일회성 기반 인프라를 남기므로 다음 CD가
Cloud Run을 자동으로 다시 만들 수 있습니다.

```bash
PROJECT_ID=stunning-crane-508614-c1
REGION=asia-northeast1
SERVICE=builder-cup

gcloud run services delete "$SERVICE" --project="$PROJECT_ID" --region="$REGION"
```

다음 명령이 서비스가 없다고 보고할 때까지 기다린 뒤 release를 시작합니다.

```bash
gcloud run services describe builder-cup \
  --project=stunning-crane-508614-c1 --region=asia-northeast1
```

다음 release는 서비스가 없음을 감지해 `--no-traffic` 없이 새로 만듭니다. 같은 project, region,
service 이름으로 재생성하면 같은 `run.app` endpoint를 받습니다. 이 경로에는 이전 revision이 없으므로
traffic 보존과 rollback은 release 성공 후부터 사용할 수 있습니다. Smoke test가 실패하면 새 서비스를
확인하거나 삭제한 다음 원인을 고쳐 다시 배포합니다.

### 저장된 application image도 삭제

Cloud Run을 먼저 삭제한 다음 image 묶음을 삭제합니다. 다음 CD가 bootstrap 없이 image를 게시할 수
있도록 Artifact Registry의 `builder-cup` repository 자체는 남깁니다.

```bash
IMAGE=asia-northeast1-docker.pkg.dev/stunning-crane-508614-c1/builder-cup/app

gcloud artifacts docker images delete "$IMAGE" \
  --project=stunning-crane-508614-c1 --delete-tags
```

대화형 확인 화면에서 삭제 대상을 확인합니다. 이 명령은 `app` 아래의 모든 digest와 tag를 삭제합니다.
다음 release는 해당 commit image만 다시 build하고 게시합니다.

### Terraform 관리 기반 전체 삭제

Terraform remote state와 실제 resource의 일관성을 유지하도록 Terraform으로 삭제합니다. State bucket을
먼저 수동 삭제하면 안 됩니다. State file이 없는데 실제 resource가 남으면 Terraform이 이를 새 resource로
취급해 생성 충돌이 날 수 있습니다.

1. 앞 절차대로 Cloud Run과 application image를 삭제합니다.
2. 저장소 root에서 기존 remote state를 연결하고 삭제 plan을 검토합니다.

   ```bash
   export PATH="$PWD/.tools:$PATH"
   export TF_VAR_github_repository_id
   export TF_VAR_github_owner_id
   TF_VAR_github_repository_id=$(gh api repos/Sihyeon-Ji/2026-google-ai-builder-cup --jq '.id | tostring')
   TF_VAR_github_owner_id=$(gh api repos/Sihyeon-Ji/2026-google-ai-builder-cup --jq '.owner.id | tostring')

   terraform -chdir=infra/gcp init -reconfigure \
     -backend-config="bucket=stunning-crane-508614-c1-tfstate" \
     -backend-config="prefix=foundation"
   terraform -chdir=infra/gcp plan -destroy -out=destroy.tfplan
   ```

3. 예상하지 않은 삭제 대상이 없는지 확인한 뒤 plan을 적용합니다.

   ```bash
   terraform -chdir=infra/gcp apply destroy.tfplan
   ```

4. Terraform이 성공한 뒤에만 versioning된 state bucket을 삭제합니다.

   ```bash
   gcloud storage rm --recursive gs://stunning-crane-508614-c1-tfstate/
   ```

5. 완전히 연결이 끊긴 상태가 필요하면 이제 유효하지 않은 GitHub variable을 삭제합니다.

   ```bash
   gh variable delete GCP_WORKLOAD_IDENTITY_PROVIDER \
     --repo Sihyeon-Ji/2026-google-ai-builder-cup
   gh variable delete GCP_DEPLOY_SERVICE_ACCOUNT \
     --repo Sihyeon-Ji/2026-google-ai-builder-cup
   ```

Terraform은 Artifact Registry, service account 두 개와 IAM binding, Workload Identity Federation,
Secret Manager metadata, dashboard, log 기반 metric을 삭제합니다. Terraform resource의
`disable_on_destroy = false` 설정 때문에 project API는 활성 상태로 남습니다. API 활성화만으로 실행 중인
workload가 생기지는 않습니다. GitHub의 `gcp` environment도 남습니다. 이 절차는 같은 GCP project에
별도로 만든 resource를 검색하거나 삭제하지 않습니다.

## 전체 삭제 후 복구와 재배포

CD를 실행하기 전에 아래 조건이 모두 충족되어야 합니다.

- Project `stunning-crane-508614-c1`이 존재하고 활성 billing account가 연결되어 있습니다.
- `gcloud auth login`, `gcloud auth application-default login`, `gh auth login`이 유효합니다.
- 로컬 checkout에서 Terraform 1.6 이상 2.0 미만, Bash, Python 3을 사용할 수 있습니다.
- 운영자가 GCP project를 관리하고 repository variable을 쓸 수 있습니다.
- 배포할 application commit이 `develop`에 있습니다.

기반을 다시 만들고 확인합니다.

```bash
bash scripts/bootstrap-gcp.sh

gcloud artifacts repositories describe builder-cup \
  --project=stunning-crane-508614-c1 --location=asia-northeast1
gcloud iam service-accounts describe \
  builder-cup-runtime@stunning-crane-508614-c1.iam.gserviceaccount.com \
  --project=stunning-crane-508614-c1
gcloud secrets describe builder-cup-demo-key --project=stunning-crane-508614-c1
gh variable list --repo Sihyeon-Ji/2026-google-ai-builder-cup
```

Secret을 삭제했다면 bootstrap이 새 team access code를 만듭니다. 예전 code는 더 이상 동작하지 않으므로
새 값을 private channel로 전달합니다.

평소처럼 새 application commit을 승격합니다. `release/gcp`가 원하는 commit을 이미 가리키면 일반
`git push`로는 push event가 생기지 않아 배포가 시작되지 않습니다. 이 경우 먼저 재배포용 빈 commit을
명시적으로 만듭니다.

```bash
git switch develop
git commit --allow-empty -m "ops: redeploy GCP"
git push origin develop
git switch release/gcp
git merge --ff-only develop
git push origin release/gcp
git switch develop
```

Release 완료를 기다리고 배포된 서비스를 확인합니다.

```bash
RUN_ID=$(gh run list --repo Sihyeon-Ji/2026-google-ai-builder-cup \
  --workflow="Deploy GCP" --branch=release/gcp --limit=1 \
  --json=databaseId --jq='.[0].databaseId')
gh run watch "$RUN_ID" --repo Sihyeon-Ji/2026-google-ai-builder-cup --exit-status

SERVICE_URL=$(gcloud run services describe builder-cup \
  --project=stunning-crane-508614-c1 --region=asia-northeast1 \
  --format='value(status.url)')
curl --fail --silent --show-error "$SERVICE_URL/" >/dev/null
curl --fail --silent --show-error "$SERVICE_URL/api/health"
curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' \
  --header 'Content-Type: application/json' \
  --data '{"text":"Deployment verification"}' \
  "$SERVICE_URL/api/analyze"
```

마지막 명령은 `401`을 반환해야 합니다. Anonymous caller가 model token 비용을 발생시킬 수 없다는 뜻입니다.
그다음 team code를 private하게 조회하고 `SERVICE_URL`을 연 뒤 합성 text를 제출합니다. UI에 provider
`gemini`, 설정한 model, 성공 결과가 나오는지 확인합니다. Health만으로는 Vertex AI 접근을 증명할 수
없습니다.

### 삭제 상태별 예상 결과

| 삭제되거나 손상된 항목 | CD를 바로 실행한 결과 | 복구 방법 |
| --- | --- | --- |
| Cloud Run 서비스만 삭제 | 자동으로 재생성 | 삭제 완료 후 새 `release/gcp` commit push |
| `app` image 묶음만 삭제 | 자동으로 재build·게시 | Bootstrap 불필요 |
| Artifact Registry repository | Image push 실패 | Bootstrap 후 release |
| Workload Identity provider 또는 배포 service account | GitHub 인증 실패 | Bootstrap 후 release |
| Runtime service account 또는 demo secret | Cloud Run 배포 실패 | Bootstrap 후 release |
| 관리 resource가 남은 상태에서 Terraform state bucket | Bootstrap이 resource 충돌 가능 | State를 복구/import하고 빈 state로 진행하지 않음 |
| 문서 순서대로 전체 기반 삭제 | 예상대로 직접 CD 실패 | Bootstrap 후 release |
| 결제 비활성화 또는 project 삭제 | Bootstrap과 CD 실패 | Project와 결제를 먼저 복구 |

## 로그와 모니터링

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="builder-cup"' \
  --project=stunning-crane-508614-c1 --limit=30 --format=json
```

`jsonPayload.request_id`로 검색하면 request, retry, completion record를 연결할 수 있습니다.
`Builder Cup operations` dashboard는 request rate와 application error를 보여줍니다. 기존 Cloud Run
metric에는 latency와 instance 수가 있으며 token 사용량과 추정 비용은 구조화된 completion log에
기록됩니다. 비용 추정치를 활성화할 때는 가격 값을 의도적으로 설정합니다. 팀 수신자가 정해질 때까지
paging/notification channel은 만들지 않습니다.

## 되돌리기

```bash
gcloud run revisions list --service=builder-cup --region=asia-northeast1 \
  --project=stunning-crane-508614-c1
bash scripts/rollback-gcp.sh KNOWN_GOOD_REVISION
```

Rollback은 traffic만 옮깁니다. 문제가 있는 image와 log는 조사할 수 있도록 남습니다. 다음 release 전에
`develop`에서 문제 commit을 revert하고 수정 commit을 `release/gcp`로 승격합니다. Rollback에
`--to-latest`를 사용하지 않습니다.

## 비밀값 교체

Secret Manager에 새 version을 추가한 뒤 새 release를 실행해 instance가 값을 다시 읽게 합니다.
현재 배포는 `latest`를 참조하므로 예전 revision으로 rollback해도 secret이 함께 돌아가지는 않습니다.
예전 instance가 모두 종료될 때까지 이전 version을 유지합니다. Secret 값을 issue나 CI log에 붙이지
않습니다.

## 로컬 Docker 설정

`docker compose up -d`나 로컬 image test 전에 Docker Desktop을 설치하고 실행합니다. `docker info`로
engine을 확인합니다. 시작하지 않으면 Docker Desktop의 로컬 onboarding을 끝내고 `docker context ls`를
확인합니다. 예전 계정 path 복구 과정은 세션 인수인계 문서에 과거 기록으로만 남아 있으며 다른 Mac의
필수 설정 단계가 아닙니다. Context를 고치기 위해 기존 Docker data를 삭제하지 않습니다.
