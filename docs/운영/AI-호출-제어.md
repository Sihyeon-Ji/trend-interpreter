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
| `USE_LOCAL_GEMMA` | `0` | `1`이면 번역·재작성에 로컬 Gemma 사용 | Gemini 대신 `LOCAL_LLM_BASE_URL`의 모델 호출 |

호출이 꺼진 상태에서 파이프라인을 돌리면 Gemini가 필요한 단계는 `pipeline_runs`에 오류로 남고 다음 단계는
계속 진행합니다. ADK 에이전트 팀(`agents/team.py`)은 예산 가드에서 같은 조건을 확인해 모델을 부르기 전에
짧은 응답으로 대체합니다. 로컬 Gemma 호출은 이 제어와 무관하게 `LOCAL_LLM_BASE_URL`·Ollama 준비 여부로 결정됩니다.

## 로컬에서 확인하기

기본 개발 스택은 `compose.yaml`에서 `MODEL_PROVIDER=mock`, `MODEL_REQUESTS_ENABLED=false`를 고정합니다.
호스트 `.env`를 읽지 않으므로 실수로 유료 호출이 나가지 않습니다. 차단 동작은 자동 테스트로 확인합니다.

```bash
docker compose run --rm --build check
```

`apps/trend-api/tests/test_model_client.py`가 mock 모드에서 클라이언트를 만들지 않는 것과, vertex 모드에서
API key 없이 프로젝트·위치만으로 클라이언트를 만드는 것을 검사합니다.

## 운영 배포 뒤 조정 방법

Trend 앱은 아직 Cloud Run에 배포하지 않았습니다. [Plan 03](../plans/03-trend-cloud-run-deployment.md)에서
배포 스크립트를 만들 때 위 값을 Cloud Run 환경변수로 넘기고, 중지·재개는 새 revision 배포로 적용합니다.
배포 후에는 이 절에 실제 명령을 채웁니다.

## 이전 서비스(`builder-cup`) 임시 조치

이전 실습 앱은 `builder-cup` Cloud Run 서비스로 계속 운영 중이며, 그 코드와 설정 파일은 2026-09-28에 저장소에서
제거했습니다. Trend 릴리스가 대체하기 전에 모델 호출을 멈춰야 하면 저장소를 거치지 않고 환경변수만 바꿉니다.

```bash
gcloud run services update builder-cup \
  --project=stunning-crane-508614-c1 --region=asia-northeast1 \
  --update-env-vars=MODEL_REQUESTS_ENABLED=false
```

이 명령은 같은 이미지로 새 revision을 만들어 트래픽을 옮깁니다. 재개는 `true`로 되돌립니다. 확인은 비용이 들지
않는 health와 인증 거부 응답으로 합니다.

```bash
curl --fail --silent --show-error \
  https://builder-cup-266542883304.asia-northeast1.run.app/api/health
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  --header 'Content-Type: application/json' \
  --data '{"text":"검증용 합성 문장"}' \
  https://builder-cup-266542883304.asia-northeast1.run.app/api/analyze
```

첫 응답의 `status`는 `ok`, 인증 코드 없이 보낸 두 번째 요청은 `401`이어야 합니다. 서비스를 이전 revision으로
되돌리는 절차는 [배포 복구](배포-복구.md)에 있습니다. 팀 접근 코드는 문서·Git·로그에 기록하지 않습니다.
