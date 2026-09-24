# 운영 준비 계획

작성일 **2026-09-23** · 최종 갱신 **2026-09-24** · 상태 **Plan 03~06 제안·미착수, Plan 02 제출 전 대기**

[현재 준비 상태 조사](../development-readiness-review.md) · [실습 종합 보고서](../ai-lab-report.md) · [운영 명령](../commands.md) · [완료 계획](archive/)

## 현재 계획

| ID | 상태 | 작업 | 완료 기준 |
| --- | --- | --- | --- |
| [03](03-alert-delivery-hardening.md) | 제안·우선 | 알림 유지와 전달 검증 보완 | 구독 비만료, 대시보드 변경 반영, 실제 전달 결과 확인 |
| [04](04-ci-change-routing.md) | 제안·우선 | 변경 범위에 따른 CI와 배포 | 전체 CI 1회 공유, 검증 파일 변경도 검사, 필요한 서비스만 배포 |
| [05](05-model-request-controls.md) | 제안 | AI 요청량 제어와 결과 검증 | 호출 중지·초과 요청 차단·빈 핵심 문장 거부 |
| [06](06-release-recovery.md) | 제안 | 배포 복구와 운영 문서 정합성 | 배포 설정 추적, 복구 검증, 최신 운영 안내 일치 |
| [02](02-public-repository-release-protection.md) | 제출 전 대기 | 공개 저장소와 GCP 배포 승인 | 외부 사용자는 push할 수 없고 collaborator의 배포는 Environment 승인 후 진행 |

권장 순서는 **03 → 04 → 05 → 06**입니다. 새 계획은 구현 완료를 뜻하지 않습니다. 주제가 정해지기 전에 모두 끝내야 하는 필수 조건도 아니며, 실제 결함과 운영 위험을 먼저 줄이는 순서입니다.

Plan 02는 제출 1~3일 전 공개 준비를 마친 뒤 public 전환 직후 보호 규칙을 활성화합니다. Collaborator 목록 정리는 이미 완료되어 다시 수행하지 않습니다.

## 완료 계획

다음 계획은 구현과 검증을 마쳐 [archive](archive/)에 보관했습니다.

| ID | 완료 작업 |
| --- | --- |
| [Archive 01](archive/01-environment-reproducibility.md) | 개발환경 재현성과 진단 |
| [Archive 02](archive/02-model-evaluation.md) | 모델 평가와 비교 보고서 |
| [Archive 03](archive/03-local-model-history.md) | 실제 모델 실행 이력 연결 |
| [Archive 04](archive/04-database-recovery.md) | DB 변경과 백업·복구 |
| [운영 Archive 01](archive/01-production-alerting.md) | Discord 운영 알림 중계기 |

## 공통 원칙

- `develop`에서 작업하고 `release/gcp` push만 실제 GCP 배포를 시작합니다.
- 배포 전에 Compose 전체 검사와 인프라 검증을 통과시킵니다.
- 운영 로그와 알림에 원문, 생성 결과, API key를 포함하지 않습니다.
- GitHub와 GCP 설정을 바꾸면 문서의 현재 상태와 검증 결과도 함께 갱신합니다.
