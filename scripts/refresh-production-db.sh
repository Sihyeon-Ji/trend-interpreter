#!/usr/bin/env bash
# Build a new production database from a newer snapshot while keeping production's human decisions (Plan 19).
#
#   capture <snapshot-id>              pin GCS db/latest into artifacts/snapshots and manifests/
#   create <database>                  create an empty database owned by trend_app through a temporary admin user
#   load <snapshot-id> <database>      load the snapshot without user tables and check per-table counts
#   overlay <database> [report]        copy production's human decisions and user data, then compare
#   recompute <database> [report]      rerun rule-only lifecycle, risk, board and dashboard stages
#   compare <database> [report]        fail when a production decision is missing from the new database
#
# The current production database is the one the latest trend-production-database-url version points to. Connection
# strings reach containers only as environment variables; reports hold counts and keys, never row contents.
set -euo pipefail

project_id=${PROJECT_ID:-stunning-crane-508614-c1}
instance=${SQL_INSTANCE:-trend-project}
secret=trend-production-database-url
proxy_image=gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.26.0@sha256:86e4f3cc266020e7ee07740df78d7511e2c340c274b56f84d80b7251913af9ad
postgres_image=postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650
temp_admin=trend_refresh_admin
root=$(cd "$(dirname "$0")/.." && pwd)
compose_project=trend-refresh
network=trend-refresh-$$
work=$(mktemp -d)
proxy_container=
admin_created=

cleanup() {
  status=$?
  if [ -n "$proxy_container" ]; then
    if [ "$status" -ne 0 ]; then docker logs "$proxy_container" >&2 2>&1 || true; fi
    docker rm -f "$proxy_container" >/dev/null
  fi
  docker network rm "$network" >/dev/null 2>&1 || true
  if [ -n "$admin_created" ]; then
    gcloud sql users delete "$temp_admin" --instance="$instance" --project="$project_id" --quiet >/dev/null ||
      echo "WARNING: delete the temporary user $temp_admin by hand" >&2
  fi
  rm -rf "$work"
}
trap cleanup EXIT

valid_database() {
  case "$1" in trend) echo "refusing to touch the live database name trend" >&2; exit 1 ;; esac
  [[ "$1" =~ ^trend_[a-z0-9_]{1,40}$ ]] || { echo "database name must match trend_[a-z0-9_]+" >&2; exit 1; }
}

# Reads the production connection string and exports SOURCE_DATABASE_URL and, for $1, TARGET_DATABASE_URL in the TCP
# form the proxy serves. Cloud Run uses the socket form stored in the secret.
read_urls() {
  eval "$(gcloud secrets versions access latest --secret "$secret" --project "$project_id" | TARGET_DB="${1:-}" python3 -c '
import os, shlex, sys
from urllib.parse import parse_qs, urlsplit
url = urlsplit(sys.stdin.read().strip())
base = "postgresql://" + url.username + ":" + url.password + "@cloudsql:5432/"
print("sql_connection=" + shlex.quote(parse_qs(url.query)["host"][0].removeprefix("/cloudsql/")))
print("source_database=" + shlex.quote(url.path.lstrip("/")))
print("SOURCE_DATABASE_URL=" + shlex.quote(base + url.path.lstrip("/")))
if os.environ["TARGET_DB"]:
    print("TARGET_DATABASE_URL=" + shlex.quote(base + os.environ["TARGET_DB"]))
')"
  export SOURCE_DATABASE_URL TARGET_DATABASE_URL=${TARGET_DATABASE_URL:-}
}

start_proxy() {
  CSQL_PROXY_TOKEN=$(gcloud auth print-access-token)
  export CSQL_PROXY_TOKEN
  docker network create "$network" >/dev/null
  proxy_container=$(docker run -d --network "$network" --network-alias cloudsql -e CSQL_PROXY_TOKEN \
    "$proxy_image" --address 0.0.0.0 --port 5432 "$sql_connection")
  for _ in $(seq 1 30); do
    case "$(docker logs "$proxy_container" 2>&1)" in *"ready for new connections"*) return ;; esac
    sleep 1
  done
  echo "Cloud SQL Auth Proxy did not become ready" >&2
  exit 1
}

