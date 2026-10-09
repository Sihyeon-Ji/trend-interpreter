# GCP 설정 및 운영

> **2026-10-04 변경:** 이전 실습 앱 `builder-cup` 서비스와 팀 접근 코드 secret, 전용 런타임 계정을 삭제했다. 운영 서비스는 `trend-production-web`(공개)과 `trend-production-api`(IAM 인증 필수)이며 `release/gcp`의 `trend_app` job이 `scripts/deploy-trend.sh`로 배포한다. uptime check는 웹 `/map`, 오류 경보는 두 서비스의 5xx를 본다. 현재 구성과 명령은 [Cloud Run 서비스 준비](../개발환경/Cloud-Run-서비스-준비.md)를 따른다. 아래의 `builder-cup`·`/api/analyze` 명령은 이전 기록이며, Artifact Registry `builder-cup` repository와 `builder-cup-deploy` 배포 계정·알림 relay는 계속 쓴다.

Project는 `stunning-crane-508614-c1`입니다. Cloud Run과 Artifact Registry는 도쿄
`asia-northeast1`을 사용합니다. Gemini location은 `global`이며 이는 한국 내 데이터 보관을
보장한다는 뜻이 아닙니다.

자주 찾는 운영 절차는 [AI 호출 중지·요청 한도 조정](AI-호출-제어.md),
[개발 명령어](../개발환경/개발-명령어.md), [배포 기록과 복구](배포-복구.md)에서 바로 확인할 수 있습니다.

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
6. `release/gcp`에 push하면 변경 범위를 확인해 필요한 검사와 서비스 배포만 실행됩니다.

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
- Discord webhook Secret Manager metadata
- Pub/Sub 알림 전달·dead-letter 리소스
- Uptime check, alert policy, log 기반 metric과 운영 dashboard
- GitHub 배포 variable과 `gcp` environment

Cloud Run 서비스에는 변경할 수 없는 image digest가 필요하므로 bootstrap은 application과 alert relay
서비스를 만들지 않습니다. 각 첫 CD가 서비스를 만들고 이후 CD는 후보 revision을 만든 뒤 smoke check에
성공할 때까지 현재 revision의 traffic을 유지합니다. Domain mapping은 별도이며 팀 소유 domain이 생길
때까지 만들지 않습니다.

`release/gcp`의 `Release GCP` workflow는 변경 범위를 계산하고 공통 검사를 최대 한 번 실행합니다.
Application과 alert relay는 변경된 서비스만 별도 job으로 배포합니다. Terraform만 바뀌면 인프라 검증만
실행하며 자동 apply하지 않습니다. `develop` push는 자동 CI를 시작하지 않습니다.
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

## AI 호출 일시 중지와 요청 한도

호출 중지·재개, 분당·동시 요청 수 조정, 배포와 비용 없는 확인 방법은
[운영 AI 호출 제어 안내](AI-호출-제어.md)에 모았습니다. 현재 기본값은 인스턴스당 분당 12건,
동시 실행 2건입니다.

## Discord 운영 알림

운영 장애 알림은 다음 경로로 전달합니다.

```text
Cloud Monitoring → Pub/Sub → private Cloud Run relay → Discord
```

Discord 경로가 실패하면 운영 이메일 채널이 relay 5xx와 dead-letter backlog를 알립니다. 실제 이메일
주소는 Git 제외 `infra/gcp/operations.auto.tfvars.json`에만 두고 저장소에는 기록하지 않습니다.

```json
{
  "alert_email_address": "team@example.com"
}
```

Terraform이 `discord-webhook` secret metadata를 관리하지만 값은 state에 넣지 않습니다. Discord에서
webhook을 새로 만들거나 교체했을 때 다음과 같이 새 version을 추가합니다.

```bash
read -r -s DISCORD_WEBHOOK_URL
printf '%s' "$DISCORD_WEBHOOK_URL" |
  gcloud secrets versions add discord-webhook \
    --data-file=- \
    --project=stunning-crane-508614-c1
unset DISCORD_WEBHOOK_URL
```

Webhook URL을 명령 인수, 문서, issue, chat에 직접 쓰지 않습니다. Relay 배포는 최신 활성 secret version의
숫자를 확인해 해당 version에 고정합니다.

