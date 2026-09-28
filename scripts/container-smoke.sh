#!/usr/bin/env bash
set -euo pipefail

api_image=${1:?API image required}
web_image=${2:?Web image required}
network=builder-cup-smoke-$$
db_container=
api_container=
web_container=
cleanup() {
  if [ -n "$web_container" ]; then docker rm -f "$web_container" >/dev/null; fi
  if [ -n "$api_container" ]; then docker rm -f "$api_container" >/dev/null; fi
  if [ -n "$db_container" ]; then docker rm -f "$db_container" >/dev/null; fi
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create "$network" >/dev/null
db_container=$(docker run -d --network "$network" --network-alias db \
  -e POSTGRES_USER=trend -e POSTGRES_PASSWORD=trend -e POSTGRES_DB=trend postgres:18.6-bookworm)
for attempt in $(seq 1 30); do
  if docker exec "$db_container" pg_isready -U trend -d trend >/dev/null 2>&1; then break; fi
  sleep 1
done

api_container=$(docker run -d --network "$network" -p 127.0.0.1::8080 \
  -e DATABASE_URL=postgresql://trend:trend@db:5432/trend \
  -e MODEL_PROVIDER=mock -e MODEL_REQUESTS_ENABLED=false "$api_image")
api_port=$(docker port "$api_container" 8080/tcp | awk -F: '{print $NF}')
for attempt in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$api_port/health" >/dev/null; then break; fi
  sleep 1
done
curl -fsS "http://127.0.0.1:$api_port/health" |
  python3 -c 'import json,sys; assert json.load(sys.stdin)["ok"] is True'

web_container=$(docker run -d -p 127.0.0.1::8080 -e DATA_MODE=sample "$web_image")
web_port=$(docker port "$web_container" 8080/tcp | awk -F: '{print $NF}')
for attempt in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$web_port/" >/dev/null; then break; fi
  sleep 1
done
curl -fsS "http://127.0.0.1:$web_port/" |
  python3 -c 'import sys; assert "Trend Interpreter" in sys.stdin.read()'
