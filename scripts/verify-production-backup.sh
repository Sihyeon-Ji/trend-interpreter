#!/usr/bin/env bash
# Restore a production backup into a throwaway PostgreSQL and report per-table row counts. The dump is downloaded
# to a private temporary directory and removed on exit; the report holds object metadata and counts only.
set -euo pipefail

object=${1:-}
output=${2:-}
project_id=${PROJECT_ID:-stunning-crane-508614-c1}
bucket=${BACKUP_BUCKET:-$project_id-trend-production-backups}
image=postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
container=

cleanup() {
  if [ -n "$container" ]; then docker rm -f "$container" >/dev/null; fi
  rm -rf "$work"
}
trap cleanup EXIT
chmod 700 "$work"

if [ -z "$object" ]; then
  object=$(gcloud storage ls "gs://$bucket/trend-*.dump" --project "$project_id" | sort | tail -n 1)
  object=${object##*/}
fi
test -n "$object" || { echo "no backup in gs://$bucket" >&2; exit 1; }

# Sliced downloads fail their hash check in some gcloud releases; a single stream is fast enough for one dump.
CLOUDSDK_STORAGE_SLICED_OBJECT_DOWNLOAD_THRESHOLD=0 \
  gcloud storage cp "gs://$bucket/$object" "$work/trend.dump" --project "$project_id" --quiet
dump_sha256=$(shasum -a 256 "$work/trend.dump" | cut -d' ' -f1)
dump_bytes=$(wc -c <"$work/trend.dump" | tr -d ' ')

container=$(docker run -d -e POSTGRES_PASSWORD=verify -e POSTGRES_DB=restored "$image")
for _ in $(seq 1 60); do
  docker exec "$container" pg_isready -U postgres -d restored -h 127.0.0.1 >/dev/null 2>&1 && break
  sleep 1
done
docker cp "$work/trend.dump" "$container:/tmp/trend.dump"
# The dump carries its own CREATE SCHEMA public, so the new database's default schema goes first.
docker exec "$container" psql -U postgres -d restored -qc 'DROP SCHEMA public CASCADE'
started=$(date +%s)
docker exec "$container" pg_restore -U postgres --no-owner --no-privileges --exit-on-error -d restored /tmp/trend.dump
restored=$(date +%s)

docker exec "$container" psql -U postgres -d restored -AtF $'\t' -c "
SELECT table_name,
       (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name), false, true, '')))[1]::text
FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1" >"$work/counts.tsv"
repo_migrations=$(find "$root/apps/trend-api/src/trend_agents/storage/migrations" -name '[0-9]*.sql' | wc -l | tr -d ' ')

report=$(python3 - "$bucket" "$object" "$dump_sha256" "$dump_bytes" "$((restored - started))" "$repo_migrations" "$work/counts.tsv" <<'PY'
import datetime, json, sys
bucket, name, sha256, size, seconds, repo_migrations, counts_path = sys.argv[1:]
counts = {table: int(rows) for table, rows in (line.split("\t") for line in open(counts_path).read().splitlines())}
if not counts.get("terms"):
    raise SystemExit("restored backup has no dictionary terms")
print(json.dumps({
    "object": f"gs://{bucket}/{name}",
    "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "dump_sha256": sha256,
    "dump_bytes": int(size),
    "restore_seconds": int(seconds),
    "tables": len(counts),
    "rows": sum(counts.values()),
    "schema_migrations": counts.get("schema_migrations", 0),
    "repository_migrations": int(repo_migrations),
    "table_rows": counts,
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
)
if [ -n "$output" ]; then printf '%s\n' "$report" >"$output"; else printf '%s\n' "$report"; fi
