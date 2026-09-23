import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from pydantic import BaseModel

from builder_cup.config import Settings

CONNECT_TIMEOUT_SECONDS = 3
STATEMENT_TIMEOUT_MS = 3000
LAB_ROLE = "builder_lab"
LAB_RECORD_LABEL = "PostgreSQL persistence exercise"
MIGRATION_PATTERN = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")
MIGRATIONS_DIR = Path(__file__).with_name("migrations")


class DatabaseUnavailable(Exception):
    pass


class DatabaseMigrationError(Exception):
    pass


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    checksum: str
    sql: str


class LabRecord(BaseModel):
    id: UUID
    label: str
    created_at: datetime


@contextmanager
def connection(
    settings: Settings, *, admin: bool = False
) -> Iterator[psycopg.Connection[dict[str, Any]]]:
    password_path = (
        settings.database_admin_password_file if admin else settings.database_password_file
    )
    try:
        password = Path(password_path).read_text().strip()
        with psycopg.connect(
            host=settings.database_host,
            dbname=settings.database_name,
            user="builder_cup" if admin else LAB_ROLE,
            password=password,
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
            row_factory=dict_row,
        ) as conn:
            yield conn
    except (OSError, psycopg.Error) as exc:
        raise DatabaseUnavailable("database_unavailable") from exc


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_PATTERN.fullmatch(path.name)
        if match is None:
            raise DatabaseMigrationError(f"Invalid migration filename: {path.name}")
        raw = path.read_bytes()
        migrations.append(
            Migration(
                version=match.group(1),
                name=match.group(2),
                checksum=hashlib.sha256(raw).hexdigest(),
                sql=raw.decode(),
            )
        )
    versions = [migration.version for migration in migrations]
    if not migrations or len(versions) != len(set(versions)):
        raise DatabaseMigrationError("Migration versions must be present and unique")
    return migrations


def _bootstrap(settings: Settings) -> None:
    with connection(settings, admin=True) as conn:
        conn.execute("SET LOCAL log_min_error_statement = 'panic'")
        conn.execute("CREATE SCHEMA IF NOT EXISTS lab")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS lab.schema_migrations (
                version text PRIMARY KEY,
                name text NOT NULL,
                checksum text NOT NULL CHECK (length(checksum) = 64),
                applied_at timestamptz NOT NULL DEFAULT now()
            )"""
        )
        role = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (LAB_ROLE,)).fetchone()
        if role is None:
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(LAB_ROLE)))
        password = Path(settings.database_password_file).read_text().strip()
        conn.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(LAB_ROLE), sql.Literal(password)
            )
        )


def apply_migration(settings: Settings, migration: Migration) -> None:
    try:
        with connection(settings, admin=True) as conn:
            applied = conn.execute(
                "SELECT checksum FROM lab.schema_migrations WHERE version = %s",
                (migration.version,),
            ).fetchone()
            if applied is not None:
                if applied["checksum"] != migration.checksum:
                    raise DatabaseMigrationError(
                        f"Migration checksum mismatch: {migration.version}"
                    )
                return
            conn.execute(migration.sql)
            conn.execute(
                """INSERT INTO lab.schema_migrations (version, name, checksum)
                   VALUES (%s, %s, %s)""",
                (migration.version, migration.name, migration.checksum),
            )
    except DatabaseUnavailable as exc:
        raise DatabaseMigrationError(f"Migration failed: {migration.version}") from exc


def _grant_permissions(settings: Settings) -> None:
    with connection(settings, admin=True) as conn:
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA lab TO {}").format(sql.Identifier(LAB_ROLE)))
        conn.execute(
            sql.SQL("GRANT SELECT, INSERT ON lab.records TO {}").format(sql.Identifier(LAB_ROLE))
        )
        conn.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE ON lab.workflow_runs, lab.workflow_nodes TO {}"
            ).format(sql.Identifier(LAB_ROLE))
        )


def initialize(settings: Settings) -> None:
    _bootstrap(settings)
    for migration in discover_migrations():
        apply_migration(settings, migration)
    _grant_permissions(settings)


def create_record(settings: Settings) -> LabRecord:
    with connection(settings) as conn:
        row = conn.execute(
            "INSERT INTO lab.records (id, label) VALUES (%s, %s) RETURNING id, label, created_at",
            (uuid4(), LAB_RECORD_LABEL),
        ).fetchone()
        return LabRecord.model_validate(row)


def read_record(settings: Settings, record_id: UUID) -> LabRecord | None:
    with connection(settings) as conn:
        row = conn.execute(
            "SELECT id, label, created_at FROM lab.records WHERE id = %s", (record_id,)
        ).fetchone()
        return LabRecord.model_validate(row) if row else None
