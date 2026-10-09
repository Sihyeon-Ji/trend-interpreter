#!/usr/bin/env bash
# Deploy the Trend API and web images as candidates, verify each, and only then move traffic: API first, then the
# web that talks to it. Terraform owns every other service setting (network, secrets, limits, identities); this
# script changes only the image. A failed check leaves the serving revisions untouched.
set -euo pipefail

: "${PROJECT_ID:?}" "${REGION:?}" "${ENVIRONMENT:?}" "${API_ID_TOKEN:?}"
api_image=${1:?Usage: deploy-trend.sh API_IMAGE@DIGEST WEB_IMAGE@DIGEST}
web_image=${2:?Usage: deploy-trend.sh API_IMAGE@DIGEST WEB_IMAGE@DIGEST}
api=trend-$ENVIRONMENT-api
web=trend-$ENVIRONMENT-web
for image in "$api_image" "$web_image"; do
  [[ $image == *@sha256:* ]] || { echo "pin images by digest" >&2; exit 1; }
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
describe() {
  gcloud run services describe "$1" --project="$PROJECT_ID" --region="$REGION" --format=json >"$work/$1.json"
}
field() {
  python3 - "$work/$1.json" "$2" <<'PY'
import json, sys
data, what = json.load(open(sys.argv[1])), sys.argv[2]
status = data["status"]
if what == "serving":
    print(next((x.get("revisionName", "") for x in status.get("traffic", []) if x.get("percent") == 100), ""))
elif what == "candidate":
    print(next(x["url"] for x in status["traffic"] if x.get("tag") == "candidate"))
else:
    print(status["latestReadyRevisionName"])
PY
}
deploy_candidate() {
  gcloud run deploy "$1" --project="$PROJECT_ID" --region="$REGION" --image="$2" \
    --no-traffic --tag=candidate --quiet >/dev/null
  describe "$1"
}
promote() {
  gcloud run services update-traffic "$1" --project="$PROJECT_ID" --region="$REGION" \
    --to-revisions="$2=100" --remove-tags=candidate --quiet >/dev/null
}
fetch() {
  curl --fail --silent --show-error --retry 5 --retry-all-errors --max-time 60 "$@"
}

describe "$api"
describe "$web"
previous_api=$(field "$api" serving)
previous_web=$(field "$web" serving)

deploy_candidate "$api" "$api_image"
api_candidate=$(field "$api" candidate)
api_revision=$(field "$api" latest)
fetch -H "Authorization: Bearer $API_ID_TOKEN" "$api_candidate/health" |
  python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["ok"] is True and d["terms"] > 0, "API candidate has no data"'
anonymous=$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 30 "$api_candidate/health")
[[ $anonymous == 401 || $anonymous == 403 ]] || { echo "API candidate accepted an anonymous request ($anonymous)" >&2; exit 1; }
promote "$api" "$api_revision"

deploy_candidate "$web" "$web_image"
web_candidate=$(field "$web" candidate)
web_revision=$(field "$web" latest)
fetch "$web_candidate/" | grep -q "<html" || { echo "web candidate did not render" >&2; exit 1; }
fetch -o /dev/null "$web_candidate/map"
fetch -o /dev/null "$web_candidate/briefing"
promote "$web" "$web_revision"

python3 scripts/release_summary.py \
  --service "$api" --previous "$previous_api" --revision "$api_revision" --image "$api_image" \
  --secret "trend-$ENVIRONMENT-database-url" --model 'Gemini through Vertex AI with the configured monthly cap' \
  --checks 'authenticated health with data, anonymous request refused, traffic 100%'
python3 scripts/release_summary.py \
  --service "$web" --previous "$previous_web" --revision "$web_revision" --image "$web_image" \
  --secret "trend-$ENVIRONMENT-session-secret" --model '' \
  --checks 'home and briefing pages 200 through the new API, traffic 100%'
