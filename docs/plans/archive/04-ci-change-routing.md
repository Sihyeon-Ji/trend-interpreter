# Plan 04 변경 범위에 따른 CI와 배포 실행

작성일 **2026-09-24** · 상태 **구현·배포 검증 완료** · 구현 커밋 **21bc5db**

[조사 근거](../../development-readiness-review.md) · [현재 계획](../README.md)

## 목표

release push에서 필요한 검사를 빠뜨리지 않고 한 번 수행한 뒤, 변경된 서비스만 배포합니다. develop 자동 CI와 PR 필수화는 도입하지 않습니다.

## 현재 근거

- 변경 전 두 [배포 workflow](../../../.github/workflows/)는 각각 `ci.yml` 전체를 호출했습니다.
- 앱·relay가 함께 바뀌면 같은 CI가 두 번 실행됩니다.
- 테스트·Compose·Terraform·CI 설정만 바뀌는 release는 두 배포의 paths에 해당하지 않습니다.
- CI는 main production image를 검사하지만 relay image의 build·health는 현재 relay 배포 시점에 확인됩니다.

## 권장 구조

하나의 release 진입 workflow에서 변경 범위를 판단하고, 공통 검사 뒤 application과 relay 배포 job을 각각 조건부 실행합니다. 화면에 workflow 한 개가 보여도 배포 job은 두 개로 구분합니다. 두 배포가 필요할 때 전체 CI가 한 번만 실행되는 것이 핵심입니다.

| 변경 범위 | 검사 | Application 배포 | Relay 배포 |
| --- | --- | --- | --- |
| `apps/api/`, `apps/web/`, main Dockerfile·lockfile | 전체 CI 1회 | 실행 | 생략 |
| `apps/alert-relay/`, relay 배포 script | 전체 CI 1회·relay image 검사 | 생략 | 실행 |
| 양쪽 서비스 또는 `.dockerignore` | 전체 CI 1회·양쪽 image 검사 | 실행 | 실행 |
| `tests/`, `evaluation-cases/`, `compose.yaml`, `Dockerfile.dev`, CI 검증 script | 전체 CI 1회 | 생략 | 생략 |
| `infra/gcp/`만 | Terraform fmt·validate | 생략 | 생략 |
| Release workflow 자체 | 전체 CI 1회 | 생략 | 생략 |
| `docs/`, README만 | 생략 | 생략 | 생략 |
| `prototype/`만 | 공통 CI 생략, 후보 자체 검사 안내 | 생략 | 생략 |

main 배포 script의 수정은 application 배포, relay 배포 script의 수정은 relay 배포에 해당합니다. 공통 CI를 통과해도 prototype 검증 완료로 표시하지 않습니다.

## 작업 순서

1. 기존 CI를 호출하는 release 진입점을 하나로 합치고 배포 job의 권한·environment·service별 동시 실행 제한을 보존합니다.
2. push 전 SHA와 현재 SHA의 전체 차이를 기준으로 판정합니다. 여러 commit·삭제·rename·첫 branch 생성·기준 SHA 부재를 처리하며, 판정 불가를 변경 없음으로 취급하지 않습니다.
3. 필요한 history만 fetch하고 파일명은 안전하게 처리합니다. GitHub 기본 paths diff의 파일 수 제한도 고려해 변경을 누락하지 않게 합니다.
4. shell/YAML routing 검증을 추가하고 위 표를 합성 Git 이력으로 재현합니다. 검증 때문에 Cloud Run 배포나 유료 모델 호출을 만들지 않습니다.
5. 적용 전후 같은 변경 조합의 CI 실행 횟수와 시간을 비교합니다. 캐시는 lockfile을 기준으로 적용하고 검사 생략으로 시간을 줄이지 않습니다.

## 완료 기준

- 양쪽 변경의 전체 CI 실행 횟수는 정확히 1회입니다.
- tests·Compose·CI 변경만 있어도 검사는 실행되고 배포는 생략됩니다.
- Terraform 변경은 자동 apply하지 않습니다.
- 문서만 변경하거나 develop에 push할 때 유료 배포 작업이 시작되지 않습니다.
- 각 배포 job은 `environment: gcp`와 기존 OIDC 제한을 유지합니다.
- 수동 전체 CI 실행은 계속 가능합니다. 수동 배포 trigger를 추가해 WIF 제약을 넓히지 않습니다.

## 검증 결과

기존 두 배포 workflow를 [Release GCP](../../../.github/workflows/release-gcp.yml) 하나로 합쳤습니다.
[release_scope.py](../../../scripts/release_scope.py)가 push 전후 SHA의 Git 변경 파일을 읽고 검사·인프라·
앱·relay 범위를 판정합니다. 기준 commit을 읽을 수 없으면 검사와 두 배포를 요구하는 방향으로 처리합니다.
문서와 prototype만 변경되면 검사·배포 job은 실행되지 않습니다.

로컬 합성 Git 이력과 파일 조합 테스트 3개가 통과했습니다. CI 컨테이너에는 Git CLI가 없어 합성 Git
이력 테스트 1개는 skip하고 분류 단위 테스트 2개를 실행했습니다. GitHub runner에는 Git이 있어
실제 release의 변경 범위 판정을 수행했습니다.

2026-09-24 [실제 release](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions/runs/36003893219)
`21bc5db`에서 workflow 1개가 실행됐습니다. `scope`와 **공통 CI 1회**가 성공했고,
이번 commit은 메인 앱과 relay 관련 파일을 모두 포함해 배포 job 두 개가 각각 성공했습니다.
인프라 전용 job은 공통 CI에 Terraform 검사가 포함되어 skip됐습니다. CI에서는 기존 검사에 relay
production image build·health를 추가했습니다. Terraform만 변경될 때의 GitHub 실제 실행은
이번 release에서 발생하지 않아 합성 분류 검사와 workflow 조건으로 확인했습니다.

이후 [검사 전용 release](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions/runs/36004803676)
`c438c86`도 성공했습니다. 변경 범위 판정 script·테스트·문서만 바뀌어 공통 CI 1회가 실행됐고,
application과 relay 배포 job은 모두 skip됐습니다. Relay 실코드만 바뀌는 release의 GitHub 실제
실행은 아직 없으며 합성 분류 테스트로 확인했습니다.

## 참고

[GitHub workflow paths와 Git diff 동작](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
