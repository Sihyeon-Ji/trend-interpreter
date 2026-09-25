#!/usr/bin/env bash
set -euo pipefail
: "${PROJECT_ID:?}" "${REGION:?}" "${SERVICE:?}" "${GEMINI_MODEL:?}"
image=${1:?Usage: deploy-gcp.sh IMAGE_DIGEST}
previous_revision=$(
  gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" \
    --format=json 2>/dev/null |
    python3 -c 'import json,sys; data=json.load(sys.stdin); print(next((x.get("revisionName", "") for x in data["status"].get("traffic", []) if x.get("percent")==100), ""))' 2>/dev/null || true
)
secret_version=$(
  gcloud secrets versions list builder-cup-demo-key \
    --project="$PROJECT_ID" --filter='state=ENABLED' \
    --sort-by='~createTime' --limit=1 --format='value(name)'
)
[[ "$secret_version" =~ ^[0-9]+$ ]]
read -r model_requests_enabled model_requests_per_minute model_max_concurrent_requests < <(
  python3 - <<'PY'
import json
from pathlib import Path

controls = json.loads(Path("deployment/model-controls.json").read_text())
assert set(controls) == {"enabled", "requests_per_minute", "max_concurrent_requests"}
assert type(controls["enabled"]) is bool
for key in ("requests_per_minute", "max_concurrent_requests"):
    assert type(controls[key]) is int and 1 <= controls[key] <= 100
print(str(controls["enabled"]).lower(), controls["requests_per_minute"], controls["max_concurrent_requests"])
PY
)
deploy_args=(
  "$SERVICE" --project="$PROJECT_ID" --region="$REGION"
  --image="$image" --service-account="builder-cup-runtime@$PROJECT_ID.iam.gserviceaccount.com"
  --port=8080 --cpu=1 --memory=512Mi --concurrency=10 --min=0 --max=2 --timeout=120
  --set-env-vars="MODEL_PROVIDER=gemini,GCP_PROJECT_ID=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=$GEMINI_MODEL,MODEL_REQUESTS_ENABLED=$model_requests_enabled,MODEL_REQUESTS_PER_MINUTE=$model_requests_per_minute,MODEL_MAX_CONCURRENT_REQUESTS=$model_max_concurrent_requests"
  --set-secrets="DEMO_API_KEY=builder-cup-demo-key:$secret_version"
  --tag=candidate --quiet
)
# Cloud Run rejects --no-traffic when the service does not exist yet. Later releases keep the
# serving revision in place until the candidate smoke checks pass.
if gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" >/dev/null 2>&1; then
  deploy_args+=(--no-traffic)
fi
gcloud run deploy "${deploy_args[@]}"
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
gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" \
  --format=json | python3 -c 'import json,sys; data=json.load(sys.stdin); rev=sys.argv[1]; assert any(x.get("revisionName")==rev and x.get("percent")==100 for x in data["status"]["traffic"]); print(data["status"]["url"])' "$revision"
python3 scripts/release_summary.py \
  --service "$SERVICE" --previous "$previous_revision" --revision "$revision" \
  --image "$image" --secret "builder-cup-demo-key:$secret_version" \
  --model "$GEMINI_MODEL" --checks 'candidate health 200, anonymous analysis 401, traffic 100%'
