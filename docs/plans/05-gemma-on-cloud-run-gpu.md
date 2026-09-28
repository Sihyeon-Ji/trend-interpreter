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

GPU는 켜져 있는 동안 계속 과금되므로 기존 서비스별 지출 한도와 별도로 Gemma 전용 예산과 알림을 둡니다.
설정 방식은 [GCP 운영의 예산과 리전](../운영/GCP-운영.md#예산과-리전)에서 서비스별 지출 한도를 만든 방식과 같습니다.

| 장치 | 설정 | 효과 |
| --- | --- | --- |
| 기존 Cloud Run 월 지출 한도(₩100,000) | 변경 없음 | Cloud Run GPU 비용도 Cloud Run 서비스에 청구되므로 이 한도에 함께 포함됨. 100%에서 Cloud Run 전체 사용이 중지됨 |
| **Gemma 전용 알림 예산** | 월 **₩50,000**, 필터는 서비스 라벨 `app=builder-cup-gemma`, 50%·80%·100% 알림 | Cloud Run 한도에 닿기 전에 GPU 지출만 따로 경고. ₩50,000은 L4 약 50시간 분량 |
| **GPU 켜짐 경보** | Cloud Monitoring 알림 정책. `builder-cup-gemma`의 인스턴스 수가 **2시간 연속 1 이상**이면 발생 | 시연 뒤 최소 인스턴스를 되돌리지 않은 실수를 Discord로 알림 |

알림 경로는 기존과 같이 Cloud Monitoring → Pub/Sub → Discord 중계기와 보조 이메일을 씁니다. 예산 알림은 결제 관리자 이메일로도 갑니다.
금액과 시간 기준은 시연 일정이 정해지면 조정합니다.

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
6. **비용 통제.** 배포 명령에 `--labels app=builder-cup-gemma`를 붙이고, 위 [예산과 알림](#예산과-알림)의 Gemma 전용 알림 예산과
   GPU 켜짐 경보를 만듭니다. 경보 정책은 `infra/gcp`에 Terraform으로, 예산은 기존 방식대로 콘솔에서 만든 뒤 문서에 상태를 기록합니다.
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
