"""Load a verified snapshot into an empty PostgreSQL database and compare a restored copy with it.

Runs inside the Compose `check` image through scripts/restore-rehearsal.sh. Output holds table names,
counts and checksums only, never row contents or connection credentials.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_SCRIPT = ROOT / "apps/trend-api/scripts/migrate_sqlite_to_postgres.py"
DATABASE_FILE = "trend-latest.db.gz"
HASH_CHUNK = 1 << 20

COLUMNS_SQL = """
SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
       coalesce(pg_get_expr(d.adbin, d.adrelid), '')
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
WHERE n.nspname = %s AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY 1, 2
"""
CONSTRAINTS_SQL = """
SELECT c.relname, k.conname, pg_get_constraintdef(k.oid)
FROM pg_constraint k
JOIN pg_class c ON c.oid = k.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s
ORDER BY 1, 2
"""
INDEXES_SQL = "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = %s ORDER BY 1, 2"
SEQUENCES_SQL = "SELECT sequencename, last_value FROM pg_sequences WHERE schemaname = %s ORDER BY 1"
TABLES_SQL = "SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY 1"


def load_migration():
    spec = importlib.util.spec_from_file_location("migrate_sqlite_to_postgres", MIGRATION_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def expected_database_hash(manifest: dict) -> str:
    for item in manifest["objects"]:
        if item["name"] == DATABASE_FILE:
            return item["sha256"]
    raise SystemExit(f"manifest has no {DATABASE_FILE}")


def source_counts(sqlite_path: Path, migration) -> dict[str, dict[str, int]]:
    """Expected destination rows per migrated table: source rows minus rows the migration filters out."""
    from trend_agents.storage import db

    with sqlite3.connect(sqlite_path) as src:
        present = {row[0] for row in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {}
        for name in sorted(present & set(db.TABLES) - migration.SKIP - migration.USER_DATA):
            total = src.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            predicate = migration.WHERE.get(name)
            excluded = src.execute(f'SELECT COUNT(*) FROM "{name}" WHERE NOT ({predicate})').fetchone()[0] if predicate else 0
            counts[name] = {"source": total, "excluded": excluded}
    return counts


def load(manifest_path: Path, snapshot_dir: Path, database_url: str) -> dict:
    """Verify the snapshot hash, migrate it with user data excluded and check every migrated table count."""
    from trend_agents.storage import db

    manifest = json.loads(manifest_path.read_text())
    archive = snapshot_dir / DATABASE_FILE
    if sha256(archive) != expected_database_hash(manifest):
        raise SystemExit(f"{DATABASE_FILE} does not match the manifest")
    migration = load_migration()
    with tempfile.TemporaryDirectory() as work:
        sqlite_path = Path(work) / "snapshot.db"
        with gzip.open(archive, "rb") as source, sqlite_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        expected = source_counts(sqlite_path, migration)
        dst = db.connect(url=database_url)
        try:
            migration.migrate(sqlite_path, dst, fresh=True, skip_user_data=True)
            mismatched = {}
            for name, count in expected.items():
                actual = dst.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                count["destination"] = actual
                if actual != count["source"] - count["excluded"]:
                    mismatched[name] = count
            user_rows = {name: dst.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in sorted(migration.USER_DATA)}
        finally:
            dst.close()
    if mismatched or any(user_rows.values()):
        raise SystemExit(json.dumps({"mismatched_tables": mismatched, "user_rows": user_rows}, sort_keys=True))
    return {
        "snapshot_id": manifest["snapshot_id"],
        "database_sha256": expected_database_hash(manifest),
        "migrated_tables": expected,
        "excluded_user_tables": user_rows,
    }


def unqualified(rows: list[tuple], schema: str) -> list[list[str]]:
    """Catalog definitions without the schema prefix, so copies in different schemas compare equal."""
    return [[value.replace(f"{schema}.", "") for value in row] for row in rows]


def fingerprint(conn: psycopg.Connection, schema: str = "public") -> dict:
    """Schema catalog plus an order-independent content checksum for every table in the schema."""
    tables = {}
    for (name,) in conn.execute(TABLES_SQL, (schema,)).fetchall():
        rows, checksum = conn.execute(
            f'SELECT COUNT(*), coalesce(md5(string_agg(md5(t::text), \'\' ORDER BY md5(t::text))), \'\') '
            f'FROM "{schema}"."{name}" t'
        ).fetchone()
        tables[name] = {"rows": rows, "checksum": checksum}
    return {
        "tables": tables,
        "columns": [list(row) for row in conn.execute(COLUMNS_SQL, (schema,)).fetchall()],
        "constraints": unqualified(conn.execute(CONSTRAINTS_SQL, (schema,)).fetchall(), schema),
        "indexes": unqualified(conn.execute(INDEXES_SQL, (schema,)).fetchall(), schema),
        "sequences": [list(row) for row in conn.execute(SEQUENCES_SQL, (schema,)).fetchall()],
    }


def differences(source: dict, restored: dict) -> list[str]:
    found = [f"table {name}" for name in sorted(source["tables"].keys() ^ restored["tables"].keys())]
    found += [f"rows or content of {name}" for name in sorted(source["tables"].keys() & restored["tables"].keys())
              if source["tables"][name] != restored["tables"][name]]
    found += [section for section in ("columns", "constraints", "indexes", "sequences") if source[section] != restored[section]]
    return found


def compare(source_url: str, restored_url: str) -> dict:
    with psycopg.connect(source_url) as source, psycopg.connect(restored_url) as restored:
        expected, actual = fingerprint(source), fingerprint(restored)
    found = differences(expected, actual)
    if found:
        raise SystemExit("restored database differs from the source: " + ", ".join(found))
    return {
        "tables": len(expected["tables"]),
        "rows": sum(table["rows"] for table in expected["tables"].values()),
        "columns": len(expected["columns"]),
        "constraints": len(expected["constraints"]),
        "indexes": len(expected["indexes"]),
        "sequences": len(expected["sequences"]),
        "table_checksums": {name: table["checksum"] for name, table in expected["tables"].items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    load_command = commands.add_parser("load")
    load_command.add_argument("--manifest", type=Path, required=True)
    load_command.add_argument("--snapshot-dir", type=Path, required=True)
    load_command.add_argument("--database-url", default=os.environ.get("LOAD_DATABASE_URL"),
                              help="defaults to LOAD_DATABASE_URL so a Cloud SQL password stays out of the process list")
    compare_command = commands.add_parser("compare")
    compare_command.add_argument("--source-url", required=True)
    compare_command.add_argument("--restored-url", required=True)
    args = parser.parse_args()
    if args.command == "load" and not args.database_url:
        parser.error("load needs --database-url or LOAD_DATABASE_URL")
    if args.command == "load":
        result = load(args.manifest, args.snapshot_dir, args.database_url)
    else:
        result = compare(args.source_url, args.restored_url)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