`release/gcp`에서 relay 관련 파일이 바뀌면 `Release GCP`의 alert relay job이 별도 image를 만들고 private
Cloud Run 서비스 `builder-cup-alert-relay`를 배포합니다. 인증된 `/health` 확인 후 traffic을 전환하고,
합성 복구 알림을 Pub/Sub에 발행합니다. 배포 job은 해당 revision의 전달 성공 로그까지 기다립니다.
제한 시간 안에 확인되지 않으면 성공으로 표시하지 않으며, 전파 지연만으로 자동 rollback하지 않습니다.

현재 구성을 확인할 때는 secret 값을 읽지 않는 다음 명령을 사용합니다.

```bash
gcloud run services describe builder-cup-alert-relay \
  --project=stunning-crane-508614-c1 \
  --region=asia-northeast1

gcloud pubsub subscriptions describe builder-cup-discord-relay \
  --project=stunning-crane-508614-c1

gcloud monitoring uptime list-configs \
  --project=stunning-crane-508614-c1
```

Relay 로그는 허용 목록 metadata만 남깁니다. 전달 성공·실패를 확인할 때 전체 payload 대신 다음 event를
조회합니다.

```text
resource.type="cloud_run_revision"
resource.labels.service_name="builder-cup-alert-relay"
textPayload:"discord_delivery_"
```

Relay는 최소 instance 0, 최대 1입니다. Pub/Sub은 최소 10초, 최대 600초의 backoff로 재시도하며
5회 전달 시도를 설정했습니다. 실제 횟수는 Pub/Sub의 근사 처리 결과라 다를 수 있습니다. 반복 실패는
`builder-cup-monitoring-alerts-dlq`로 격리하고 확인용 subscription은 메시지를 7일간 보존합니다.
두 subscription은 비활성 만료를 해제했습니다.

구현과 실제 장애·복구·dead-letter 검증 결과는
[Discord 운영 알림 중계기 완료 기록](../plans/archive/01-production-alerting.md)에 있습니다.

## 웹 화면과 팀 접근 코드 사용법

Cloud Run은 구매한 domain 없이도 HTTPS `run.app` URL을 제공합니다. 배포된 서비스 URL을 browser에서
열면 됩니다. Custom domain mapping은 팀이 소유하고 소유권을 확인할 수 있는 domain이 있어야 합니다.
Domain을 사거나 이전한 뒤에만 추가하며 현재 배포와 공개 web 접근에는 필요하지 않습니다.

화면의 `Team access code`는 Google 계정 비밀번호나 Gemini API key가 아닙니다. 공개된 Cloud Run
주소에서 팀원만 모델을 호출하도록 bootstrap이 무작위로 생성한 팀 공용 비밀번호입니다. 실제 값은
Secret Manager의 `builder-cup-demo-key`에 있습니다. 배포 이후 새 version을 추가했더라도 배포 전까지는
현재 traffic을 받는 revision이 참조하는 숫자 version의 코드가 유효합니다.

