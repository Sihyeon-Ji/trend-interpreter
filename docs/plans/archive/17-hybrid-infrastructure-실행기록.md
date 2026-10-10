# Plan 17 실행 기록

작성일 **2026-10-02** · 브랜치 **develop** · 최종 점검 **2026-10-06** · 상태 **기록 보관(10-10) – Plan 17과 함께 archive**

> 10-10에 Plan 17과 함께 보관했다. GPU 시험 기록은 [Plan 21](../21-gemma-live-classify.md)이 참고한다.

[계획](17-hybrid-infrastructure.md) · [인수·DVC 명령](../../개발환경/데이터-스냅숏-DVC.md)

## 10-06 후속 재점검

문서 앞부분의 10-03 최초 판정 뒤에 staging·production·GCE 실제 시험 기록이 추가돼 있다. 현재 통합 진척도는 [10-06 재점검](구현-완료도-실측-점검-2026-10-06.md)을 따른다. 승인 게시·독립 품질·최종 데모 완료로 해석하지 않는다.

## 10-03 전체 진척도 점검

[전체 점검 보고서](구현-완료도-실측-점검-2026-10-03.md)에서 현재 계획 17개·과거 계획 9개와 고정 사본을 대조했다. 아래 단계 표의 날짜별 완료는 그 범위에서 유지한다. 최초 점검의 미커밋 GPU 코드는 후속 `4e237db`에서 커밋됐으며 실제 자원 구축과 구분한다. 동시 작업의 후속 실행 기록은 이 절 뒤에 보존한다.

| 단계 | 10-03 판정 | 남은 확인 |
| --- | --- | --- |
| 0 입력·권한·예산 | 고정 로컬 인수 검증 | 생산자 manifest·IAM 경계·GPU zone/quota·승인 예산 |
| 1 데이터/DVC | 도구·선택 대상·로컬 독립 재현 구현 | GCS 고정 게시/push·실제 팀원 2명 재현 |
| 2 Kaggle | 실제 짧은 학습/재개·독립 평가 후보 준비 | 전체 학습·사람 정답 20개·출처 확인·모델 승격 |
| 3 API·DB | 로컬 41표 대조·VPC/IAM 코드 | Cloud SQL staging·비공개 API·복원·실제 권한 |
| 4 GPU | gateway·VM/설치/adapter 코드 커밋, 실제 서빙 미검증 | 준비 image·승인 release·실제 추론/TLS·재시작/종료 |
| 5 웹 | 공통 ID token fetch·sample 흐름 검증 | 실제 Cloud Run IAM·staging 분리·API 모드 |
| 6 게시·운영 | 유지보수·기존 게시 시각 신호 일부 | 승인 배치/활성 publication·Job·백업·경보 |
| 7 배포·평가 | 미실행 | 호환 release/복구·Gemini/Gemma·배포 데모 3개 |

현재 확대 사전의 생애주기 unknown 91.7%, 리스크 검사 전 4,048개, 현재 뜻의 감사 flagged 3,093개와 최초 의존성 보안 검사 14건 실패를 후속 완료 조건에 반영한다. 이후 13건 수정·개발 도구 1건 기한부 예외로 보안 재검사는 통과했다(10-03 커밋 전). 로컬 검사 통과로 이 항목들을 완료 처리하지 않는다.

## 이번에 구현·실측한 범위

| 단계 | 결과 | 남은 완료 조건 |
| --- | --- | --- |
| 0 입력·권한 확인 | DB 3개 객체의 generation·CRC32C·SHA-256 고정, 41개 표 무결성·행 수 대조, GCP·버킷 권한 읽기 전용 확인 | 생산자 완료 manifest, GPU quota·zone·승인 예산, 수집 DB와 서비스 승인 DB 경계 확정 |
| 1 인수·DVC 도구 | `scripts/snapshot.py`, 루트 uv lockfile, ADC GCS remote, v5 입력 2개 `.dvc`, SHA-256·표제어 누수 검사 | GCS 고정 사본·DVC push, 비공개 Kaggle Dataset, 실제 팀원 2명 재현·과거판 복원 |
| 2 학습·재개 기반 | 독립 lockfile·입력/계보 계약, CPU 재개 상태 일치, 실제 Gemma/T4의 optimizer 2→4회·상태/가중치 검증 | 팀원 2명 재현·전체 학습·독립 사람 평가·기존 v5 revision 계보 |
| 3 DB 선행 검증 | `--skip-user-data`의 `lookups` 누락 수정, 실제 백업을 로컬 PostgreSQL 임시 스키마에 이관·41개 표 대조 | Cloud SQL staging 이관·권한 분리·백업·복원 |
| 5 웹 서버 인증 준비 | 모든 서버 API 호출의 Google ID token·갱신·공유·취소, 서버/브라우저 경계 검증 | 실제 Cloud Run IAM·staging 분리·인증 API 연결·배포 검증 |

2단계의 전체 학습·독립 품질 평가와 4·5·6·7단계의 서빙·웹 인증·승인 게시·배포는 아직 완료가 아니다. 기존 배포 job은 계속 비활성이다.

## 실제 인수

`manifests/20261001T224511-e56b90d.json`은 수집 시각 `2026-10-01T22:45:11+09:00`, 수집 코드 `e56b90d`의 **로컬 인수 기록**이다. 고정 경로 게시 전이므로 `state=captured`이며 `latest/`의 해당 generation이 삭제돼도 다시 읽을 수 있다고 보증하지 않는다. 압축 DB의 SHA-256은 `a36671658bd999ec4f6a8cb471498d47b3f04c1ca303b0a3af796536d9a95e23`다. DB 압축 75,133,150바이트, 표제어 11,244개, 뜻 16,085개, 근거 40,176개를 확인했다.

