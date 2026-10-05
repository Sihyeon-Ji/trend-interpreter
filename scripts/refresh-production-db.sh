#!/usr/bin/env bash
# Build a new production database from a newer snapshot while keeping production's human decisions (Plan 19).
#
#   capture <snapshot-id>              pin GCS db/latest into artifacts/snapshots and manifests/
#   build <snapshot-id>                in a throwaway local PostgreSQL: load the snapshot, carry production's human
#                                      decisions and user data, rerun rule stages, compare, then dump to artifacts/refresh/
#   create <database>                  create an empty Cloud SQL database owned by trend_app through a temporary admin user
#   upload <database> <dump>           restore a built dump into that empty database
#   overlay <database> [report]        carry decisions made since the build, then compare (run right before switching)
#   compare <database> [report]        fail when a production decision is missing from the new database
#   secret <database>                  add a trend-production-database-url version pointing to <database> and print it
#
# The rule stages read every news row per term, so they run against the local copy; over the proxy they take hours.
# The current production database is the one the latest trend-production-database-url version points to. Connection
# strings reach containers only as environment variables; reports hold counts and keys, never row contents.
set -euo pipefail

project_id=${PROJECT_ID:-stunning-crane-508614-c1}
instance=${SQL_INSTANCE:-trend-project}
secret=trend-production-database-url
proxy_image=gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.26.0@sha256:86e4f3cc266020e7ee07740df78d7511e2c340c274b56f84d80b7251913af9ad
postgres_image=postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650
temp_admin=trend_refresh_admin
local_url=postgresql://trend:trend@localdb:5432/trend_build
root=$(cd "$(dirname "$0")/.." && pwd)
compose_project=trend-refresh
network=trend-refresh-$$
work=$(mktemp -d)
proxy_container=
local_container=
admin_created=

cleanup() {
  status=$?
  if [ -n "$proxy_container" ]; then
    if [ "$status" -ne 0 ]; then docker logs "$proxy_container" >&2 2>&1 || true; fi
    docker rm -f "$proxy_container" >/dev/null
  fi
  if [ -n "$local_container" ]; then docker rm -f -v "$local_container" >/dev/null; fi
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
  docker network create "$network" >/dev/null 2>&1 || true
  proxy_container=$(docker run -d --network "$network" --network-alias cloudsql -e CSQL_PROXY_TOKEN \
    "$proxy_image" --address 0.0.0.0 --port 5432 "$sql_connection")
  for _ in $(seq 1 30); do
    case "$(docker logs "$proxy_container" 2>&1)" in *"ready for new connections"*) return ;; esac
    sleep 1
  done
  echo "Cloud SQL Auth Proxy did not become ready" >&2
  exit 1
}

# Proxy tokens last an hour, so the proxy is started fresh right before each step that reads production.
stop_proxy() {
  if [ -n "$proxy_container" ]; then docker rm -f "$proxy_container" >/dev/null; fi
  proxy_container=
}

start_local_db() {
  docker network create "$network" >/dev/null 2>&1 || true
  local_container=$(docker run -d --network "$network" --network-alias localdb -e POSTGRES_USER=trend \
    -e POSTGRES_PASSWORD=trend -e POSTGRES_DB=trend_build "$postgres_image")
  for _ in $(seq 1 60); do
    docker exec "$local_container" pg_isready -h 127.0.0.1 -U trend -d trend_build >/dev/null 2>&1 && return
    sleep 1
  done
  echo "local PostgreSQL did not become ready" >&2
  exit 1
}

check_image() {
  docker compose --project-directory "$root" -p "$compose_project" build check >/dev/null
  echo "$compose_project-check"
}

# Runs scripts/refresh_production.py <command> in the check image and copies its report to $2 (or stdout).
run_refresh() {
  local command=$1 report=$2 image
  image=$(check_image)
  docker run --rm --network "$network" -e SOURCE_DATABASE_URL -e TARGET_DATABASE_URL \
    -e MODEL_PROVIDER=mock -e MODEL_REQUESTS_ENABLED=false -v "$work:/out" \
    "$image" uv run --offline --project apps/trend-api --locked python scripts/refresh_production.py --output /out/report.json "$command" ||
    { cat "$work/report.json" >&2 2>/dev/null || true; exit 1; }
  if [ -n "$report" ]; then cp "$work/report.json" "$report"; else cat "$work/report.json"; fi
}