```bash
SERVING_REVISION=$(gcloud run services describe builder-cup \
  --project=stunning-crane-508614-c1 --region=asia-northeast1 \
  --format=json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(next(x["revisionName"] for x in d["status"]["traffic"] if x.get("percent")==100))')
SECRET_VERSION=$(gcloud run revisions describe "$SERVING_REVISION" \
  --project=stunning-crane-508614-c1 --region=asia-northeast1 \
  --format=json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(next(x["valueFrom"]["secretKeyRef"]["key"] for x in d["spec"]["containers"][0]["env"] if x["name"]=="DEMO_API_KEY"))')
gcloud secrets versions access "$SECRET_VERSION" \
  --secret=builder-cup-demo-key \
  --project=stunning-crane-508614-c1
unset SERVING_REVISION SECRET_VERSION
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

추가적인 계정 전체 알림 예산이 필요하다면 무시 대상인 `infra/gcp/terraform.tfvars`에 billing
account 통화와 일치하는 `billing_account`, `monthly_budget`, `budget_currency`를 설정한 뒤 plan/apply합니다.
현재는 이 선택적 알림 예산을 사용하지 않습니다. 생성하면 account의 기본 billing 수신자에게 50%, 90%,
100% 알림을 보냅니다. Budget 생성에는 billing account 권한이 필요합니다. **알림 전용 예산은 지출을
중단하지 않습니다.** 실제 account에서 model quota와
접근 권한, budget, 알림 수신자, 실제 model 가격을 확인해야 합니다. Cloud Run이 0으로 축소돼도 image
storage는 남습니다.

2026-09-26에 계정 전체 월 ₩100,000 **알림 전용 예산은 삭제**하고, 이 프로젝트에 월 ₩100,000
**지출 한도**를 서비스별로 설정했습니다. 현재 메인 API의 `GeminiProvider`는 Vertex AI
(`aiplatform.googleapis.com`)를 사용하므로 **Vertex AI** 한도가 배포된 모델 요청에 적용됩니다.
**Gemini API**(`generativelanguage.googleapis.com`) 한도는 직접 API 키를 쓰는 별도 경로에 적용됩니다.
**Cloud Run** 한도는 이 프로젝트의 메인 서비스와 알림 중계기를 포함한 Cloud Run 사용에 적용됩니다.
세 상한은 합산 ₩100,000이 아니라 **각 서비스별 ₩100,000**입니다.

지출 한도는 [Billing → 예산 및 알림](https://console.cloud.google.com/billing?project=stunning-crane-508614-c1)에서
`Builder Cup Vertex AI Gemini 월 지출 한도`, `Builder Cup Gemini API 월 지출 한도`,
`Builder Cup Cloud Run 월 지출 한도`의 상태 `구성됨`으로 확인합니다. 세 한도 각각에 50%·80%·100%
이메일 알림이 설정돼 있으며 결제 관리자·사용자와 프로젝트 소유자가 수신 대상으로 활성화돼 있습니다.
100% 도달 시 해당 서비스의 새 사용이 일시중지됩니다. 집행은 즉시가 아니어서 초과 요금이
발생할 수 있고, Cloud Run이 중지되면 데모 요청은 `5xx`가 됩니다. 사용을 재개하려면 콘솔에서 한도를
해제하거나 조정해야 합니다. 다른 서비스의 비용은 이 상한에 포함되지 않습니다.
[GCP 지출 한도 설명](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps)

이 Preview 한도는 gcloud에 옵션이 없어 콘솔에서 관리합니다(2026-09-26 생성 시 콘솔 화면을 자동 조작). 종전 Plan 06의 Gemma GPU 전용 예산·경보는 GPU 배포 계획과 함께 철회했습니다([결정과 비용 비교](../AI-개발/Gemma-로컬-편집-엔진-결정.md)). 기존 알림 예산의 Terraform 설정과 구별하며,
`gcloud billing budgets list` 결과에 세 지출 한도가 보이지 않더라도 콘솔의 `구성됨` 상태를 확인합니다.

### Cloud Storage

2026-10-01 콘솔에서 확인한 값입니다.

| 항목 | 값 |
| --- | --- |
| 프로젝트 ID (`x-goog-project-id`) | `stunning-crane-508614-c1` |
| 요청 엔드포인트 | `https://storage.googleapis.com` |
| 버킷 | `gs://stunning-crane-508614-c1-tfstate` 하나. Terraform state 전용입니다([콘솔](https://console.cloud.google.com/storage/browser/stunning-crane-508614-c1-tfstate)) |
| 버킷 설정 | `scripts/bootstrap-gcp.sh`가 도쿄(`asia-northeast1`)에 만들고 균일한 버킷 수준 액세스·공개 액세스 방지·버전 관리를 켭니다. 저장 등급을 지정하지 않으므로 Standard입니다 |

도쿄(`asia-northeast1`) 저장 요금은 GiB당 월 **Standard US$0.023**, Nearline US$0.016, Coldline US$0.006, Archive US$0.0025, Rapid Cache US$0.120012입니다([Cloud Storage 가격](https://cloud.google.com/storage/pricing), 2026-10-01 화면). 요청 횟수와 리전 밖 데이터 전송은 별도로 과금됩니다.
Terraform state는 KB 단위 JSON이라 버전 관리로 이전 판이 쌓여도 저장 비용은 사실상 0입니다.

**Cloud Storage는 위 서비스별 지출 한도에 포함되지 않습니다.** 사용량이 늘어도 자동으로 멈추지 않습니다. Kaggle Gemma 실험은 GCS·BigQuery 등 이 프로젝트의 GCP에 연결하지 않고 Kaggle 저장 공간만 씁니다([Plan 06](../plans/06-gemma-on-cloud-run-gpu.md)). 새 버킷을 만들거나 모델·데이터를 GCS에 둘 계획이 생기면, 그 전에 Cloud Storage 지출 한도를 걸고 이 표를 갱신합니다.

## Gemini 사용량과 비용 확인

운영 화면에서 올바른 `Team access code`로 `Analyze text`를 실행하면 Cloud Run의 FastAPI가
`gemini-3.5-flash`를 Vertex AI Gemini API로 호출합니다. 확인 목적에 따라 보는 화면이 다릅니다.

| 확인할 내용 | Console 위치 | 표시 시점 |
| --- | --- | --- |
| 개별 요청의 입력·출력 token | **Logging → Logs Explorer**에서 `analysis_completed` 검색 | 요청 직후에 가까움 |
| Model별 호출 수·token 추이 | **Monitoring → Metrics Explorer**에서 Vertex AI Publisher Model metric 선택 | Monitoring 수집 지연 후 |
| API request·error·latency | **APIs & Services → Vertex AI API → Metrics** | 짧은 수집 지연 후 |
| 실제 청구 비용 | **Billing → Reports**에서 project와 service/SKU filter | 실시간 아님 |

바로 확인할 때는 [Logs Explorer](https://console.cloud.google.com/logs/query?project=stunning-crane-508614-c1)에서
다음 query를 사용합니다.

```text
resource.type="cloud_run_revision"
resource.labels.service_name="builder-cup"
jsonPayload.message="analysis_completed"
```

Log record의 `usage.input_tokens`, `usage.output_tokens`, `model`, `request_id`를 확인할 수 있습니다. 원문과
생성 결과는 log에 남기지 않습니다. 같은 값은 웹 결과의 **Run details → Tokens in / out**에서도 볼 수
있습니다.

시간에 따른 사용량은 [Metrics Explorer](https://console.cloud.google.com/monitoring/metrics-explorer?project=stunning-crane-508614-c1)에서
resource type을 **Vertex AI Publisher Model**로 선택하고 다음 metric을 사용합니다.

- `Model invocation count`: 모델 호출 수
- `Token count`: 누적 입력·출력 token 수
- 필요하면 model, input/output token type, response code로 구분

실제 비용은 [Cloud Billing Reports](https://console.cloud.google.com/billing/reports?project=stunning-crane-508614-c1)에서
기간을 현재 월로 두고 project를 `stunning-crane-508614-c1`로 제한한 뒤 **Service** 또는 **SKU**로
grouping합니다. `Vertex AI` 관련 항목이 Gemini 비용입니다. 필요하면 `Cloud Run`과 `Artifact Registry`도
각각 filter합니다.

Billing report는 실시간 계측 화면이 아닙니다. 빠르면 사용 후 5~15분에 반영되는 항목도 있지만 보통
하루 안에 나타나며 24시간 이상 늦을 수도 있습니다. 따라서 방금 한 요청은 Logs Explorer와 Metrics
Explorer로 먼저 확인하고, 청구 금액은 Billing report에서 나중에 확인합니다. 현재 Cloud Run에는 token
단가 환경 변수를 넣지 않았으므로 웹 화면의 `Estimated cost`는 `Pricing not configured`로 표시됩니다.
Metric 이름은 [Google Cloud의 Vertex AI metric 목록](https://docs.cloud.google.com/monitoring/api/metrics_gcp_a_b),
비용 반영 지연은 [Cloud Billing report 안내](https://docs.cloud.google.com/billing/docs/how-to/reports#data-availability)에서
확인할 수 있습니다.

## Artifact Registry image 자동 정리

배포할 때마다 commit SHA tag가 붙은 image와 관련 manifest가 Artifact Registry에 추가됩니다. Layer를
공유하더라도 아무 정책이 없으면 version이 계속 남아 storage 사용량이 증가합니다. 이 저장소의 Terraform은
다음 cleanup policy를 관리합니다.

| 정책 | 동작 |
| --- | --- |
| `keep-10-most-recent-versions` | Package별 최근 version 10개는 나이와 관계없이 보존 |
| `delete-images-older-than-30-days` | 30일보다 오래된 나머지 tagged·untagged version 삭제 |

Cleanup은 CD 단계에서 실행하지 않습니다. Artifact Registry background job이 주기적으로 실행하며 정책
변경이 실제 삭제에 반영되기까지 약 하루가 걸릴 수 있습니다. Docker parent manifest가 참조하는 image는
parent가 삭제될 때까지 유지됩니다.

현재 repository 크기는 다음 명령으로 확인합니다.

```bash
gcloud artifacts repositories describe builder-cup \
  --project=stunning-crane-508614-c1 \
  --location=asia-northeast1
```

Artifact Registry 저장 용량은 billing account 전체 합산 기준 월 0.5GiB까지 무료이고, 그 이상은 저장량에
따라 과금됩니다. 따라서 작은 초기 저장량의 비용은 0일 수 있지만 자동 정리 없이 배포를 계속하는 것은
좋지 않습니다. 모든 image 저장 비용까지 없애려면 Cloud Run을 먼저 삭제한 다음 아래의 수동 image 삭제
절차를 사용합니다.

## 비용 절감을 위한 삭제 수준

목표에 맞는 가장 작은 삭제 범위를 선택합니다. Release workflow는 Terraform이나
`bootstrap-gcp.sh`를 실행하지 않으며 기반 인프라가 이미 있다고 가정합니다. Cloud Run 서비스가 없으면
새로 만들 수 있지만 Registry, identity, IAM binding, secret이 없으면 복구하지 못하고 실패합니다.

**이 project에서는 개발을 오래 쉴 때 Cloud Run 서비스만 삭제하는 것으로 충분합니다.** 그러면 Cloud
Run request가 처리되지 않고 Gemini도 호출되지 않습니다. Artifact Registry, Terraform state bucket,
Secret Manager 같은 작은 기반 resource는 남으므로 비용이 절대 0이라고 보장할 수는 없지만, image 자동
정리 정책까지 적용되어 있어 남는 비용은 매우 작게 유지됩니다. 이후 기반 resource가 그대로 있는 상태에서
서비스에 영향을 주는 새 commit이나 [명시적 재배포 commit](배포-복구.md#변경-파일-없이-서비스-재배포)을
`release/gcp`에 push하면 CD가 Cloud Run 서비스를 다시 만듭니다.

| 단계 | 삭제 대상 | 남는 대상 | 관련 변경 또는 명시적 재배포 push로 복구 가능? |
| --- | --- | --- | --- |
| 그대로 유지 | 없음 | 서비스와 전체 기반 인프라 | 가능 |
| 서비스 중단 | Cloud Run 서비스 | Image, registry, identity, secret, monitoring, Terraform state | 서비스 삭제가 끝난 뒤 가능 |
| 서비스와 image 정리 | Cloud Run 서비스와 `app` image 묶음 | 비어 있는 registry와 나머지 기반 인프라 | 가능. CD가 새 image를 먼저 게시 |
| 기반 인프라 전체 제거 | Cloud Run, image, Terraform 관리 기반, state bucket | Project, 결제 연결, 활성 API | 불가능. CD 전에 bootstrap 필요 |

최소 instance 0인 요청 기반 서비스에는 유휴 Cloud Run instance 비용이 없지만 공개 request가 들어오면
instance가 시작될 수 있습니다. 서비스를 삭제하면 request를 막고 revision도 함께 삭제합니다. Artifact
Registry image는 Cloud Run과 함께 삭제되지 않지만 위 cleanup policy가 오래된 version을 정리합니다.
Artifact Registry storage, Terraform state storage, Gemini request, project의 다른 resource는 각각 별도
과금 기준을 가집니다. 공식 문서는
[Cloud Run 과금 설정](https://docs.cloud.google.com/run/docs/configuring/billing-settings),
[서비스 삭제 동작](https://docs.cloud.google.com/run/docs/managing/services#delete),
[Artifact Registry 가격](https://cloud.google.com/artifact-registry/pricing),
[cleanup policy](https://docs.cloud.google.com/artifact-registry/docs/repositories/cleanup-policy)를 참고합니다.

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

평소처럼 새 application commit을 승격합니다. 변경 파일 없이 서비스를 다시 만들 때는
[명시적 재배포 commit](배포-복구.md#변경-파일-없이-서비스-재배포)을 사용합니다.

Release 완료를 기다리고 배포된 서비스를 확인합니다.

```bash
RUN_ID=$(gh run list --repo Sihyeon-Ji/2026-google-ai-builder-cup \
  --workflow="Release GCP" --branch=release/gcp --limit=1 \
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
| Cloud Run 서비스만 삭제 | 자동으로 재생성 | 삭제 완료 후 서비스 관련 변경 또는 명시적 재배포 commit push |
| `app` image 묶음만 삭제 | 자동으로 재build·게시 | Bootstrap 불필요 |
| Artifact Registry repository | Image push 실패 | Bootstrap 후 release |
| Workload Identity provider 또는 배포 service account | GitHub 인증 실패 | Bootstrap 후 release |
| Runtime service account 또는 demo secret | Cloud Run 배포 실패 | Bootstrap 후 release |
| 관리 resource가 남은 상태에서 Terraform state bucket | Bootstrap이 resource 충돌 가능 | State를 복구/import하고 빈 state로 진행하지 않음 |
| 문서 순서대로 전체 기반 삭제 | 예상대로 직접 CD 실패 | Bootstrap 후 release |
| 결제 비활성화 또는 project 삭제 | Bootstrap과 CD 실패 | Project와 결제를 먼저 복구 |

## 운영 DB 백업

운영 Cloud SQL의 `trend` DB는 매일 03:00 KST에 논리 백업한다. 체험 인스턴스는 관리형 백업·PITR을 지원하지 않으므로 이 백업이 유일한 복구 수단이다([Plan 13](../plans/13-cloud-sql-trial-to-paid-transition.md)). 리소스는 `infra/gcp/hybrid/backup.tf`에 있다.

| 항목 | 값 |
| --- | --- |
| 실행 | Scheduler `trend-production-backup-daily`가 Cloud Run Job `trend-production-backup`을 실행한다 |
| 내용 | `pg_dump --format=custom --no-owner --no-privileges --schema=public`. 검수 기록·계정 설정·Gemini 장부 같은 사용자 표도 포함한다. Cloud SQL 전용 `google_vacuum_mgmt` 스키마는 일반 PostgreSQL에서 복원되지 않아 뺀다 |
| 보관 | 비공개 버킷 `stunning-crane-508614-c1-trend-production-backups`. 14일 뒤 삭제, 지운 객체는 soft delete로 7일 더 남는다 |
| 권한 | `trend-production-backup` SA는 Cloud SQL 연결, 운영 DB secret 읽기, 이 버킷 객체 읽기·쓰기, 이 Job 실행만 가진다. DB 접속은 앱과 같은 `trend_app` 계정이다(10-04 결정) |
| 경보 | Job 실행이 실패하면 "Trend scheduled job failed", Scheduler가 Job을 실행하지 못하면 "Trend scheduled job was not started"가 Discord와 운영 이메일로 온다. 두 경보는 유지보수 Job도 함께 본다 |

수동 실행과 상태 확인은 다음과 같다.

```bash
gcloud scheduler jobs run trend-production-backup-daily --location=asia-northeast1 --project=stunning-crane-508614-c1
gcloud run jobs executions list --job=trend-production-backup --region=asia-northeast1 --project=stunning-crane-508614-c1 --limit=5
gcloud storage ls -l gs://stunning-crane-508614-c1-trend-production-backups/
```

복원 검증은 최신 백업(또는 인자로 준 객체)을 내려받아 임시 PostgreSQL 18.6에 복원하고 표별 행 수만 보고한다. 덤프는 임시 디렉터리에만 두고 끝나면 지운다.

```bash
scripts/verify-production-backup.sh "" manifests/production-backup-verify-<날짜>.json
```

2026-10-04 첫 실행 결과([보고서](../../manifests/production-backup-verify-20261004.json)): 덤프 52.9MB, Job 8초, 로컬 복원 2초, 표 48개·659,712행, `schema_migrations` 15개가 저장소 migration 수와 같다.

다른 DB에 복원할 때는 덤프에 `CREATE SCHEMA public`이 들어 있으므로 빈 DB의 기본 `public` 스키마를 먼저 지우고 `pg_restore --no-owner --no-privileges --exit-on-error`로 복원한다. 사용자 표가 포함된 사본을 복원한 뒤에는 보존 기간 정리(`prune_user_text`)를 실행한다. 운영 DB에 덮어쓰는 복원은 하지 않는다.

## 유지보수 Job

PC와 무관하게 매일 04:00 KST에 `trend-production-maintenance`가 API 이미지의 `scripts/maintenance.py`를 한 번 실행한다. 리소스는 `infra/gcp/hybrid/maintenance.tf`에 있다.

| 항목 | 내용 |
| --- | --- |
| 정리 | 해석 캐시 7일, 못 답한 질문 30일이 지난 행을 지운다(`prune_user_text`) |
| 점검 | 마지막 정상 게시(board·dashboard 성공)가 `STALE_AFTER_HOURS`보다 오래됐는지 본다. 운영 DB는 갱신 도구로 며칠에 한 번 바뀌므로 Job에서는 192시간(8일)이다. API의 `/meta`는 기본 12시간 그대로다 |
| 결과 | 지운 건수·게시 시각·경과 시간만 담은 `event=maintenance` 로그 한 줄. 종료 코드 0 정상, 1 실패, 2 오래됨. 0이 아니면 "Trend scheduled job failed" 경보가 온다. 재시도는 하지 않는다 |
| 권한 | `trend-production-maintenance` SA는 Cloud SQL 연결, 운영 DB secret 읽기, 이 Job 실행만 가진다 |
| 이미지 | `production.tfvars.json`의 `services.api_image`. 유지보수 코드를 바꾸면 배포 뒤 이 값을 새 digest로 바꾸고 적용한다 |

```bash
gcloud scheduler jobs run trend-production-maintenance-daily --location=asia-northeast1 --project=stunning-crane-508614-c1
gcloud logging read 'resource.labels.job_name="trend-production-maintenance" AND jsonPayload.event="maintenance"' \
  --project=stunning-crane-508614-c1 --limit=1 --format='value(jsonPayload.message)'
```

2026-10-05 첫 실행: `status=ok`, 지운 행 0건, 마지막 게시 1.8시간 전(기준 192시간).

## Terraform 변수 파일 사본

`infra/gcp`와 `infra/gcp/hybrid`의 `*.tfvars.json` 5개(경보 이메일, GitHub ID, staging·production·GPU 검증 입력)는 Git에서 제외된다. 이 파일이 없으면 다른 checkout에서 운영 Terraform을 적용할 수 없으므로 Secret Manager `trend-terraform-vars`(도쿄 단일 지역)에 묶어 둔다. 자격증명은 들어 있지 않고 이미지 digest·숫자 secret version·이메일 주소만 있다.

```bash
scripts/terraform-vars.sh save      # 파일을 고친 뒤 새 version 저장
scripts/terraform-vars.sh restore   # 없는 파일만 되살린다. 내용이 다른 로컬 파일은 덮지 않는다
```

## 운영 DB 갱신

수집 PC의 새 snapshot을 운영에 반영하는 절차다. 설계와 결정은 [Plan 19](../plans/19-production-data-refresh.md)에 있다. 운영 DB에 직접 덮어쓰지 않고, 새 DB를 만들어 운영의 사람 결정(검수 기록·사람 승인 뜻·사람 리스크·제외)과 Gemini 장부·사용자 표를 덮어 얹은 뒤 API 연결만 바꾼다. 도구는 `scripts/refresh-production-db.sh`다.

### 준비 – 서비스에 영향 없음

```bash
# 1. 수집 PC가 올린 최신본 고정. ID는 updated_at.txt의 수집 시각과 수집기 커밋이다.
gcloud storage cat gs://copybara-team-shared-bucket/taewoo/trend-interpreter/db/latest/updated_at.txt
scripts/refresh-production-db.sh capture <snapshot-id>

# 2. 로컬 임시 PostgreSQL에서 적재·덮어 얹기·재계산·대조 후 덤프. 운영 DB는 읽기만 한다. 생애주기 재계산 때문에 40분 넘게 걸린다.
scripts/refresh-production-db.sh build <snapshot-id>

# 3. Cloud SQL에 빈 DB를 만들고(임시 관리자 계정은 끝나면 지운다) 덤프를 올린다.
scripts/refresh-production-db.sh create trend_<날짜>
scripts/refresh-production-db.sh upload trend_<날짜> artifacts/refresh/<snapshot-id>/trend.dump
```

`build`의 보고서는 `artifacts/refresh/<snapshot-id>/`(Git 제외)에 남는다. `compare.json`의 `differences`가 비어 있어야 한다. 덤프에는 사용자 표가 들어 있으므로 권한 600으로 두고 공유하지 않는다.

### 전환 – 검수 5분 중지

```bash
# 4. 검수자에게 알리고 검수를 멈춘 뒤, 그 사이 결정을 다시 옮기고 대조한다. 빠진 결정이 있으면 실패한다.
scripts/refresh-production-db.sh overlay trend_<날짜> artifacts/refresh/<snapshot-id>/catchup.json

# 5. 새 DB를 가리키는 secret version을 추가한다. 출력의 마지막 숫자가 새 version이다.
scripts/refresh-production-db.sh secret trend_<날짜>
```

6. `infra/gcp/hybrid/production.tfvars.json`의 `services.database_secret_version`을 새 version으로 바꾸고 (Terraform은 `infra/gcp/hybrid`에서 `TF_DATA_DIR=.terraform/production`으로 실행한다 – 기본 `.terraform`은 staging 상태다) `scripts/terraform-vars.sh save`로 사본을 남긴 뒤, API와 백업 Job만 적용한다. API는 새 revision이 생기지만 트래픽은 지금 revision에 남는다.

```bash
terraform plan -var-file=production.tfvars.json \
  -target=google_cloud_run_v2_service.api -target=google_cloud_run_v2_job.backup \
  -target='google_secret_manager_secret_iam_member.runtime["api-DATABASE_URL"]' \
  -target='google_secret_manager_secret_iam_member.runtime["backup-DATABASE_URL"]' -out=switch.tfplan
terraform apply switch.tfplan
```

   10-09부터 API는 배포 스크립트가 revision 이름을 정해 Terraform이 409로 실패한다. 그때는 백업 Job만 Terraform으로 맞추고, API는 **서비스 정의를 막 다시 읽어** Cloud Run v2 API로 template의 DB secret 버전과 새 revision 이름만 바꾼다(트래픽은 그대로, [Plan 19 10-09 기록](../plans/19-production-data-refresh.md#2026-10-09-두-번째-전환)). 덮어 얹기(4)는 반드시 secret(5) 전에 끝낸다.

7. 새 API revision이 Ready인지 보고 트래픽을 옮긴다. 웹은 DB를 직접 쓰지 않아 바꾸지 않는다.

```bash
gcloud run services describe trend-production-api --region=asia-northeast1 --format='value(status.latestCreatedRevisionName,status.latestReadyRevisionName)'
gcloud run services update-traffic trend-production-api --region=asia-northeast1 --to-revisions=<새 revision>=100
```

8. 운영 웹의 사전·지도·해석과 사전 항목 한 건을 열어 보고, 백업을 한 번 실행해 새 DB가 백업되는지 확인한다. 검수 재개를 알린다.

### 되돌리기

이전 API revision은 이전 secret version, 즉 이전 DB를 가리킨다. 트래픽만 돌리면 바로 이전 DB로 돌아간다.

```bash
gcloud run services update-traffic trend-production-api --region=asia-northeast1 --to-revisions=<이전 revision>=100
```

그 뒤 `production.tfvars.json`의 version을 되돌리고 같은 `terraform apply`로 백업 Job도 맞춘다. 전환 뒤 새 DB에 생긴 검수가 있으면, 되돌린 다음 반대 방향으로 옮겨야 하므로 Plan 19 4단계 규칙을 따른다. 이전 DB는 다음 갱신 때까지 지우지 않는다. 지울 때는 소유자인 `trend_app`으로 `DROP DATABASE`를 실행한다.

## 로그와 모니터링

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="builder-cup"' \
  --project=stunning-crane-508614-c1 --limit=30 --format=json
```

`jsonPayload.request_id`로 검색하면 request, retry, completion record를 연결할 수 있습니다.
`Builder Cup operations` dashboard는 request rate와 application error를 보여줍니다. 기존 Cloud Run
metric에는 latency와 instance 수가 있으며 token 사용량과 추정 비용은 구조화된 completion log에
기록됩니다. 비용 추정치를 활성화할 때는 가격 값을 의도적으로 설정합니다. Discord와 운영 이메일
알림 채널, uptime·오류 alert policy는 이미 활성화되어 있습니다.

## 되돌리기

메인과 relay의 안전한 사전 점검, 명시적 traffic 전환, 사후 health 확인은
[배포 복구 절차](배포-복구.md#이전-revision으로-되돌리기)를 사용합니다. `--to-latest`로 대상 revision을
추측하지 않습니다.

## 비밀값 교체

Secret Manager에 새 version을 추가한 뒤 새 release를 실행합니다. 메인 접근 코드와 relay webhook은
배포 시점에 활성 숫자 version으로 고정해 revision과 함께 기록합니다. 과거 `latest` 참조 메인 revision은
복구 명령에서 거부합니다. 예전 instance가 모두 종료될 때까지 이전 version을 유지합니다. Secret 값을
issue나 CI log에 붙이지 않습니다.

## 로컬 Docker 설정

`docker compose up -d`나 로컬 image test 전에 Docker Desktop을 설치하고 실행합니다. `docker info`로
engine을 확인합니다. 시작하지 않으면 Docker Desktop의 로컬 onboarding을 끝내고 `docker context ls`를
확인합니다. Mac 계정 이름을 바꾼 뒤 예전 home path를 참조하는 문제는 특정 장비의 복구 사례이며 다른
Mac의 필수 설정 단계가 아닙니다. Context를 고치기 위해 기존 Docker data를 삭제하지 않습니다.
