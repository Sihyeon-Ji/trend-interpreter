# 주제 선정 전 개발·운영 준비 점검

조사일 **2026-09-24** · 코드 기준 **2351886** · 범위 **공통 개발 기반**

[현재 계획](plans/README.md) · [아키텍처](architecture.md) · [운영 문서](operations.md)

## 결론

지금은 새 DB나 에이전트 프레임워크를 더 도입하기보다, 이미 만든 개발·배포·알림 기능의 실제 운영 빈틈을 보완하는 편이 효과적입니다. 주제 선정 없이 진행 가능한 작업을 Plan 03~06으로 나눴습니다.

이 문서는 조사 결과와 실행 제안입니다. 계획 작성으로 애플리케이션이나 운영 리소스를 변경하지 않았습니다.

## 확인 방법과 한계

- Git 추적 파일의 API·relay·Compose·CI·배포 script·Terraform·검증 기록을 대조했습니다.
- Cloud Run 리비전과 Pub/Sub 구독 설정은 GCP에서 읽기 전용으로 확인했습니다.
- `Analysis` schema에 합성 값을 넣어 빈 문자열·공백·10만 자 핵심 문장의 통과 여부를 로컬에서 재현했습니다. 모델은 호출하지 않았습니다.
- 전체 테스트, 유료 Gemini 요청, 알림 발송, 배포, 비밀값 조회는 이번 조사에서 실행하지 않았습니다. 과거 테스트 통과 기록을 현재 재실행 결과로 표시하지 않습니다.
- `prototype/disease`, `prototype/pmo-agent`, `prototype/trend`는 공통 CI와 분리된 후보 프로젝트입니다. 개별 제품 기능·외부 API·의존성 전체를 감사한 결과는 아닙니다.
- graphify 그래프와 Serena 도구가 없어 현재 파일을 직접 확인했습니다.

## 영역별 판단

| 영역 | 확인된 준비 | 남은 사항 | 처리 |
| --- | --- | --- | --- |
| 로컬 개발 | Compose 기동·reload·Mock·진단·OS별 설치 안내 | 다른 팀원 Mac의 실제 재현 기록은 아직 없음 | 기존 archive 검증 기록에 추가, 신규 구현 계획 중복 생성 안 함 |
| 데이터 | PostgreSQL migration·백업·별도 DB 복원 | 제품 도메인 schema와 cloud DB 요구는 미정 | 주제 후 결정 |
| 모델 | Gemini·Gemma 4 adapter, timeout·재시도·출력 token 제한·평가 자료 | 빈 핵심 문장 통과, 요청 횟수 제한·모델 호출 중지 기능 없음 | Plan 05 |
| CI | 변경 경로별 배포 분리와 재사용 전체 검사 | 양쪽 변경 시 전체 CI 중복, 검증 관련 파일만 바꾸면 자동 검사 안 됨 | Plan 04 |
| 알림 | 실제 장애·복구 전달과 dead-letter 검증 기록 | 구독 자동 만료, 배포 시 최종 전달 확인 미자동화, Terraform 대시보드 변경 무시 | Plan 03 |
| 배포·복구 | 후보 리비전 검사와 main rollback script | secret 버전 재현성, relay 복구 절차와 실행 증거 보완 | Plan 06 |
| 공개 제출 | 기존 Plan 02 존재 | public 전환과 Environment 승인 설정은 아직 계획 | 제출 1~3일 전 유지 |
| 문서 | 설치·운영·실습 기록이 있음 | 현재 운영 안내와 과거 실습 상태가 혼재 | Plan 06에서 현재 안내만 정리 |
| 의존성·비밀정보 | 주요 lockfile과 action SHA 고정 | 전용 Python/이미지 취약점 검사·신규 secret 유입 검사가 CI에 없음 | 아래 조건부 후속 작업 |

## 근거가 있는 우선순위

### 1. 알림을 오래 유지하고 변경을 반영할 수 있게 하기

