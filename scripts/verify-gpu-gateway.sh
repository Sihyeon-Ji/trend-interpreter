#!/usr/bin/env bash
# Verify an installed GPU gateway from inside its VM over IAP SSH: install result, TLS against the staging CA,
# rejection of missing or wrong credentials, readiness and timed inference. The gateway token never leaves the
# VM. The JSON report holds status codes, timings and GPU memory only, never prompts, outputs or credentials.
set -euo pipefail

vm=${1:?VM name, e.g. trend-staging-gpu}
zone=${2:?zone}
ca_secret=${3:?CA secret name, e.g. trend-staging-gpu-ca}
address=${4:-10.40.1.4}
project=${PROJECT_ID:-stunning-crane-508614-c1}

ca=$(gcloud secrets versions access latest --secret "$ca_secret" --project "$project")
remote=$(cat <<SH
set -eu
cat >/tmp/trend-ca.pem <<'PEM'
$ca
PEM
python3 - "$address" <<'PY'
$(cat "$(dirname "$0")/verify_gpu_gateway.py")
PY
rm -f /tmp/trend-ca.pem
SH
)
printf '%s\n' "$remote" | gcloud compute ssh "$vm" --zone "$zone" --project "$project" --tunnel-through-iap \
  --quiet --command 'sudo bash -s'
