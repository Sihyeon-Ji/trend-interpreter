#!/usr/bin/env bash
set -euo pipefail
image=${1:?Image required}
container=$(docker run -d -p 127.0.0.1::8080 -e MODEL_PROVIDER=mock "$image")
trap 'docker rm -f "$container" >/dev/null' EXIT
port=$(docker port "$container" 8080/tcp | awk -F: '{print $NF}')
for attempt in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$port/api/health" >/dev/null; then break; fi
  sleep 1
done
curl -fsS "http://127.0.0.1:$port/" >/dev/null
curl -fsS -H 'Content-Type: application/json' --data '{"text":"Container smoke test"}' \
  "http://127.0.0.1:$port/api/analyze" |
  python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["result"]["summary"]=="Container smoke test"'
