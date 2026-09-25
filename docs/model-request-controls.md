# 운영 AI 호출 중지와 요청 한도 조정

이 안내는 **배포된 메인 Cloud Run `builder-cup`**의 `/api/analyze`에 적용됩니다. 로컬 `docker compose up -d`의 Mock 실습과 별도 relay 서비스에는 적용되지 않습니다.

[개발 명령어](commands.md) · [전체 운영 문서](operations.md) · [구현·검증 기록](plans/archive/05-model-request-controls.md)

## 먼저 설정 파일 보기

저장소 루트의 [`deployment/model-controls.json`](../deployment/model-controls.json)을 엽니다.

```json
{
  "enabled": true,
  "requests_per_minute": 12,
  "max_concurrent_requests": 2
}
```

| 항목 | 조정 방법 | 적용 결과 |
| --- | --- | --- |
| `enabled` | `false`로 바꾸면 중지, `true`로 되돌리면 재개 | 중지 중 인증된 분석 요청은 HTTP 503 `model_disabled`, 모델 호출 0회 |
| `requests_per_minute` | 인스턴스 한 개가 60초 동안 받는 분석 요청 수로 조정 | 초과 요청은 HTTP 429 `model_rate_limited` |
| `max_concurrent_requests` | 인스턴스 한 개에서 동시에 진행할 분석 요청 수로 조정 | 초과 요청은 HTTP 429 `model_rate_limited` |

숫자 두 개는 각각 **1~100의 정수**로 입력합니다. 현재 기본값은 분당 12건·동시 2건입니다. `true`와 `false`는 따옴표 없는 JSON boolean입니다. 변경은 현재 실행 중인 서버에 즉시 반영되지 않고 **새 Cloud Run revision을 배포한 뒤** 적용됩니다.

## 호출 중지·한도 변경·재개 순서

저장소 루트에서 `develop`으로 작업합니다.

1. `deployment/model-controls.json`에서 필요한 값만 수정합니다. 호출 중지는 `"enabled": false`로, 재개는 `"enabled": true`로 바꿉니다.
2. JSON 문법과 변경 내용을 확인합니다.

   ```bash
   python3 -m json.tool deployment/model-controls.json >/dev/null
   git diff -- deployment/model-controls.json
   docker compose run --rm --build check
   ```

3. 검사가 성공하면 변경을 기록하고 `develop`에 올립니다. 한도만 바꿀 때는 메시지를 변경 내용에 맞게 적습니다.

   ```bash
   git add deployment/model-controls.json
   git commit -m "ops: 운영 AI 호출 일시 중지"
   git push origin develop
   ```

4. 배포할 때 `release/gcp`가 현재 `develop`의 이전 commit인지 확인한 뒤 fast-forward로 올립니다.

   ```bash
   git fetch origin
   git merge-base --is-ancestor origin/release/gcp develop
   git push origin develop:release/gcp
   ```

   조상 관계 확인 명령에서 오류가 나거나 push가 거부되면 중단하고 두 브랜치의 차이를 확인합니다. `--force`를 사용하지 않습니다.

5. GitHub Actions의 **Release GCP**에서 공통 검사와 **application** 배포 job이 성공했는지 확인합니다. 새 revision이 트래픽 100%를 받으면 변경이 적용된 것입니다. 이 설정 파일 변경만으로는 **alert_relay**를 재배포하지 않습니다.

호출을 다시 열 때는 `"enabled": true`로 수정하고 2~5단계를 반복합니다. **JSON 값만 로컬에서 고치거나 `develop`에만 push하면 운영 서버는 바뀌지 않습니다.**

## 배포 후 확인

먼저 비용이 들지 않는 health와 인증 거부 동작을 확인합니다.

```bash
curl --fail --silent --show-error \
  https://builder-cup-266542883304.asia-northeast1.run.app/api/health

curl --silent --output /dev/null --write-out '%{http_code}\n' \
  --header 'Content-Type: application/json' \
  --data '{"text":"검증용 합성 문장"}' \
  https://builder-cup-266542883304.asia-northeast1.run.app/api/analyze
```

