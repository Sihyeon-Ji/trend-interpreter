"""Translation packaging binds outputs to original versions without changing public data."""
import hashlib
import json

import pytest

from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import db, dictionary_store as ds, publication_inputs as inputs, publications as pub


@pytest.fixture
def packet():
    con = db.connect(":memory:")
    for tid in ("t_one", "t_two"):
        ds.upsert_term(con, Term(term_id=tid, canonical=tid, status="verified"))
        source = MeaningDraft(definition="a documented published definition", origin="origin", nuance="nuance",
                              generations=["20s"], regions=["KR"], self_confidence=0.9)
        ds.add_meaning(con, tid, source, "verified_auto", [])
    content = inputs.translation_inputs(con, ["t_two", "t_one"], "fixed-snapshot", "a" * 64)
    run = {"input_sha256": hashlib.sha256(content).hexdigest(), "model": "gemma4:12b",
           "model_digest": "b" * 64, "gemma_translate_sha256": "c" * 64}
    results = [{"term_id": row["term_id"], "term": row["term"], "source": row["entry"],
                "expected_meaning_id": row["expected_meaning_id"], "derived_from_sha256": row["derived_from_sha256"],
                "en": {"definition": "English translation", "origin": "origin", "nuance": "nuance"}, "error": None,
                **{key: run[key] for key in ("model", "model_digest", "gemma_translate_sha256", "input_sha256")}}
               for row in map(json.loads, content.splitlines())]
    yield con, content, run, results
    con.close()


def lines(rows):
    return ("\n".join(json.dumps(row) for row in rows) + "\n").encode()


def test_pack_stage_review_publish_preserves_original_meaning_and_exposes_translation_only_after_publish(packet):
    con, content, run, results = packet
    original = ds.current_meaning(con, "t_one").meaning_id
    batch, failed = inputs.pack_translations(content, lines(results), run, "translated")
    assert failed == 0 and batch.model_id == "local:gemma4:12b@sha256:" + "b" * 64
    assert [item.term_id for item in batch.items] == ["t_one", "t_two"]
    staged = pub.stage(con, batch)
    assert ds.get_translation(con, "t_one", "en") is None
    pub.review(con, batch.batch_id, staged["payload_sha256"], "reviewer", approve=True)
    pub.publish(con, batch.batch_id)
    assert ds.get_translation(con, "t_one", "en").definition == "English translation"
    assert ds.current_meaning(con, "t_one").meaning_id == original


@pytest.mark.parametrize("change,code", [
    ("hash", "translation_input_hash_conflict"), ("old", "translation_source_conflict"),
    ("source", "translation_source_conflict"), ("model", "translation_model_conflict"),
    ("duplicate", "translation_term_conflict"), ("unknown", "translation_term_conflict"),
    ("missing", "incomplete_translation_output"), ("empty", "invalid_translation_output"),
])
def test_pack_refuses_wrong_lineage_or_incomplete_outputs(packet, change, code):
    con, content, run, results = packet
    if change == "hash":
        run["input_sha256"] = "d" * 64
    elif change == "old":
        results[0].pop("expected_meaning_id")
    elif change == "source":
        results[0]["source"]["definition"] = "changed input"
    elif change == "model":
        results[0]["model_digest"] = "d" * 64
    elif change == "duplicate":
        results.append(results[0])
    elif change == "unknown":
        results[0]["term_id"] = "unknown"
    elif change == "missing":
        results.pop()
    else:
        results[0]["en"]["definition"] = " "
    with pytest.raises(pub.PublicationError, match=code):
        inputs.pack_translations(content, lines(results), run, "invalid")
    assert con.execute("SELECT COUNT(*) FROM change_batches").fetchone()[0] == 0


def test_failed_rows_need_explicit_skip_and_stale_versions_still_conflict(packet):
    con, content, run, results = packet
    results[1]["error"] = "Private generated error text"
    results[1]["en"] = None
    with pytest.raises(pub.PublicationError, match="translation_failed_rows"):
        inputs.pack_translations(content, lines(results), run, "translated")
    batch, failed = inputs.pack_translations(content, lines(results), run, "translated", skip_failed=True)
    assert failed == 1 and len(batch.items) == 1
    ds.add_meaning(con, "t_one", MeaningDraft(definition="a newer version of the meaning", origin="o", nuance="n",
                                            generations=[], regions=[], self_confidence=0.9), "verified_auto", [])
    with pytest.raises(pub.PublicationError, match="meaning_conflict"):
        pub.stage(con, batch)


def test_export_refuses_unapproved_or_duplicate_selections(packet):
    con, _, _, _ = packet
    with pytest.raises(pub.PublicationError, match="invalid_term_selection"):
        inputs.translation_inputs(con, ["t_one", "t_one"], "s", "a" * 64)
    meaning = ds.current_meaning(con, "t_one")
    ds.set_verification(con, meaning.meaning_id, "unverified", "reviewer")
    with pytest.raises(pub.PublicationError, match="unapproved_source"):
        inputs.translation_inputs(con, ["t_one"], "s", "a" * 64)


