#!/usr/bin/env bash
# Load a verified snapshot into an empty Cloud SQL database through the Cloud SQL Auth Proxy, using the same
# per-table checks as restore-rehearsal.sh. The connection string is read from Secret Manager and reaches the
# loader only as an environment variable; it is never printed or written to the report.
set -euo pipefail

snapshot_id=${1:?snapshot id required, e.g. 20261001T224511-e56b90d}
secret=${2:?Secret Manager secret holding the DATABASE_URL, e.g. trend-staging-database-url}
output=${3:-}
project_id=${PROJECT_ID:-stunning-crane-508614-c1}
proxy_image=gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.26.0@sha256:86e4f3cc266020e7ee07740df78d7511e2c340c274b56f84d80b7251913af9ad
root=$(cd "$(dirname "$0")/.." && pwd)
snapshot_dir="$root/artifacts/snapshots/$snapshot_id"
manifest="manifests/$snapshot_id.json"
compose_project=trend-cloud-sql-load
network=trend-cloud-sql-load-$$
work=$(mktemp -d)
proxy_container=

cleanup() {
  status=$?
  if [ -n "$proxy_container" ]; then
    if [ "$status" -ne 0 ]; then docker logs "$proxy_container" >&2 2>&1 || true; fi
    docker rm -f "$proxy_container" >/dev/null
  fi
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

test -f "$snapshot_dir/trend-latest.db.gz" || { echo "missing snapshot $snapshot_dir" >&2; exit 1; }
test -f "$root/$manifest" || { echo "missing $manifest" >&2; exit 1; }

# The secret holds the Cloud Run socket form; the loader reaches the same database through the proxy over TCP.
eval "$(gcloud secrets versions access latest --secret "$secret" --project "$project_id" | python3 -c '
import shlex, sys
from urllib.parse import parse_qs, urlsplit
url = urlsplit(sys.stdin.read().strip())
socket = parse_qs(url.query)["host"][0]
instance = socket.removeprefix("/cloudsql/")
database = url.path.lstrip("/")
print(f"instance={shlex.quote(instance)}")
print(f"database={shlex.quote(database)}")
tcp = "postgresql://" + url.username + ":" + url.password + "@cloudsql:5432/" + database
print("LOAD_DATABASE_URL=" + shlex.quote(tcp))
')"
export LOAD_DATABASE_URL
CSQL_PROXY_TOKEN=$(gcloud auth print-access-token)
export CSQL_PROXY_TOKEN

docker compose --project-directory "$root" -p "$compose_project" build check
docker network create "$network" >/dev/null
proxy_container=$(docker run -d --network "$network" --network-alias cloudsql -e CSQL_PROXY_TOKEN \
  "$proxy_image" --address 0.0.0.0 --port 5432 "$instance")
for attempt in $(seq 1 30); do
  case "$(docker logs "$proxy_container" 2>&1)" in *"ready for new connections"*) break ;; esac
  sleep 1
done

started=$(date +%s)
docker run --rm --network "$network" -e LOAD_DATABASE_URL \
  -v "$snapshot_dir:/intake:ro" -v "$root/$manifest:/manifest.json:ro" -v "$work:/out" \
  "$compose_project-check" uv run --offline --project apps/trend-api --locked \
  python scripts/restore_rehearsal.py --output /out/load.json load --manifest /manifest.json --snapshot-dir /intake
finished=$(date +%s)

report=$(python3 - "$snapshot_id" "$instance" "$database" "$((finished - started))" "$work/load.json" <<'PY'
import datetime, json, sys
snapshot_id, instance, database, seconds, load_path = sys.argv[1:]
print(json.dumps({
    "snapshot_id": snapshot_id,
    "loaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "instance": instance,
    "database": database,
    "load_seconds": int(seconds),
    "load": json.load(open(load_path)),
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
)
if [ -n "$output" ]; then printf '%s\n' "$report" >"$output"; else printf '%s\n' "$report"; fi
