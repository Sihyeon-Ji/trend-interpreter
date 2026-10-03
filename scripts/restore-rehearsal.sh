#!/usr/bin/env bash
# Migrate a verified snapshot into a throwaway PostgreSQL, dump it with pg_dump, restore the dump into a
# second empty database and compare schema and content. The Compose project, its volume and the dump are
# removed on exit; nothing touches the development database or Cloud SQL.
set -euo pipefail

snapshot_id=${1:?snapshot id required, e.g. 20261001T224511-e56b90d}
output=${2:-}
root=$(cd "$(dirname "$0")/.." && pwd)
snapshot_dir="$root/artifacts/snapshots/$snapshot_id"
manifest="manifests/$snapshot_id.json"
project=trend-restore-rehearsal
source_db=rehearsal_source
restored_db=rehearsal_restored
dump=/tmp/rehearsal.dump
work=$(mktemp -d)

compose() { docker compose --project-directory "$root" -p "$project" "$@"; }
in_db() { compose exec -T db "$@"; }
check() { compose run --rm -T -v "$snapshot_dir:/intake:ro" -v "$root/$manifest:/manifest.json:ro" -v "$work:/out" check uv run --offline --project apps/trend-api --locked python scripts/restore_rehearsal.py "$@"; }
cleanup() { compose down -v --remove-orphans >/dev/null 2>&1 || true; }
finish() { cleanup; rm -rf "$work"; }
trap finish EXIT

test -f "$snapshot_dir/trend-latest.db.gz" || { echo "missing snapshot $snapshot_dir" >&2; exit 1; }
test -f "$root/$manifest" || { echo "missing $manifest" >&2; exit 1; }

cleanup
compose build check
compose up -d --wait db
in_db createdb -U trend "$source_db"
in_db createdb -U trend "$restored_db"

started=$(date +%s)
check --output /out/load.json load --manifest /manifest.json --snapshot-dir /intake \
  --database-url "postgresql://trend:trend@db:5432/$source_db"
loaded=$(date +%s)

# The dump never leaves the database container.
in_db pg_dump -U trend --format=custom --no-owner --no-privileges -d "$source_db" -f "$dump"
dump_bytes=$(in_db stat -c %s "$dump")
in_db pg_restore -U trend --no-owner --no-privileges --exit-on-error -d "$restored_db" "$dump"
restored=$(date +%s)

check --output /out/compare.json compare --source-url "postgresql://trend:trend@db:5432/$source_db" \
  --restored-url "postgresql://trend:trend@db:5432/$restored_db"
server_version=$(in_db psql -U trend -d "$source_db" -Atc 'SHOW server_version')

report=$(python3 - "$snapshot_id" "$server_version" "$dump_bytes" "$((loaded - started))" "$((restored - loaded))" \
  "$work/load.json" "$work/compare.json" <<'PY'
import datetime, json, sys
snapshot_id, version, dump_bytes, load_seconds, restore_seconds, load_path, compare_path = sys.argv[1:]
print(json.dumps({
    "snapshot_id": snapshot_id,
    "rehearsed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "postgres_server_version": version,
    "dump_format": "pg_dump custom, --no-owner --no-privileges",
    "dump_bytes": int(dump_bytes),
    "load_seconds": int(load_seconds),
    "dump_and_restore_seconds": int(restore_seconds),
    "load": json.load(open(load_path)),
    "restore_comparison": json.load(open(compare_path)),
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
)
if [ -n "$output" ]; then printf '%s\n' "$report" >"$output"; else printf '%s\n' "$report"; fi
