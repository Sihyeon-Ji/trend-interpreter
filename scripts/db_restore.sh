#!/bin/sh
set -eu

backup_file=${BACKUP_FILE:-}
restore_database=${RESTORE_DATABASE:-}
database_host=${DATABASE_HOST:-db}
password_file=${DATABASE_ADMIN_PASSWORD_FILE:-/run/db-admin/password}
pgpass_file=/tmp/builder-cup-pgpass

if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
  echo "FAIL set BACKUP_FILE to an existing /backups/*.dump file" >&2
  exit 2
fi
case "$restore_database" in
  builder_cup_restore_*) restore_suffix=${restore_database#builder_cup_restore_} ;;
  *)
    echo "FAIL RESTORE_DATABASE must start with builder_cup_restore_ and use lowercase letters, digits or underscores" >&2
    exit 2
    ;;
esac
case "$restore_suffix" in
  ""|*[!a-z0-9_]*)
    echo "FAIL RESTORE_DATABASE must start with builder_cup_restore_ and use lowercase letters, digits or underscores" >&2
    exit 2
    ;;
esac

umask 077
password=$(cat "$password_file")
printf '%s:%s:*:%s:%s\n' "$database_host" 5432 builder_cup "$password" > "$pgpass_file"
unset password
export PGPASSFILE="$pgpass_file"

if [ -f "$backup_file.sha256" ]; then
  sha256sum -c "$backup_file.sha256"
else
  echo "FAIL checksum file is missing" >&2
  exit 2
fi

exists=$(psql \
  --host "$database_host" \
  --username builder_cup \
  --dbname postgres \
  --tuples-only \
  --no-align \
  --set target="$restore_database" <<'SQL'
SELECT 1 FROM pg_database WHERE datname = :'target';
SQL
)
if [ "$exists" = "1" ]; then
  echo "FAIL restore target already exists; choose a new RESTORE_DATABASE" >&2
  exit 2
fi

createdb --host "$database_host" --username builder_cup "$restore_database"
pg_restore \
  --host "$database_host" \
  --username builder_cup \
  --dbname "$restore_database" \
  --exit-on-error \
  --no-owner \
  --no-acl \
  "$backup_file"

psql --host "$database_host" --username builder_cup --dbname "$restore_database" <<'SQL'
GRANT USAGE ON SCHEMA lab TO builder_lab;
GRANT SELECT, INSERT ON lab.records TO builder_lab;
GRANT SELECT, INSERT, UPDATE ON lab.workflow_runs, lab.workflow_nodes TO builder_lab;
SQL

printf 'PASS restored into new database\nRestore database: %s\nBackup file: %s\n' "$restore_database" "$backup_file"
