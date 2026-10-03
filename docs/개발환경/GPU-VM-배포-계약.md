# GPU VM 배포·모델 설치 계약

## 코드에 추가한 범위

`infra/gcp/hybrid`의 `gpu` 입력이 `null`이면 VM·모델 디스크·모델 읽기 권한을 만들지 않는다. 기반의 `enabled=true`와 모든 GPU 입력이 있을 때만 다음 구성을 정의한다. 아직 GCP apply나 유료 실행은 하지 않았다.

| 항목 | 정의 |
| --- | --- |
| VM | 명시한 도쿄 zone, `g2-standard-8`, L4 1장 |
| 네트워크 | 외부 IP 없음, GPU 전용 SA·서브넷, staging `10.40.1.4` / production `10.41.1.4`의 예약 내부 IP |
| 디스크 | 모델용 `pd-balanced` 200GB 별도 유지, 부트용 50GB |
| 실행 제한 | GCE `max_run_duration=7200`, `instance_termination_action=STOP`, 자동 재시작 꺼짐 |
| 보호 | VM 삭제 보호, VM·디스크·내부 주소의 `prevent_destroy`, OS Login·프로젝트 SSH 키 차단 |
| 다운로드 권한 | 지정 모델 버킷의 지정 객체 prefix 읽기만, TLS secret 하나의 읽기 권한 |

[공식 최대 실행 시간](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime)은 중지 시작이 지정 시간보다 최대 30초 늦을 수 있다. 실행 시간은 부팅·설치 시간도 포함하며 VM을 다시 시작하면 새 실행 시간이 시작된다. **월 지출 상한이나 하루 시작 횟수 제한을 대신하지 않는다.** VM이 중지돼도 디스크 저장 비용은 남는다.

`gpu`에는 실제 `zone`, 고정 `boot_image`, `release_uri`·`release_generation`·`release_sha256`, `models_bucket`·`models_prefix`, 숫자로 고정한 `tls_secret_version`·`token_version`이 필요하다. `format_model_disk`는 기본 false다. 새 빈 디스크의 첫 초기화에만 true로 지정하며 기존 signature나 다른 파일시스템을 자동으로 덮어쓰지 않는다. 다른 VM·공유 디스크를 이 설치 경로에 연결하지 않는다.

현재는 예산·zone/quota·승인 모델·준비된 image·secret version이 확정되지 않았다. 코드의 synthetic 테스트 값은 운영 입력이 아니다. 실제 적용 전에 비용과 변경 목록을 승인받고 환경별 원격 state를 구성해야 한다.

## 준비된 boot image

`boot_image`는 family/latest가 아닌 특정 image 경로를 사용한다. 운영 image에는 다음을 사전 설치·검증한다. VM의 실행 중 일반 인터넷 설치나 image pull에 의존하지 않는다.

- Linux x86_64, GCE guest agent·OS Login, NVIDIA 드라이버·Container Toolkit, Docker
- Python과 이 커밋의 `models/serving` lockfile을 설치한 `/opt/trend-gateway/bin/python`
- `mountpoint`·`findmnt`·`blkid`·`wipefs`·`mkfs.ext4`·`mount` 도구
- 승인 release가 지정한 Ollama·gateway image digest의 로컬 Docker image

Image 제작·GCP 등록과 실제 드라이버/GPU 검증은 아직 실행하지 않았다. Terraform은 지정 image를 참조하며 이 준비 조건까지 검사하지는 못한다. 실제 배포 전에 확인해야 한다.

## 승인 release

Startup script는 `python -m model_gateway.install`을 실행한다. 설치기는 VM metadata의 `trend-runtime` 설정을 읽고, VM SA의 단기 토큰으로 지정 GCS generation을 내려받는다. release 파일 자체의 SHA-256이 다르면 어떤 모델도 설치하지 않는다.

Release JSON의 필수 값은 다음과 같다.

| 값 | 검증 |
| --- | --- |
| `schema_version` | 1 |
| `approved`·`approved_by`·`approved_at` | true, 실제 승인자, 시간대가 있는 승인 시각 |
| `evaluation_sha256` | 독립 평가 기록 SHA-256 |
| `model`·`model_digest` | 고정된 Ollama 태그와 manifest digest |
| `ollama_image`·`gateway_image` | digest로 고정하고 boot image에 미리 적재한 image |
| `files` | `model.gguf`·`Modelfile` 두 개만 |
| 각 파일 | 지정 prefix의 `uri`, 숫자 `generation`, `sha256`, 정확한 `size` |

모델 파일은 release 해시별 디렉터리에 저장한다. 기존 파일도 다시 해시 검증하고, 새 다운로드는 크기·해시가 맞아야 atomic rename한다. 실패한 다운로드는 가져올 수 있는 최종 파일로 남지 않는다. 디스크의 여유 공간은 import 사본까지 보수적으로 확인한다.

