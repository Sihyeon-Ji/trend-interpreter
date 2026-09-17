#!/usr/bin/env bash
set -euo pipefail
: "${PROJECT_ID:?}" "${REGION:?}" "${SERVICE:?}" "${GEMINI_MODEL:?}"
image=${1:?Usage: deploy-gcp.sh IMAGE_DIGEST}
gcloud run deploy "$SERVICE" --project="$PROJECT_ID" --region="$REGION" \
  --image="$image" --service-account="builder-cup-runtime@$PROJECT_ID.iam.gserviceaccount.com" \
  --port=8080 --cpu=1 --memory=512Mi --concurrency=10 --min=0 --max=2 --timeout=120 \
  --set-env-vars="MODEL_PROVIDER=gemini,GCP_PROJECT_ID=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=$GEMINI_MODEL" \
  --set-secrets=DEMO_API_KEY=builder-cup-demo-key:latest \
  --no-traffic --tag=candidate --quiet
gcloud run services add-iam-policy-binding "$SERVICE" --project="$PROJECT_ID" --region="$REGION" \
  --member=allUsers --role=roles/run.invoker --quiet >/dev/null
service_json=$(mktemp)
trap 'rm -f "$service_json"' EXIT
gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" \
  --format=json > "$service_json"
candidate_url=$(python3 - "$service_json" <<'PY'
import json,sys
data=json.load(open(sys.argv[1]))
print(next(t['url'] for t in data['status']['traffic'] if t.get('tag') == 'candidate'))
PY
)
curl --fail --silent --show-error --retry 5 --retry-all-errors --max-time 20 \
  "$candidate_url/api/health" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="ok" and d["provider"]=="gemini"'
curl --fail --silent --show-error --max-time 20 "$candidate_url/" >/dev/null
# Verify that anonymous calls cannot spend model tokens.
status=$(curl --silent --show-error --max-time 20 -o /dev/null -w '%{http_code}' \
  -H 'Content-Type: application/json' --data '{"text":"Deployment check"}' "$candidate_url/api/analyze")
test "$status" = 401
revision=$(python3 - "$service_json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['status']['latestReadyRevisionName'])
PY
)
gcloud run services update-traffic "$SERVICE" --project="$PROJECT_ID" --region="$REGION" \
  --to-revisions="$revision=100" --remove-tags=candidate --quiet
gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)'
