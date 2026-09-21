# 세션 인수인계 — 2026-09-21

## 목표와 결정 사항

AI Builder Cup 주제를 정하기 전에 재사용 가능한 개발 기반을 준비합니다. 팀원은 네 명이고 개발자는
한 명이며 인프라도 개발자가 담당합니다. 하나의 저장소 안에서 web, API, model runtime, infrastructure
directory의 책임을 분리합니다. 한 명이 운영할 수 있는 규모로 유지합니다.

- 저장소: [Sihyeon-Ji/2026-google-ai-builder-cup](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup)
- 개발 및 기본 branch: `develop`. Push해도 CI가 자동으로 실행되지 않습니다.
- 배포 branch: `release/gcp`. Push하면 CI, image build, GCP 배포가 실행됩니다.
- GCP project: `stunning-crane-508614-c1`(번호 `266542883304`)
- 2026-09-21에 결제를 연결하고 cloud 배포를 재개했습니다. Cloud Run Tier 1 가격과 직접 custom domain
  mapping 지원을 고려해 도쿄(`asia-northeast1`)를 배포 대상으로 선택했습니다.
- Notion 작업 범위는 [대회 페이지](https://www.notion.so/)와
  그 하위 page로 제한합니다. 외부에 연결된 page는 범위에 포함하지 않습니다.

## 진행 과정

| 단계 | 결과 |
| --- | --- |
| 범위 검토 | React/Vite, FastAPI, Gemini, Docker, Cloud Run, GitHub Actions와 기본 관측 기능을 선택했습니다. Database, queue, Kubernetes, 전체 monitoring stack은 요구사항이 생길 때까지 보류했습니다. |
| 초기 기반 구성 (`41b306e`) | 애플리케이션, model adapter, test, container, Terraform, CI/CD, 운영 문서를 만들었습니다. |
| CI 유지보수 (`63b59fa`) | GitHub Actions를 갱신하고 공식 release commit SHA로 고정했습니다. |
| 검증 전용 workflow (`2167858`) | 인자 없는 `make`가 help를 표시하고 `make eval`은 mock만 사용하도록 바꿨습니다. `eval-live`와 `infra-apply`를 분리하고 결제 사전 검사를 추가했으며 Notion/GCP 제한을 기록했습니다. |
| 인수인계 정리 | Sample directory 이름을 `evaluation-cases`로 바꾸고 runner와 문서를 갱신했으며 남은 작업을 기록했습니다. |
| 첫 cloud release (`07ef775`) | 도쿄 리전에 기반 인프라를 적용하고 최초 서비스 배포 처리를 수정한 뒤 Cloud Run 배포와 실제 Gemini request를 검증했습니다. |

## 완료 및 검증 사항

- React + TypeScript playground와 FastAPI endpoint를 만들었고 release container 하나에서 함께 제공합니다.
- Mock, Gemini/Vertex AI, OpenAI 호환 vLLM adapter를 구현했습니다. API에는 CUDA/vLLM 의존성이 없습니다.
- 입출력 검증, 제한된 retry와 timeout, request ID, 구조화 log, 사용량 metadata를 구현했습니다.
- 배포된 모델 request는 팀 공용 access code로 보호하며 credential을 UI bundle에 넣지 않습니다.
- Python test 7개, browser test 2개, mock 평가, frontend build, Terraform 검증을 통과했습니다.
- GCP용 `linux/amd64` image를 포함해 Docker build와 container smoke check를 로컬에서 통과했습니다.
- Desktop/mobile UI를 확인했습니다. GitHub CI는 commit `2167858`까지 통과했으며 이후 결과는
  [Actions](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions)에서 볼 수 있습니다.
- GitHub CLI 접근과 `develop` push가 동작합니다. GitHub Project board도 CLI로 접근할 수 있습니다.
- GCP CLI login, ADC 갱신, project Owner role, 활성 API 목록, 로컬 Terraform 검증을 확인했습니다.
  ADC의 quota project도 이 project로 설정했습니다. 이 설정 자체가 결제를 활성화하지는 않습니다.
- Mac 계정 이름을 `sihyeon`에서 `sean`으로 바꾼 뒤 Docker Desktop이 예전 `/Users/sihyeon` disk path를
  참조했습니다. 기존 disk가 현재 home directory 아래에 있음을 확인했고 이후 engine이 정상적으로
  시작되었습니다. Container 검사로 실제 동작도 확인했습니다.
- 도쿄 리전에 Terraform 기반 리소스 25개를 적용했습니다. 저장된 service-account key 없이 GitHub
  Workload Identity 인증과 release workflow가 성공했습니다.
- Cloud Run revision `builder-cup-00003-nec`가
  `https://builder-cup-7jftqxfz3q-an.a.run.app`에서 traffic 100%를 처리합니다. Static UI, health,
  anonymous request 거부, 인증된 `gemini-3.5-flash` 추론을 모두 확인했습니다. 실제 호출은 token 사용량
  metadata와 함께 HTTP 200을 반환했습니다. Release 전용 workflow도
  [실행 35587198212](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions/runs/35587198212)에서 통과했습니다.

## 남은 작업

| 영역 | 현재 상태 | 다음 단계 |
| --- | --- | --- |
| 로컬 Gemma/vLLM | 별도 Linux/NVIDIA Compose profile과 연결 안내를 준비했습니다. | GPU model, VRAM, driver 정보를 확보하고 model/image 호환성과 실제 추론을 검증합니다. |
| GitHub·Notion plugin | 설치했지만 최근 MCP 호출은 `USER_NOT_LOGGED_IN`을 반환했습니다. CLI 인증은 GitHub plugin 인증과 별개입니다. | 각 plugin에서 OAuth를 완료한 뒤 지정한 저장소와 Notion page 범위 안의 읽기 접근만 검증합니다. |
| 예산·알림 | Monitoring dashboard를 배포했습니다. 선택 사항인 Terraform billing budget은 설정하지 않았습니다. | KRW 예산과 수신자를 정합니다. 예산 알림은 지출을 중단하지 않습니다. |
| 주제·평가 품질 | 주제는 아직 정하지 않았고 현재 평가는 contract smoke check입니다. | 사용자 scenario, 대표 데이터, domain별 성공·실패 case를 수집합니다. |

대화 중 token이 노출된 적이 있지만 이 저장소나 MCP 설정에는 복사하지 않았습니다. 폐기·교체 여부는
확인하지 못했습니다. 해당 값을 문서나 log에 다시 남기지 않습니다.

## 로컬 개발 이어가기

예전 Make 기반 설정은 기록일 뿐이며 지금은 대체되었습니다. 최신 [로컬 개발 안내](../README.md#local-development)나
[한글 시작 안내](setup.md)를 따릅니다. Git과 Docker를 설치하고 `develop`을 clone한 뒤
`docker compose up -d`를 실행합니다. Mount한 source file이 바뀌면 web과 API가 reload됩니다.
Image에 Node 24.21.0과 Python 3.12가 들어 있으므로 mock stack에는 host language tool이나 `.env`가
필요하지 않습니다.

검사, test, frontend build, mock contract 검증은 `docker compose run --rm --build check`로 실행합니다.
Browser test는 `docker compose run --rm --build e2e`, 로컬 Terraform 검증은
`docker compose run --rm infra-check`로 실행합니다. 이 명령은 cloud resource를 만들지 않습니다.
포트 8080에서 운영 방식의 mock app을 실행하려면 `docker compose up -d --build preview`를 사용합니다.
Makefile은 삭제됐고 `scripts/`에는 내부 평가 및 운영자용 script가 남아 있습니다.

예전 Docker 계정 path 복구는 다른 Mac에서 수행해야 할 준비 단계가 아니라 과거 기록입니다. 두 Mac의
home path가 같아도 설치한 tool과 credential은 장비마다 다릅니다. Mock 검증은 실제 Gemini 접근이나
AI 품질을 입증하지 않습니다.

## GCP에 배포하기

1. Resource를 만들기 전에 선택한 region과 예산을 확인합니다. Cloud Run 애플리케이션과 Artifact
   Registry는 도쿄(`asia-northeast1`)를 사용합니다. [운영 문서](operations.md)를 참고합니다.
2. 활성 billing account, 권한, API, model 제공 여부를 확인합니다. Credential, Terraform state,
   secret 값은 commit하지 않습니다.
3. `bash scripts/bootstrap-gcp.sh`를 실행합니다. 기반 인프라를 구성하고 GitHub 배포 variable을 설정합니다.
4. 현재 code를 승격한 뒤 개발 branch로 돌아옵니다.

   ```bash
   git switch release/gcp             # branch가 없으면 git switch -c release/gcp develop
   git merge --ff-only develop
   git push -u origin release/gcp
   git switch develop
   ```

5. GitHub Actions를 지켜봅니다. Secret Manager의 team code로 배포 URL과 실제 Gemini request를
   검증합니다. Health check만으로는 model 접근을 검증할 수 없습니다. 문제가 있으면
   [운영 문서](operations.md)의 rollback 절차를 따릅니다.

## 다음에 확인할 문서

- [README](../README.md): 자주 쓰는 명령과 저장소 구조
- [아키텍처](architecture.md): 책임 경계와 보류한 component
- [운영](operations.md): bootstrap, 비용, 접근, log, rollback
- [Gemma/vLLM](../models/vllm/README.md): GPU host 설정과 SSH tunnel
- [팀 workflow](team-workflow.md): 조사, acceptance criteria, 팀 역할
- [GitHub Project](https://github.com/users/Sihyeon-Ji/projects/1): 팀 board

모든 source와 문서는 `develop`을 기준으로 관리합니다. 로컬 credential, `.env`, model weight,
dependency cache, screenshot, 생성된 평가 결과, 복구 tool은 Git에 올리지 않습니다.
