# Plan 01 운영 상태 감시와 알림

작성일 **2026-09-23** · 상태 **실행 준비**

[현재 계획](README.md) · [운영 명령](../commands.md)

## 목적

배포된 서비스가 응답하지 않거나 API 오류가 발생할 때 팀이 GitHub Actions 화면을 직접 확인하지 않아도 빠르게 알 수 있게 합니다. 알림에는 장애 판단에 필요한 서비스, 시각, 상태 코드, 리비전만 포함하고 사용자 입력과 모델 출력은 포함하지 않습니다.

## 현재 상태

2026-09-23 배포 후 다음 상태를 확인했습니다.

- Cloud Run 최신 리비전 `builder-cup-00005-cib`가 트래픽 100%를 처리합니다.
- 공개 페이지와 `/api/health`가 HTTP 200으로 응답합니다.
- 인증정보가 없는 분석 요청은 HTTP 401로 거부됩니다.
- Cloud Monitoring 대시보드 `Builder Cup operations`와 로그 기반 지표 `builder_cup_api_errors`가 있습니다.
- 월 ₩100,000 예산과 50%, 90%, 100%, 150% 알림 기준이 있습니다.
- uptime check, alert policy, notification channel은 아직 없습니다.

예산 알림은 비용 증가를 알려줄 뿐 요청이나 배포를 자동으로 중단하지 않습니다.

## 적용 계획

### 1. 알림 수신처 확정

현재 팀의 소통 수단을 기준으로 다음 후보를 사용합니다.

| 후보 | 연결 방식 | 장점 | 제약 | 판단 |
| --- | --- | --- | --- | --- |
| 이메일 | Cloud Monitoring 기본 채널 | 추가 서비스와 코드가 필요 없고 설정이 가장 단순함 | 팀 대화방처럼 함께 처리하기 어려움 | 기본 채널로 사용 |
| Discord | Pub/Sub → Cloud Run 중계기 → Discord webhook | 현재 팀 채널에서 모두 확인 가능 | payload 변환, webhook secret, 작은 운영 리소스가 필요함 | 필요할 때 보조 채널로 추가 |
| Google Cloud 앱 | Cloud Monitoring 기본 채널 | 별도 메신저 연동 없이 모바일 알림 가능 | 프로젝트 접근 권한이 있는 개인 중심 채널 | 개인 보조 채널 후보 |
| SMS | Cloud Monitoring 기본 채널 | 인터넷 메신저를 열지 않아도 확인 가능 | 지역별 지원 차이와 전달 신뢰성 제약이 있음 | 긴급 백업 외에는 사용하지 않음 |
| 카카오톡 | Kakao Business 알림 또는 별도 연동 | 팀이 이미 사용하는 메신저 | 일반 Kakao Talk Message API는 자동 운영 알림 용도가 아니며 구성 부담이 큼 | 이번 프로젝트에서는 제외 |
| Microsoft Teams | 중계 서비스 → Teams | 조직용 채널 관리 가능 | 중계기가 필요하고 회사 계정 사용이 불편함 | 이번 프로젝트에서는 제외 |

우선 팀원 이메일을 기본 채널로 등록합니다. 한 곳에서 공동 대응할 필요가 생기면 Discord를 보조 채널로 추가합니다. Google Cloud도 webhook 계열 채널만 단독으로 쓰지 말고 이메일 또는 Pub/Sub를 함께 사용하도록 권장하므로 Discord를 추가해도 이메일은 유지합니다.

테스트 알림 수신까지 확인하기 전에는 완료로 처리하지 않습니다.

### 2. 공개 상태 검사 추가

Cloud Monitoring uptime check가 5분마다 `/api/health`를 호출하도록 설정합니다.

- 기대 상태 코드 `200`
- 기대 응답 `status` 값 `ok`
- 여러 지역에서 확인
- 연속 2회 실패 시 장애로 판정

이 검사는 모델 요청을 보내지 않으므로 Gemini 비용을 발생시키지 않습니다. `provider` 값은 설정 상태만 보여주며 실제 Gemini 호출 성공을 증명하지는 않습니다.

### 3. API 오류 알림 연결

기존 `builder_cup_api_errors` 지표를 사용해 5분 안에 서버 오류가 1회 이상 발생하면 알림을 보냅니다. 인증 실패인 401은 공개 서비스의 정상 방어 동작일 수 있으므로 서버 장애 알림에 포함하지 않습니다.

### 4. 지연 시간 알림 기준 수집

실제 사용 데이터가 충분해질 때까지 고정 임곗값을 임의로 설정하지 않습니다. 배포 후 실행 시간 분포를 수집한 뒤 p95 기준을 정하고, 모델 지연과 Cloud Run 지연을 구분할 수 있는 지표를 사용합니다.

### 5. 알림 동작 검증

운영 데이터나 인증정보를 변경하지 않는 테스트 조건으로 각 알림을 한 번 발생시킵니다.

1. 테스트 알림이 지정 수신처에 도착하는지 확인합니다.
2. 알림에서 서비스, 발생 시각, 조건, 확인 링크를 식별할 수 있는지 확인합니다.
3. 조건을 원복한 뒤 알림이 정상 상태로 전환되는지 확인합니다.
4. 검증 시각과 결과를 이 문서에 기록합니다.

### 6. 배포 후 확인 절차 고정

`release/gcp` 배포가 끝날 때마다 다음 항목을 확인합니다.

1. GitHub Actions 배포 성공
2. 최신 Cloud Run 리비전과 트래픽 100%
3. 공개 페이지와 `/api/health` 응답
4. 인증 없는 분석 요청의 401 응답
5. 배포 직후 새 ERROR 또는 CRITICAL 로그 유무

## 완료 기준

- uptime check와 API 오류 alert policy가 활성 상태입니다.
- 알림 수신처와 담당자가 기록되어 있습니다.
- 장애와 복구 테스트 알림을 모두 수신했습니다.
- 알림 본문과 관련 로그에 사용자 원문, 모델 출력, API key가 없습니다.
- 팀원이 알림에서 해당 Cloud Run 리비전과 로그로 이동할 수 있습니다.

## 실행에 필요한 결정

첫 적용에는 알림을 받을 팀원 이메일 주소만 정하면 됩니다. Discord도 함께 사용하려면 알림 전용 채널과 webhook을 만들고, webhook URL은 Secret Manager에 저장합니다.

## 참고 자료

- [Cloud Monitoring notification channel](https://docs.cloud.google.com/monitoring/support/notification-options)
- [Discord webhook 안내](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)
- [Kakao Talk Message API 용도와 제한](https://developers.kakao.com/docs/en/kakaotalk-message/common)
