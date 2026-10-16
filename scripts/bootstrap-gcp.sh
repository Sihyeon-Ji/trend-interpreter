#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools:$PATH"
PROJECT_ID=stunning-crane-508614-c1
REGION=asia-northeast1
REPO=Sihyeon-Ji/trend-interpreter
STATE_BUCKET="$PROJECT_ID-tfstate"
for command in gcloud gh terraform python3; do command -v "$command" >/dev/null; done
gcloud projects describe "$PROJECT_ID" --format='value(projectId)' >/dev/null
billing_enabled=$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)')
if [[ "$billing_enabled" != "True" && "$billing_enabled" != "true" ]]; then
  printf '%s\n' 'Billing is disabled. No resources were changed. Use docker compose run --rm infra-check for local validation.' >&2
  exit 2
fi
gh api "repos/$REPO" --jq '.permissions.push' | python3 -c 'import sys; assert sys.stdin.read().strip() == "true", "GitHub write access required"'
gcloud services enable serviceusage.googleapis.com storage.googleapis.com --project="$PROJECT_ID"
if ! gcloud storage buckets describe "gs://$STATE_BUCKET" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$STATE_BUCKET" --project="$PROJECT_ID" \
    --location="$REGION" --uniform-bucket-level-access --public-access-prevention
fi
gcloud storage buckets update "gs://$STATE_BUCKET" --versioning
export TF_VAR_github_repository_id
export TF_VAR_github_owner_id
TF_VAR_github_repository_id=$(gh api "repos/$REPO" --jq '.id | tostring')
TF_VAR_github_owner_id=$(gh api "repos/$REPO" --jq '.owner.id | tostring')
# Persist only non-secret configuration so later plan commands do not prompt for IDs.
python3 - <<'PY'
import json, os
from pathlib import Path
Path('infra/gcp/github.auto.tfvars.json').write_text(json.dumps({
    'github_repository_id': os.environ['TF_VAR_github_repository_id'],
    'github_owner_id': os.environ['TF_VAR_github_owner_id'],
}, indent=2) + '\n')
PY
terraform -chdir=infra/gcp init -reconfigure -backend-config="bucket=$STATE_BUCKET" -backend-config="prefix=foundation"
terraform -chdir=infra/gcp plan -out=bootstrap.tfplan
terraform -chdir=infra/gcp apply bootstrap.tfplan
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "$REPO" \
  --body "$(terraform -chdir=infra/gcp output -raw workload_identity_provider)"
gh variable set GCP_DEPLOY_SERVICE_ACCOUNT --repo "$REPO" \
  --body "$(terraform -chdir=infra/gcp output -raw deploy_service_account)"
gh variable set GCP_IMAGE_SERVICE_ACCOUNT --repo "$REPO" \
  --body "$(terraform -chdir=infra/gcp output -raw image_push_service_account)"
gh api --method PUT "repos/$REPO/environments/gcp" >/dev/null
printf '%s\n' 'Infrastructure and GitHub variables configured.'