- SQLite `PRAGMA integrity_check` 통과, 전체 41개 표의 목록·행 수 대조 완료.
- `explain_cache`·`lookups`·`reader_prefs` 3개 표는 실제 DB에 없음.
- 다운로드 중 generation 변경 없음. 생산자 완료 manifest가 없어 같은 행 수인 다른 업로드의 혼합 가능성까지 증명하지는 못함.
- 로컬 PostgreSQL 이관에서 41개 표 대조 완료. `news` 51,632개 중 기존 기본키 길이 정책으로 6개 제외, 나머지 51,626개 일치. 다른 표의 제외·건수 차이 없음. `terms.diffusion` 723개 보정, 별칭 599개 재구축. 원본에만 있는 미지원 표 없음.
- 사용자 표 3개는 이관 후 모두 0행. 검증은 Compose DB의 임시 스키마에서 실행하고 연결 종료 시 제거. 운영 Cloud SQL에는 쓰지 않음.

`manifests/audit-v5-baseline.json`에는 기존 감사관 SFT·holdout 원본 generation과 해시를 기록했다. 약 1.45MB만 내려받고 DVC 로컬 캐시에 등록했다. GCS의 57GB 전체 복제는 하지 않았다.

| 자료 | 행 수 | SHA-256 |
| --- | --- | --- |
| `audit_sft_v5.jsonl` | 371 | `7f46275e4268501b1747c084eb37945c3342098ba487b397b448f7e397196c6a` |
| `audit_holdout_sft.jsonl` | 20 | `1e4621a962bdb3e9fd30048762c570247d84189aba4a961e89f88636288a22f3` |

SFT는 train 319행·test 32행·test2 20행이다. 학습 표제어 276개와 평가 표제어 52개는 겹치지 않으며, holdout과 학습 표제어도 겹치지 않는다. 그러나 **test2와 holdout의 표제어 20개는 모두 겹친다.** 독립 사람 평가셋으로 승격하지 않는다. 출처 단위 겹침, 사람 정답 여부, 최신 DB와 학습셋의 생성 계보는 아직 확인하지 않았다.

## GCP 확인

| 항목 | 읽기 전용 확인 결과 | 실행 전에 할 일 |
| --- | --- | --- |
| 프로젝트 | `stunning-crane-508614-c1`, 번호 `266542883304` | 생성 자원과 비용 상한 확정 |
| 공유 버킷 | 같은 프로젝트, `ASIA-NORTHEAST1`, uniform bucket-level access, public access prevention `enforced` | 연구·운영 경로별 실제 IAM 경계 구성 |
| 버킷 보존 | versioning 꺼짐, lifecycle 규칙 없음, soft delete 7일 | 사용 중인 snapshot·DVC·release의 보존 정책 확정 |
| 기존 IAM | 프로젝트 단위 legacy owner/reader 바인딩 | 팀원·업로더·GPU·Job의 최소 권한 검증 |
| Cloud SQL | `trend-project`, PostgreSQL 18, `RUNNABLE`, `db-perf-optimized-N-8`, 도쿄 | 인수·사양·서비스 DB 역할 확정 |
| Cloud SQL 보호 | 자동 백업·PITR·삭제 보호 꺼짐, 공개 IP 사용, private network 미설정 | Plan 05·13과 함께 보호·접속·복원 정책 결정 |
| Compute API | 비활성 | 사용자 확인 후 활성화, GPU quota·zone 조회 |
| 개발 인증 | `gcloud` 로그인으로 읽기 가능, ADC 미설정 | ADC 로그인과 Compose의 읽기 전용 인증 mount |

현재 계정에 대해 `testIamPermissions`로 아래 권한을 확인했다. 추가 권한을 요청하거나 IAM을 변경하지 않았다.

- 프로젝트에서 `serviceusage.services.enable`, `compute.regions.get`, `compute.instances.create`, `compute.networks.create`, `iam.serviceAccounts.create`, `resourcemanager.projects.setIamPolicy`, `run.services.create`, `secretmanager.secrets.create`, `cloudsql.instances.update` 모두 허용.
- 공유 버킷에서 `storage.objects.get/create/delete`, `storage.managedFolders.create/setIamPolicy` 허용.

이는 배포자의 현재 권한 확인이며, 향후 런타임 서비스 계정의 권한 분리를 구현했다는 뜻은 아니다. GPU quota나 실제 공급도 보증하지 않는다. GCP MCP는 필수가 아니며 설치된 `gcloud`와 ADC·서비스 계정으로 진행할 수 있다. Kaggle CLI 2.2.4를 루트 lockfile에 고정했고 사용자가 OAuth 로그인을 완료했다. 이메일·account number·키·토큰은 저장소에 넣지 않는다.

### Kaggle 실제 확인

