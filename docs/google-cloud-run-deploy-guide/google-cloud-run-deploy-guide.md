## 1. 공개 이미지(Docker Hub/GHCR) 배포

Docker Hub 및 공개 GHCR 이미지는 Cloud Run에서 직접 사용할 수 있습니다. 아래는 HTTP 서버가 8080 포트를 사용한다고 가정한 예시입니다. (80 포트 사용 시 `--port=80`으로 변경)

**배포 명령어**

```bash
PROJECT_ID=stunning-crane-508614-c1
REGION=asia-northeast1
SERVICE=builder-cup-sandbox
IMAGE=docker.io/조직명/이미지명:태그

gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="$IMAGE" \
  --port=8080 \
  --cpu=1 \
  --memory=512Mi \
  --concurrency=10 \
  --min=0 \
  --max=1 \
  --allow-unauthenticated

```

**배포 URL 확인 및 테스트**

```bash
SERVICE_URL=$(gcloud run services describe builder-cup-sandbox \
  --project=stunning-crane-508614-c1 \
  --region=asia-northeast1 \
  --format='value(status.url)')

echo "$SERVICE_URL"
curl --fail --show-error "$SERVICE_URL"

```

## 2. 로컬 Dockerfile 빌드 및 배포

Apple Silicon Mac 환경에서는 반드시 `linux/amd64` 아키텍처로 빌드해야 합니다.

**이미지 빌드 및 푸시**

```bash
PROJECT_ID=stunning-crane-508614-c1
REGION=asia-northeast1
SERVICE=builder-cup-sandbox
TAG=$(date +%Y%m%d-%H%M%S)
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/builder-cup/sandbox:$TAG"

# Artifact Registry 인증 구성
gcloud auth configure-docker "$REGION-docker.pkg.dev"

# 플랫폼 지정 빌드 및 푸시 (경로는 실제 프로젝트 경로로 변경)
docker buildx build \
  --platform linux/amd64 \
  --push \
  -t "$IMAGE" \
  /전혀/다른/프로젝트/경로

```

**Cloud Run 서비스 배포**

```bash
gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="$IMAGE" \
  --port=8080 \
  --cpu=1 \
  --memory=512Mi \
  --concurrency=10 \
  --min=0 \
  --max=1 \
  --allow-unauthenticated \
  --set-env-vars="KEY1=value1,KEY2=value2" # 환경변수 필요 시 추가

```

**Cloud Run 컨테이너 필수 실행 조건**

- Linux `amd64` 이미지 사용
- 배포 시 지정한 포트(`-port`)에서 실행
- `127.0.0.1`이 아닌 `0.0.0.0`에 바인딩
- HTTP 요청을 지속적으로 수신할 수 있는 서버 프로세스 구성 (실행 직후 종료되는 배치 작업은 Cloud Run Job 사용)

## 3. 테스트 종료 후 리소스 완전 삭제

기존 운영 환경이나 배포 파이프라인에 영향을 주지 않도록 임시 생성한 서비스와 이미지를 삭제합니다.

**Cloud Run 서비스 삭제**

```bash
gcloud run services delete builder-cup-sandbox \
  --project=stunning-crane-508614-c1 \
  --region=asia-northeast1

```

**Artifact Registry 이미지 삭제** (로컬 이미지를 업로드한 경우)

```bash
gcloud artifacts docker images delete \
  asia-northeast1-docker.pkg.dev/stunning-crane-508614-c1/builder-cup/sandbox \
  --project=stunning-crane-508614-c1 \
  --delete-tags

```

## 4. Artifact Registry 정리 정책(Cleanup Policies) 확인

이미지가 자동으로 관리되도록 설정된 정책을 검증합니다. 정책 적용 및 실제 삭제는 백그라운드 작업으로 처리되어 최대 1일이 소요될 수 있습니다.

**CLI를 통한 확인 방법**

```bash
gcloud artifacts repositories list-cleanup-policies builder-cup \
  --project=stunning-crane-508614-c1 \
  --location=asia-northeast1

```

**GCP 콘솔을 통한 확인 방법**

1. Artifact Registry 저장소 접속
2. 리전이 `asia-northeast1`인 `builder-cup` 저장소 선택 후 **저장소 수정(Edit repository)** 클릭
3. **정리 정책(Cleanup policies)** 항목에서 아래 두 정책이 존재하는지 확인:
   - `delete-images-older-than-30-days`: 모든 태그 상태 대상, 30일 경과 버전 삭제 (조건부 삭제)
   - `keep-10-most-recent-versions`: 최신 버전 10개 보존
4. **Dry run(테스트 실행) 비활성화** 및 **아티팩트 삭제(Delete artifacts)** 옵션이 선택되어 있는지 최종 확인
