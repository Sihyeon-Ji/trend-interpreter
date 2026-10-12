"""Carry the production database's human decisions and user data onto a database freshly loaded from a newer snapshot.

Runs inside the Compose `check` image through scripts/refresh-production-db.sh (Plan 19). The production database is
opened read-only. Reports hold table names, counts and keys only, never row contents or connection credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from trend_agents import config
from trend_agents.storage import db
from trend_agents.storage import dictionary_store as ds

# A human-decided term keeps production's rows in these tables; the snapshot's automatic rows for it are dropped.
REPLACED = ("terms", "meanings", "review_queue", "translations", "topic_notes", "term_fit")
# Evidence a reviewer cited may exist only in production; the snapshot's newer evidence stays.
MERGED = ("evidences",)
# Written only by the service, so production is the only source. gemini_calls holds the monthly spending ledger.
PUBLICATION_TABLES = ("change_batches", "change_items", "publications", "publication_state")
# Copy approval records (migration 025): reviewers' decisions on marketing copy, written only on production.
APPROVAL_TABLES = ("copy_approvals",)
# Tables an older database may not have yet; their keys count as empty there.
OPTIONAL_TABLES = (*PUBLICATION_TABLES, *APPROVAL_TABLES)
CARRIED = ("review_history", "gemini_calls", "reader_prefs", "lookups", "explain_cache", *PUBLICATION_TABLES, *APPROVAL_TABLES)
# Ad-fit tags set by a person or re-tagged with Gemini on production (fit_backfill --gemini, Plan 07) are newer than the
# snapshot's local-model tags, so production's rows win for every term the new database still has.
FIT_CARRIED_WHERE = "(model LIKE 'human:%' OR model LIKE 'gemini-%')"

HUMAN_TERMS_SQL = (
    "SELECT DISTINCT term_id FROM review_history",
    "SELECT term_id FROM review_queue WHERE decision IS NOT NULL AND COALESCE(decided_by, 'gate') <> 'gate'",
    "SELECT DISTINCT term_id FROM meanings WHERE verification = 'verified_human'",
    "SELECT term_id FROM terms WHERE json::jsonb ->> 'risk_decided_by' IS NOT NULL",
)
# Keys that must all reach the new database; the snapshot may add more of its own.
KEYS_SQL = {
    "review_history": "SELECT term_id, queued_at, decided_at FROM review_history",
    "verified_human": "SELECT meaning_id FROM meanings WHERE verification = 'verified_human'",
    "risk_decided": "SELECT term_id, json::jsonb ->> 'risk_human', json::jsonb ->> 'risk_decided_at' FROM terms "
                    "WHERE json::jsonb ->> 'risk_decided_by' IS NOT NULL",
    "retired": "SELECT term_id FROM terms WHERE status = 'retired' AND term_id IN (SELECT term_id FROM review_history)",
    "fit_human": "SELECT term_id, meaning_id, json FROM term_fit WHERE model LIKE 'human:%'",
    "gemini_calls": "SELECT day, count FROM gemini_calls",
    "reader_prefs": "SELECT reader, updated_at FROM reader_prefs",
    "change_batches": "SELECT batch_id, payload_sha256, status, reviewed_by, reviewed_at FROM change_batches",
    "change_items": "SELECT batch_id, term_id, item_sha256, baseline_sha256 FROM change_items",
    "publications": "SELECT publication_id, batch_id, payload_sha256, published_at FROM publications",
    "publication_state": "SELECT singleton, publication_id FROM publication_state",
    "copy_approvals": "SELECT approval_id, status, decided_by, decided_at FROM copy_approvals",
}
COLUMNS_SQL = ("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = ? "
               "ORDER BY ordinal_position")
PRIMARY_KEY_SQL = """
SELECT a.attname FROM pg_index i
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
WHERE i.indisprimary AND n.nspname = current_schema() AND c.relname = ?
ORDER BY array_position(i.indkey, a.attnum)
"""


def _has_table(con: db.Connection, name: str) -> bool:
    return bool(con.execute("SELECT to_regclass(?)", (name,)).fetchone()[0])


def human_terms(con: db.Connection) -> set[str]:
    ids = {row[0] for sql in HUMAN_TERMS_SQL for row in con.execute(sql).fetchall()}
    if _has_table(con, "change_items"):
        ids.update(r[0] for r in con.execute("SELECT DISTINCT i.term_id FROM change_items i JOIN change_batches b "
                                            "ON b.batch_id=i.batch_id WHERE b.status='published'"))
    return ids


def _columns(src: db.Connection, dst: db.Connection, table: str) -> list[str]:
    """Columns both databases have, so a migration that only one side has applied cannot break the copy."""
    target = {row[0] for row in dst.execute(COLUMNS_SQL, (table,)).fetchall()}
    return [row[0] for row in src.execute(COLUMNS_SQL, (table,)).fetchall() if row[0] in target]


def _copy(src: db.Connection, dst: db.Connection, table: str, conflict: str, term_ids: list[str] | None = None) -> int:
    cols = _columns(src, dst, table)
    if not cols:
        return 0
    names = ", ".join(cols)
    where = " WHERE term_id = ANY(?)" if term_ids is not None else ""
    rows = src.execute(f"SELECT {names} FROM {table}{where}", (term_ids,) if term_ids is not None else ()).fetchall()
    if conflict == "update":
        key = [row[0] for row in dst.execute(PRIMARY_KEY_SQL, (table,)).fetchall()]
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in key)
        conflict_sql = f" ON CONFLICT ({', '.join(key)}) DO " + (f"UPDATE SET {updates}" if updates else "NOTHING")
    else:
        conflict_sql = " ON CONFLICT DO NOTHING"
    dst.executemany(f"INSERT INTO {table} ({names}) VALUES ({', '.join('?' * len(cols))}){conflict_sql}", rows)
    return len(rows)


def overlay(src: db.Connection, dst: db.Connection) -> dict:
    """Idempotent: running it again after more production decisions brings the new database up to date."""
    ids = sorted(human_terms(src))
    copied: dict[str, int] = {}
    for table in REPLACED:
        dst.execute(f"DELETE FROM {table} WHERE term_id = ANY(?)", (ids,))
        copied[table] = _copy(src, dst, table, "nothing", ids)
    for table in MERGED:
        copied[table] = _copy(src, dst, table, "nothing", ids)
    for table in CARRIED:
        copied[table] = _copy(src, dst, table, "update")
    copied["term_fit_carried"] = carry_fits(src, dst)
    dst.commit()
    ds.rebuild_aliases(dst)
    return {"human_terms": len(ids), "copied_rows": copied, "risk_rejudged": rejudge_risk(dst, ids)}


def carry_fits(src: db.Connection, dst: db.Connection) -> int:
    present = {row[0] for row in dst.execute("SELECT term_id FROM terms").fetchall()}
    cols = _columns(src, dst, "term_fit")
    names = ", ".join(cols)
    rows = [r for r in src.execute(f"SELECT {names} FROM term_fit WHERE {FIT_CARRIED_WHERE}").fetchall()
            if r[cols.index("term_id")] in present]
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "term_id")
    dst.executemany(f"INSERT INTO term_fit ({names}) VALUES ({', '.join('?' * len(cols))}) "
                    f"ON CONFLICT (term_id) DO UPDATE SET {updates}", rows)
    return len(rows)


def rejudge_risk(con: db.Connection, term_ids: list[str]) -> int:
    """Rule risk for the terms whose rows the overlay just replaced. Replacing a whole `terms` row also brings back
    production's old automatic risk fields: the overlay right before the 10-05 switch returned all 106 human-touched
    terms to their 09-30 judgement after recompute had run. Rule-only and model-free; risk.apply keeps a stored human
    decision (risk_human) as the actual level."""
    from trend_agents.pipeline import risk

    done = 0
    for term_id in term_ids:
        term = ds.get_term(con, term_id)
        if term and term.status == "verified":
            risk.apply(con, term)
            done += 1
    con.commit()
    return done


def _keys(con: db.Connection) -> dict[str, set[tuple]]:
    return {name: {tuple(row) for row in con.execute(sql).fetchall()}
            if name not in OPTIONAL_TABLES or _has_table(con, name) else set() for name, sql in KEYS_SQL.items()}


def counts(con: db.Connection) -> dict[str, int]:
    return {name: len(keys) for name, keys in _keys(con).items()} | {
        "terms": con.execute("SELECT COUNT(*) FROM terms").fetchone()[0]}


def compare(src: db.Connection, dst: db.Connection) -> dict:
    """Every human decision and ledger row in production must exist unchanged in the new database."""
    source, target = _keys(src), _keys(dst)
    missing = {name: len(source[name] - target[name]) for name in KEYS_SQL}
    return {"source": counts(src), "target": counts(dst), "missing": missing,
            "differences": [name for name, n in missing.items() if n]}


def recompute(con: db.Connection) -> dict:
    """Rule-only stages on the new database: lifecycle, rule risk, board and dashboard. Never calls a model."""
    if config.MODEL_REQUESTS_ENABLED:
        raise SystemExit("recompute must run with MODEL_REQUESTS_ENABLED=false")
    from trend_agents.pipeline import board, dashboard, risk, track

    done = {"track": track.run(con)["track"].count}
    terms = ds.list_terms(con, ("verified",))
    for term in terms:
        risk.apply(con, term)
    con.commit()
    done["risk"] = len(terms)
    done["board"] = board.run(con)["board"].count
    done["dashboard"] = dashboard.run(con)["dashboard"].count
    lifecycle = dict(con.execute("SELECT lifecycle, COUNT(*) FROM terms WHERE status = 'verified' GROUP BY 1").fetchall())
    return {"recomputed": done, "verified_lifecycle": lifecycle}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("command", choices=("overlay", "compare", "recompute"))
    args = parser.parse_args()
    # URLs come from the environment so passwords stay out of the process list.
    target = db.connect(url=os.environ["TARGET_DATABASE_URL"])
    try:
        if args.command == "recompute":
            result = recompute(target)
        else:
            source = db.connect_read_only(os.environ["SOURCE_DATABASE_URL"])
            try:
                result = overlay(source, target) | compare(source, target) if args.command == "overlay" else compare(source, target)
            finally:
                source.close()
    finally:
        target.close()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n")
    if args.command != "recompute" and result["differences"]:
        raise SystemExit("new database is missing production decisions: " + ", ".join(result["differences"]))


if __name__ == "__main__":
    main()
