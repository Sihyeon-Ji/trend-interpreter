# 운영 준비 계획

작성일 **2026-09-23** · 상태 **Plan 01~02 실행 전**

[종합 보고서](../ai-lab-report.md) · [운영 명령](../commands.md) · [완료 계획](archive/)

## 현재 계획

| ID | 상태 | 작업 | 완료 기준 |
| --- | --- | --- | --- |
| [01](01-production-alerting.md) | 실행 준비 | 운영 상태 감시와 알림 | 실제 장애 조건으로 지정 수신처에 알림이 도착하고 복구 상태를 확인 |
| [02](02-public-repository-release-protection.md) | 실행 준비 | 공개 저장소와 GCP 배포 승인 | 외부 사용자는 push할 수 없고 collaborator의 배포는 Environment 승인 후 진행 |

두 계획은 서로 독립적으로 진행할 수 있습니다. Plan 01은 알림 수신처를 정한 뒤 적용하고, Plan 02는 저장소를 공개하기 전에 준비한 다음 공개 직후 보호 규칙을 활성화합니다.

## 완료 계획

다음 계획은 구현과 검증을 마쳐 [archive](archive/)에 보관했습니다.

| ID | 완료 작업 |
| --- | --- |
| [Archive 01](archive/01-environment-reproducibility.md) | 개발환경 재현성과 진단 |
| [Archive 02](archive/02-model-evaluation.md) | 모델 평가와 비교 보고서 |
| [Archive 03](archive/03-local-model-history.md) | 실제 모델 실행 이력 연결 |
| [Archive 04](archive/04-database-recovery.md) | DB 변경과 백업·복구 |

## 공통 원칙

- `develop`에서 작업하고 `release/gcp` push만 실제 GCP 배포를 시작합니다.
- 배포 전에 Compose 전체 검사와 인프라 검증을 통과시킵니다.
- 운영 로그와 알림에 원문, 생성 결과, API key를 포함하지 않습니다.
- GitHub와 GCP 설정을 바꾸면 문서의 현재 상태와 검증 결과도 함께 갱신합니다.
