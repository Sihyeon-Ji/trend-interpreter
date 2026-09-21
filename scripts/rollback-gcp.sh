#!/usr/bin/env bash
set -euo pipefail
revision=${1:?Usage: bash scripts/rollback-gcp.sh KNOWN_GOOD_REVISION}
gcloud run services update-traffic builder-cup --project=stunning-crane-508614-c1 \
  --region=asia-northeast1 --to-revisions="$revision=100" --quiet
