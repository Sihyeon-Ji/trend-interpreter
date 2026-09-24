#!/usr/bin/env bash
set -euo pipefail

image=${1:?Usage: bash scripts/alert-relay-smoke.sh IMAGE}
container=$(docker run -d --rm -e DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/test/token \
  -p 127.0.0.1::8080 "$image")
trap 'docker stop "$container" >/dev/null 2>&1 || true' EXIT
port=$(docker port "$container" 8080/tcp | sed 's/.*://')
for _ in {1..20}; do
  if curl --fail --silent --max-time 2 "http://127.0.0.1:$port/health" |
    python3 -c 'import json,sys; assert json.load(sys.stdin) == {"status": "ok"}' 2>/dev/null; then
    exit 0
  fi
  sleep 1
done
docker logs "$container" >&2
exit 1
