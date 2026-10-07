"""Publication Jobs require an explicit approved batch and never prepare schemas."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from trend_agents import config
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import db, dictionary_store as ds, publications as pub

spec = importlib.util.spec_from_file_location("publication_job", Path(__file__).resolve().parents[1] / "scripts/publication_job.py")
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


def test_missing_or_invalid_batch_fails_before_connecting(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["publication_job.py"])
    monkeypatch.delenv("PUBLICATION_BATCH_ID", raising=False)
    monkeypatch.setattr(job.db, "connect_existing", lambda: pytest.fail("implicit job connected"))
    with pytest.raises(SystemExit, match="explicit_batch_id_required"):
        job.main()
    monkeypatch.setenv("PUBLICATION_BATCH_ID", "invalid raw input / secret")
    with pytest.raises(SystemExit, match="explicit_batch_id_required"):
        job.main()


@pytest.mark.parametrize("mismatch", ["missing", "checksum", "newer"])
def test_existing_connection_does_not_apply_or_rewrite_mismatched_migrations(mismatch):
    con = db.connect(":memory:")
    schema = con.execute("SELECT current_schema()").fetchone()[0]
    url = config.DATABASE_URL + "?options=-csearch_path%3D" + schema
    try:
        existing = db.connect_existing(url)
        existing.close()
        if mismatch == "missing":
            con.execute("DELETE FROM schema_migrations WHERE version=20")
        elif mismatch == "checksum":
            con.execute("UPDATE schema_migrations SET checksum=? WHERE version=20", ("0" * 64,))
        else:
            future = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] + 1
            con.execute("INSERT INTO schema_migrations VALUES (?,?,?,?)", (future, "future.sql", "0" * 64, ds.now_s()))
        con.commit()
        before = con.execute("SELECT version, checksum FROM schema_migrations ORDER BY version").fetchall()
        with pytest.raises(RuntimeError, match="publication_schema_not_ready"):
            db.connect_existing(url)
        assert con.execute("SELECT version, checksum FROM schema_migrations ORDER BY version").fetchall() == before
    finally:
        con.close()


def test_job_requires_approval_then_replays_same_publication(monkeypatch, capsys):
    con = db.connect(":memory:")
    schema = con.execute("SELECT current_schema()").fetchone()[0]
    url = config.DATABASE_URL + "?options=-csearch_path%3D" + schema
    connect = db.connect_existing
    monkeypatch.setattr(job.db, "connect_existing", lambda: connect(url))
    monkeypatch.setattr(job.db, "connect", lambda *a, **kw: pytest.fail("job must not migrate"))
    monkeypatch.setattr(sys, "argv", ["publication_job.py"])
    monkeypatch.setenv("PUBLICATION_BATCH_ID", "job_batch")
    try:
        ds.upsert_term(con, Term(term_id="t_one", canonical="one", status="verified"))
        draft = MeaningDraft(definition="the originally approved dictionary meaning", origin="origin", nuance="nuance",
                             generations=["20s"], regions=["KR"], self_confidence=0.9)
        old = ds.add_meaning(con, "t_one", draft, "verified_auto", [])
        b = pub.ChangeBatch(batch_id="job_batch", snapshot_id="s", snapshot_sha256="a" * 64,
                            model_id="mock", prompt_version="p", rule_version="r", items=[
                                pub.ChangeItem(term_id="t_one", expected_meaning_id=old.meaning_id,
                                               meaning=draft.model_copy(update={"definition": "a newly proposed dictionary meaning"}))])
        staged = pub.stage(con, b)
        with pytest.raises(SystemExit, match="not_approved"):
            job.main()
        assert ds.current_meaning(con, "t_one").meaning_id == old.meaning_id
        pub.review(con, b.batch_id, staged["payload_sha256"], "reviewer", approve=True)
        job.main()
        first = json.loads(capsys.readouterr().out)
        job.main()
        assert json.loads(capsys.readouterr().out) == first
        assert con.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 1
    finally:
        con.close()


@pytest.mark.parametrize("message,code", [("private connection credentials and generated output", "publication_job_failed"),
                                         ("publication_schema_not_ready", "publication_schema_not_ready")])
def test_unexpected_job_failure_never_prints_error_contents(monkeypatch, message, code):
    monkeypatch.setattr(sys, "argv", ["publication_job.py", "--batch-id", "selected"])
    def fail():
        raise RuntimeError(message)
    monkeypatch.setattr(job.db, "connect_existing", fail)
    with pytest.raises(SystemExit, match=f"^{code}$"):
        job.main()
