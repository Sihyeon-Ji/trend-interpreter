"""Real PostgreSQL role tests separate publication from approval and user-text access."""
import uuid

import psycopg
import pytest

from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import db, dictionary_store as ds, publications as pub, publisher_permissions as permissions


@pytest.fixture
def restricted():
    con = db.connect(":memory:")
    role = "p_" + uuid.uuid4().hex[:16]
    con.execute(f'CREATE ROLE "{role}" NOLOGIN')
    con.commit()
    try:
        permissions.configure(con, role)
        permissions.configure(con, role)
        yield con, role
    finally:
        con.raw.execute("RESET ROLE")
        con.raw.commit()
        con.close()
        cleanup = db.connect()
        cleanup.execute(f'DROP ROLE "{role}"')
        cleanup.commit()
        cleanup.close()


def change(con, name="approved"):
    ds.upsert_term(con, Term(term_id="t_one", canonical="one", status="verified"))
    draft = MeaningDraft(definition="the originally published dictionary meaning", origin="origin", nuance="nuance",
                         generations=["20s"], regions=["KR"], self_confidence=0.9)
    meaning = ds.add_meaning(con, "t_one", draft, "verified_auto", [])
    batch = pub.ChangeBatch(batch_id=name, snapshot_id="s", snapshot_sha256="a" * 64, model_id="mock",
                            prompt_version="p", rule_version="r", items=[pub.ChangeItem(
                                term_id="t_one", expected_meaning_id=meaning.meaning_id,
                                meaning=draft.model_copy(update={"definition": "a newly approved dictionary meaning"}))])
    return pub.stage(con, batch)


def test_restricted_role_can_publish_and_replay_without_owner_privileges(restricted, monkeypatch):
    con, role = restricted
    staged = change(con)
    pub.review(con, "approved", staged["payload_sha256"], "actual-reviewer", approve=True)
    con.execute(f'SET ROLE "{role}"')
    con.commit()
    execute = con.execute
    def traced(sql, params=None):
        try:
            return execute(sql, params)
        except psycopg.errors.InsufficientPrivilege:
            pytest.fail(f"Missing publication privilege for SQL: {sql}", pytrace=False)
    monkeypatch.setattr(con, "execute", traced)
    result = pub.publish(con, "approved")
    assert pub.publish(con, "approved") == result
    assert ds.current_meaning(con, "t_one").verification == "verified_human"
    assert ds.cache_get(con, "board") and ds.cache_get(con, "dashboard")
    assert ds.last_published(con) == result["published_at"]


@pytest.mark.parametrize("sql", [
    "SELECT * FROM lookups", "SELECT * FROM reader_prefs", "SELECT * FROM explain_cache", "SELECT * FROM gemini_calls",
    "SELECT * FROM copy_approvals", "UPDATE copy_approvals SET status='approved'",
    "CREATE TABLE unauthorized (value TEXT)", "ALTER TABLE terms ADD COLUMN unauthorized TEXT",
    "TRUNCATE terms", "UPDATE change_batches SET status='approved', reviewed_by='spoofed'",
    "UPDATE change_items SET item_sha256='changed'", "INSERT INTO publisher_db_roles VALUES ('spoofed')",
])
def test_restricted_role_cannot_read_user_text_create_schema_or_approve(restricted, sql):
    con, role = restricted
    change(con, "draft")
    con.execute(f'SET ROLE "{role}"')
    con.commit()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        con.execute(sql)


def test_batch_guard_cannot_promote_draft_or_rejected_status_even_without_changing_reviewer(restricted):
    con, role = restricted
    staged = change(con, "rejected")
    pub.review(con, "rejected", staged["payload_sha256"], "real-reviewer", approve=False)
    con.execute(f'SET ROLE "{role}"')
    con.commit()
    for status in ("approved", "published", "failed"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="publisher_cannot_review_batches"):
            con.execute("UPDATE change_batches SET status=? WHERE batch_id='rejected'", (status,))
    assert pub.inspect(con, "rejected")["status"] == "rejected"


def test_configuration_refuses_owner_and_privileged_roles_before_granting(restricted):
    con, _ = restricted
    owner = con.execute("SELECT current_user").fetchone()[0]
    with pytest.raises(pub.PublicationError, match="publisher_role_not_restricted"):
        permissions.configure(con, owner)


