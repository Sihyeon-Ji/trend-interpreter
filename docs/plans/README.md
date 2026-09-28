# 운영 준비 계획

작성일 **2026-09-23** · 최종 갱신 **2026-09-28** · 상태 **Plan 03 설계 대기, Plan 02 제출 전 대기**

[현재 준비 상태 조사](../AI-개발/개발-준비-점검.md) · [실습 종합 보고서](../AI-개발/AI-개발-종합-보고서.md) · [운영 명령](../개발환경/개발-명령어.md) · [완료 계획](archive/)

## 현재 계획

| ID | 상태 | 작업 | 완료 기준 |
| --- | --- | --- | --- |
| [03](03-trend-cloud-run-deployment.md) | 설계 대기 | Trend 앱 Cloud Run 배포 | 영속 저장소를 정한 뒤 `release/gcp` 한 번으로 API·웹·파이프라인 Job이 검증 후 배포 |
| [02](02-public-repository-release-protection.md) | 제출 전 대기 | 공개 저장소와 GCP 배포 승인 | 외부 사용자는 push할 수 없고 collaborator의 배포는 Environment 승인 후 진행 |

2026-09-28에 `prototype/trend`를 메인 앱(`apps/trend-api`, `apps/trend-web`)으로 승격했습니다. Plan 03은 그 배포 계획이며, 이전 실습 앱의 배포 job은 제거했습니다. 운영 Plan 03~06은 구현과 운영 검증을 마쳤습니다.

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
| [운영 Archive 03](archive/03-alert-delivery-hardening.md) | 알림 유지와 전달 검증 보완 |
| [운영 Archive 04](archive/04-ci-change-routing.md) | 변경 범위에 따른 CI와 배포 |
| [운영 Archive 05](archive/05-model-request-controls.md) | AI 요청량 제어와 결과 형식 검증 |
| [운영 Archive 06](archive/06-release-recovery.md) | 배포 기록과 안전 복구 경로 |

## 공통 원칙

- `develop`에서 작업하고 `release/gcp` push만 실제 GCP 배포를 시작합니다.
- 배포 전에 Compose 전체 검사와 인프라 검증을 통과시킵니다.
- 운영 로그와 알림에 원문, 생성 결과, API key를 포함하지 않습니다.
- GitHub와 GCP 설정을 바꾸면 문서의 현재 상태와 검증 결과도 함께 갱신합니다.