[onzlchoi/ai-builder-cup-gemma](https://www.kaggle.com/code/onzlchoi/ai-builder-cup-gemma)를 `jseanj` 인증으로 읽었다. 비공개, GPU 활성·`NvidiaTeslaT4`, 인터넷 활성, `dataset_sources=[]`, 최근 실행 상태 `COMPLETE`다. 코드 셀 11개를 포함한 19셀 Notebook이며 **리스크 분류 추론 실험**이다. CSV와 환경 명세를 입력으로 받아 Ollama 추론 결과를 JSON 체크포인트에 저장하지만 QLoRA·optimizer·scheduler 학습 재개는 없다. 실행 완료 상태만으로 GPU 추론·품질 성공이라고 판단하지 않는다. 로컬 risk Notebook과 코드 셀은 일치하고 첫 안내 Markdown 셀만 다르며 덮어쓰지 않았다.

`manifests/kaggle-context.json`에 소스 해시와 읽은 설정을 기록했다. 공동 작업 쓰기 권한은 시험하지 않았다. 검증한 v5 파일 2개·manifest·평가 제한 안내만 담은 `artifacts/kaggle/audit-v5-inputs.zip`을 준비했으며, 비공개 Dataset 업로드·Notebook push·GPU 실행은 하지 않았다. 이 SFT 자료는 CSV 기반 기존 Notebook에 그대로 붙여도 학습되지 않으므로 별도 감사관 학습 Notebook이 필요하다.

## 비용 검토안

사용자는 **예산 미정, 비용안부터 준비**를 선택했다. 따라서 비용 승인·Compute API 활성화·GCS 쓰기·VM 생성·실제 모델 호출·배포를 실행하지 않았다.

권장 시작은 L4 후보의 **2시간 검증 세션 1회**다. 실제 추론·형식·VRAM을 측정한 뒤 일일 가동 시간을 정한다. 월간 상시 GPU부터 시작하지 않는다. 아래 **$1.50/시간은 예산 편성용 가정이며 도쿄 견적이 아니다.** 도쿄 SKU와 zone·quota를 확인한 뒤 실제 승인안을 확정한다.

| GPU 가동안 | 가동 시간 | GPU·VM 예산 가정 |
| --- | --- | --- |
| 최초 검증 | 2시간 | $3 |
| 일일 2시간 | 30일 × 2시간 = 60시간 | $90/월 |
| 일일 4시간 | 30일 × 4시간 = 120시간 | $180/월 |
| 데모 주간 상시 | 7일 × 24시간 = 168시간 | $252/주 |
| 월 상시 | 30일 × 24시간 = 720시간 | $1,080/월 |

[공식 가속기 가격표](https://cloud.google.com/products/compute/pricing/accelerator-optimized)의 기본 지역 표에서 `g2-standard-8` 주문형 $0.853624312/시간을 확인했지만 도쿄 선택 가격은 아니다. 위 가정은 지역 차이를 포함해 비용안을 검토하기 위한 값이며 실제 가격 상한을 보장하지 않는다. VM이 `RUNNING`이면 요청이 없어도 과금되므로 종료 예약을 따로 구현해야 한다([VM 과금](https://cloud.google.com/products/compute/pricing)).

총비용에는 아래 항목을 더한다. 현재 값이 정해지지 않은 항목은 0으로 합산하지 않는다.

| 비용 항목 | 산정 입력과 결정 |
| --- | --- |
| 모델·부트 디스크 | 모델 200GB 후보 + 부트 디스크, VM 중지 중에도 저장 비용 |
| Cloud SQL | 현재 N-8의 체험 종료 후 SKU, 축소/이전 결정, 백업·PITR·저장 공간 |
| 웹/API/Job | min instances 0 후보, max API instances 2 후보, CPU·메모리·요청 시간·작업 예약 |
| GCS | 원본 53GiB 이상, 고정 snapshot·선택 DVC·모델·백업·soft delete 사본, Kaggle 전송 |
| NAT | 필요할 때만 사용. IP 유지 720시간이면 $3.60 + VM 할당 시간당 $0.0014 + 처리 GiB당 $0.045, 인터넷 전송 별도 |
| Gemini | 승인 모델·입출력 토큰 단가·요청 상한. 현재 기본 mock는 유료 호출 없음 |
| 빌드·감시·레지스트리 | 빌드 분·이미지 보존량·로그량·예약 작업 |

NAT 계산은 [공식 가격표](https://cloud.google.com/nat/pricing) 기준이다. [Cloud Run](https://cloud.google.com/run/pricing)과 [GCS](https://cloud.google.com/storage/pricing)는 지역·실사용량·무료 할당량에 따라 계산한다. 기존 Cloud SQL 체험은 실제 콘솔 종료 시각과 Plan 13의 사양 결정을 먼저 확인한다. 환율·세금·크레딧은 이 표에 반영하지 않았다.

## 검증 결과

- 새 도구 테스트 20개 통과. SHA/CRC 변조·행 수 불일치·사용자 표·경로 탈출·다운로드 중 변경·manifest 이전 실패·고정 generation 읽기 거부/허용을 검증.
- 로컬 remote에서 독립 DVC 환경 2개의 같은 해시·선택 pull·과거판 복원 검증. 합성 자료 테스트이며 실제 팀원 Kaggle 재현과 구분.
- `docker compose run --rm --build check` 통과. API 테스트 306개, 기존 배포 검사 9개, relay 테스트 10개, 프론트 lint·build 포함.
- `docker compose run --rm --build e2e` 36개 통과. 기본 sample/mock 흐름이며 staging 실데이터·실제 모델 검증이 아님.
- `docker compose run --rm infra-check`의 `terraform fmt -check`·`validate` 통과. 이번 작업에서 Terraform 자원 변경·apply 없음.

## 남은 작업과 다음 실행 단위

현재 완료 범위는 인수/DVC 도구, 사용자 자료 제외 이관 검증, 비공개 Dataset 전달, 실제 Gemma의 짧은 학습·체크포인트·다음 버전 재개다. 전체 Plan 17 완료와 구분한다.

1. **자원·비용 결정** – GPU zone/quota·가동 시간·지출 상한, Cloud SQL 인수·사양·백업 정책, 웹/API 동시성·timeout·인스턴스 상한과 실행 주체를 확정한다. GCP 자원 생성·배포는 사용자 확인 후 실행한다.
2. **데이터 고정·팀 공유** – shared bucket의 실제 IAM 경계와 보존 정책, 생산자 완료 manifest를 구성한다. snapshot과 선택 DVC 대상의 GCS 게시/push, 비공개 Dataset의 팀원 공유, 팀원 두 명의 동일 Git/DVC 해시·과거판·학습 재개를 확인한다. 자동 latest 업로드를 운영 DB 덮어쓰기로 연결하지 않는다.
3. **전체 학습·독립 평가** – 사람 정답과 용어/출처 단위로 겹치지 않는 평가셋을 준비한다. 현재 test2와 holdout 20개 중복을 해소하고 원본 기본 모델 revision/가중치 계보를 확인한다. 전체 학습 후 기본 모델·기존 v5·새 후보를 품질·오탐/누락·형식·속도·VRAM으로 비교하고 사람 승인으로 모델 사용 범위를 정한다.
4. **API·DB·GPU 기반** – Terraform의 VPC·IAM·secret metadata, 기존 Cloud SQL staging 이관·역할 분리·백업/복원, 비공개 Cloud Run API를 구현한다. GCE GPU·고정 runtime·인증 gateway와 실제 readiness·전체 동시성·deadline·종료 예약을 구성하고 승인 모델만 서빙한다.
5. **웹 연결** – 별도 Cloud Run 웹과 공통 Google ID token fetch를 구현한다. 로그인·검수 권한, 읽기/쓰기/스트리밍·취소, 사진 한도·MIME, staging의 production 접근 거부를 실제 API 모드에서 검증한다.
6. **게시·운영** – 승인 배치 migration·트랜잭션·중복/이전 버전 충돌·사람 결정 보호를 구현한다. publication 기반 신선도, 게시/유지보수/백업 Job·Scheduler·Monitoring·Discord 경보, GPU/PC 중단·복원·보존 정리를 검증한다.
7. **배포·품질·데모** – 웹/API 이미지·DB 게시 ID·모델·snapshot·평가를 묶는 release와 복구 절차를 구현한다. Plan 05·17의 조건이 충족되면 승인받은 release/gcp 배포를 실행하고 실제 Gemini/Gemma 호출, Plan 09 독립 품질 결과·데모 3개·비용을 기록한다. 기존 builder-cup은 새 운영본과 복구 확인까지 유지한다.

다음 우선순위는 **데이터 고정·팀 재현과 독립 평가셋 확보**다. 웹/API·DB 인프라 코드 준비는 병행할 수 있다. 전체 학습이나 운영 모델 승격 전에 지금의 모델 판정 평가 자료를 사람 정답으로 취급하지 않는다.

## 10-02 다음 단계 실행

`models/kaggle/audit/`에 학습 전용 pyproject/lockfile·`train.py`·`prepare.py`·검증 6개를 추가했다. 기존 서버 학습 스크립트와 리스크 Notebook은 수정하지 않았다. 별도 `docker compose run --rm --build audit-check`를 CI에 연결했다. CPU에서 2단계 중단→4단계 재개와 연속 4단계의 최종 어댑터·optimizer tensor·scheduler 상태가 정확히 일치했다. 실제 v5 입력 319행의 토큰 길이도 확인했다. 이는 CUDA/Gemma 학습 완료와 구분한다.

[비공개 Dataset](https://www.kaggle.com/datasets/jseanj/trend-audit-v5-baseline)을 생성했고 `isPrivate=true`, Dataset ID `12317109`를 확인했다. 내려받은 입력을 원본 manifest의 SHA-256·행 수·분할과 대조해 통과했다. 자료와 학습 runtime 외에 DB·인증·모델 가중치는 업로드하지 않았다. 팀원 공유 권한은 아직 추가하지 않았다.

[smoke Notebook](https://www.kaggle.com/code/jseanj/trend-audit-qlora-smoke)의 1판은 ZIP 자동 해제 경로 때문에 실패했다. 실제 입력은 `runtime.zip`이 아니라 `runtime/`였으며, `prepare.py`를 bundle/파일별 SHA-256 검증으로 수정했다. 2판은 uv bootstrap의 외부 DNS 해석에서 실패했다. 3판은 연결 진단 전용으로 실행해 `COMPLETE`를 확인했다. **학습 성공 상태가 아니다.**

진단 결과는 Python 3.12.13, 설치된 PyTorch `2.10.0+cpu`, CUDA 비활성이며 `files.pythonhosted.org`·`pypi.org`·`huggingface.co`·`google.com` 모두 DNS `gaierror`였다. API로 읽은 설정은 GPU·Internet 모두 true지만 실제 실행 환경을 보증하지 않는다. CPU PyTorch만으로 물리 GPU가 없다고 단정하지는 않는다. 사용자에게 계정 전화번호 인증과 Notebook Settings의 GPU T4·Internet 사용 가능 상태를 확인하도록 요청했다. 같은 차단 상태에서 학습을 반복 실행하지 않는다.

현재 학습 코드·수정한 Notebook 패키지는 `artifacts/kaggle/audit-v4/`, 계약/실측 정보는 `manifests/gemma-audit-training-profile.json`, 절차는 [Kaggle 감사관 학습](../../개발환경/Kaggle-감사관-학습.md)에 있다. 기본 모델은 현재 확인한 revision을 고정한 새 기준선이며 과거 어댑터 계보를 소급 확정하지 않았다. 모든 실험은 `promotion_eligible=false`다. 최종 코드에서 `check`와 별도 `audit-check`는 통과했으며 기존 E2E 36개·Terraform 통과 기록은 앞 단계와 같다.

### Codex 재시작 후 연결 재확인

로컬에서 네 호스트의 DNS·HTTPS를 다시 확인했다. `pypi.org`·`huggingface.co`·`google.com`은 200이며 `files.pythonhosted.org`의 실제 uv 설치 wheel도 200이다. 설치 파일 호스트의 루트 경로 404는 DNS/HTTPS 실패가 아니다.

smoke 4판은 네 호스트의 DNS·HTTPS와 `nvidia-smi`를 확인하는 진단 전용이다. 실행 상태는 `COMPLETE`지만 네 호스트 모두 DNS `gaierror`·HTTPS `URLError`이며, PyTorch는 CPU 빌드·CUDA 비활성, `nvidia-smi` 실행 파일도 없다. 실학습은 진행하지 않았다.

사용자가 열어 둔 Chrome의 Notebook을 읽어 원인을 확인했다. Session options의 **Internet off가 비활성화**돼 있고, GPU/인터넷 사용에 **Get phone verified** 안내가 표시된다. 안내를 열면 전화번호·CAPTCHA·문자 인증을 요구한다. 따라서 현재 차단 원인은 Kaggle 계정의 전화번호 인증 전 기능 제한이다. API 요청/metadata의 GPU·Internet true는 실제 사용 가능 상태를 증명하지 않는다.

전화번호나 인증 코드는 입력·저장하지 않았고, CAPTCHA도 수행하지 않았다. Chrome에 인증 창을 남겼다. 사용자가 직접 인증한 뒤 Internet on·GPU T4 사용 가능 상태를 확인하고 새 세션에서 연결 진단과 실제 학습을 이어간다. Codex 재시작이나 로컬 브라우저에서 사이트 접속만으로 Kaggle 실행 환경의 제한은 해제되지 않는다.

### 전화번호 인증 완료 후 GPU 실측

사용자가 휴대전화 인증을 완료한 뒤 smoke 5판의 진단에서 네 호스트 DNS가 정상으로 바뀌었다. PyPI·Hugging Face·Google HTTPS는 200이고 파일 호스트 루트는 404 응답이다. 실제 uv wheel 주소는 200이다. CUDA 활성과 Tesla T4 15,360MiB 두 장·드라이버 580.178.04를 확인했다. 계정 제한은 해제됐으며 GCP 자원은 생성하지 않았다.

smoke 6판에서 실제 Gemma 12B 가중치 로딩과 첫 추론 2개가 완료됐다. `ok/fix` 판정 2개를 파싱했고 모델 판정 정답 대비 정확도는 0.5였다. 2개 표본의 smoke 결과이며 사람 평가나 품질 승격 근거가 아니다. 학습 첫 forward의 손실 계산에서 메모리가 부족했다. 7판 진단으로 `ForCausalLMLoss`의 `logits.float()`에서 추가 1.39GiB를 확보하지 못한 것을 확인했다. GPU 용량 14.56GiB, 가용 약 473MiB였다.

`completion_trainer`는 정답 토큰 위치의 logits만 계산하고 같은 causal masked loss를 사용한다. CPU에서 전체 logits 방식과 손실·gradient 일치를 검증했다. 입력·정답은 자르지 않는다. 8판에서 메모리 부족은 해소됐지만 FP16 gradient가 NaN이어서 optimizer 업데이트가 모두 건너뛰어졌다. 스케일은 65,536에서 32,768·16,384로 감소했고 checkpoint 1·2의 optimizer state가 모두 비어 있었다. `COMPLETE`·`global_step=2`를 학습 성공으로 인정하지 않았다.

BF16 지원은 에뮬레이션을 포함해 확인하고, 한 GPU만 노출해 batch 1을 유지하도록 수정했다. NaN/Infinity 손실·gradient에서 checkpoint 저장 전에 중단하고, 실제 optimizer update 수가 global step과 같아야 결과를 저장한다. FP16 fallback에서는 scaler 파일도 재개 필수 상태다. 관련 CPU·Compose audit 테스트 9개와 기존 앱 검사가 통과했다. Dataset의 이전 버전은 보존했고 수정한 런타임을 새 비공개 버전으로 올렸다. 현재 9판에서 실제 학습·저장·재개를 검증 중이다.

### 실제 학습·재개 smoke 완료

smoke 9판과 [재개 Notebook 1판](https://www.kaggle.com/code/jseanj/trend-audit-qlora-resume)이 모두 `COMPLETE`이며 실제 optimizer 상태로 검증했다. 기본 모델은 고정한 Gemma 12B revision, 4bit NF4·LoRA r/alpha 16, BF16, 한 개의 visible T4 GPU, batch 1·누적 4, train 8행·test 2행이다.

| 검증 | 중단 실행 | 재개 실행 |
| --- | --- | --- |
| Notebook | `jseanj/trend-audit-qlora-smoke`, 9판 | `jseanj/trend-audit-qlora-resume`, 1판 |
| global step / 실제 optimizer update | 2 / 2 | 4 / 4 |
| 시작 체크포인트 | 새 기준선 | checkpoint-2 |
| 학습 시간 | 193.152초 | 207.797초 |
| 최대 VRAM | 12.9501GiB | 12.9626GiB |
| optimizer parameter state | 656개, 모두 step 2 | 656개, 모두 step 4 |
| 숫자 상태 | loss·gradient·optimizer tensor 모두 유한 | loss·gradient·optimizer·adapter tensor 모두 유한 |

입력·모델·프롬프트·코드·lockfile·라이브러리·학습 옵션의 `run-contract.json`이 두 실행에서 같았다. 필수 adapter/optimizer/scheduler/RNG/trainer state 파일도 확인했다. 재개 후 어댑터 SHA-256은 중단 실행의 `65d22de42d1ed1497703d22d89491065f95eb8d83ceb5bd55d7da745eb33b286`에서 `825a3aebed1531d0a1355c69e7aaa492967b395a32bf66bf4528df451c5ff676`으로 바뀌었다. `resumed_from_step=2`, `optimizer_updates=4`와 실제 저장 tensor를 대조했다.

근거 manifest는 `manifests/gemma-audit-training-smoke.json`이다. 로컬 상태 파일은 Git 제외 `artifacts/kaggle/audit-smoke-v9-weights/`와 `artifacts/kaggle/audit-resume-v1-output/`에 보관했다. 이번 단계는 실제 짧은 학습·저장·다음 버전 재개 경로의 검증이다. 평가 2개는 모델 판정 정답이며, 기본 모델·2단계·4단계 모두 정확도 0.5였다. 독립 사람 평가나 품질 개선을 입증하지 않았고 모든 후보는 `promotion_eligible=false`로 유지한다. 전체 학습·팀원 두 명 재현·독립 평가·GCE 서빙·운영 배포는 남았다.


### 독립 사람 평가 후보·비교 도구 준비

[검토 절차](../../개발환경/감사관-독립-평가.md)와 `scripts/prepare_audit_review.py`·`models/kaggle/audit/quality.py`를 추가했다. 실제 인수 DB에서 후보 20건·11개 언어·발췌 24개를 추출했다. 기존 자료의 표제어 328개·별칭·관련 출처 2,792개와 후보 간 중복을 제외했으며 원본 입력 해시와 SQLite 무결성을 검증했다. 자동 정답은 넣지 않았다. 상세 입력은 Git 제외 로컬에 있고, 추적 가능한 집계는 `manifests/audit-human-review-preparation.json`에 있다.

출처 목록은 과거 학습 자료의 모든 실제 출처를 자동 증명하지 못하므로 담당자의 명시적 확인이 필요하다. 사람 판정·이유·검토자·시각이 있고, 두 클래스가 모두 있는 확정 판정 20건 이상이어야 봉인한다. 이후 동일 모델 계보·평가셋·추론 계약으로 기본 모델과 어댑터를 비교한다. JSON 형식 실패도 평가 분모와 미탐에 포함하며, 개선 결과는 승인 후보로만 추천한다. `promotion_eligible=false`를 유지한다.

이번 단계의 완료 범위는 후보 생성과 평가 경로의 자동 검증이다. 실제 사람 정답·Gemma 독립 품질 평가·전체 학습·운영 승격은 아직 완료되지 않았다.

검증 결과는 `check`의 데이터 20개·API 306개·배포/검토 13개·알림 10개 테스트와 웹 lint/build 통과, `audit-check` 40개 통과다. 이 중 새 검토 내보내기 테스트는 4개다. 실제 후보를 별도 경로에 재생성해 동일 해시를 확인했고 신규 Python lint도 통과했다. 테스트의 합성 판정 점수는 실제 모델 품질로 보고하지 않는다. UI·인프라는 바꾸지 않아 이번 단계에서 E2E·Terraform 검사는 다시 실행하지 않았다.


### Cloud Run 웹 → API 인증 코드 준비

데이터 출처 확인 책임자는 아직 미지정이다. 기존 SFT 생성 또는 원본 출처 이력을 확인할 수 있는 팀원이 이 확인을 맡아야 하며 GCS 경로명·Kaggle Notebook 소유자만으로 담당자를 확정하지 않는다. 사람 정답 판정·출처 확인은 대기 상태로 유지한다.

그와 독립적으로 5단계의 웹 서버 인증 연결을 구현했다. 읽기·로그인·설정·검수·사진 업로드·생성·질문 스트리밍을 공통 API fetch로 모았다. Google 모드에서 고정 메타데이터 서버의 ID token을 만료 전에 갱신·공유하고, 기존 사용자 권한 헤더·본문·Next 캐시 옵션·취소 신호를 유지한다. 설정 오류·발급 실패·외부 origin·redirect에서는 인증 없는 호출을 거부한다. 상세 설정은 [Cloud Run 웹 API 인증](../../개발환경/Cloud-Run-웹-API-인증.md)에 있다.

Terraform apply·IAM 변경·서비스 생성·release/gcp 배포는 실행하지 않았다. 실제 Cloud Run 토큰·API 권한·staging 분리·GPU 연결은 아직 검증되지 않았으며 5단계 전체 완료로 표시하지 않는다.

검증은 `check`의 기존 Python 테스트 349개와 웹 transport 테스트 13개, 웹 lint/build 통과다. `e2e`는 검색 서버/브라우저 경계 회귀 1개를 추가해 37개 통과했다. 최초 빌드에서 확인한 검색 모듈의 클라이언트 import 경로는 서버 로더 분리 후 같은 빌드로 재검증했다. 모델 품질·Google IAM·GPU 성공 근거로 이 로컬 결과를 사용하지 않는다.


### 10-03 네트워크·IAM 기반과 GPU gateway 구현

`infra/gcp/hybrid`에 기존 운영 state와 분리된 VPC·API/GPU 서브넷·환경별 SA·8443/IAP ingress·gateway secret metadata·최소 역할을 정의했다. 기본값은 비활성으로 자원을 만들지 않는다. default/staging/production의 mock plan으로 비활성·접근 범위·환경 분리를 검증한다. 실제 자원 생성·IAM 변경은 하지 않았다. 일반 provider plan은 로컬 ADC가 없어 실행되지 않았으며 mock plan 검증과 구분한다.

`models/serving`의 독립 lockfile·TLS image·gateway는 고정 Ollama 모델만 받는다. 실제 짧은 추론과 resident manifest digest·양수 VRAM을 준비 조건으로 사용하고, bearer 인증·입출력 한도·한 슬롯·deadline·연결 중단·재검증 격리·중복 프로세스 잠금을 구현했다. 모델 관리 API는 노출하지 않는다. 상세 조건은 [GPU gateway·인프라 기반](../../개발환경/GPU-gateway-인프라-기반.md)에 있다.

이 단계는 네트워크/IAM 기반과 제한된 추론 경로의 코드·로컬 검증이다. GCE VM/디스크·모델 release·설치/자동 종료·API adapter·Cloud Run 서비스·기존 Cloud SQL 보호·운영 egress/TLS/IAM 연결은 아직 남았다. 실제 GPU readiness·모델 품질·운영 인증 성공을 합성 테스트로 주장하지 않는다.

검증은 gateway Compose 테스트 18개·lint, 기존/새 Terraform fmt·validate와 mock plan 3개, gateway image build, 합성 인증서의 실제 TLS 검증·비인가 `/ready` 401, 앱 `check` 통과다. Gateway lockfile 단독 OSV 검사에서 취약점은 발견되지 않았다. 전체 OSV 검사는 수정하지 않은 기존 웹/API lockfile의 14건(critical 1·high 7·medium 6)으로 실패했다. 기존 의존성 보안 수정은 배포 전 해소해야 할 별도 차단 항목이며 이번 진행 커밋을 운영 배포 승인으로 사용하지 않는다.


### 10-03 GPU VM·모델 설치·API 연결 코드 추가

선택 GPU 입력이 있을 때만 L4 1장·별도 모델 디스크·예약 내부 IP·GCE 2시간 STOP을 정의했다. 고정 boot image의 설치기는 승인 release와 객체 generation/해시·GGUF·Modelfile을 검사하고, 준비된 image에서 loopback Ollama·TLS gateway를 시작한다. 새 빈 디스크 초기화는 명시한 옵션이 있어야 하며 기존 데이터 signature를 덮어쓰지 않는다. 비밀값은 metadata/state·명령에 넣지 않는다.

API에는 별도 허용 flag·CA·token·고정 모델/digest 검증을 추가하고 기존 텍스트/구조화 호출과 감사관 준비 검사에 연결했다. Gateway가 선택된 경우 미지원 기능과 실패를 직접 Ollama로 우회하지 않는다. 동기 worker 호출의 즉시 취소·vision/tool/stream 경로는 아직 지원하지 않는다. 상세 조건은 [GPU VM 배포 계약](../../개발환경/GPU-VM-배포-계약.md)에 있다.

실제 image 제작·GCP 등록·모델 승인·TLS/secret version 준비·quota/비용 승인·VM 생성·종료·Cloud Run 연결은 실행하지 않았다. 기존 전체 보안 검사 실패도 배포 차단 항목으로 유지한다.


### 10-03 Cloud SQL 원격 현황과 복원 리허설

원격 `trend-project`를 읽기 전용으로 조회했다. 자동 백업·PITR·삭제 보호 꺼짐, 백업 0건, 공개 IP, DB는 기본 `postgres`만, 사용자는 기본 `postgres`만 있다. Cloud Monitoring 디스크 사용량 약 100MB·`postgres` 연결 0으로 보존할 앱 데이터는 없다고 판단했다. 그래서 원격 DB 내용을 읽기 위한 SQL 인증 정보는 요청하지 않는다. 무료 체험 인스턴스는 최종 백업 외 백업·복원을 지원하지 않으므로 관리형 보호 설정은 유료 전환 후로 미룬다.

`scripts/restore-rehearsal.sh`·`scripts/restore_rehearsal.py`를 추가했다. 별도 Compose 프로젝트의 임시 PostgreSQL 18.6에 snapshot을 `--fresh --skip-user-data`로 이관하고, `pg_dump` custom 형식 사본을 빈 DB에 복원해 표·행 수·내용 checksum·컬럼·제약·색인·sequence를 비교한다. 실제 snapshot에서 41개 표 이관 일치(`news` 6행 정책 제외), 사용자 표 3개 0행, 복원본 48개 표·659,707행·스키마 일치를 확인했다. dump 52.9MB, 이관 15초, dump+복원 8초다. 보고서는 `manifests/restore-rehearsal-20261001T224511-e56b90d.json`이며 행 내용과 접속 정보는 담지 않는다.

유료 전환 직후의 백업·PITR·삭제 보호 변경안, 환경별 DB·사용자·Secret Manager 연결 문자열 기반 staging 연결안은 [Cloud SQL 복원 리허설](../../개발환경/Cloud-SQL-복원-리허설.md)에 정리했다. Cloud SQL 설정 변경·DB/사용자 생성·적재는 실행하지 않았다. Cloud SQL 관리형 백업 복원·실제 소켓 접속·권한 분리 검증이 남았다.

검증은 새 지문 비교 테스트 2개를 포함한 `check` 통과(데이터 20개·API 331개·배포/검토/리허설 15개·알림 10개·웹 transport 13개, 웹 lint/build)와 실제 snapshot 리허설 통과다. UI·Terraform은 바꾸지 않아 E2E·infra-check는 다시 실행하지 않았다.


### 10-03 사용자 결정과 Cloud SQL staging 적재

사용자가 다음을 결정했다. Cloud SQL 새 인스턴스는 공유 코어 소형·월 상한 약 $30으로 하고 Plan 13 일정(10-24 확정, 10-26 실행)을 따른다. staging은 지금 체험 인스턴스에 적재한다. 최초 GPU 검증은 L4 최대 2시간·$10 상한으로 승인했다. 사람 평가와 학습 출처 확인은 팀원 ejchoi에게 요청한다. 백업·PITR은 지금 켜지 않고 10-24 운영 인스턴스 확정 때 다시 판단한다. GPU 검증은 사람 평가를 기다리지 않고 기본 Gemma로 인프라 동작부터 확인한다.

체험 인스턴스에 `trend_staging` DB와 `trend_staging_app` 사용자를 만들고, 연결 문자열을 Secret Manager `trend-staging-database-url`에만 저장했다. 첫 version은 셸 변수 확장 오류로 연결 이름이 잘못 저장돼 폐기하고 비밀번호를 다시 발급해 version 2로 교체했다. `scripts/load-cloud-sql.sh`로 Cloud SQL Auth Proxy를 거쳐 snapshot을 적재했고 41개 표 건수 일치·사용자 표 0행을 확인했다(115초). 보고서는 `manifests/cloud-sql-load-staging-20261001T224511-e56b90d.json`, 절차는 [Cloud SQL 복원 리허설](../../개발환경/Cloud-SQL-복원-리허설.md)에 있다.

GPU 검증은 승인됐지만 [GPU VM 배포 계약](../../개발환경/GPU-VM-배포-계약.md)상 승인 release·준비된 boot image·TLS/token secret version이 먼저 필요하다. 이후 사용자 승인으로 Compute API를 활성화했다. 조직 정책이 없어 자동 생성된 `default` 네트워크와 SSH·RDP·ICMP를 `0.0.0.0/0`에 연 기본 방화벽 규칙 4개는 VM이 없는 상태에서 바로 삭제했다. 현재 프로젝트에 VPC·방화벽 규칙·VM은 없다.

도쿄 `asia-northeast1-a/b/c` 모두 L4를 제공하고 지역 할당량 `NVIDIA_L4_GPUS`는 1이다. 그러나 프로젝트 전체 `GPUS_ALL_REGIONS`가 **0**이라 할당량 증가 승인 전에는 GPU VM을 만들 수 없다. 사용자 승인으로 Cloud Quotas API를 켜고 `GPUS-ALL-REGIONS-per-project`를 1로 요청했으며 즉시 승인돼 현재 값은 1이다. 남은 선행 조건은 준비된 boot image·기본 Gemma 검증용 release·TLS/token secret version이다.


### 10-03 실제 GPU 인프라 검증

기본 Gemma(`gemma4:12b` 텍스트 GGUF)로 boot image·release·TLS/token secret을 만들고 L4 1장의 GPU VM을 Terraform으로 적용했다. 설치 완료, staging CA TLS 검증, 무인증·잘못된 token 401, 모델·digest 일치, 추론 3/3(이후 0.35초), VRAM 7.9GB/23GB를 확인했다. cold start 모델 적재가 gateway deadline 30초를 넘어 첫 `/ready`가 4회 504였고, 이 문제는 운영 전에 고친다. 검증 후 VM·디스크·내부 IP를 삭제했다(GPU 약 8분). 세부 절차와 결과는 [GPU VM 배포 계약](../../개발환경/GPU-VM-배포-계약.md)에 있다. 이 release는 인프라 확인용이며 운영 승인 모델이 아니다.

boot image 빌드는 다섯 번째 실행에서 성공했다. 첫 실행은 실행 중인 스크립트를 수정해 중단됐고, 이후 두 번은 builder 권한을 prefix로 좁히면서 생긴 목록 조회 권한 문제, 한 번은 조건 인자 형식 문제였다. 각 실패 뒤 builder VM·네트워크·권한이 정리된 것을 확인했다.

### 10-03 GPU 준비 지연 수정과 Cloud Run 연결 확인

첫 검증에서 찾은 cold start 문제를 고쳤다. 설치기가 gateway와 같은 요청 옵션으로 모델을 미리 적재한 뒤 gateway를 시작한다. boot image r2로 다시 확인한 결과 `/ready`는 첫 시도 0.42초, 첫 추론은 0.38초였다(수정 전 504 4회·25초).

같은 VM에 대해 trend-api 이미지를 임시 Cloud Run Job으로 실행했다. API SA와 API 서브넷의 Direct VPC egress로 실제 감사관 `local_chat` 경로를 호출해 준비 확인과 `AuditCheck` 구조화 호출 3/3(각 약 2.1초)이 통과했다. 무인증·잘못된 token은 401이었다. 검증 뒤 VM·디스크·내부 IP·Job·임시 권한을 삭제했고 r1 image와 모델 파일도 지웠다(GPU r2 약 10분). 상세는 [GPU VM 배포 계약](../../개발환경/GPU-VM-배포-계약.md)에 있다. 남은 일은 운영 release(사람 평가 후)와 웹·API Cloud Run 서비스 배포다.

### 10-03 TLS 갱신 체계와 staging 웹·API 배포

GPU gateway TLS를 갱신할 수 있게 CA 개인키를 런타임이 읽지 못하는 secret에 보관하고 `scripts/rotate-gpu-tls.sh`를 추가했다. 서버 인증서 재발급까지 실제로 확인했다. 사용자 결정에 따라 staging 웹·API만 Terraform으로 직접 배포했다(GPU 미연결, API mock). 웹은 주소를 아는 사람에게 공개하고 검수는 로그인으로 보호하며, 검수 계정은 사용자 1명이다. API 익명 403, 웹→API→DB 실데이터 표시, `/admin` 로그인 이동을 확인했다. `/dictionary`는 API `/terms`의 N+1 조회가 Cloud SQL 지연과 겹쳐 90초를 넘겨 504이며 다음 수정 대상이다. 상세는 [Cloud Run 서비스 준비](../../개발환경/Cloud-Run-서비스-준비.md)와 [GPU VM 배포 계약](../../개발환경/GPU-VM-배포-계약.md)에 있다.

### 10-03 staging 목록 응답 시간 수정

staging에서 사전 화면 504와 검수 목록 멈춤을 고쳤다. 목록을 만드는 동안 표제어별 행을 표마다 한 번에 읽고(약 10만 번 조회 → 표마다 1번), API 응답을 gzip으로 압축해 Cloud Run 32MiB 한도를 피했다. `/terms` 8.2초, 관리자 전체 목록 10.5초, 검수 목록 1.8초, 웹 사전 첫 요청 9.7초·캐시 후 1.1초를 확인했다. 사용자가 검수 계정 로그인과 관리 화면 접근을 확인했다.

### 10-03 staging 실제 Gemini 연결

사용자 결정에 따라 staging API에서 Vertex AI Gemini를 월 $20 상한으로 켰다. 앱이 실제 토큰 사용량과 공식 단가로 월 금액을 세고 상한 전에 호출을 멈추며, 모든 호출에 출력 상한을 둔다. 데모 흐름(사전에 묻기 3종·밈 추천·카피 생성·카피 검사)이 실제 Gemini로 동작했고 시험 비용은 약 $0.017이었다. 챗봇 도구의 표제어별 조회도 일괄 읽기로 고쳤다. Billing 예산 알림 금액 조정은 API가 거부해 콘솔 작업으로 남았다. 상세는 [Cloud Run 서비스 준비](../../개발환경/Cloud-Run-서비스-준비.md)에 있다.

### 10-04 production 배포와 이전 서비스 정리

사용자 결정(운영 DB는 체험 인스턴스의 분리 DB, Gemini production $15·staging $5, 확인 뒤 `builder-cup` 삭제)에 따라 production 기반·DB·secret·웹/API를 만들고, `release/gcp` 배포 경로를 구현해 실제 push로 배포했다. 후보 검사와 트래픽 전환까지 성공했고 이미지 digest가 release 커밋 빌드와 일치했다. CI가 세 번 실패해(설치기 테스트의 디스크 의존, E2E 첫 컴파일 시간, 웹 `public` 폴더) 각각 고쳤다. 이후 uptime check와 오류 경보를 Trend로 옮기고 `builder-cup` 서비스와 데모 키·전용 계정을 삭제했다. 상세는 [Plan 05](05-trend-cloud-run-deployment.md)와 [Cloud Run 서비스 준비](../../개발환경/Cloud-Run-서비스-준비.md)에 있다.

### 10-04 staging 정리와 사람 판정 수령

공모전 범위에서는 staging이 필요하지 않다는 사용자 판단에 따라 staging 웹·API·DB·앱 secret을 삭제하고 GPU 시험용 기반만 남겼다([Cloud Run 서비스 준비](../../개발환경/Cloud-Run-서비스-준비.md)). ejchoi의 사람 판정 20건(ok 10·fix 10)을 받아 입력 변경 없음·필수 값·시간대를 확인했다. 봉인에 필요한 학습 출처 확인은 응답 해석을 확인하는 중이다.


## 10-07 승인 배치 게시·웹 검수 연결

불변 배치·항목 해시, 실제 검수 계정과 정확한 내용 해시의 승인, 뜻 판/사람 결정 보호, 뜻·파생 출력·캐시의 원자적 게시, 활성 게시 ID·신선도 전환을 로컬 구현했다. 관리자 목록·현재/제안 비교·승인/거절도 연결했다. 별도 임시 PostgreSQL 스키마와 production 이미지의 API 모드에서 비교→승인→별도 게시→공개 조회를 확인했다. Cloud Run Job·전용 DB 역할·생산자 배치 포장·운영 migration/게시·운영 복구 검증은 남으며, 이 기록으로 계획 전체를 완료 처리하지 않는다. [명령·검증·제한](../../개발환경/승인-배치-게시.md)을 따른다.
