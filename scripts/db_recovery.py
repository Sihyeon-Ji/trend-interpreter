"""Compare a source database with an isolated restored database without exposing row data."""

import os

from builder_cup.config import Settings
from builder_cup.database import LAB_ROLE, connection

TABLES = {
    "records": "SELECT id, label, created_at FROM lab.records ORDER BY id",
    "workflow_runs": "SELECT * FROM lab.workflow_runs ORDER BY id",
    "workflow_nodes": "SELECT * FROM lab.workflow_nodes ORDER BY run_id, position",
    "schema_migrations": "SELECT * FROM lab.schema_migrations ORDER BY version",
}


def fingerprint(settings: Settings, query: str) -> tuple[int, str]:
    with connection(settings, admin=True) as conn:
        row = conn.execute(
            f"""SELECT count(*) AS count,
                       md5(COALESCE(
                         string_agg(to_jsonb(data)::text, '' ORDER BY to_jsonb(data)::text),
                         ''
                       )) AS digest
                FROM ({query}) AS data"""
        ).fetchone()
    return row["count"], row["digest"]


def permissions(settings: Settings) -> dict:
    with connection(settings, admin=True) as conn:
        return conn.execute(
            """SELECT
                 has_schema_privilege(%s, 'lab', 'USAGE') AS schema_usage,
                 has_schema_privilege(%s, 'lab', 'CREATE') AS schema_create,
                 has_table_privilege(%s, 'lab.records', 'SELECT,INSERT') AS records_use,
                 has_table_privilege(%s, 'lab.records', 'DELETE') AS records_delete,
                 has_table_privilege(%s, 'lab.workflow_runs', 'SELECT,INSERT,UPDATE') AS runs_use,
                 has_table_privilege(%s, 'lab.workflow_runs', 'DELETE') AS runs_delete""",
            (LAB_ROLE, LAB_ROLE, LAB_ROLE, LAB_ROLE, LAB_ROLE, LAB_ROLE),
        ).fetchone()


def main() -> None:
    target_name = os.environ.get("RESTORE_DATABASE", "")
    if not target_name.startswith("builder_cup_restore_"):
        raise SystemExit("FAIL RESTORE_DATABASE must name an isolated restore database")
    source = Settings(_env_file=None)
    target = source.model_copy(update={"database_name": target_name})
    for name, query in TABLES.items():
        source_value = fingerprint(source, query)
        target_value = fingerprint(target, query)
        if source_value != target_value:
            raise RuntimeError(f"Restored {name} fingerprint does not match source")
        print(f"PASS {name}: count={source_value[0]} digest={source_value[1]}")
    expected_permissions = {
        "schema_usage": True,
        "schema_create": False,
        "records_use": True,
        "records_delete": False,
        "runs_use": True,
        "runs_delete": False,
    }
    if permissions(target) != expected_permissions:
        raise RuntimeError("Restored application permissions do not match policy")
    with connection(target) as conn:
        conn.execute("SELECT count(*) FROM lab.records").fetchone()
    print("PASS restored application role access and least-privilege policy")


if __name__ == "__main__":
    main()
