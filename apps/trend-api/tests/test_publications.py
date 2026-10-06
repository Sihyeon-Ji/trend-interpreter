"""Approved batches publish atomically with current-version and human-decision guards."""
from datetime import datetime, timezone

import psycopg
import pytest

from trend_agents.schemas import Evidence, MeaningDraft, MeaningText, MemeFit, Term
from trend_agents.storage import db, dictionary_store as ds, publications as pub


def draft(text="a specific new meme usage definition"):
    return MeaningDraft(definition=text, origin="a documented origin", nuance="a friendly reaction", generations=["20s"],
                        regions=["KR"], self_confidence=0.9)


def evidence(tid):
    return Evidence(evidence_id="e_" + tid, kind="wiki", url="https://namu.wiki/w/" + tid, title=tid,
                    source_domain="namu.wiki", observed_at=datetime.now(timezone.utc), excerpt=tid + " is a meme")


def seed(con, tid="t_one", verification="verified_auto"):
    ds.upsert_term(con, Term(term_id=tid, canonical=tid, status="verified"))
    m = ds.add_meaning(con, tid, draft("the previously published meme definition"), verification, [])
    ds.add_evidences(con, tid, [evidence(tid)])
    return m


def batch(con, name="batch_one", tids=("t_one",), translations=False):
    items = []
    for tid in tids:
        m = ds.current_meaning(con, tid)
        change = draft()
        items.append(pub.ChangeItem(term_id=tid, expected_meaning_id=m.meaning_id, meaning=change,
                                    citations=[evidence(tid).url], derived_from_sha256=pub.digest(change),
                                    translations={"en": MeaningText(definition="translated meaning", origin="origin", nuance="nuance")} if translations else {}))
    return pub.ChangeBatch(batch_id=name, snapshot_id="fixed-snapshot", snapshot_sha256="a" * 64,
                           model_id="local:gemma-test", prompt_version="prompt-v1", rule_version="rules-v1", items=items)


def approved(con, b):
    result = pub.stage(con, b)
    pub.review(con, b.batch_id, result["payload_sha256"], "reviewer", approve=True)


@pytest.mark.parametrize("output", ["note", "fit"])
def test_derived_only_batch_preserves_team_outputs(output):
    con = db.connect(":memory:")
    try:
        m = seed(con)
        fit = MemeFit(feelings=["joy"], uses=["reaction"], voice="playful")
        note = pub.CountryNote(local_name="t_one", what_changed={"ko": "local usage"},
                               self_confidence=0.6, evidence_ids=["e_t_one"])
        if output == "note":
            ds.set_topic_note(con, "t_one", "KR", pub.canonical(note), "team")
        else:
            ds.set_fit(con, "t_one", m.meaning_id, fit, "team")
        item = pub.ChangeItem(term_id="t_one", expected_meaning_id=m.meaning_id,
                              country_notes={"KR": note} if output == "note" else {},
                              fit=fit if output == "fit" else None,
                              derived_from_sha256=pub.digest(m.model_dump(include=set(MeaningDraft.model_fields), mode="json")))
        b = batch(con).model_copy(update={"items": [item]})
        with pytest.raises(pub.PublicationError, match="human_derived_output"):
            pub.stage(con, b)
        assert con.execute("SELECT COUNT(*) FROM change_batches").fetchone()[0] == 0
    finally:
        con.close()


def test_new_terms_with_colliding_aliases_cannot_enter_same_batch():
    from pydantic import ValidationError

    items = [pub.ChangeItem(term_id=tid, expected_meaning_id=None, meaning=draft(),
                            new_term=pub.NewTerm(canonical=tid, lang="en", aliases=["same alias"]))
             for tid in ("first", "second")]
    with pytest.raises(ValidationError, match="unambiguous"):
        pub.ChangeBatch(batch_id="colliding", snapshot_id="s", snapshot_sha256="a" * 64,
                        model_id="mock", prompt_version="p", rule_version="r", items=items)


def test_legacy_commits_are_atomic_and_swallowed_database_errors_abort():
    con = db.connect(":memory:")
    try:
        with pytest.raises(RuntimeError, match="injected"):
            with con.transaction():
                seed(con)
                ds.cache_set(con, "board", "new")
                raise RuntimeError("injected")
        assert ds.get_term(con, "t_one") is None and ds.cache_get(con, "board") is None
        with pytest.raises(RuntimeError, match="failed"):
            with con.transaction():
                seed(con)
                try:
                    con.execute("SELECT * FROM no_such_table")
                except psycopg.Error:
                    pass
        assert ds.get_term(con, "t_one") is None
        seed(con)
        assert ds.get_term(con, "t_one") is not None
    finally:
        con.close()