첫 응답의 `status`는 `ok`, 인증 코드 없이 보낸 두 번째 요청은 `401`이어야 합니다. **중지 상태**를 직접 확인할 때는 팀 접근 코드를 인증 헤더에 넣어 합성 문장 하나만 요청합니다. 응답이 HTTP `503`이고 오류 코드가 `model_disabled`이면 Gemini를 호출하지 않은 것입니다. 접근 코드는 문서·Git·로그에 기록하지 않습니다.

**반드시 `enabled: false`가 배포된 것을 확인한 뒤에만** 다음 요청을 보냅니다. Secret Manager 값을 화면에 출력하지 않고 현재 셸 변수로만 받습니다.

```bash
TEAM_ACCESS_CODE=$(gcloud secrets versions access latest \
  --secret=builder-cup-demo-key \
  --project=stunning-crane-508614-c1)

curl --silent --show-error --include --max-time 20 \
  --header "Authorization: Bearer $TEAM_ACCESS_CODE" \
  --header 'Content-Type: application/json' \
  --data '{"text":"검증용 합성 문장"}' \
  https://builder-cup-266542883304.asia-northeast1.run.app/api/analyze

unset TEAM_ACCESS_CODE
```

`HTTP/2 503`과 `"code":"model_disabled"`를 확인합니다. `200`이라면 중지 설정이 적용되지 않은 것이므로 출력된 결과를 팀 외부에 공유하지 말고 배포 revision과 설정을 확인합니다.

한도 초과는 HTTP `429`와 초 단위 `Retry-After` 헤더로 알려줍니다. 동시 요청 제한 시 대기 시간은 보수적으로 1초입니다. **운영 Gemini에 반복 요청을 보내 429를 만드는 검사는 하지 마세요.** 이 경로는 Mock 기반 API 테스트로 확인합니다. 웹 화면에는 중지와 한도 초과에 서로 다른 안내가 표시됩니다.

## 어떤 요청이 한도에 포함되나요?

- 팀 접근 코드가 틀린 요청은 먼저 `401`로 거부하며 한도에 포함되지 않습니다.
- 인증된 `/api/analyze` 요청 한 건이 분당 한 자리와 동시 실행 한 자리를 사용합니다. 모델 내부 재시도는 새 API 요청 자리로 세지지 않지만 실제 모델 호출·비용은 추가될 수 있습니다.
- 처리 완료·timeout·취소 후 동시 실행 자리는 반환됩니다. 분당 기록은 60초가 지나야 사라집니다.
- 한도는 **Cloud Run 인스턴스의 각 프로세스 메모리**에 있습니다. 인스턴스가 둘이면 기본 분당 한도의 합계가 약 24건까지 될 수 있고, 재시작·새 revision에서는 기록이 초기화됩니다. 월 과금 상한이나 사용자별 quota가 아닙니다.
- `enabled` 변경은 배포가 끝난 새 요청부터 적용됩니다. 이미 진행 중인 요청이나 이미 발생한 비용을 되돌리지 않습니다.

## 모델 결과가 거부되는 기준

모델 응답은 [schemas.py](../apps/api/src/builder_cup/schemas.py)에서 검사합니다. 요약은 공백만으로 채울 수 없고 최대 1,500자입니다. 핵심 문장은 **1~5개**, 각각 공백만으로 채울 수 없으며 최대 **500자**입니다. 추가 필드·잘린 JSON도 성공 응답으로 처리하지 않고 `invalid_model_response` 오류를 반환합니다.

이 길이와 형식 기준은 `model-controls.json`으로 바꾸는 운영 한도가 아닙니다. 바꾸려면 schema와 관련 테스트를 수정하고 검증 후 새 revision을 배포해야 합니다. 이 검사는 내용의 사실성이나 AI 답변의 품질을 보장하지 않습니다.
