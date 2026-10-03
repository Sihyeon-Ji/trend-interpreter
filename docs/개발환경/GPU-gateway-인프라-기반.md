# GPU gateway와 하이브리드 인프라 기반

## 이번 구현 범위

`infra/gcp/hybrid`는 기존 `infra/gcp`와 별도의 Terraform root다. 기존 builder-cup·공유 버킷·Cloud SQL을 import하거나 변경하지 않는다. 빈 state에서 기본 `enabled=false`이면 새 자원을 선언하지 않는다. 네트워크·서브넷·SA·secret metadata는 `prevent_destroy`로 보호하며, 이미 생성한 state에서 비활성으로 돌리는 것은 안전한 중지 명령이 아니다. 이번 검증은 mock provider의 plan이며 GCP apply·API 활성화·IAM 변경은 실행하지 않았다.

| 기반 | 코드에 정의한 내용 |
| --- | --- |
| 네트워크 | 환경별 custom VPC, API /26·GPU /28 서브넷, Private Google Access |
| 환경 분리 | staging `10.40.*`, production `10.41.*`, 서로 다른 서비스 계정 이름 |
| GPU ingress | 해당 환경의 API 서브넷에서 TLS 8443만 허용, GPU SA 대상 |
| 관리 접속 | [공식 IAP 범위](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding)의 SSH 22만 허용 |
| 실행 주체 | 웹·API·GPU·게시·유지보수·백업 SA 6종 |
| 최소 권한 | API의 Vertex·Cloud SQL 접속 역할, API/GPU만 gateway secret 읽기 |
| 비밀값 | Secret Manager metadata만 생성 대상으로 정의. 값·version은 Terraform 밖에서 관리 |

이 기반에는 **GCE VM·디스크·Cloud Run 서비스·Cloud SQL 변경·NAT·예약 종료·게시 Job이 아직 없다**. 서브넷 허용은 API SA 신원 검증을 대체하지 않는다. 해당 서브넷에 배치할 실행 주체와 `actAs` 권한도 배포 단계에서 제한해야 한다. GPU의 모델 객체 읽기 권한·웹의 해당 API invoke 권한·Job의 DB 역할은 대상 자원이 확정된 뒤 부여한다. 현재 서브넷의 기본 egress를 운영 제한 정책으로 간주하지 않는다.

실제 적용 전에 사용자 비용 승인, 기존 네트워크 주소 충돌 확인, 환경별 원격 state 분리, 생성·변경 목록 검토가 필요하다. 현재 root는 로컬 backend라서 같은 작업 디렉터리를 staging/production에 번갈아 apply하면 안 된다. 승인된 배포 설정에서 별도 backend를 구성한 뒤 사용한다. `enabled=true`는 승인 증거가 아니다.

## Gateway의 호출 계약

