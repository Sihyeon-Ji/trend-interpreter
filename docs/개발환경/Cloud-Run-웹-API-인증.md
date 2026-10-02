# Cloud Run 웹 → API 인증

## 구현 범위

웹의 서버 API 요청은 `lib/api-fetch.ts`를 거친다. 사전·대시보드 읽기, 로그인·설정·검수 쓰기, 추천 사진 업로드, 생성·질문 스트리밍에 같은 인증을 적용한다. 클라이언트에서는 `server-only` 경계 때문에 이 헬퍼를 가져올 수 없다.

Google 서비스 인증은 [공식 서비스 간 인증](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)에 따라 런타임 서비스 계정의 ID token을 메타데이터 서버에서 받아 `X-Serverless-Authorization`에 넣는다. 사용자 로그인·검수에 쓰는 `Authorization`과 `x-frontend-token`은 유지한다. Google invoke 권한과 앱의 사용자 권한을 각각 검사하는 구조다.

## 환경 설정

| 환경 | 설정 | 동작 |
| --- | --- | --- |
| 로컬 | `TREND_API_AUTH=none`, `TREND_API_URL=http://api:8000` | Google 토큰 발급 없이 로컬 API 호출 |
| Cloud Run 웹 | `TREND_API_AUTH=google-id-token`, `TREND_API_URL`은 대상 API의 기본 HTTPS `run.app` URL | 메타데이터 ID token으로 API 호출 |

`TREND_API_URL`은 경로·쿼리·fragment·사용자 정보가 없는 origin이어야 한다. Google 모드는 기본 Cloud Run URL만 지원하며 custom domain·traffic tag·custom audience는 이번 범위에 포함하지 않는다. `K_SERVICE`가 있는 Cloud Run에서 API 호출 시 인증 모드가 빠졌거나 `none`이면 요청을 거부한다. 로컬에서 Google 모드를 강제로 켜면 메타데이터 발급이 실패한다. 장기 서비스 계정 키나 수동 복사 토큰은 사용하지 않는다.

대상 API는 IAM 인증 필수로 배포하고, **웹 런타임 서비스 계정만 해당 API의 `roles/run.invoker`**를 가져야 한다. staging 웹에는 production API 권한을 주지 않는다. 실제 IAM·네트워크 설정과 배포는 Plan 05·17의 승인 단계에서 적용하고 연결을 확인한다. 현재 코드는 이 권한을 생성하거나 배포 job을 활성화하지 않는다.

## 갱신·실패·취소

- 토큰은 서버 프로세스별 메모리에 보관하고 만료 60초 전에 갱신한다. 같은 audience의 동시 요청은 한 번의 발급을 공유한다. 사용자별 요청 헤더·본문은 공유하지 않는다.
- 메타데이터 요청은 3초 timeout·캐시 금지·redirect 거부를 사용한다. 응답의 메타데이터 표식, 토큰 형식·audience·유효기간을 검사한다. 서명 검증은 호출을 받는 Cloud Run이 담당한다.
- 발급 실패·잘못된 설정에서는 인증 없는 API 호출로 전환하지 않는다. 로그에 토큰·메타데이터 응답을 출력하지 않는다. 다음 요청에서 토큰 발급을 다시 시도할 수 있다.
- 외부 URL·다른 origin으로의 요청과 redirect를 거부한다. 호출자가 넘긴 Google invoke 헤더는 제거한 뒤 서버 토큰을 넣는다.
- 요청 취소는 API fetch까지 전달한다. 공유 토큰을 기다리는 한 요청이 취소돼도 다른 요청의 발급을 취소하지 않는다. 스트림과 multipart 본문은 버퍼링·재인코딩하지 않는다.

## 검증과 남은 조건

```bash
docker compose run --rm --build check
docker compose run --rm --build e2e
```

`check`에 웹 transport 테스트를 포함했다. 메타데이터·토큰·API 응답은 합성 자료로 확인한다. 로컬 E2E는 기존 사용자 흐름의 회귀 검사이며 실제 Google IAM 접근 성공을 뜻하지 않는다.

배포 이후에는 웹 SA의 실제 토큰 발급, 인증 필수 API 호출, 권한 없는 호출의 401/403, staging→production 접근 거부, 읽기·쓰기·사진·스트리밍·취소를 확인해야 한다. 현재 상태는 **서버 인증 연결 코드와 로컬 검증 준비 완료, 운영 연결 미검증**이다.