command=${1:?usage: refresh-production-db.sh capture|build|create|upload|overlay|compare|secret ...}
shift
case "$command" in
  capture)
    snapshot_id=${1:?snapshot id required, e.g. 20261009T224511-abc1234}
    GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)
    export GOOGLE_OAUTH_ACCESS_TOKEN GOOGLE_CLOUD_PROJECT=$project_id
    docker compose --project-directory "$root" run --rm --build -e GOOGLE_OAUTH_ACCESS_TOKEN -e GOOGLE_CLOUD_PROJECT \
      data-tools python scripts/snapshot.py capture --snapshot-id "$snapshot_id" --directory "artifacts/snapshots/$snapshot_id"
    cp "$root/artifacts/snapshots/$snapshot_id/manifest.json" "$root/manifests/$snapshot_id.json"
    ;;
  build)
    snapshot_id=${1:?snapshot id required}
    test -f "$root/artifacts/snapshots/$snapshot_id/trend-latest.db.gz" || { echo "missing snapshot $snapshot_id" >&2; exit 1; }
    test -f "$root/manifests/$snapshot_id.json" || { echo "missing manifests/$snapshot_id.json" >&2; exit 1; }
    out="$root/artifacts/refresh/$snapshot_id"
    mkdir -p "$out"
    chmod 700 "$out"
    read_urls
    TARGET_DATABASE_URL=$local_url
    LOAD_DATABASE_URL=$local_url
    export TARGET_DATABASE_URL LOAD_DATABASE_URL
    start_local_db
    image=$(check_image)
    docker run --rm --network "$network" -e LOAD_DATABASE_URL \
      -v "$root/artifacts/snapshots/$snapshot_id:/intake:ro" -v "$root/manifests/$snapshot_id.json:/manifest.json:ro" -v "$work:/out" \
      "$image" uv run --offline --project apps/trend-api --locked \
      python scripts/restore_rehearsal.py --output /out/load.json load --manifest /manifest.json --snapshot-dir /intake >/dev/null
    cp "$work/load.json" "$out/load.json"
    start_proxy
    run_refresh overlay "$out/overlay.json"
    stop_proxy
    run_refresh recompute "$out/recompute.json"
    start_proxy
    run_refresh compare "$out/compare.json"
    stop_proxy
    docker exec "$local_container" pg_dump -U trend -d trend_build --format=custom --no-owner --no-privileges --schema=public \
      -f /tmp/build.dump
    docker cp "$local_container:/tmp/build.dump" "$out/trend.dump"
    chmod 600 "$out/trend.dump"
    echo "built $out/trend.dump ($(wc -c <"$out/trend.dump" | tr -d ' ') bytes)"
    ;;
  create)
    database=${1:?database name required, e.g. trend_20261010}
    valid_database "$database"
    read_urls
    # A temporary built-in user gets CREATEDB through cloudsqlsuperuser; it is deleted on exit, so it must not own anything.
    ADMIN_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
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
  upload)
    database=${1:?database name required}
    dump=${2:?built dump required, e.g. artifacts/refresh/<snapshot-id>/trend.dump}
    valid_database "$database"
    test -f "$dump" || { echo "missing $dump" >&2; exit 1; }
    read_urls "$database"
    [ "$source_database" != "$database" ] || { echo "the latest secret already points to $database" >&2; exit 1; }
    start_proxy
    # The dump carries its own CREATE SCHEMA public, so the empty database's default schema goes first.
    docker run --rm -i --network "$network" -e TARGET_DATABASE_URL "$postgres_image" sh -ec '
      test "$(psql "$TARGET_DATABASE_URL" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname = '"'"'public'"'"'")" = 0 ||
        { echo "target database is not empty" >&2; exit 1; }
      psql "$TARGET_DATABASE_URL" -qc "DROP SCHEMA IF EXISTS public CASCADE"
      cat >/tmp/build.dump
      pg_restore --no-owner --no-privileges --exit-on-error -d "$TARGET_DATABASE_URL" /tmp/build.dump
      psql "$TARGET_DATABASE_URL" -Atc "SELECT count(*) || '"'"' tables'"'"' FROM pg_tables WHERE schemaname = '"'"'public'"'"'"' <"$dump"
    ;;
  overlay|compare)
    database=${1:?database name required}
    valid_database "$database"
    read_urls "$database"
    [ "$source_database" != "$database" ] || { echo "the latest secret already points to $database" >&2; exit 1; }
    start_proxy
    run_refresh "$command" "${2:-}"
    ;;
  secret)
    database=${1:?database name required}
    valid_database "$database"
    # Adding a version changes nothing until production.tfvars.json pins it; the running revisions keep their own version.
    gcloud secrets versions access latest --secret "$secret" --project "$project_id" | DATABASE="$database" python3 -c '
import os, sys
from urllib.parse import urlsplit, urlunsplit
url = urlsplit(sys.stdin.read().strip())
sys.stdout.write(urlunsplit(url._replace(path="/" + os.environ["DATABASE"])))
' | gcloud secrets versions add "$secret" --project "$project_id" --data-file=- --format='value(name)'
    ;;
  *)
    echo "unknown command $command" >&2
    exit 1
    ;;
esac