def test_stage_is_private_immutable_and_review_requires_seen_hash():
    con = db.connect(":memory:")
    try:
        old = seed(con)
        b = batch(con)
        staged = pub.stage(con, b)
        assert ds.current_meaning(con, "t_one").meaning_id == old.meaning_id
        assert pub.stage(con, b) == staged
        altered = b.model_copy(update={"rule_version": "changed"})
        with pytest.raises(pub.PublicationError, match="batch_id_conflict"):
            pub.stage(con, altered)
        with pytest.raises(pub.PublicationError, match="review_conflict"):
            pub.review(con, b.batch_id, "b" * 64, "reviewer", approve=True)
        with pytest.raises(pub.PublicationError, match="not_approved"):
            pub.publish(con, b.batch_id)
        assert pub.inspect(con, b.batch_id)["status"] == "draft"
    finally:
        con.close()


def test_publication_updates_versions_translations_caches_and_metadata_once(monkeypatch):
    from fastapi.testclient import TestClient
    from trend_agents.api import app as api

    con = db.connect(":memory:")
    try:
        monkeypatch.setattr(api, "_con", con)
        client = TestClient(api.app)
        assert client.get("/meta").json()["publication_id"] is None
        old = seed(con)
        b = batch(con, translations=True)
        approved(con, b)
        result = pub.publish(con, b.batch_id)
        current = ds.current_meaning(con, "t_one")
        assert current.version == old.version + 1 and current.verification == "verified_human"
        assert ds.list_meanings(con, "t_one")[0].valid_to is not None
        assert ds.get_translation(con, "t_one", "en").definition == "translated meaning"
        assert ds.cache_get(con, "board") and ds.cache_get(con, "dashboard")
        assert ds.last_published(con) == result["published_at"]
        meta = client.get("/meta").json()
        assert meta["publication_id"] == result["publication_id"]
        assert meta["last_run"] == result["published_at"] and meta["stale"] is False
        assert pub.publish(con, b.batch_id) == result
        assert len(ds.list_meanings(con, "t_one")) == 2
        assert con.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 1
    finally:
        con.close()


def test_failed_second_item_or_cache_keeps_entire_last_good_snapshot(monkeypatch):
    con = db.connect(":memory:")
    try:
        originals = {tid: seed(con, tid).meaning_id for tid in ("t_one", "t_two")}
        ds.cache_set(con, "board", "OLD BOARD")
        b = batch(con, tids=("t_one", "t_two"))
        approved(con, b)
        apply = pub._apply

        def fail_second(con, b, item, by):
            apply(con, b, item, by)
            if item.term_id == "t_two":
                raise RuntimeError("sensitive generated output")

        monkeypatch.setattr(pub, "_apply", fail_second)
        with pytest.raises(pub.PublicationError, match="publication_failed"):
            pub.publish(con, b.batch_id)
        assert {tid: ds.current_meaning(con, tid).meaning_id for tid in originals} == originals
        assert ds.cache_get(con, "board")[0] == "OLD BOARD"
        assert con.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 0
        assert pub.inspect(con, b.batch_id)["failure_code"] == "RuntimeError"
        monkeypatch.setattr(pub, "_apply", apply)

        def fail_cache(con):
            ds.cache_set(con, "board", "PARTIAL BOARD")
            raise ValueError("private output")

        monkeypatch.setattr(pub, "refresh_caches", fail_cache)
        with pytest.raises(pub.PublicationError):
            pub.publish(con, b.batch_id)
        assert ds.cache_get(con, "board")[0] == "OLD BOARD"
        assert {tid: ds.current_meaning(con, tid).meaning_id for tid in originals} == originals
    finally:
        con.close()


@pytest.mark.parametrize("change,code", [("version", "meaning_conflict"), ("human", "human_meaning"),
                                          ("risk", "baseline_conflict"), ("retired", "human_retired")])
def test_changes_after_approval_conflict_without_overwriting_people(change, code):
    con = db.connect(":memory:")
    try:
        m = seed(con)
        b = batch(con)
        approved(con, b)
        if change == "version":
            ds.add_meaning(con, "t_one", draft("a concurrent new meaning definition"), "verified_auto", [])
        elif change == "human":
            ds.set_verification(con, m.meaning_id, "verified_human", "person")
        else:
            t = ds.get_term(con, "t_one")
            if change == "risk":
                t.risk_human = "avoid"
            else:
                t.status = "retired"
            ds.upsert_term(con, t, human=True)
        before = ds.current_meaning(con, "t_one").model_dump()
        with pytest.raises(pub.PublicationError, match=code):
            pub.publish(con, b.batch_id)
        assert ds.current_meaning(con, "t_one").model_dump() == before
        assert pub.inspect(con, b.batch_id)["status"] == "conflict"
    finally:
        con.close()