GGUF magic을 검사하고 Modelfile은 `FROM /models/model.gguf`로 시작해야 한다. 추가 FROM·ADAPTER는 거부한다. merged GGUF에 같은 LoRA를 다시 적용하지 않는다. 원본 Modelfile이 다른 FROM을 사용했다면 고정 경로로 재생성·평가한 뒤 승인해야 하며, 기존 v5 결과의 계보를 소급 확정하지 않는다.

이 계약은 승인 증거를 대신 만들지 않는다. 현재 짧은 학습 후보와 사람 판정 전 holdout을 승인 release로 표시하지 않는다.

## 설치·TLS·실패 처리

설치기는 이미 실행 중인 runtime을 중단·덮어쓰지 않는다. 운영 교체는 별도 drain 절차로 수행한다. 중지된 컨테이너만 제거하고, 준비된 image를 `--pull=never`로 시작한다. Ollama는 host loopback·cloud 비활성·parallel 1·loaded model 1로 실행한다.

TLS secret의 숫자 version은 `cert_pem`·`key_pem` JSON을 담는다. Gateway token도 숫자 version으로 읽는다. 인증서/키 쌍을 검증하고 키는 UID 10001의 0400, token env 파일은 root의 0600으로 기록한다. Gateway는 공유 잠금 디렉터리만 쓰기 mount하고 TLS는 별도 read-only mount한다. 인증서 SAN에는 위 예약 내부 IP를 넣으며 API의 별도 CA bundle이 이 인증서를 신뢰해야 한다.

명령 인자·Terraform metadata/state에는 비밀값을 넣지 않는다. 두 runtime의 Docker log driver는 꺼서 프롬프트·생성문·비밀값을 기록하지 않는다. 설치 오류는 종류만 출력하며 시작 중 실패한 runtime은 정리한다. 성공 메시지의 `gpu_readiness=not-verified`는 실제 추론 성공을 의미하지 않는다. 설치 후 인증된 `/ready`와 작업별 품질·VRAM·시간을 따로 확인해야 한다.

## API 연결

`interpreters/gpu_gateway.py`를 기존 `local_chat`의 단일 텍스트·구조화 요청에 연결했다. 감사관의 모델 존재 검사도 gateway readiness를 사용한다.

| 환경 변수 | 의미 |
| --- | --- |
| `GPU_GATEWAY_URL` | 해당 환경 예약 내부 IP의 HTTPS 8443 origin |
| `GPU_GATEWAY_REQUESTS_ENABLED` | 기본 false, 명시적으로 true일 때만 호출 |
| `GPU_GATEWAY_TOKEN` | 해당 환경 gateway token |
| `GPU_GATEWAY_CA_FILE` | API에 mount한 신뢰 CA bundle 경로 |
| `GPU_GATEWAY_MODEL`·`GPU_GATEWAY_MODEL_DIGEST` | 승인 release와 동일한 이름·digest |

감사관 연결 시 `AUDIT_MODEL`을 선택 모델과 맞추고 `AUDIT_OLLAMA_HOST`를 비운다. 감사관 LoRA를 추천·카피·번역에 재사용하지 않는다. 그 작업의 모델 선택·Vertex 호출 정책은 별도로 유지한다.

HTTPS·CA 검증·bearer·고정 release 일치를 검사하고 redirect·환경 프록시를 사용하지 않는다. 미지원 모델·image·host override·tool 요청과 429/503/504 등 실패는 로컬 Ollama로 자동 우회하지 않는다. 기존 기본 설정에서는 gateway를 호출하지 않는다.

현재 연결은 동기 `local_chat` 경로다. API의 worker thread에서 실행 중인 호출을 브라우저 취소만으로 즉시 종료하는 기능은 아직 제공하지 않으며 gateway deadline으로 제한한다. 스트리밍·vision·tool 작업과 전체 API deadline/취소 조립은 후속 구현이다. Cloud Run의 Direct VPC egress·secret/CA mount와 실제 API→VM 연결도 아직 검증되지 않았다.

## 2026-10-03 실제 GPU 인프라 검증

기본 Gemma로 boot image·설치·TLS·인증·GPU 추론 경로를 실제 L4에서 확인했다. **인프라 확인용**이며 품질 평가나 운영 승인 release가 아니다. 범위와 승인 기록은 `manifests/gpu-validation-scope-gemma4-12b-20261003.json`이고, release는 운영 `releases/`와 분리한 `validation/` prefix에 두었다(`promotion_eligible=false`).

