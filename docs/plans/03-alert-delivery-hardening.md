# Plan 03 알림 유지와 전달 검증 보완

작성일 **2026-09-24** · 상태 **제안·미착수** · 우선순위 **높음**

[조사 근거](../development-readiness-review.md) · [현재 계획](README.md) · [기존 구축 결과](archive/01-production-alerting.md)

## 목표

이미 동작하는 Discord 알림을 장기간 유지하고, 설정 변경과 배포 성공 판정이 실제 동작을 반영하게 합니다.

## 현재 근거

- [main.tf](../../infra/gcp/main.tf)의 두 Pub/Sub subscription에 expiration policy가 없고, 실제 GCP에서는 31일 비활성 만료가 설정되어 있습니다.
- 대시보드 전체 JSON이 Terraform update 대상에서 제외되어 있습니다.
- [relay 배포](../../scripts/deploy-alert-relay.sh)는 traffic 전환 후 Pub/Sub 발행 성공까지만 검사합니다.
- relay 테스트는 5개이며 정상·복구·잘못된 Base64·429·health를 확인합니다. timeout·5xx·잘못된 JSON은 아직 별도 검사하지 않습니다.

## 작업 범위와 순서

1. 두 구독을 명시적 비만료로 설정하고 메시지 보존 7일은 유지합니다. 별도의 topic이나 queue를 추가하지 않습니다.
2. provider의 JSON 정규화 동작을 확인하고 대시보드 기본값을 맞춰 전체 `ignore_changes`를 제거합니다. 차트 하나의 실제 변경은 plan에 나타나고, apply 후 반복 plan은 불필요한 변경 없이 끝나야 합니다.
3. 배포 smoke에 고유 incident ID와 대상 revision을 기록합니다. 제한된 시간 안에 해당 ID·revision의 Discord 성공 기록을 조회하며 publish 성공과 delivery 성공을 구분합니다. 필요한 log 조회 권한의 범위를 검토합니다.
4. 후보에 대한 검사와 traffic 전환 후 Pub/Sub 검사를 구분합니다. 최종 전달 확인이 실패하거나 지연되면 성공으로 보고하지 않고 이전 revision 복구 또는 확인 대기로 표시합니다. 전파 지연만으로 무조건 rollback하지 않습니다.
5. MockTransport로 Discord timeout·5xx·429·복구와 잘못된 JSON을 테스트합니다. 전체 payload나 webhook 값이 로그에 남지 않는지 함께 확인합니다.
6. 운영 문서의 ‘5회 후 반드시 격리’ 표현을 ‘설정 5회, 실제 전달 횟수는 근사치’로 구분합니다. 과거 실험에서 5회를 관찰했다는 기록은 보존합니다.

## 완료 기준

- GCP 조회에서 두 subscription의 비활성 만료가 해제되어 있습니다.
- 대시보드 제목 변경을 plan이 감지하고 원복 후 plan이 수렴합니다.
- Discord가 실패한 합성 실행은 배포 검증 성공으로 표시되지 않습니다.
- 정상 메시지의 고유 ID와 revision으로 전달 성공을 추적할 수 있습니다.
- 로컬 실패 테스트, Compose `check`, Terraform fmt·validate를 통과합니다.
- 통합 검증에서는 승인된 테스트 채널과 합성 메시지만 사용하며 live webhook 폐기나 서비스 중단을 유발하지 않습니다.

## 범위 제한과 복구

기존 API와 DB에는 변경이 없습니다. exactly-once 저장소·정기 테스트 알림·새 메시징 플랫폼을 추가하지 않습니다. 중복 가능성은 계속 문서화합니다. IAM과 대시보드 변경은 검토한 plan만 적용하고 문제가 생기면 해당 설정 변경을 복구합니다.

## 참고

- [Pub/Sub 만료 정책](https://docs.cloud.google.com/pubsub/docs/subscription-properties)
- [Dead-letter 전달 횟수의 보장 범위](https://docs.cloud.google.com/pubsub/docs/dead-letter-topics)
- [Terraform ignore_changes](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle)
