#!/usr/bin/env bash
# Cloud Run 배포 (결제 계정 연결 후 실행). 프로젝트: trend-agents-2026, 리전: asia-northeast3(서울)
# 사용: bash deploy/cloud-run.sh            (사전 조건: gcloud auth login, 결제 연결)
set -euo pipefail
PROJECT=${GOOGLE_CLOUD_PROJECT:-trend-agents-2026}
REGION=${REGION:-asia-northeast3}
gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com

# 1) 비밀은 Secret Manager 로 (.env 의 값만, 파일은 올리지 않는다)
for k in GEMINI_API_KEY YOUTUBE_API_KEY NAVER_CLIENT_ID NAVER_CLIENT_SECRET BLUESKY_HANDLE BLUESKY_APP_PASSWORD; do
  v=$(grep -E "^$k=" .env | cut -d= -f2- || true); [ -z "$v" ] && continue
  printf '%s' "$v" | gcloud secrets create "$k" --data-file=- 2>/dev/null || printf '%s' "$v" | gcloud secrets versions add "$k" --data-file=-
done
SECRETS=$(for k in GEMINI_API_KEY YOUTUBE_API_KEY NAVER_CLIENT_ID NAVER_CLIENT_SECRET BLUESKY_HANDLE BLUESKY_APP_PASSWORD; do gcloud secrets describe "$k" >/dev/null 2>&1 && printf '%s=%s:latest,' "$k" "$k"; done | sed 's/,$//')

# 2) API (+ 파이프라인 잡용 이미지)
gcloud run deploy trend-api --source . --region "$REGION" --allow-unauthenticated --port 8080 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT,NAVER_API_HUB=1,GEMINI_DAILY_BUDGET=400,WEB_ORIGINS=*" --set-secrets "$SECRETS" \
  --memory 1Gi --min-instances 0 --max-instances 2
API_URL=$(gcloud run services describe trend-api --region "$REGION" --format='value(status.url)')

# 3) 웹 (NEXT_PUBLIC_* 는 빌드 인자)
gcloud run deploy trend-web --source web --region "$REGION" --allow-unauthenticated --port 8080 \
  --build-env-vars-file <(printf 'NEXT_PUBLIC_DATA_MODE: api\nNEXT_PUBLIC_API_BASE: %s\n' "$API_URL") --memory 512Mi --min-instances 0 --max-instances 2

# 4) 파이프라인: Cloud Run Job + Scheduler 6시간 (같은 이미지)
IMAGE=$(gcloud run services describe trend-api --region "$REGION" --format='value(spec.template.spec.containers[0].image)')
gcloud run jobs deploy trend-pipeline --image "$IMAGE" --region "$REGION" --command python --args scripts/run_pipeline.py \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT,NAVER_API_HUB=1,GEMINI_DAILY_BUDGET=400" --set-secrets "$SECRETS" --task-timeout 1800 --memory 1Gi
gcloud scheduler jobs create http trend-pipeline-6h --location "$REGION" --schedule "0 */6 * * *" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/trend-pipeline:run" --http-method POST \
  --oauth-service-account-email "$(gcloud iam service-accounts list --format='value(email)' --filter='compute' | head -1)" 2>/dev/null || true
echo "API: $API_URL"; gcloud run services describe trend-web --region "$REGION" --format='value(status.url)'
