"""Grant a dedicated existing database role only publication-related privileges."""
from __future__ import annotations

import re

from .db import Connection
from .publications import PublicationError

READ_TABLES = (
    "schema_migrations", "publisher_db_roles", "change_batches", "change_items", "publications", "publication_state",
    "terms", "term_aliases", "meanings", "evidences", "translations", "topic_notes", "term_fit", "review_queue",
    "review_history", "board_cache", "usage", "term_timeline", "mentions_weekly", "mentions_weekly_region",
    "mention_samples", "gen_curves", "term_media", "wiki_catalog", "audit_log", "evidence_labels", "trend_queries",
    "trend_explanations", "trend_class", "interpretations", "pipeline_runs", "news", "videos", "edges", "term_pageviews", "shopping_trends",
    "research_log", "search_interest", "term_readings",
)
WRITE_TABLES = {
    "terms": "INSERT, UPDATE",
    "term_aliases": "INSERT, UPDATE, DELETE",
    "meanings": "INSERT, UPDATE",
    "evidences": "INSERT, UPDATE",
    "translations": "INSERT, UPDATE, DELETE",
    "topic_notes": "INSERT, UPDATE, DELETE",
    "term_fit": "INSERT, UPDATE, DELETE",
    "review_queue": "UPDATE",
    "review_history": "INSERT, UPDATE",
    "board_cache": "INSERT, UPDATE, DELETE",
    "change_batches": "UPDATE",
    "publications": "INSERT",
    "publication_state": "INSERT, UPDATE",
    # Invalidate cached user text without reading it.
    "explain_cache": "DELETE",
}


def _restricted_identity(con: Connection, role: str, schema: str) -> None:
    flags = con.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=?", (role,)).fetchone()
    if flags is None or any(flags):
        raise PublicationError("publisher_role_not_restricted")
    if con.execute("SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=?)", (role,)).fetchone():
        raise PublicationError("publisher_role_has_memberships")
    if con.execute("SELECT has_database_privilege(?, current_database(), 'CREATE'), has_schema_privilege(?, ?, 'CREATE')", (role, role, schema)).fetchone() != (False, False):
        raise PublicationError("publisher_role_can_create")
    if con.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname=? AND r.rolname=?", (schema, role)).fetchone():
        raise PublicationError("publisher_role_owns_objects")


def require_role(con: Connection) -> None:
    role, schema = con.execute("SELECT current_user, current_schema()").fetchone()
    _restricted_identity(con, role, schema)
    if not con.execute("SELECT 1 FROM publisher_db_roles WHERE role_name=?", (role,)).fetchone():
        raise PublicationError("publisher_role_not_configured")
    _forbidden_access(con, role, schema)


def _forbidden_access(con: Connection, role: str, schema: str) -> None:
    # copy_approvals (user copy, migration 025) is checked only where the migration has run.
    present = con.execute("SELECT to_regclass(?) IS NOT NULL", (f'"{schema}"."copy_approvals"',)).fetchone()[0]
    for table in ("lookups", "reader_prefs", "gemini_calls", *(("copy_approvals",) if present else ())):
        if con.execute("SELECT has_table_privilege(?, ?, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER') "
                       "OR has_any_column_privilege(?, ?, 'SELECT, INSERT, UPDATE, REFERENCES')",
                       (role, f'"{schema}"."{table}"', role, f'"{schema}"."{table}"')).fetchone()[0]:
            raise PublicationError("publisher_role_has_forbidden_access")
    if con.execute("SELECT has_table_privilege(?, ?, 'SELECT, INSERT, UPDATE, TRUNCATE, REFERENCES, TRIGGER') "
                   "OR has_any_column_privilege(?, ?, 'SELECT, INSERT, UPDATE, REFERENCES')",
                   (role, f'"{schema}"."explain_cache"', role, f'"{schema}"."explain_cache"')).fetchone()[0]:
        raise PublicationError("publisher_role_has_forbidden_access")


def configure(con: Connection, role: str) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role):
        raise PublicationError("invalid_publisher_role")
    schema = con.execute("SELECT current_schema()").fetchone()[0]
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
        raise PublicationError("invalid_publisher_schema")
    with con.transaction():
        _restricted_identity(con, role, schema)
        # Replace only this role's direct grants in the service schema. No PUBLIC or other-role changes.
        con.execute(f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA "{schema}" FROM "{role}"')
        con.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
        for table in READ_TABLES:
            con.execute(f'GRANT SELECT ON "{schema}"."{table}" TO "{role}"')
        for table, privileges in WRITE_TABLES.items():
            con.execute(f'GRANT {privileges} ON "{schema}"."{table}" TO "{role}"')
        con.execute("INSERT INTO publisher_db_roles VALUES (?) ON CONFLICT DO NOTHING", (role,))
        _forbidden_access(con, role, schema)
    return {"role": role, "schema": schema, "read_tables": len(READ_TABLES), "write_tables": len(WRITE_TABLES)}