def test_input_cannot_claim_original_meaning_hash_while_translating_different_text(packet):
    _, content, run, results = packet
    rows = [json.loads(line) for line in content.splitlines()]
    rows[0]["entry"]["definition"] = "a different source text"
    modified = lines(rows)
    run["input_sha256"] = hashlib.sha256(modified).hexdigest()
    results[0]["source"] = rows[0]["entry"]
    with pytest.raises(pub.PublicationError, match="invalid_translation_files"):
        inputs.pack_translations(modified, lines(results), run, "invalid")


def test_review_exclusions_leave_rows_out_but_keep_lineage_checks(packet):
    con, content, run, results = packet
    batch, failed = inputs.pack_translations(content, lines(results), run, "translated", exclude=frozenset({"t_two"}))
    assert failed == 0 and [item.term_id for item in batch.items] == ["t_one"]
    with pytest.raises(pub.PublicationError, match="translation_exclude_unknown"):
        inputs.pack_translations(content, lines(results), run, "translated", exclude=frozenset({"t_other"}))
    with pytest.raises(pub.PublicationError, match="empty_translation_batch"):
        inputs.pack_translations(content, lines(results), run, "translated", exclude=frozenset({"t_one", "t_two"}))
    results[1]["source"]["definition"] = "changed input"                 # 뺀 행도 원문 계보는 맞아야 한다
    with pytest.raises(pub.PublicationError, match="translation_source_conflict"):
        inputs.pack_translations(content, lines(results), run, "translated", exclude=frozenset({"t_two"}))


def test_empty_source_fields_may_stay_empty_in_translation(packet):
    con, _, _, _ = packet
    ds.upsert_term(con, Term(term_id="t_bare", canonical="t_bare", status="verified"))
    ds.add_meaning(con, "t_bare", MeaningDraft(definition="a documented published definition", origin="origin", nuance="",
                                               generations=["20s"], regions=["KR"], self_confidence=0.9), "verified_auto", [])
    content = inputs.translation_inputs(con, ["t_bare"], "fixed-snapshot", "a" * 64)
    run = {"input_sha256": hashlib.sha256(content).hexdigest(), "model": "gemma4:12b", "model_digest": "b" * 64, "gemma_translate_sha256": "c" * 64}
    row = json.loads(content)
    result = {"term_id": "t_bare", "term": row["term"], "source": row["entry"], "expected_meaning_id": row["expected_meaning_id"],
              "derived_from_sha256": row["derived_from_sha256"], "en": {"definition": "English", "origin": "origin", "nuance": ""},
              "error": None, **{key: run[key] for key in ("model", "model_digest", "gemma_translate_sha256", "input_sha256")}}
    batch, _ = inputs.pack_translations(content, lines([result]), run, "bare")
    staged = pub.stage(con, batch)
    pub.review(con, batch.batch_id, staged["payload_sha256"], "reviewer", approve=True)
    pub.publish(con, batch.batch_id)
    assert ds.get_translation(con, "t_bare", "en").definition == "English"
    result["en"]["origin"] = ""                                            # 원문에 있는 유래를 빠뜨리면 막는다
    with pytest.raises(pub.PublicationError, match="invalid_translation_output"):
        inputs.pack_translations(content, lines([result]), run, "bare2")



def test_glossary_rides_in_the_hashed_input_and_must_name_text_in_the_entry(packet):
    con, _, _, _ = packet
    content = inputs.translation_inputs(con, ["t_one"], "fixed-snapshot", "a" * 64, {"t_one": {"origin": "Origin"}})
    row = json.loads(content)
    assert row["glossary"] == {"origin": "Origin"}
    run = {"input_sha256": hashlib.sha256(content).hexdigest(), "model": "gemma4:12b", "model_digest": "b" * 64, "gemma_translate_sha256": "c" * 64}
    result = {"term_id": "t_one", "term": row["term"], "source": row["entry"], "expected_meaning_id": row["expected_meaning_id"],
              "derived_from_sha256": row["derived_from_sha256"], "en": {"definition": "English", "origin": "Origin", "nuance": "nuance"},
              "error": None, **{key: run[key] for key in ("model", "model_digest", "gemma_translate_sha256", "input_sha256")}}
    batch, _ = inputs.pack_translations(content, lines([result]), run, "named")
    assert [item.term_id for item in batch.items] == ["t_one"]
    with pytest.raises(pub.PublicationError, match="glossary_term_unknown"):
        inputs.translation_inputs(con, ["t_one"], "s", "a" * 64, {"t_two": {"origin": "Origin"}})
    with pytest.raises(Exception):                                   # 원문에 없는 표기는 받지 않는다
        inputs.translation_inputs(con, ["t_one"], "s", "a" * 64, {"t_one": {"not in the entry": "X"}})