`models/serving`은 API·학습 프로젝트와 독립된 uv 프로젝트다. 승인된 단일 Ollama 모델만 호출하고 요청에서 모델·도구·다운로드 옵션을 선택할 수 없다. Ollama [chat API](https://docs.ollama.com/api/chat)는 loopback `127.0.0.1:11434`에서만 사용한다. 프록시 환경 변수·redirect를 사용하지 않는다.

| 경로 | 인증·동작 |
| --- | --- |
| `GET /health` | 프로세스 생존만 반환. GPU 준비 상태가 아님 |
| `GET /ready` | bearer 인증 후 짧은 실제 추론, resident 모델의 digest·양수 VRAM 확인 |
| `POST /v1/generate` | bearer 인증, 준비된 모델에 `prompt`·`max_tokens`만 전달 |

준비 검사는 Ollama manifest digest 기준이며 GGUF 파일 SHA-256과 같은 값이 아니다. 실제 release에는 두 해시와 원본 모델 계보를 별도로 고정한다. `/ready` 성공은 GPU 추론 준비 근거이며 독립 품질 평가나 모델 승격 승인이 아니다.

본문 최대 64KiB, prompt 최대 12,000자, 출력 본문 최대 64KiB, 생성 최대 512토큰·기본 256토큰, context 4,096, thinking 비활성·temperature 0을 고정한다. 문자 한도는 토큰 한도가 아니므로 실제 작업 프롬프트가 context에 들어가는지는 모델별 평가에서 따로 검증해야 한다. gateway는 JSON 정답 판정을 대신하지 않는 제한된 텍스트 추론 경로다. 질문·추천·감사관별 API adapter와 출력 검증 연결은 후속 작업이다.

추론·준비 검사는 하나의 슬롯을 공유하며 대기열 없이 초과 요청을 429로 거부한다. 기본 전체 작업 deadline은 30초다. timeout은 504, 연결 중단은 499로 처리하고 backend 요청을 닫는다. **연결을 닫았다고 GPU 계산 종료를 보증하지 않는다.** 이후 준비 상태를 해제해 새 생성 요청을 막고, 실제 준비 검사 성공 뒤에만 다시 허용한다.

## 런타임 조건

운영 Dockerfile은 TLS 인증서·키가 없으면 시작하지 않으며 8443·worker 1·비특권 UID 10001을 사용한다. 실제 VM에서는 다음 조건을 모두 적용한다.

- Ollama와 gateway는 같은 Linux VM에서 실행하며 Ollama는 loopback에만 바인딩한다. [Ollama 설정](https://docs.ollama.com/faq)에 따라 `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NO_CLOUD=1`을 사용한다.
- gateway 컨테이너는 host network를 사용한다. VM 외부 IP와 Ollama 11434의 외부 허용 규칙을 만들지 않는다. gateway TLS 인증서는 내부 주소의 SAN을 포함하고 API client는 해당 CA를 검증해야 한다. 검증을 끄는 client를 사용하지 않는다.
- 모든 gateway 인스턴스는 호스트의 동일한 `/run/trend-gateway` 디렉터리를 공유 mount한다. UID 10001이 쓸 수 있게 준비하며 `owner.lock`의 프로세스 잠금으로 중복 worker를 거부한다. 서로 다른 lock 경로나 mount를 쓰면 전체 동시성 보장이 깨진다.
- `GATEWAY_TOKEN`은 32~256자의 URL-safe 임의 토큰으로 Secret Manager에서 전달한다. `GATEWAY_MODEL`·`GATEWAY_MODEL_DIGEST`는 승인 release의 실제 값을 사용한다. 로그·명령 출력·Terraform state에 토큰을 남기지 않는다.
- 인증서·secret·모델 파일은 image에 포함하지 않고 접근을 제한해 mount한다. VM 생성·드라이버·Ollama 설치·모델 검증 다운로드·TLS 배포·자동 종료는 아직 실행하지 않았다.

## 검증 명령

```bash
docker compose run --rm --build gateway-check
docker compose run --rm infra-check
docker compose run --rm --build check
docker build -f models/serving/Dockerfile -t trend-model-gateway:local models/serving
```

`gateway-check`는 합성 backend로 인증·한도·모델 일치·GPU 준비·동시성·deadline·취소·오류 비노출·프로세스 소유 잠금을 검증한다. 실제 GPU·GGUF·TLS handshake 성공과 구분한다. `infra-check`는 기존 root와 새 root의 fmt/validate 및 새 root의 mock plan을 검사한다. 플랫폼별 provider checksum과 uv lockfile을 Git에 포함한다.

2026-10-03 검증에서 새 gateway 단독 의존성 스캔은 통과했지만 전체 프로젝트 스캔은 기존 웹/API 취약점 14건으로 실패했다. 기존 lockfile은 이번 구현에서 바꾸지 않았다. 운영 배포 전에 패치·도달 가능성 검토가 필요하며, [Next.js advisory](https://github.com/advisories/GHSA-vcvr-r3jv-pc5j)와 [braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)를 포함한다. Braces advisory에는 현재 패치 버전이 없어 빌드 도구 의존 경로의 별도 평가가 필요하다.
