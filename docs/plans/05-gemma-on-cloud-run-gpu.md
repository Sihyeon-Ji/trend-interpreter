# Plan 05. Gemma 4를 Cloud Run GPU + vLLM으로 제공

작성일 **2026-09-28** · 상태 **설계 확정, 구현 대기** · 선행 작업 **없음(Plan 03과 독립)**

[계획 목록](README.md) · [Plan 03 배포](03-trend-cloud-run-deployment.md) · [모델 호출 경계](../운영/시스템-아키텍처.md#모델-호출-경계) · [로컬 vLLM 프로필](../../models/vllm/README.md)

## 왜 필요한가

번역(`gemma_translate`), 쉽게 풀어 쓰기(`gemma_rewrite`), 검색어 분류, 사전에 묻기(`pipeline/ask.py`)가
`USE_LOCAL_GEMMA`일 때 로컬 Gemma를 부릅니다. 지금은 개발 PC의 Ollama나 GPU 서버의 vLLM이 그 역할을 하는데,
Cloud Run에는 GPU도 Ollama도 없습니다. 대회 요건상 로컬 LLM은 Gemma 4 계열이어야 하므로, 운영에서도 Gemma 4를
어딘가에서 돌려야 합니다. 이 계획은 Google이 공식 예제로 안내하는 **Cloud Run GPU + vLLM** 방식으로 그 자리를 채웁니다.

코드는 이미 OpenAI 호환 주소(`LOCAL_LLM_BASE_URL`)를 지원하므로, 호출 인증만 추가하면 됩니다.

## 조사한 사실 (2026-09-28)

| 항목 | 내용 | 출처 |
| --- | --- | --- |
| GPU 리전 | NVIDIA L4는 **asia-southeast1(싱가포르)**, europe-west1·4, us-central1, us-east4. **도쿄(asia-northeast1)는 미지원** | [Cloud Run GPU 문서](https://docs.cloud.google.com/run/docs/configuring/services/gpu) |
| 최소 사양 | L4는 CPU 4·메모리 16 GiB 이상, 인스턴스당 GPU 1개 | 같은 문서 |
| 스케일 | 0으로 줄어들 수 있음. 요청이 없으면 GPU 비용 0 | 같은 문서 |
| 할당량 | 리전에서 처음 배포하면 `nvidia-l4` 3개(zonal redundancy 끔)가 자동 부여 | 같은 문서 |
| 비용 | L4 초당 과금, Tier 1 리전 기준 시간당 약 $0.67(zonal redundancy 끔). 인스턴스 기반 과금이라 켜져 있는 동안 CPU·메모리도 함께 과금 | [Cloud Run 요금](https://cloud.google.com/run/pricing) |
| 공식 예제 | 사전 빌드 이미지 `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:gemma4`로 `google/gemma-4-E2B-it` 서빙, `--no-allow-unauthenticated`, ID 토큰으로 호출 | [Codelab](https://codelabs.developers.google.com/codelabs/how-to-run-inference-cloud-run-gpu-vllm), [튜토리얼](https://docs.cloud.google.com/run/docs/tutorials/gpu-gemma2-with-vllm) |
| 모델 요구 | Gemma 4 E2B-it는 24 GB GPU 하나로 충분. vLLM 0.19.1 이상 | [vLLM 레시피](https://recipes.vllm.ai/Google/gemma-4-E2B-it) |
| 가중치 보관 | 10 GB 미만이면 컨테이너 이미지에 담는 것이 시작이 빠르고 예측 가능. Cloud Storage 볼륨은 저장 비용이 낮지만 Direct VPC 설정 필요. 인터넷 다운로드는 비권장 | [GPU 모범 사례](https://docs.cloud.google.com/run/docs/configuring/services/gpu-best-practices) |

공식 튜토리얼의 최신판은 RTX PRO 6000(CPU 20·메모리 80 GiB)을 쓰지만, E2B 모델은 L4로 충분하고 비용이 훨씬 낮습니다.

## 확정한 결정 (2026-09-28)

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 리전 | **asia-southeast1(싱가포르)** | 도쿄에는 Cloud Run GPU가 없음. 도쿄 API에서 부르는 지연은 수십 ms 수준 |
| 모델 | **`google/gemma-4-E2B-it`** | 로컬에서 같은 계열로 실측했고 L4 하나(24 GB)에 들어감 |
| 가중치 위치 | **컨테이너 이미지에 포함**(약 5 GB) | 빌드 때만 HF 토큰이 필요하고 콜드 스타트가 짧고 예측 가능 |
| 공개 범위 | **비공개**(`--no-allow-unauthenticated`) | Trend API 런타임 서비스 계정에만 `roles/run.invoker` |
| 인스턴스 | **최소 0 · 최대 1**, 동시성 4 | 요청이 없으면 GPU 비용 0. 첫 요청은 콜드 스타트 1~3분을 감수 |
| 이미지 | `vllm/vllm-openai:v0.19.1` 기반 자체 빌드 | 가중치를 담고 `models/vllm/compose.yaml`과 같은 인자를 쓰기 위해 |

시연 직전에만 최소 인스턴스를 1로 올리고, 끝나면 0으로 되돌립니다. 이 규칙은 아래 예산·알림으로 감시합니다.

## 예산과 알림

GPU는 켜져 있는 동안 계속 과금되므로 기존 서비스별 지출 한도와 별도로 Gemma 전용 예산과 경보를 둡니다.
**둘 다 gcloud로 만들며, Gemma 서비스를 처음 배포한 직후에 실행합니다.**

| 장치 | 설정 | 효과 | 만드는 방법 |
| --- | --- | --- | --- |
| 기존 Cloud Run 월 지출 한도(₩100,000) | 변경 없음 | GPU 비용도 Cloud Run에 청구되므로 이 한도에 포함됨. 100%에서 Cloud Run 전체 사용 중지 | 이미 있음(콘솔 전용 Preview 기능, gcloud 옵션 없음) |
| **Gemma 전용 알림 예산** | 월 **₩50,000**, 라벨 `app=builder-cup-gemma`만, 50%·80%·100% | Cloud Run 한도에 닿기 전에 GPU 지출만 따로 경고. ₩50,000은 L4 약 50시간 분량 | `gcloud billing budgets create` |
| **GPU 켜짐 경보** | `builder-cup-gemma` 인스턴스 수가 **2시간 연속 1 이상** | 시연 뒤 최소 인스턴스를 되돌리지 않은 실수를 Discord와 이메일로 알림 | `gcloud monitoring policies create` |

알림 예산은 지출을 멈추지 않습니다. 멈추는 장치는 기존 Cloud Run 지출 한도입니다.

### 1. 알림 채널 확인

기존 Discord 중계 채널과 운영 이메일 채널의 이름을 확인해 변수에 담습니다.

```bash
PROJECT_ID=stunning-crane-508614-c1
BILLING_ACCOUNT=011938-DF350E-463C2B
gcloud monitoring channels list --project="$PROJECT_ID" --format='table(name,displayName,type)'
DISCORD_CHANNEL=$(gcloud monitoring channels list --project="$PROJECT_ID" \
  --filter='displayName="Builder Cup Discord relay"' --format='value(name)')
EMAIL_CHANNEL=$(gcloud monitoring channels list --project="$PROJECT_ID" \
  --filter='displayName="Builder Cup operations email"' --format='value(name)')
```

### 2. Gemma 전용 알림 예산

배포 명령의 `--labels app=builder-cup-gemma`가 청구 데이터에 붙으므로 그 라벨로만 거릅니다.
예산 알림은 이메일 채널로 보내고, 결제 관리자 기본 수신자에게도 갑니다. 예산 알림은 Pub/Sub 형식이 Monitoring 사건과 달라 Discord 중계기로는 보내지 않습니다.

```bash
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT" \
  --display-name="Builder Cup Gemma GPU 월 알림 예산" \
  --budget-amount=50000KRW \
  --calendar-period=month \
  --filter-projects="projects/$PROJECT_ID" \
  --filter-labels=app=builder-cup-gemma \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.8 \
  --threshold-rule=percent=1.0 \
  --notifications-rule-monitoring-notification-channels="$EMAIL_CHANNEL"

gcloud billing budgets list --billing-account="$BILLING_ACCOUNT" \
  --format='table(displayName,amount.specifiedAmount.units,budgetFilter.labels)'
```

### 3. GPU 켜짐 경보

정책 파일은 저장소의 `infra/gcp/policies/gemma-gpu-on.json`으로 두고 커밋합니다(구현 단계에서 추가).

```json
{
  "displayName": "Builder Cup Gemma GPU 2시간 연속 켜짐",
  "combiner": "OR",
  "severity": "WARNING",
  "conditions": [{
    "displayName": "builder-cup-gemma instance count >= 1 for 2h",
    "conditionThreshold": {
      "filter": "metric.type=\"run.googleapis.com/container/instance_count\" resource.type=\"cloud_run_revision\" resource.label.service_name=\"builder-cup-gemma\"",
      "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_MAX", "crossSeriesReducer": "REDUCE_SUM"}],
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "7200s",
      "trigger": {"count": 1}
    }
  }],
  "alertStrategy": {"autoClose": "1800s", "notificationPrompts": ["OPENED", "CLOSED"]},
  "documentation": {"content": "시연이 끝났다면 gcloud run services update builder-cup-gemma --region asia-southeast1 --min-instances 0 으로 되돌립니다.", "mimeType": "text/markdown"}
}
```

```bash
gcloud monitoring policies create --project="$PROJECT_ID" \
  --policy-from-file=infra/gcp/policies/gemma-gpu-on.json \
  --notification-channels="$DISCORD_CHANNEL,$EMAIL_CHANNEL"

gcloud monitoring policies list --project="$PROJECT_ID" \
  --filter='displayName="Builder Cup Gemma GPU 2시간 연속 켜짐"' --format='table(name,displayName,enabled)'
```

### 4. 확인

- 예산 목록에 `Builder Cup Gemma GPU 월 알림 예산`이 ₩50,000·라벨 필터로 보인다.
- 경보 정책이 켜져 있고 두 채널이 연결돼 있다.
- 시연 전 `--min-instances 1`로 두고 2시간 뒤 Discord에 경보가 오는지 한 번 확인한 뒤 0으로 되돌린다.
- 결과와 생성된 예산·정책 이름을 [GCP 운영의 예산과 리전](../운영/GCP-운영.md#예산과-리전)에 기록한다.

금액과 시간 기준은 시연 일정이 정해지면 `gcloud billing budgets update`와 `gcloud monitoring policies update`로 조정합니다.

## 구현 순서

1. **이미지.** `models/vllm/Dockerfile.cloudrun`을 만듭니다. `vllm/vllm-openai:v0.19.1`을 베이스로 빌드 단계에서 HF 토큰(빌드 secret)으로
   `google/gemma-4-E2B-it`를 내려받아 `/models`에 담고, `vllm serve /models --served-model-name google/gemma-4-E2B-it --max-model-len 4096
   --max-num-seqs 4 --gpu-memory-utilization 0.85 --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4`로 시작합니다.
   멀티모달 입력은 `--limit-mm-per-prompt`로 끕니다. Artifact Registry의 싱가포르 저장소(또는 기존 도쿄 저장소)에 올립니다.
2. **인프라.** `infra/gcp`에 Gemma용 서비스 계정, 싱가포르 Artifact Registry, API 런타임 계정의 `roles/run.invoker`를 추가합니다.
   Cloud Run 서비스 자체는 다른 서비스와 같이 배포 스크립트가 만듭니다.
3. **배포 스크립트.** `scripts/deploy-gemma.sh`가 다음 형태로 배포하고 `/health`와 `/v1/models`를 ID 토큰으로 확인합니다.

   ```bash
   gcloud beta run deploy builder-cup-gemma \
     --image "$IMAGE" --region asia-southeast1 \
     --no-allow-unauthenticated --execution-environment gen2 \
     --cpu 4 --memory 16Gi --gpu 1 --gpu-type nvidia-l4 --no-gpu-zonal-redundancy \
     --no-cpu-throttling --min-instances 0 --max-instances 1 --concurrency 4 --timeout 300 \
     --startup-probe tcpSocket.port=8000,initialDelaySeconds=60,failureThreshold=5,timeoutSeconds=60,periodSeconds=60 \
     --port 8000 --labels app=builder-cup-gemma
   ```

4. **API 호출 인증.** `interpreters/local_chat.py`의 `httpx` 요청에 `LOCAL_LLM_AUDIENCE`가 설정되면 `google.oauth2.id_token.fetch_id_token`으로
   받은 ID 토큰을 `Authorization: Bearer`로 붙입니다. 로컬(Ollama·SSH 터널)에서는 값을 비워 두면 지금과 같습니다.
   Cloud Run의 API·파이프라인 Job에는 `USE_LOCAL_GEMMA=1`, `LOCAL_LLM_BASE_URL=https://<gemma 서비스 URL>/v1`,
   `LOCAL_LLM_AUDIENCE=https://<gemma 서비스 URL>`, `GEMMA_LOCAL_MODEL=google/gemma-4-E2B-it`을 넣습니다.
5. **검증.** `scripts/test_gemma_translate.py`와 `scripts/test_gemma_rewrite.py`를 Cloud Run 주소로 실행해 로컬 실측(한→영 8~13초)과 비교하고,
   콜드 스타트 시간과 인스턴스 1개당 처리량을 기록합니다.
6. **비용 통제.** 첫 배포 직후 위 [예산과 알림](#예산과-알림)의 1~4단계를 gcloud로 실행해 Gemma 전용 알림 예산과
   GPU 켜짐 경보를 만들고, 정책 파일 `infra/gcp/policies/gemma-gpu-on.json`을 커밋합니다.
   시간당 약 $0.67이면 하루 3시간 켜 두는 시연 2주가 약 $28입니다.
7. **문서.** [AI 호출 제어](../운영/AI-호출-제어.md)에 Gemma 서비스를 끄고 켜는 방법(`--min-instances`, `USE_LOCAL_GEMMA=0`으로 Gemini 대체)을 적습니다.

## 완료 기준

- 비공개 Cloud Run `builder-cup-gemma`가 싱가포르에서 `google/gemma-4-E2B-it`를 서빙하고, 익명 호출은 403을 받는다.
- 도쿄의 Trend API가 ID 토큰으로 번역·재작성·질문 응답을 처리한다.
- 요청이 없을 때 인스턴스가 0으로 내려가고, Gemma 전용 예산 알림과 GPU 켜짐 경보가 동작한다.
- 콜드 스타트·응답 시간·비용 실측이 문서에 기록되어 있다.

## 대안 (선택하지 않는 이유)

- **Vertex AI Model Garden 엔드포인트**: 관리형이지만 GPU 노드가 상시 켜져 유휴 비용이 크다.
- **GCE GPU VM + vLLM**(`models/vllm/`): 직접 운영해야 하고 VM이 켜진 동안 계속 과금된다. 대회 이후 장기 운영에는 고려할 수 있다.
- **Gemma 없이 Gemini만 사용**: `USE_LOCAL_GEMMA=0`으로 코드상 가능하지만 대회의 로컬 LLM 요건을 충족하지 못한다.
