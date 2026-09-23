"""Verify migration replay and atomic failure behavior against the selected local database."""

from builder_cup.config import Settings
from builder_cup.database import (
    DatabaseMigrationError,
    DatabaseUnavailable,
    Migration,
    apply_migration,
    connection,
    discover_migrations,
    initialize,
)

FAILURE_VERSION = "999"
FAILURE_TABLE = "lab.plan04_failure_probe"


def snapshot(settings: Settings) -> dict:
    with connection(settings, admin=True) as conn:
        return {
            "versions": conn.execute(
                "SELECT version, checksum FROM lab.schema_migrations ORDER BY version"
            ).fetchall(),
            "records": conn.execute("SELECT count(*) AS count FROM lab.records").fetchone()[
                "count"
            ],
            "runs": conn.execute("SELECT count(*) AS count FROM lab.workflow_runs").fetchone()[
                "count"
            ],
            "nodes": conn.execute("SELECT count(*) AS count FROM lab.workflow_nodes").fetchone()[
                "count"
            ],
        }


def verify_failed_transaction(settings: Settings) -> None:
    try:
        with connection(settings, admin=True) as conn:
            conn.execute(f"CREATE TABLE {FAILURE_TABLE} (id integer PRIMARY KEY)")
            conn.execute(
                """INSERT INTO lab.schema_migrations (version, name, checksum)
                   VALUES (%s, %s, %s)""",
                (FAILURE_VERSION, "failure_probe", "0" * 64),
            )
            conn.execute("SELECT 1 / 0")
    except DatabaseUnavailable:
        pass
    with connection(settings, admin=True) as conn:
        version = conn.execute(
            "SELECT 1 FROM lab.schema_migrations WHERE version = %s", (FAILURE_VERSION,)
        ).fetchone()
        table = conn.execute("SELECT to_regclass(%s) AS table_name", (FAILURE_TABLE,)).fetchone()
    if version is not None or table["table_name"] is not None:
        raise RuntimeError("Failed migration transaction left schema or version state")


def verify_checksum_drift(settings: Settings) -> None:
    migration = discover_migrations()[0]
    changed = Migration(
        version=migration.version,
        name=migration.name,
        checksum="0" * 64,
        sql=migration.sql,
    )
    try:
        apply_migration(settings, changed)
    except DatabaseMigrationError as exc:
        if "checksum mismatch" not in str(exc):
            raise
    else:
        raise RuntimeError("Changed applied migration checksum was accepted")


def main() -> None:
    settings = Settings()
    initialize(settings)
    before = snapshot(settings)
    initialize(settings)
    after = snapshot(settings)
    expected = [migration.version for migration in discover_migrations()]
    if before != after or [row["version"] for row in after["versions"]] != expected:
        raise RuntimeError("Migration replay changed data or version state")
    verify_checksum_drift(settings)
    verify_failed_transaction(settings)
    print(
        "PASS: ordered migrations, checksum drift, replay safety, data retention and rollback; "
        f"records={after['records']} runs={after['runs']} nodes={after['nodes']}"
    )


if __name__ == "__main__":
    main()