@pytest.mark.parametrize("grant", ["SELECT ON lookups", "SELECT (text) ON lookups", "SELECT ON explain_cache",
                                   "SELECT ON copy_approvals", "SELECT (copies_json) ON copy_approvals"])
def test_runtime_rejects_added_user_text_privileges_including_column_grants(restricted, grant):
    con, role = restricted
    con.execute(f'GRANT {grant} TO "{role}"')
    con.commit()
    con.execute(f'SET ROLE "{role}"')
    con.commit()
    with pytest.raises(pub.PublicationError, match="publisher_role_has_forbidden_access"):
        permissions.require_role(con)


def test_runtime_rejects_role_membership_added_after_configuration(restricted):
    con, role = restricted
    # pg_monitor is a built-in role; the publisher must have no inherited memberships.
    con.execute(f'GRANT pg_monitor TO "{role}"')
    con.commit()
    con.execute(f'SET ROLE "{role}"')
    con.commit()
    with pytest.raises(pub.PublicationError, match="publisher_role_has_memberships"):
        permissions.require_role(con)


def test_registered_role_cannot_change_approval_identity_or_payload(restricted):
    con, role = restricted
    staged = change(con)
    pub.review(con, "approved", staged["payload_sha256"], "actual-reviewer", approve=True)
    con.execute(f'SET ROLE "{role}"')
    con.commit()
    for column in ("reviewed_by", "payload_json", "payload_sha256", "reviewed_at"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="publisher_cannot_review_batches"):
            con.execute(f"UPDATE change_batches SET {column}='spoofed' WHERE batch_id='approved'")


def test_restricted_publication_failure_rolls_back_and_can_retry(restricted, monkeypatch):
    con, role = restricted
    staged = change(con)
    pub.review(con, "approved", staged["payload_sha256"], "actual-reviewer", approve=True)
    old = ds.current_meaning(con, "t_one").meaning_id
    ds.cache_set(con, "board", "LAST GOOD BOARD")
    refresh = pub.refresh_caches
    def fail_cache(con):
        ds.cache_set(con, "board", "PARTIAL BOARD")
        raise RuntimeError("private generated output")
    monkeypatch.setattr(pub, "refresh_caches", fail_cache)
    con.execute(f'SET ROLE "{role}"')
    con.commit()
    with pytest.raises(pub.PublicationError, match="publication_failed"):
        pub.publish(con, "approved")
    assert pub.inspect(con, "approved")["status"] == "failed"
    assert ds.current_meaning(con, "t_one").meaning_id == old
    assert ds.cache_get(con, "board")[0] == "LAST GOOD BOARD"
    monkeypatch.setattr(pub, "refresh_caches", refresh)
    assert pub.publish(con, "approved")["item_count"] == 1


def test_migration_gives_an_already_registered_role_read_access_to_headword_readings(restricted):
    """026 이전에 등록된 게시 역할도 027 만으로 표제어 읽기를 읽는다(배포 뒤 configure 를 다시 돌리기 전에도 캐시를 만든다)."""
    con, role = restricted
    con.execute(f'REVOKE SELECT ON term_readings FROM "{role}"')
    con.commit()
    sql = (db.MIGRATIONS_DIR / "027_term_readings_publisher_grant.sql").read_text()
    con.raw.execute(sql)
    con.commit()
    assert con.execute("SELECT has_table_privilege(?, 'term_readings', 'SELECT'), has_table_privilege(?, 'term_readings', 'INSERT')",
                       (role, role)).fetchone() == (True, False)


def test_migration_gives_an_already_registered_role_read_access_to_original_names(restricted):
    con, role = restricted
    con.execute(f'REVOKE SELECT ON term_names FROM "{role}"')
    con.commit()
    con.raw.execute((db.MIGRATIONS_DIR / "028_term_names.sql").read_text())
    con.commit()
    assert con.execute("SELECT has_table_privilege(?, 'term_names', 'SELECT'), has_table_privilege(?, 'term_names', 'INSERT')",
                       (role, role)).fetchone() == (True, False)
