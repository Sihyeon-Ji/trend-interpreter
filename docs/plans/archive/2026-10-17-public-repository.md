# 10-17 저장소 공개 전환과 배포 승인

실행일 **2026-10-17** · 담당 **shji(지시현)** · 상태 **완료(10-16, 하루 앞당김) – 공개 전환, 배포는 release/gcp에서만, 외부 계정 push 거부 확인** · 선행 [10-16 운영 DB 갱신](2026-10-16-final-db-refresh.md) · 제출 **10-18**

[계획 목록](../README.md) · [GCP 운영](../../운영/GCP-운영.md) · [WIF 배포 계정 분리](../../운영/WIF-배포-계정-분리.md) · 경위 [옛 Plan 11](11-public-repository-release-protection.md)

## 10-16 실행 – 하루 앞당김

- 마지막 이력 검사: 전체 554개 커밋, 3건 – 10-06에 오탐으로 판별한 것과 같음. 원격 브랜치 둘 다 Claude 공동 작성자 표시 0, 비밀 파일 추적 없음.
- 공개 전환(22시경, `gh repo edit --visibility public`).
- `gcp` environment: 배포 브랜치를 `release/gcp`로만 제한했다. 승인자는 두지 않는다 – collaborator는 승인 없이 develop·`release/gcp`에 push하고 바로 배포된다(10-16 사용자 결정. 승인자·develop PR 필수를 잠깐 켰다가 같은 날 풀었다).
- collaborator가 아닌 사람은 push·브랜치 생성을 할 수 없다(공개 저장소의 기본). fork·PR만 되고, 워크플로는 PR로 돌지 않는다.
- 남는 위험: collaborator 계정이 털리면 검토 없이 운영에 배포될 수 있다. 막는 것은 GitHub 계정 보안(2단계 인증)뿐이다.
- Actions 기본 `GITHUB_TOKEN`은 읽기 전용(이미 그랬음). 워크플로는 `release/gcp` push·수동 실행에만 돌아 fork PR에서 secret·OIDC가 나갈 길이 없다. 외부 기여자의 PR 워크플로는 모두 승인 뒤 돌게 했다.
- 운영 주소는 README·문서에서 뺐다(제출 양식에만). 10-04·10-14 커밋 기록에는 남아 있다 – 이력을 다시 쓰지 않았다.

외부 계정 확인(10-16, 지시현): collaborator가 아닌 GitHub 계정으로 push하면 거부된다.

## 10-16 미리 한 것

- 저장소 이름을 `Sihyeon-Ji/trend-interpreter`로 바꿨다. 배포 인증(WIF)은 저장소 ID·environment 속성으로 묶여 있어 그대로 동작한다. 로컬 remote는 `git remote set-url origin https://github.com/Sihyeon-Ji/trend-interpreter.git`(옛 주소도 넘겨 준다).
- 오래된 원격 브랜치 `claude/focused-gagarin-383da1`·`security/wif-environment`를 지웠다(develop에 없는 커밋 0). 남은 원격 브랜치는 `develop`·`release/gcp`.
- 10-10 뒤 커밋 비밀값 재검사 0건, 모든 원격 브랜치에 Claude 공동 작성자 표시 0.
- 이전 DB로 되돌리기 훈련은 하지 않는다(10-16 결정).


## 미리 할 일 (10-17 전)

- **이력 재검사(10-10 실행).** `gitleaks 8.30.1 git --log-opts=--all --redact=100`(노트북 diff는 `cat`으로, [공개 전 보안 점검](../../운영/공개-전-보안-점검.md)). 473개 커밋 중 줄이 더해진 457개를 검사, 3건 – 10-06에 오탐으로 판별한 것과 같은 파일·커밋(이미지 digest, 빈 `.env.example` 값, 공개 프로젝트 ID)이다. 공개 당일에는 10-10 뒤 커밋만 다시 본다.
- **WIF 배포 계정 분리 – 적용 완료(10-10).** 바인딩을 OIDC subject 대신 토큰 속성(배포 계정은 `environment=gcp`, 이미지 계정은 저장소 ID)으로 바꿔 적용했다. 이미지 job은 이미지 계정으로, 배포 job은 배포 계정으로 인증해 배포까지 성공했다(eb17d5b, API `00068-vif`). 경위는 [WIF 배포 계정 분리](../../운영/WIF-배포-계정-분리.md#2026-10-10-적용과-바꾼-점). 절차 1은 끝났다.
- **검사용 계정.** 외부 GitHub 계정 하나(저장소 권한 없음)와 collaborator 계정 하나(예: ktwoo)가 필요하다. 외부 계정으로 직접 push 거부·fork PR에 secret이 없음을, collaborator 계정으로 develop push와 `release/gcp` 배포가 승인을 기다리는 것을 확인한다.

## 절차

전체 이력 재검사는 10-06에 마쳤다(오탐 3건). 공개 직전에 그 뒤 커밋까지 다시 검사한다. 순서는 아래와 같다. 상세는 [옛 Plan 11](11-public-repository-release-protection.md#공개-직후-보호-설정)에 있다.

1. WIF 배포 계정 분리(`security/wif-environment`)를 적용한다. GCP IAM 적용과 GitHub 변수 등록이 코드 병합보다 먼저다([적용 순서](../../운영/WIF-배포-계정-분리.md#적용-순서)).
2. 이력 재검사 → 공개 전환.
3. `gcp` environment 보호(required reviewer, self-review 금지, `release/gcp` 한정, 관리자 우회 금지).
4. Actions 기본 `GITHUB_TOKEN` read-only, fork PR의 secret·OIDC 차단 확인.

완료 기준

- 외부 사용자는 fork와 PR만 가능하고 직접 push할 수 없다. collaborator는 기존처럼 직접 push한다.
- `release/gcp` 배포에는 별도 Environment 승인이 필요하다.
- fork PR에 GitHub secret과 GCP OIDC가 노출되지 않는다.
- 실제 외부 계정과 collaborator 계정으로 거부·승인 경로를 각각 확인했다.