`builder-cup-discord-relay`와 `builder-cup-monitoring-alerts-dlq-inspect`를 조회한 결과 모두 `expirationPolicy.ttl=2678400s`였습니다. 이는 메시지 보존 7일과 별개인 비활성 구독 만료 설정입니다. 특히 평소 비어 있는 dead-letter 구독을 지속 유지할 설정이 필요합니다. [Pub/Sub 구독 정책](https://docs.cloud.google.com/pubsub/docs/subscription-properties)

[main.tf](../infra/gcp/main.tf)의 `ignore_changes = [dashboard_json]`은 서버가 추가하는 기본값뿐 아니라 앞으로 코드에서 바꾸는 차트도 update에서 제외합니다. 따라서 기존 `No changes` 결과만으로 대시보드 재현성이 확보됐다고 판단하면 안 됩니다. [Terraform ignore_changes](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle)

[deploy-alert-relay.sh](../scripts/deploy-alert-relay.sh)는 Pub/Sub publish 성공으로 끝납니다. 과거 실제 Discord 전달 확인은 유효하지만 이후 모든 배포가 자동으로 전달 완료를 검증하는 구조는 아닙니다.

### 2. 배포와 검사를 별도로 판단하기

[배포 workflow](../.github/workflows/) 두 개가 각각 전체 CI를 호출합니다. API와 relay를 한 번에 수정하면 같은 검사가 두 번 실행됩니다. 반대로 `tests/`, `compose.yaml`, `Dockerfile.dev`, `infra/gcp/`, `ci.yml`만 변경하면 현재 push 경로 필터에 걸리지 않습니다. 수동 CI는 가능하지만 release 시 자동 검증에는 공백이 있습니다.

이는 매 develop push에 CI를 켜자는 제안이 아닙니다. release에서 검사 한 번을 공유하고 배포 대상만 선택하면 됩니다.

### 3. 유료 요청의 범위와 모델 응답 경계 정하기

API에는 8,000자 입력 한도, Gemini 출력 1,024 token 한도, timeout과 재시도가 이미 있습니다. 팀 접근 코드도 적용돼 있습니다. 그러나 인증된 반복 요청을 제한하는 로직은 없으며, Cloud Run instance 수 제한은 모델 호출 횟수나 월 비용 제한과 같지 않습니다.

[schemas.py](../apps/api/src/builder_cup/schemas.py)의 `key_points`는 배열 개수만 검사합니다. `['']`, `[' ']`, 10만 자 문자열을 담은 배열이 모두 통과했습니다. 모델 지침의 nonempty 조건을 코드가 동일하게 보장하지 않는 구체적인 보완점입니다.

### 4. 배포를 되돌리는 절차를 실제로 재현하기

[메인 배포 script](../scripts/deploy-gcp.sh)는 팀 접근 secret의 `latest`를 참조하고, [relay 배포 script](../scripts/deploy-alert-relay.sh)는 숫자 version을 선택합니다. 이미지·리비전·설정·secret version을 같이 기록해야 복구 범위가 명확해집니다.

[운영 문서](operations.md)에는 이미 Discord·이메일을 설명하는 절과 함께 아직 알림 채널을 만들지 않는다는 과거 문장이 남아 있습니다. [실습 보고서](ai-lab-report.md)는 9월 21일 기준 역사 자료이므로 그 기록은 보존하고 현재 운영 상태를 가리키는 안내가 필요합니다.

### 제출 전 계획의 보완

현재 WIF 조건은 저장소·소유자·branch·push event를 검사하지만 `gcp` Environment를 나타내는 subject를
요구하지 않습니다. Plan 02에는 Environment 승인 설정과 함께 이 신뢰 조건을 맞추는 검증도 추가했습니다.
collaborator 목록 정리나 PR 의무화는 다시 넣지 않았고 실행 시점도 제출 전으로 유지합니다.

## 조건부 후속 작업

- 의존성 점검은 공통 API·relay·web의 lockfile부터 수동 또는 주간 검사로 시작할 수 있습니다. 현재 취약점 존재를 확인한 것은 아닙니다. 자동 버전 변경이나 자동 merge는 도입하지 않습니다.
- 새 secret 유입 방지는 개발 중에도 유용합니다. 모든 과거 이력의 공개 검사는 Plan 02에 남기고, 별도 작업을 택하면 오류 출력에 값을 노출하지 않는 검사부터 도입합니다.
- 새 팀원 Mac 검증은 지금 바로 사람이 실행할 수 있습니다. OS·칩·Docker/Compose 버전과 성공/실패만 기존 기록에 추가하면 됩니다.
- 후보 prototype을 공통 stack으로 옮기는 작업은 주제 결정 후 합니다. 현재 전체 공통 CI 성공은 후보 prototype들의 검증 성공을 뜻하지 않습니다.

## 지금 도입하지 않을 것

Graph DB, vector DB, RAG, 다중 에이전트 framework, Redis, Kubernetes, Cloud SQL은 사용 시나리오가 확정된 뒤 선택합니다. 이미 있는 PostgreSQL과 함수 기반 workflow로 검증 가능한 범위는 충분하며, 범용 기능을 미리 확대하지 않습니다.

추천 실행 순서는 **03 → 04 → 05 → 06**입니다. 03·04를 먼저 마친 뒤 제품 개발 시점에 맞춰 05·06을 진행해도 됩니다.
