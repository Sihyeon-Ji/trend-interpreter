#!/bin/sh
set -eu

umask 077
backup_dir=${BACKUP_DIR:-/backups}
database_host=${DATABASE_HOST:-db}
database_name=${DATABASE_NAME:-builder_cup}
password_file=${DATABASE_ADMIN_PASSWORD_FILE:-/run/db-admin/password}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_file=${BACKUP_FILE:-$backup_dir/builder-cup-$timestamp.dump}
pgpass_file=/tmp/builder-cup-pgpass

mkdir -p "$backup_dir"
case "$backup_file" in
  "$backup_dir"/*.dump) ;;
  *)
    echo "FAIL BACKUP_FILE must be a .dump path under $backup_dir" >&2
    exit 2
    ;;
esac
if [ -e "$backup_file" ] || [ -e "$backup_file.sha256" ]; then
  echo "FAIL backup path already exists; choose a new BACKUP_FILE" >&2
  exit 2
fi
password=$(cat "$password_file")
printf '%s:%s:%s:%s:%s\n' "$database_host" 5432 "$database_name" builder_cup "$password" > "$pgpass_file"
unset password
export PGPASSFILE="$pgpass_file"

pg_dump \
  --host "$database_host" \
  --username builder_cup \
  --dbname "$database_name" \
  --format custom \
  --no-owner \
  --no-acl \
  --file "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"

printf 'PASS backup created\nBackup file: %s\nChecksum file: %s\n' "$backup_file" "$backup_file.sha256"
