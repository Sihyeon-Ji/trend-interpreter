from collections.abc import Iterator
from contextlib import contextmanager
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


class DatabaseUnavailable(Exception):
    pass


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


def initialize(settings: Settings) -> None:
    with connection(settings, admin=True) as conn:
        # Keep role credential updates out of server error statement logs.
        conn.execute("SET LOCAL log_min_error_statement = 'panic'")
        conn.execute("CREATE SCHEMA IF NOT EXISTS lab")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS lab.records (
                id uuid PRIMARY KEY,
                label text NOT NULL CHECK (length(label) BETWEEN 1 AND 100),
                created_at timestamptz NOT NULL DEFAULT now()
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
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA lab TO {}").format(sql.Identifier(LAB_ROLE)))
        conn.execute(
            sql.SQL("GRANT SELECT, INSERT ON lab.records TO {}").format(sql.Identifier(LAB_ROLE))
        )


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
