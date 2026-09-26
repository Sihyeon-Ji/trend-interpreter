# Plan 06 배포 복구와 운영 문서 정합성

작성일 **2026-09-24** · 완료일 **2026-09-26** · 상태 **완료**

[조사 근거](../../AI-개발/개발-준비-점검.md) · [현재 계획](../README.md) · [배포·복구 운영 절차](../../운영/배포-복구.md)

## 목표

배포 실패나 인증정보 교체 시 어느 리비전과 설정으로 돌아가야 하는지 팀원이 재현할 수 있게 합니다. 실제 동작·자동 검사·수동 확인·과거 실습 기록을 구분합니다.

## 착수 배경

대회 주제나 다른 팀원의 prototype을 기다릴 필요가 없습니다. 현재 운영 중인 `builder-cup`과 alert relay의
배포·복구 경로만 다룹니다. 특히 변경 파일이 없는 빈 commit은 `Release GCP`에서 배포 job을 선택하지
않으므로 명시적 재배포 절차가 필요했습니다. 배포 script와 복구 검사를 로컬·CI에서 준비했고,
운영 트래픽을 움직이는 과거 revision 복구 연습은 실행하지 않았습니다.

## 착수 당시 근거

- [rollback-gcp.sh](../../../scripts/rollback-gcp.sh)는 main 서비스 traffic만 변경하며 이후 health·인증 검증이 없었습니다.
- [deploy-gcp.sh](../../../scripts/deploy-gcp.sh)는 `DEMO_API_KEY`에 `latest`를 사용했습니다. relay는 숫자 version을 선택했습니다.
- relay의 최종 Pub/Sub 검증은 Plan 03에서 보완했습니다. 여기서는 복구 절차와 양쪽 서비스의 배포 기록을 다뤘습니다.
- [GCP 운영 문서](../../운영/GCP-운영.md)에 알림 구축 설명과 ‘수신자 미정으로 channel을 만들지 않는다’는 과거 안내가 공존했습니다.
- [실습 보고서](../../AI-개발/AI-개발-종합-보고서.md)는 오래된 commit 기준이며 현재의 GCP 상태와 구별할 필요가 있었습니다.

## 작업 순서

1. 배포마다 commit SHA, image digest, service, 이전·신규 revision, 모델 ID, secret version 번호, 검사 결과를 Actions summary에 기록합니다. secret 값과 사용자·모델 본문은 제외합니다.
2. main secret을 숫자 version으로 고정해 revision별 설정을 재현합니다. 새 version 선택과 실제 교체는 분리하며 현재 값을 불필요하게 회전하지 않습니다.
3. main·relay 복구 명령에 대상 서비스 확인과 알려진 정상 revision 확인을 넣습니다. 잘못된 서비스의 revision을 거부하고 traffic 전환 후 main health·인증 거부, relay IAM·인증 health를 확인합니다.
4. 검사 실패 시 이전 traffic이 보존되는지 배포 script 테스트로 확인합니다. 실제 되돌리기 연습은 별도 검증 대상 또는 합의된 운영 시점에 실행하고 무조건 운영 traffic을 흔들지 않습니다.
5. 기존의 살아 있는 secret version으로 rollback하는 경우와, 이미 폐기·노출된 secret 때문에 새 revision을 만들어야 하는 경우를 구분합니다. 노출된 webhook이나 팀 접근 코드를 복구 목적으로 다시 활성화하지 않습니다.
6. 운영 문서의 낡은 문장을 정리하고 역사 보고서 상단에 기준 시점과 최신 운영 문서 링크를 넣습니다. 과거 결과를 새 결과로 덮어쓰지 않습니다.
7. CI 성공 범위가 공통 stack임을 명시합니다. 다른 Mac 검증은 기존 archive의 남은 확인 항목을 사용합니다.

## 완료 기준

- 배포 기록만으로 image·revision·secret version과 복구 대상을 식별할 수 있습니다.
- 자동 검사 실패가 배포 성공으로 표시되지 않습니다.
- 숫자 secret version을 사용하는 새 revision과 복구 절차를 테스트합니다.
- main과 relay의 복구 동작 및 실패 경로 검증 결과를 따로 기록합니다.
- current 운영 문서 안에 알림 미구축·과금 보류 같은 상충하는 안내가 없습니다.
- 문서 링크 검사, 배포 script 검사, 관련 Compose 검사와 Terraform fmt·validate를 통과합니다.

## 범위 제한

새 staging 상시 환경, 복수 region, Cloud SQL, backup 플랫폼을 만들지 않습니다. 기존 로컬 DB 복원 계획은 완료 기록을 재사용합니다. Plan 02의 public 전환과 Environment 승인 설정은 제출 전에 진행합니다.

## 실행 결과

- `395783c`에서 배포 요약, 숫자 secret 버전 선택, main·relay 복구 사전 검사와 사후 검사, 실패 시 이전 리비전 복원을 구현했습니다. GCP 배포 서비스 계정에는 `builder-cup-demo-key`의 버전 메타데이터 조회 권한만 추가했습니다.
- `Release GCP` 실행 [36137631901](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions/runs/36137631901)은 공통 CI와 두 서비스 배포에 성공했습니다. 새 main revision은 숫자 secret 버전 `1`을 참조합니다.
- 변경 파일 없는 `0ebe420` (`ops: 메인 서비스 재배포`)의 [실행 36138292140](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions/runs/36138292140)은 공통 CI와 main 배포에 성공했고 relay 배포는 건너뛰었습니다. main은 `builder-cup-00017-wap`으로 교체됐으며 relay는 `builder-cup-alert-relay-00008-gas`를 유지했습니다.
- 두 현재 revision에 `--check`를 실행해 Ready, image digest, 활성 숫자 secret 버전, 100% traffic, HTTP health를 확인했습니다. 잘못된 서비스의 revision과 과거 `latest` 참조 main revision은 거부됐습니다.
- 단위 테스트에서 복구 후 HTTP 실패 시 이전 revision으로 traffic을 복원하는 경로와 후보 health 실패 시 traffic을 전환하지 않는 경로를 검증했습니다. 운영의 과거 revision으로 실제 traffic을 옮기는 연습은 하지 않았습니다.
- Compose `check`, Terraform fmt·validate, script 문법 및 문서 링크 검사를 통과했습니다. Terraform IAM 변경은 적용됐으나, 완료 시점의 별도 `terraform plan` 재확인은 로컬 ADC 부재로 실행되지 않았습니다.

실제 장애 때는 [배포·복구 운영 절차](../../운영/배포-복구.md)의 `--check` 결과와 현재 secret 상태를 다시 확인한 다음 `--apply`를 실행합니다. 폐기되거나 노출된 secret은 재활성화하지 않습니다.