check_image() {
  docker compose --project-directory "$root" -p "$compose_project" build check >/dev/null
  echo "$compose_project-check"
}

run_refresh() {
  local command=$1 report=$2 image
  image=$(check_image)
  docker run --rm --network "$network" -e SOURCE_DATABASE_URL -e TARGET_DATABASE_URL \
    -e MODEL_PROVIDER=mock -e MODEL_REQUESTS_ENABLED=false -v "$work:/out" \
    "$image" uv run --offline --project apps/trend-api --locked python scripts/refresh_production.py --output /out/report.json "$command" ||
    { cat "$work/report.json" >&2 2>/dev/null || true; exit 1; }
  if [ -n "$report" ]; then cp "$work/report.json" "$report"; else cat "$work/report.json"; fi
}

command=${1:?usage: refresh-production-db.sh capture|create|load|overlay|recompute|compare ...}
shift
case "$command" in
  capture)
    snapshot_id=${1:?snapshot id required, e.g. 20261009T224511-abc1234}
    GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)
    export GOOGLE_OAUTH_ACCESS_TOKEN GOOGLE_CLOUD_PROJECT=$project_id
    docker compose --project-directory "$root" run --rm --build -e GOOGLE_OAUTH_ACCESS_TOKEN -e GOOGLE_CLOUD_PROJECT \
      data-tools python scripts/snapshot.py capture --snapshot-id "$snapshot_id" --directory "artifacts/snapshots/$snapshot_id"
    ;;
  create)
    database=${1:?database name required, e.g. trend_20261010}
    valid_database "$database"
    read_urls
    # A temporary built-in user gets CREATEDB through cloudsqlsuperuser; it is deleted on exit, so it must not own anything.
    ADMIN_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    export ADMIN_PASSWORD
    gcloud sql users create "$temp_admin" --instance="$instance" --project="$project_id" --password="$ADMIN_PASSWORD" >/dev/null
    admin_created=1
    start_proxy
    PGPASSWORD=$ADMIN_PASSWORD
    export PGPASSWORD
    docker run --rm -i --network "$network" -e PGPASSWORD "$postgres_image" \
      psql -h cloudsql -U "$temp_admin" -d postgres -At -v ON_ERROR_STOP=1 -v db="$database" -v admin="$temp_admin" <<'SQL'
CREATE DATABASE :"db";
GRANT trend_app TO :"admin";
ALTER DATABASE :"db" OWNER TO trend_app;
REVOKE CONNECT ON DATABASE :"db" FROM PUBLIC;
REVOKE trend_app FROM :"admin";
SELECT datname || ' owner=' || pg_get_userbyid(datdba) FROM pg_database WHERE datname = :'db';
SQL
    ;;
  load)
    snapshot_id=${1:?snapshot id required}
    database=${2:?database name required}
    valid_database "$database"
    test -f "$root/artifacts/snapshots/$snapshot_id/trend-latest.db.gz" || { echo "missing snapshot $snapshot_id" >&2; exit 1; }
    test -f "$root/manifests/$snapshot_id.json" || { echo "missing manifests/$snapshot_id.json" >&2; exit 1; }
    read_urls "$database"
    start_proxy
    image=$(check_image)
    LOAD_DATABASE_URL=$TARGET_DATABASE_URL
    export LOAD_DATABASE_URL
    docker run --rm --network "$network" -e LOAD_DATABASE_URL \
      -v "$root/artifacts/snapshots/$snapshot_id:/intake:ro" -v "$root/manifests/$snapshot_id.json:/manifest.json:ro" -v "$work:/out" \
      "$image" uv run --offline --project apps/trend-api --locked \
      python scripts/restore_rehearsal.py --output /out/load.json load --manifest /manifest.json --snapshot-dir /intake
    cat "$work/load.json"
    ;;
  overlay|recompute|compare)
    database=${1:?database name required}
    valid_database "$database"
    read_urls "$database"
    [ "$source_database" != "$database" ] || { echo "the latest secret already points to $database" >&2; exit 1; }
    start_proxy
    run_refresh "$command" "${2:-}"
    ;;
  *)
    echo "unknown command $command" >&2
    exit 1
    ;;
esac
