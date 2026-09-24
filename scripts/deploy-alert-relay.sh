#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?}" "${PROJECT_NUMBER:?}" "${REGION:?}" "${SERVICE:?}" "${ALERT_TOPIC:?}"
image=${1:?Usage: deploy-alert-relay.sh IMAGE_DIGEST}
relay_audience="https://${SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app"
runtime_service_account="builder-cup-alert-relay@$PROJECT_ID.iam.gserviceaccount.com"
push_service_account="builder-cup-alert-push@$PROJECT_ID.iam.gserviceaccount.com"
deploy_service_account="builder-cup-deploy@$PROJECT_ID.iam.gserviceaccount.com"
secret_version=$(
  gcloud secrets versions list discord-webhook \
    --project="$PROJECT_ID" \
    --filter='state=ENABLED' \
    --sort-by='~createTime' \
    --limit=1 \
    --format='value(name)'
)
test -n "$secret_version"

deploy_args=(
  "$SERVICE" --project="$PROJECT_ID" --region="$REGION"
  --image="$image" --service-account="$runtime_service_account"
  --port=8080 --cpu=1 --memory=256Mi --concurrency=20 --min=0 --max=1 --timeout=15
  --set-env-vars=DISCORD_TIMEOUT_SECONDS=5
  --set-secrets="DISCORD_WEBHOOK_URL=discord-webhook:$secret_version"
  --set-custom-audiences="$relay_audience"
  --no-allow-unauthenticated --tag=candidate --quiet
)
if gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" >/dev/null 2>&1; then
  deploy_args+=(--no-traffic)
fi
gcloud run deploy "${deploy_args[@]}"

for account in "$push_service_account" "$deploy_service_account"; do
  gcloud run services add-iam-policy-binding "$SERVICE" \
    --project="$PROJECT_ID" --region="$REGION" \
    --member="serviceAccount:$account" --role=roles/run.invoker --quiet >/dev/null
done

service_json=$(mktemp)
trap 'rm -f "$service_json"' EXIT
gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format=json > "$service_json"
candidate_url=$(python3 - "$service_json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
print(next(item["url"] for item in data["status"]["traffic"] if item.get("tag") == "candidate"))
PY
)
revision=$(python3 - "$service_json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["status"]["latestReadyRevisionName"])
PY
)
identity_token=$(gcloud auth print-identity-token --audiences="$relay_audience")
curl --fail --silent --show-error --retry 5 --retry-all-errors --max-time 20 \
  -H "Authorization: Bearer $identity_token" "$candidate_url/health" |
  python3 -c 'import json,sys; assert json.load(sys.stdin) == {"status": "ok"}'

gcloud run services update-traffic "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --to-revisions="$revision=100" --remove-tags=candidate --quiet

smoke_message=$(python3 - "$revision" <<'PY'
import json, sys, time
print(json.dumps({
    "incident": {
        "incident_id": f"deployment-smoke-{int(time.time())}",
        "state": "closed",
        "policy_name": "Discord relay deployment smoke test",
        "condition_name": "Authenticated Pub/Sub delivery",
        "resource_name": "builder-cup-alert-relay",
        "resource": {"labels": {
            "service_name": "builder-cup-alert-relay",
            "revision_name": sys.argv[1],
        }},
        "ended_at": int(time.time()),
        "observed_value": "deployment verified",
        "url": "https://console.cloud.google.com/monitoring/alerting/incidents",
    }
}, separators=(",", ":")))
PY
)
gcloud pubsub topics publish "$ALERT_TOPIC" \
  --project="$PROJECT_ID" --message="$smoke_message" --quiet >/dev/null
printf '%s\n' "$relay_audience"
