#!/usr/bin/env bash
# Prove the Cloud Run to GPU path without publishing a service: run probe_gpu_gateway.py once as a temporary
# Cloud Run job with the trend-api image, the staging API service account and the same Direct VPC egress as the
# API service, then delete the job and the temporary CA secret grant. Prints the probe's JSON line.
set -euo pipefail

api_image=${1:?trend-api image pinned by digest}
release_manifest=${2:?release manifest, e.g. manifests/gpu-release-...json}
project=${PROJECT_ID:-stunning-crane-508614-c1}
region=asia-northeast1
job=trend-staging-gpu-probe
account=trend-staging-api@$project.iam.gserviceaccount.com
ca_secret=trend-staging-gpu-ca
root=$(cd "$(dirname "$0")/.." && pwd)

[[ $api_image =~ @sha256:[a-f0-9]{64}$ ]] || { echo "pin the API image by digest" >&2; exit 1; }
read -r model digest < <(python3 -c 'import json,sys;r=json.load(open(sys.argv[1]));print(r["model"],r["model_digest"])' "$release_manifest")
code=$(cat "$root/scripts/probe_gpu_gateway.py")
# gcloud splits --args on the custom delimiter, so the probe source must not contain it.
[[ $code != *@* ]] || { echo "probe source must not contain @" >&2; exit 1; }

gc() { gcloud --project "$project" --quiet "$@"; }
cleanup() {
  gc run jobs delete "$job" --region "$region" >/dev/null 2>&1 || true
  gc secrets remove-iam-policy-binding "$ca_secret" --member "serviceAccount:$account" \
    --role roles/secretmanager.secretAccessor >/dev/null 2>&1 || true
}
trap cleanup EXIT

gc secrets add-iam-policy-binding "$ca_secret" --member "serviceAccount:$account" \
  --role roles/secretmanager.secretAccessor >/dev/null
gc run jobs create "$job" --region "$region" --image "$api_image" --service-account "$account" \
  --network trend-staging-private --subnet trend-staging-api --vpc-egress private-ranges-only \
  --max-retries 0 --task-timeout 600s --cpu 1 --memory 1Gi \
  --set-env-vars "^|^GPU_GATEWAY_REQUESTS_ENABLED=true|GPU_GATEWAY_URL=https://10.40.1.4:8443|GPU_GATEWAY_MODEL=$model|GPU_GATEWAY_MODEL_DIGEST=$digest|GPU_GATEWAY_CA_FILE=/secrets/gpu/ca.pem|AUDIT_MODEL=$model|AUDIT_OLLAMA_HOST=|MODEL_PROVIDER=mock|MODEL_REQUESTS_ENABLED=false" \
  --set-secrets "GPU_GATEWAY_TOKEN=trend-staging-gateway-token:1,/secrets/gpu/ca.pem=$ca_secret:1" \
  --command python --args "^@^-c@$code" >/dev/null
gc run jobs execute "$job" --region "$region" --wait >/dev/null || echo "job execution failed; reading its logs" >&2
execution=$(gc run jobs executions list --job "$job" --region "$region" --limit 1 --format 'value(name)')
for attempt in $(seq 1 12); do
  # Cloud Run stores a JSON stdout line as a structured jsonPayload.
  line=$(gc logging read "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND jsonPayload.gpu_gateway_probe:*" \
    --freshness 1h --limit 1 --format 'json(jsonPayload)' | python3 -c 'import json,sys;rows=json.load(sys.stdin);print(json.dumps(rows[0]["jsonPayload"],sort_keys=True) if rows else "")')
  [ -n "$line" ] && break
  sleep 10
done
if [ -z "$line" ]; then
  gc logging read "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND severity>=ERROR" \
    --freshness 1h --limit 5 --format 'value(textPayload)' >&2
  echo "probe output not found in Cloud Logging" >&2
  exit 1
fi
printf '%s\n' "$line"