def test_new_term_is_visible_only_after_review_and_publication():
    con = db.connect(":memory:")
    try:
        item = pub.ChangeItem(term_id="brand_new", expected_meaning_id=None,
                              new_term=pub.NewTerm(canonical="brand_new", lang="en"), meaning=draft(),
                              evidences=[evidence("brand_new")], citations=[evidence("brand_new").url])
        b = pub.ChangeBatch(batch_id="new-term", snapshot_id="fixed", snapshot_sha256="a" * 64, model_id="local:test",
                            prompt_version="v1", rule_version="v1", items=[item])
        staged = pub.stage(con, b)
        assert ds.get_term(con, "brand_new") is None
        pub.review(con, b.batch_id, staged["payload_sha256"], "reviewer", approve=True)
        assert ds.get_term(con, "brand_new") is None
        pub.publish(con, b.batch_id)
        assert ds.get_term(con, "brand_new").status == "verified"
        assert ds.current_meaning(con, "brand_new").verification == "verified_human"
    finally:
        con.close()


def test_derived_outputs_require_matching_source_and_preserve_team_translation():
    con = db.connect(":memory:")
    try:
        seed(con)
        b = batch(con, translations=True)
        b.items[0].derived_from_sha256 = "b" * 64
        with pytest.raises(pub.PublicationError, match="derived_version_conflict"):
            pub.stage(con, b)
        b.items[0].derived_from_sha256 = pub.digest(b.items[0].meaning)
        ds.set_translation(con, "t_one", "ko", MeaningText(definition="a person wrote this", origin="x", nuance="y"), "team")
        with pytest.raises(pub.PublicationError, match="human_derived_output"):
            pub.stage(con, b)
        assert ds.get_translation(con, "t_one", "ko").definition == "a person wrote this"
    finally:
        con.close()


def test_gate_exception_requires_explicit_reviewer_decision_and_rejection_never_publishes():
    con = db.connect(":memory:")
    try:
        seed(con)
        con.execute("DELETE FROM evidences")
        con.commit()
        b = batch(con)
        b.items[0].citations = []
        b.items[0].meaning.self_confidence = 0.1
        staged = pub.stage(con, b)
        assert pub.inspect(con, b.batch_id)["validation"]["t_one"]
        with pytest.raises(pub.PublicationError, match="gate_review_required"):
            pub.review(con, b.batch_id, staged["payload_sha256"], "reviewer", approve=True)
        pub.review(con, b.batch_id, staged["payload_sha256"], "reviewer", approve=False)
        with pytest.raises(pub.PublicationError, match="not_approved"):
            pub.publish(con, b.batch_id)
        assert pub.inspect(con, b.batch_id)["status"] == "rejected"
    finally:
        con.close()


def test_concurrent_duplicate_publication_commits_exactly_once():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    con = db.connect(":memory:")
    try:
        seed(con)
        b = batch(con)
        approved(con, b)
        schema = con.execute("SELECT current_schema()").fetchone()[0]
        ready = Barrier(2)

        def publish():
            other = db.connect()
            try:
                other.execute("SELECT set_config('search_path', ?, false)", (schema,))
                ready.wait(timeout=10)
                return pub.publish(other, b.batch_id)
            finally:
                other.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(publish) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        assert results[0] == results[1]
        assert con.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 1
        assert len(ds.list_meanings(con, "t_one")) == 2
    finally:
        con.close()


def test_failed_new_batch_keeps_active_publication_and_caches(monkeypatch):
    con = db.connect(":memory:")
    try:
        seed(con)
        first = batch(con)
        approved(con, first)
        good = pub.publish(con, first.batch_id)
        old_board = ds.cache_get(con, "board")
        current = ds.current_meaning(con, "t_one")
        source = current.model_dump(include=set(MeaningDraft.model_fields), mode="json")
        second = first.model_copy(update={"batch_id": "translation-only", "items": [pub.ChangeItem(
            term_id="t_one", expected_meaning_id=current.meaning_id, derived_from_sha256=pub.digest(source),
            translations={"en": MeaningText(definition="new approved translation", origin="origin", nuance="nuance")})]})
        approved(con, second)
        monkeypatch.setattr(pub, "refresh_caches", lambda con: (_ for _ in ()).throw(RuntimeError("cache failure")))
        with pytest.raises(pub.PublicationError):
            pub.publish(con, second.batch_id)
        assert ds.last_published(con) == good["published_at"]
        assert ds.cache_get(con, "board") == old_board
        assert ds.get_translation(con, "t_one", "en") is None
    finally:
        con.close()
