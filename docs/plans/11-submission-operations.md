# Plan 11. 제출 전후 운영 – 마지막 갱신·공개 전환·Cloud SQL 전환

작성일 **2026-10-09** · 상태 **진행 – 운영 DB 두 번째 전환(10-09) 완료, 마지막 갱신·공개 전환·유료 전환 남음** · 제출 **2026-10-18**

[계획 목록](README.md) · [GCP 운영](../운영/GCP-운영.md) · [승인 배치 게시](../개발환경/승인-배치-게시.md) · [WIF 배포 계정 분리](../운영/WIF-배포-계정-분리.md)

옛 Plan 11(공개 저장소와 배포 승인), Plan 13(Cloud SQL 체험 종료 전 유료 전환), Plan 19(운영 DB 데이터 갱신)를 10-09에 합쳤다. 셋 다 제출 일정에 묶인 운영 작업이고 순서가 이어진다. 경위·절차·지난 실행 기록은 원래 문서에 그대로 있다.

- [옛 Plan 11 – 공개 저장소와 GCP 배포 승인](archive/11-public-repository-release-protection.md)
- [옛 Plan 13 – Cloud SQL 무료 체험 종료 전 유료 전환](archive/13-cloud-sql-trial-to-paid-transition.md)
- [옛 Plan 19 – 운영 DB 데이터 갱신 경로](archive/19-production-data-refresh.md)

## 일정

| 날짜 | 할 일 | 완료 증거 |
| --- | --- | --- |
| 10-16 | 마지막 운영 DB 갱신(1) | 빠진 사람 결정 0, 새 snapshot 시각으로 웹이 열림 |
| 10-17 | 저장소 공개 전환과 보호 설정(2) | 외부·collaborator 계정의 거부·승인 경로 확인 |
| 10-20~26 | Cloud SQL 유료 전환 또는 이전(3) | 체험 표시 소멸 또는 새 DB 전환, 서비스 확인 |
| 10-27~28 | 실제 청구 확인(3) | Billing 보고서와 예상치 비교 |

## 1. 마지막 운영 DB 갱신 (10-16)

절차는 [GCP 운영의 운영 DB 갱신](../운영/GCP-운영.md)을 따른다(capture → build → create → upload → overlay → secret → Terraform·API 전환). 10-09 두 번째 전환에서 바뀐 점을 지킨다.

- Terraform은 `infra/gcp/hybrid`에서 `TF_DATA_DIR=.terraform/production`으로 실행한다. 기본 `.terraform`은 staging 상태다.
- API는 배포 스크립트가 revision 이름을 정해 Terraform이 409로 실패한다. Cloud Run v2 API로 template의 secret 버전과 revision 이름만 바꾼다.
- 백업·유지보수 Job도 새 secret version으로 옮긴다. 10-09에는 유지보수 Job을 빠뜨렸다.
- 게시 역할을 새 DB로 옮긴다. `GRANT CONNECT … TO trend_publisher`, `configure_publisher_role.py --role trend_publisher`를 실행하고, 새 DB 이름으로 `trend-production-publisher-database` version을 추가한다.
- 덮어 얹기(overlay)는 secret 추가 전에 끝낸다. 운영 DB에 일괄 갱신이 도는 동안 승인 배치를 준비하지 않는다.

완료 기준(옛 Plan 19)

- 새 snapshot 반영 뒤에도 `review_history`·`verified_human` 뜻·사람 리스크·`gemini_calls`가 전환 전과 같다.
- 전환 전 백업과 그 복원 검증 보고서가 있고, 이전 DB로 되돌리는 명령을 한 번 실행해 본 기록이 있다. **되돌리기 실행은 아직 하지 않았다.**
- 운영 웹의 사전·지도·해석이 새 snapshot 시각으로 열리고, 오류 경보가 없다.

## 2. 저장소 공개 전환과 배포 승인 (10-17)

전체 이력 재검사는 10-06에 마쳤다(오탐 3건). 공개 직전에 그 뒤 커밋까지 다시 검사한다. 순서는 아래와 같다. 상세는 [옛 Plan 11](archive/11-public-repository-release-protection.md#공개-직후-보호-설정)에 있다.

1. WIF 배포 계정 분리(`security/wif-environment`)를 적용한다. GCP IAM 적용과 GitHub 변수 등록이 코드 병합보다 먼저다([적용 순서](../운영/WIF-배포-계정-분리.md#적용-순서)).
2. 이력 재검사 → 공개 전환.
3. `gcp` environment 보호(required reviewer, self-review 금지, `release/gcp` 한정, 관리자 우회 금지).
4. Actions 기본 `GITHUB_TOKEN` read-only, fork PR의 secret·OIDC 차단 확인.

완료 기준

- 외부 사용자는 fork와 PR만 가능하고 직접 push할 수 없다. collaborator는 기존처럼 직접 push한다.
- `release/gcp` 배포에는 별도 Environment 승인이 필요하다.
- fork PR에 GitHub secret과 GCP OIDC가 노출되지 않는다.
- 실제 외부 계정과 collaborator 계정으로 거부·승인 경로를 각각 확인했다.

## 3. Cloud SQL 체험 종료 전 전환 (10-26까지)

`trend-project`는 무료 체험 인스턴스다(종료 예상 10-29경). 만료 전에 업그레이드하지 않으면 요청 처리를 멈춘다. 자동 유료 전환 설정은 없고 콘솔의 **지금 업그레이드**로 사람이 실행한다. 비용 비교와 대안은 [옛 Plan 13](archive/13-cloud-sql-trial-to-paid-transition.md#비용과-서비스-연속성-비교)에 있다.

1. 10-20~22: 콘솔의 정확한 만료 시각, DB 크기·연결 수·부하를 확인하고 견적을 다시 만든다.
2. 10-24까지: 월 비용 상한과 경로(유료 전환 또는 작은 인스턴스로 이전)를 정한다. `pg_dump` 사본을 Git 밖에 두고 복원을 확인한다.
3. 10-26까지: 실행하고 API·웹·DB 연결, 게시·백업 Job을 확인한다. 새 인스턴스로 옮기면 1의 전환 절차와 게시 역할 준비를 그대로 거친다.
4. 10-27~28: 실제 청구와 SKU를 확인한다.

만료 전 전환을 확인할 때까지 종료 알림을 일정에서 지우지 않는다.
