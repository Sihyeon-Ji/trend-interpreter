"""Failed audits retry on a schedule without replaying final or human decisions."""
from datetime import datetime, timedelta, timezone

from trend_agents.pipeline import audit
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import db, dictionary_store as ds

NOW = datetime.now(timezone.utc)


def seed(con, tid, verification="verified_auto"):
    ds.upsert_term(con, Term(term_id=tid, canonical=tid, status="verified"))
    return ds.add_meaning(con, tid, MeaningDraft(definition="a usable meaning", origin="origin", nuance="nuance",
                                               generations=["20s"], regions=["KR"], self_confidence=0.9), verification, [])


def log(con, tid, m, action, ago):
    audit._log(con, tid, m.meaning_id, action, [], "test", action)
    con.execute("UPDATE audit_log SET checked_at=? WHERE term_id=?", ((NOW - ago).isoformat(), tid))
    con.commit()


def test_only_due_failures_retry_and_manual_retry_never_selects_final_verdicts():
    con = db.connect(":memory:")
    try:
        for tid, action, ago in [
            ("error_due", "error", timedelta(hours=1)), ("error_recent", "error", timedelta(minutes=59)),
            ("doc_due", "no_doc", timedelta(days=7)), ("doc_recent", "no_doc", timedelta(days=6)),
            ("ok", "ok", timedelta(days=30)), ("flagged", "flagged", timedelta(days=30)),
            ("rewritten", "rewritten", timedelta(days=30)),
        ]:
            log(con, tid, seed(con, tid), action, ago)
        seed(con, "new")
        human = seed(con, "human", "verified_human")
        log(con, "human", human, "error", timedelta(days=30))
        assert {t.term_id for t in audit.targets(con, now=NOW)} == {"new", "error_due", "doc_due"}
        assert {t.term_id for t in audit.targets(con, retry_failed=True, now=NOW)} == {
            "error_due", "error_recent", "doc_due", "doc_recent",
        }
    finally:
        con.close()


def test_model_failure_is_recorded_without_exception_text_and_is_not_immediately_retried(monkeypatch):
    con = db.connect(":memory:")
    try:
        seed(con, "failed")
        monkeypatch.setattr(audit, "documents", lambda *a: [(None, "reference")])

        def fail(*a, **kw):
            raise RuntimeError("private prompt and secret must never be persisted")

        monkeypatch.setattr(audit, "check", fail)
        assert audit.audit_one(con, ds.get_term(con, "failed")) == "error"
        row = con.execute("SELECT action, reasons_json FROM audit_log").fetchone()
        assert row == ("error", '["RuntimeError"]')
        assert audit.targets(con) == []
        assert [t.term_id for t in audit.targets(con, now=NOW + timedelta(hours=2))] == ["failed"]
    finally:
        con.close()


def test_manual_audit_and_selection_protect_human_meanings_and_pending_proposals(monkeypatch):
    con = db.connect(":memory:")
    try:
        seed(con, "human", "verified_human")
        seed(con, "pending")
        ds.queue_review(con, "pending", MeaningDraft(definition="proposal", origin="x", nuance="y", generations=["20s"],
                                                     regions=["KR"], self_confidence=0.9), ["review"], 1, kind="correction")
        monkeypatch.setattr(audit, "documents", lambda *a: (_ for _ in ()).throw(AssertionError("network must not be used")))
        assert audit.targets(con) == []
        assert audit.audit_one(con, ds.get_term(con, "human")) == "skipped"
        assert audit.audit_one(con, ds.get_term(con, "pending")) == "skipped"
    finally:
        con.close()


def test_human_approval_during_document_fetch_stops_the_model(monkeypatch):
    con = db.connect(":memory:")
    try:
        m = seed(con, "race")

        def documents(*a):
            ds.set_verification(con, m.meaning_id, "verified_human", "reviewer")
            return [(None, "reference")]

        monkeypatch.setattr(audit, "documents", documents)
        monkeypatch.setattr(audit, "check", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("model must not be used")))
        assert audit.audit_one(con, ds.get_term(con, "race")) == "skipped"
        assert ds.current_meaning(con, "race").verification == "verified_human"
    finally:
        con.close()


def daemon():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("audit_daemon", Path(__file__).resolve().parents[1] / "scripts/audit_daemon.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manual_retry_requires_one_shot_and_valid_worker_before_connecting(monkeypatch):
    import sys
    import pytest

    module = daemon()
    monkeypatch.setattr(module.db, "connect", lambda: pytest.fail("must reject arguments before opening DB"))
    for args in (["--retry-failures"], ["--workers", "0"], ["--workers", "2", "--worker", "2"]):
        monkeypatch.setattr(sys, "argv", ["audit_daemon.py", *args])
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert exc.value.code == 2


def test_manual_retry_is_one_bounded_batch(monkeypatch):
    import sys
    from types import SimpleNamespace

    module = daemon()
    closed, calls = [], []
    monkeypatch.setattr(sys, "argv", ["audit_daemon.py", "--retry-failures", "--once"])
    monkeypatch.setattr(module.db, "connect", lambda: SimpleNamespace(close=lambda: closed.append(True)))
    monkeypatch.setattr(module, "busy", lambda: False)

    def targets(con, limit, retry_failed):
        assert limit == 10_000 and retry_failed
        return [SimpleNamespace(term_id=f"t{i}") for i in range(30)]

    monkeypatch.setattr(module.audit, "targets", targets)
    monkeypatch.setattr(module.audit, "audit_one", lambda con, t: calls.append(t.term_id) or "error")
    module.main()
    assert len(calls) == 20 and closed == [True]