| 단계 | 내용 |
| --- | --- |
| 원격 state | `infra/gcp/hybrid`에 GCS backend를 선언하고 `stunning-crane-508614-c1-tfstate`의 `hybrid/staging` prefix를 사용한다. 검사는 기존처럼 `-backend=false`로 실행한다 |
| 기반 | 로컬 `staging.tfvars.json`(`enabled=true`, `environment=staging`)으로 VPC·서브넷·SA 6개·방화벽·gateway token secret을 적용했다(19개 생성) |
| 모델 버킷 | 비공개 `stunning-crane-508614-c1-trend-models`(도쿄, uniform access, public access prevention) |
| gateway image | `models/serving`을 amd64로 빌드해 `builder-cup/trend-model-gateway@sha256:ec7cc38d…`로 push |
| boot image | `scripts/build-gpu-image.sh`가 GPU 없는 임시 builder VM으로 `trend-gpu-gemma4-12b-validation-20261003`을 만든다. 기반은 `ubuntu-accelerator-2404-amd64-with-nvidia-580-v20260925`, Docker 29.1.3·NVIDIA Container Toolkit 1.20.1·Python 3.12.3. 보고서 `manifests/gpu-image-gemma4-12b-validation-20261003.json` |
| 모델 | Ollama 라이브러리 `gemma4:12b`의 텍스트 GGUF(Q4_K_M, 7.38GB)를 레지스트리 SHA-256으로 검증해 올렸다. Modelfile은 `gemma4` renderer·parser를 지정한다. `ollama create` digest `a9e8fc57…`는 두 번의 빌드에서 같았다 |
| secret | `trend-staging-gpu-tls`(SAN `10.40.1.4`, 90일), `trend-staging-gpu-ca`(API용 CA), `trend-staging-gateway-token` version 1 |
| GPU VM | 로컬 `staging-gpu-validation.tfvars.json`으로 적용, 약 3분 만에 설치 완료. tfvars는 저장소 규칙상 Git에서 제외하며 `gpu` 입력값은 위 image·release manifest와 아래 값으로 재구성한다: zone `asia-northeast1-a`, release generation `1791025228844907`, SHA-256 `ae1ac374…4087`, TLS secret version 1, token version 1, `format_model_disk=true` |

builder SA의 버킷 권한은 이번 release의 두 prefix로 제한하고(목록 조회 포함) 스크립트 종료 시 회수한다. 목록 조회는 `objectListPrefix` 조건으로만 허용되므로 조건을 JSON 파일로 넘긴다.

검증은 `scripts/verify-gpu-gateway.sh`로 VM 안에서 IAP SSH를 통해 실행했다. token은 VM 밖으로 나오지 않고 보고서에는 상태·시간·메모리만 남긴다. 결과는 `manifests/gpu-validation-gemma4-12b-20261003.json`이다.

| 항목 | 결과 |
| --- | --- |
| 설치 | `installed: true`, Ollama·gateway 컨테이너 실행 |
| TLS | staging CA로 인증서·IP SAN 검증 통과 |
| 인증 | token 없음·잘못된 token 모두 401 (`/ready`, `/v1/generate`) |
| 준비 | 첫 `/ready` 4회가 30초 deadline으로 504, 5회째 200. 모델·digest 일치 |
| 추론 | 첫 호출 25.4초, 이후 0.35·0.36초. JSON 판정 형식 3/3 |
| GPU | L4 7,938MiB / 23,034MiB 사용, 드라이버 580.178.04 |

발견한 문제와 남은 일은 다음과 같다.

- **cold start가 gateway deadline 30초보다 길다.** 모델 디스크에서 처음 GPU에 올리는 시간이 30초를 넘어 `/ready`가 반복 504가 된다. 준비 확인 전용으로 더 긴 deadline을 두거나, 설치기가 gateway 시작 전에 모델을 미리 올리도록 고쳐야 한다. 준비 직후 첫 추론도 25초가 걸렸다.
- API 서브넷에서의 접속(Cloud Run Direct VPC egress)은 아직 확인하지 않았다. 이번 검증은 VM 내부에서 자기 IP로 호출했다.
- 감사관 품질은 평가하지 않았다. 운영 release는 사람 평가와 승인 뒤 `releases/` prefix로 따로 만든다.

검증 후 사용자 결정에 따라 VM·부트 디스크·모델 디스크·예약 내부 IP를 삭제하고 Terraform state에서 정리했다. GPU 사용은 약 8분이다. boot image(40GB), GCS의 모델 파일, 기반 VPC·SA·secret은 남겨 다시 만들 때 쓴다.

## 검증

```bash
docker compose run --rm --build check
docker compose run --rm --build gateway-check
docker compose run --rm infra-check
```

Synthetic release·GCS 다운로드·host 명령·TLS/API 응답으로 승인·해시·경계·설치 순서·비밀값 비노출·모델 불일치·자동 우회 거부를 검증한다. Mock Terraform plan의 GPU/디스크/STOP 결과는 실제 quota·공급·종료 과금 검증이 아니다. 기존 전체 프로젝트 보안 검사 실패도 운영 배포 전에 해소해야 한다.
