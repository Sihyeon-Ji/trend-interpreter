# 운영 AI 호출 중지와 예산 조정

[개발 명령어](../개발환경/개발-명령어.md) · [전체 운영 문서](GCP-운영.md) · [아키텍처의 모델 호출 경계](시스템-아키텍처.md#모델-호출-경계)

## Trend 앱의 제어 값

Trend API(`apps/trend-api`)는 환경변수 두 개가 **모두** 켜져야 Gemini를 호출합니다. 코드에서 Gemini 클라이언트를
만드는 곳은 `src/trend_agents/model_client.py` 하나뿐이며 API key는 쓰지 않습니다.

| 설정 | 로컬 기본값 | 조정 방법 | 적용 결과 |
| --- | --- | --- | --- |
| `MODEL_PROVIDER` | `mock` | `vertex`로 바꾸면 Vertex AI 사용 | 그 외 값이면 클라이언트를 만들지 않음 |
| `MODEL_REQUESTS_ENABLED` | `false` | `true`로 바꾸면 호출 허용 | `false`면 `ModelRequestsDisabled`로 끝나고 비용 0 |
| `GCP_PROJECT_ID` | 비움 | Vertex AI 프로젝트 ID | 비어 있으면 `vertex`여도 호출하지 않음 |
| `GOOGLE_CLOUD_LOCATION` | `global` | Vertex AI 위치 | |
| `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL` | `gemini-3.8-flash`, `gemini-3.5-flash` | 모델 ID | 503·429가 반복되면 폴백 모델 사용 |
| `GEMINI_DAILY_BUDGET` | `36` | 하루 호출 상한 | DB `gemini_calls` 장부가 상한에 닿으면 호출하지 않음 |
| `USE_LOCAL_GEMMA` | `0` | 개발자 PC의 편집 파이프라인에서 `1` | 텍스트 작업을 로컬 Gemma로 라우팅. 운영 Cloud Run API는 `0` 유지 |

호출이 꺼진 상태에서 파이프라인을 돌리면 Gemini가 필요한 단계는 `pipeline_runs`에 오류로 남고 다음 단계는
계속 진행합니다. ADK 에이전트 팀(`agents/team.py`)은 예산 가드에서 같은 조건을 확인해 모델을 부르기 전에
짧은 응답으로 대체합니다. 로컬 Gemma 호출은 이 제어와 무관하게 `LOCAL_LLM_BASE_URL`·Ollama 준비 여부로 결정됩니다.
Cloud Run 서비스에서 `USE_LOCAL_GEMMA=1`을 켜도 개발자 PC의 Ollama에 연결되지는 않습니다. 운영 요청의 신규 서술은
[Plan 06](../plans/06-gemma-on-cloud-run-gpu.md)에 따라 게시된 데이터·규칙 또는 Gemini 경로로 구현·검증해야 합니다.

### 호출 기록

Gemini에 요청을 한 번 보낼 때마다 `pipeline/gemini.py`가 로그 한 줄을 남깁니다. `event=gemini_call`과 `model`, `ledger`(`pipeline`·`request`),
`outcome`(`ok`·`rejected`(429·503)·`error`), HTTP `code`만 담고 프롬프트·응답은 넣지 않습니다. Cloud Run 서비스와 Job의 로그는 JSON이라
`jsonPayload.event="gemini_call"`로 로그 기반 지표를 만들 수 있습니다. 이 지표는 어느 모델·장부·결과의 호출이었는지 가르는 데 씁니다.
운영 API의 Gemini 요청은 모두 이 함수를 거칩니다. 개발자 PC 파이프라인의 조사(Search grounding)·쇼츠 해석과 ADK 에이전트는
`interpreters/`·`agents/`에서 직접 부르므로 이 줄에 들지 않습니다.

`gemini_call`이 0건이라는 것만으로는 호출이 멈췄다고 할 수 없습니다.

- 이 줄은 `generate()`가 클라이언트를 얻은 뒤에만 남습니다. `MODEL_REQUESTS_ENABLED=false`면 클라이언트를 만들기 전에 끝나므로
  설계상 0이고(`gemini_calls` 장부도 깎지 않습니다), 이 함수를 거치지 않는 호출이 생겨도 0입니다.
- 성공한 호출은 INFO로 남습니다. `LOG_LEVEL`을 `WARNING` 이상으로 두면 성공한 호출이 지표에서 빠지므로 운영에서는 `INFO`로 둡니다.

그래서 호출 중지는 코드와 상관없는 프로젝트 쪽 집계와 함께 확인합니다. Cloud Monitoring의 `serviceruntime.googleapis.com/api/request_count`
(자원 `consumed_api`, `service="aiplatform.googleapis.com"`)가 Vertex AI API 요청을 세며, `credential_id`로 나누면 운영 서비스 계정의
호출과 개발자 PC 파이프라인의 조사·쇼츠 호출을 가를 수 있습니다.

1. 호출을 켠 상태에서 한 번 부르고 `gemini_call`(`outcome=ok`)과 Vertex AI API 요청 수에 모두 잡히는지 봅니다. 둘 중 하나라도
   잡히지 않으면 지표나 필터가 틀린 것이므로 0을 믿지 않습니다.
2. `MODEL_REQUESTS_ENABLED=false`로 배포한 뒤 두 값이 모두 늘지 않는지 봅니다.

## 로컬에서 확인하기

기본 개발 스택은 `compose.yaml`에서 `MODEL_PROVIDER=mock`, `MODEL_REQUESTS_ENABLED=false`를 고정합니다.
호스트 `.env`를 읽지 않으므로 실수로 유료 호출이 나가지 않습니다. 차단 동작은 자동 테스트로 확인합니다.

```bash
docker compose run --rm --build check
```

`apps/trend-api/tests/test_model_client.py`가 mock 모드에서 클라이언트를 만들지 않는 것과, vertex 모드에서
API key 없이 프로젝트·위치만으로 클라이언트를 만드는 것을 검사합니다. `test_ops_signals.py`는 요청마다 `gemini_call`이
한 줄씩 남는 것(`/explain` 재작성처럼 작업 스레드에서 부르는 호출 포함)과, 호출이 꺼져 있으면 그 줄도 장부 차감도 없는 것을 검사합니다.

## 운영 배포 뒤 조정 방법

Trend 앱은 아직 Cloud Run에 배포하지 않았습니다. [Plan 05](../plans/archive/05-trend-cloud-run-deployment.md)에서
배포 스크립트를 만들 때 위 값을 Cloud Run 환경변수로 넘기고, 중지·재개는 새 revision 배포로 적용합니다.
배포 후에는 이 절에 실제 명령을 채웁니다.

## Trend 서비스의 Gemini 사용과 상한

이전 실습 앱 `builder-cup`은 2026-10-04에 삭제했다. Trend API의 Gemini 사용은 `infra/gcp/hybrid`의 `services.gemini`로 정한다. 값이 없으면 `MODEL_PROVIDER=mock`이고, 있으면 Vertex AI를 쓰면서 앱이 실제 토큰 사용량으로 월 금액(`GEMINI_MONTHLY_USD`)을 세어 상한 전에 호출을 멈춘다. 현재 production $15, staging $5다. 호출을 멈추려면 해당 환경의 tfvars에서 `gemini`를 빼고 Terraform을 적용한다. 상세는 [Cloud Run 서비스 준비](../개발환경/Cloud-Run-서비스-준비.md)에 있다.
