# Plan 05 AI 요청량 제어와 결과 형식 검증

작성일 **2026-09-24** · 상태 **구현·운영 배포 완료** · 구현 커밋 **58db540**

[조사 근거](../../AI-개발/개발-준비-점검.md) · [현재 계획](../README.md)

## 목표

정상 인증을 거친 반복 요청도 제한할 수 있게 하고, 호출을 잠시 중지하면서 웹·상태 조회를 유지합니다. 주제별 품질 점수와 별도로 현재 응답 contract의 빈 문자열·길이 경계를 검증합니다.

## 현재 근거

- 변경 전 [Settings](../../../apps/api/src/builder_cup/config.py)에 timeout·재시도 설정은 있지만 호출 빈도·모델 호출 중지 설정은 없었습니다.
- [GeminiProvider](../../../apps/api/src/builder_cup/providers.py)에 출력 1,024 token 제한이 이미 있습니다. 중복 구현하지 않았습니다.
- [AnalyzeRequest](../../../apps/api/src/builder_cup/schemas.py)에 8,000자 한도가 있습니다.
- 같은 파일의 `Analysis.key_points`는 배열 수만 제한합니다. 로컬에서 빈 문자열·공백·10만 자 항목의 통과를 재현했습니다.
- UI의 busy 상태는 한 화면의 중복 submit만 막으며 서버 호출량 제한을 대신하지 않습니다.

## 작업 순서

1. 모델 호출 허용 여부를 server 설정으로 추가합니다. 중지 상태에서는 인증 검사 후 명확한 503 오류 코드를 반환하고 provider를 호출하지 않습니다. UI도 ‘모델 호출 일시 중지’를 구분해 표시합니다.
2. 초당/분당 처리량과 동시에 진행 중인 모델 요청 수를 제한합니다. 첫 구현은 process별 한도로 작게 시작하고 제한 초과 시 429와 Retry-After를 반환합니다. 거부된 요청을 모델 재시도 루프에 넣지 않습니다.
3. process 메모리 한도는 재시작·여러 instance에서 공유되지 않는다는 제한을 문서화합니다. 이를 프로젝트 전체 비용 상한이나 사용자별 quota라고 부르지 않습니다. 엄격한 전역 제한이 필요해질 때 저장소나 gateway를 별도 선택합니다.
4. summary와 각 key point에 공백 제외 최소 길이와 최대 길이를 적용합니다. 공백 문자열·빈 배열·과다 항목·긴 항목·추가 필드·잘린 JSON을 실패 사례로 고정합니다.
5. Mock과 실제 provider가 같은 응답 검사를 거치게 합니다. Gemini·Gemma 4 이외의 모델을 추가하지 않습니다.
6. 설정 조정 방법과 중지·재개 절차를 기록합니다. Cloud Run 설정 적용은 이미 실행 중인 upstream 요청을 즉시 취소하거나 이미 발생한 비용을 되돌리지 않는다는 점을 명시합니다.

## 검증과 완료 기준

- provider spy를 사용해 중지·인증 실패·한도 초과 요청의 실제 모델 호출 횟수가 0임을 확인합니다.
- 허용된 동시 요청 수까지만 진행하고 완료·timeout·취소 뒤 사용 슬롯이 반환됩니다.
- 짧은 합성 요청을 반복해 429와 정상 복귀를 확인합니다.
- 빈 핵심 문장이 성공 응답에 포함되지 않고 `invalid_model_response`로 처리됩니다.
- 기존 정상 계약과 브라우저 오류 안내가 유지됩니다. Compose check와 e2e를 통과합니다.
- 단위·통합 검사는 Mock만 사용합니다. 실제 모델 smoke는 별도 명시 실행이며 이 작업의 기본 검사로 자동 과금하지 않습니다.

## 제외 범위

사용자 계정·OAuth·결제 ledger·정확한 월 지출 강제 상한·새 Redis는 만들지 않습니다. 예산 알림과 Cloud Run instance 설정을 애플리케이션 요청량 제한의 대체로 설명하지 않습니다. 정확한 가격 표시와 도메인 품질 합격선은 별도로 결정합니다.

## 구현·검증 결과

- 모델 호출 전에 인증·일시 중지·분당 한도·동시 요청 수를 순서대로 확인합니다. 기본값은 프로세스당 분당 12건, 동시 실행 2건입니다.
- 중지 상태는 HTTP 503 `model_disabled`, 한도 초과는 HTTP 429 `model_rate_limited`와 `Retry-After`를 반환합니다. 오류 응답에는 `request_id`가 있습니다.
- 허용된 요청이 timeout·취소·성공으로 끝나면 동시 실행 슬롯을 반환합니다. 한도 초과 요청은 provider를 호출하지 않습니다.
- summary와 각 key point에 공백 제외 최소 길이·최대 길이를 적용했습니다. 핵심 문장은 최대 500자이며 1~5개여야 합니다.
- [운영 설정](../../../deployment/model-controls.json)을 commit하고 `release/gcp`로 승격하면 변경 범위 판정이 메인 서비스를 배포합니다. 중지·재개 방법은 [운영 문서](../../운영/GCP-운영.md)에 있습니다.
- `docker compose run --rm --build check`에서 API 테스트 **97개 통과·1개 Git 미설치 환경 skip**, relay 테스트 10개, Mock 계약 2개, 타입 검사·웹 빌드가 통과했습니다. `docker compose run --rm --build e2e`는 **8개 통과**했습니다.
- [GitHub Actions release](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions/runs/36007239153)는 공통 CI와 메인 앱 배포가 성공했고 relay 배포는 skip됐습니다.
- Cloud Run `builder-cup-00013-gej`가 트래픽 100%를 받고 `MODEL_REQUESTS_ENABLED=true`, 분당 12건, 동시 2건을 사용합니다. 공개 health는 200, 인증 없는 분석 요청은 401, 배포 직후 ERROR 이상 로그는 없었습니다.

이번 검증은 Mock과 상태·인증 smoke를 사용했습니다. 이 변경을 위해 유료 Gemini 요청은 보내지 않았으며 실제 모델 품질이나 정확한 비용 상한을 입증한 결과가 아닙니다. 각 Cloud Run 인스턴스가 별도 한도를 가지며, 재시도 횟수는 승인된 요청 한 건 안에서 별도로 발생할 수 있습니다.
