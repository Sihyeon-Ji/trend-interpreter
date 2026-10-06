"""Immutable review batches and atomic publication of approved dictionary changes."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schemas import Evidence, MeaningDraft, MeaningText, MemeFit, Term
from ..verification import gate, guessed_meaning, vacuous_meaning
from . import dictionary_store as ds
from .db import Connection

SHA = r"^[a-f0-9]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewTerm(StrictModel):
    canonical: str = Field(min_length=1, max_length=120)
    lang: str = Field(min_length=2, max_length=10)
    aliases: list[str] = Field(default_factory=list, max_length=12)


class LocalMeme(StrictModel):
    label: str = Field(min_length=1, max_length=120)
    note_ko: str = Field(default="", max_length=1000)
    note_en: str = Field(default="", max_length=1000)


class CountryNote(StrictModel):
    local_name: str = Field(min_length=1, max_length=120)
    what_changed: dict[Literal["ko", "en"], str]
    local_memes: list[LocalMeme] = Field(default_factory=list, max_length=20)
    self_confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class ChangeItem(StrictModel):
    term_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,120}$")
    expected_meaning_id: str | None
    new_term: NewTerm | None = None
    meaning: MeaningDraft | None = None
    evidences: list[Evidence] = Field(default_factory=list, max_length=100)
    citations: list[str] = Field(default_factory=list, max_length=100)
    translations: dict[Literal["ko", "en", "ja"], MeaningText] = Field(default_factory=dict)
    country_notes: dict[str, CountryNote] = Field(default_factory=dict)
    fit: MemeFit | None = None
    derived_from_sha256: str | None = Field(default=None, pattern=SHA)

    @model_validator(mode="after")
    def meaningful_change(self):
        if not (self.meaning or self.translations or self.country_notes or self.fit):
            raise ValueError("An item must contain a dictionary change")
        if len({e.evidence_id for e in self.evidences}) != len(self.evidences):
            raise ValueError("Duplicate evidence IDs")
        if any(not re.fullmatch(r"[A-Z]{2}|GLOBAL", region) for region in self.country_notes):
            raise ValueError("Country note keys must be region codes")
        if self.new_term and (self.expected_meaning_id is not None or self.meaning is None):
            raise ValueError("A new term requires a new meaning and no previous meaning")
        return self


class ChangeBatch(StrictModel):
    batch_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,96}$")
    snapshot_id: str = Field(min_length=1, max_length=120)
    snapshot_sha256: str = Field(pattern=SHA)
    model_id: str = Field(min_length=1, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=120)
    rule_version: str = Field(min_length=1, max_length=120)
    items: list[ChangeItem] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_terms(self):
        if len({i.term_id for i in self.items}) != len(self.items):
            raise ValueError("A term may appear only once per batch")
        names: dict[str, str] = {}
        for item in self.items:
            if item.new_term:
                for name in (item.new_term.canonical, *item.new_term.aliases):
                    key = ds.norm(name)
                    if not key or (key in names and names[key] != item.term_id):
                        raise ValueError("New term names must be nonempty and unambiguous")
                    names[key] = item.term_id
        return self


class PublicationError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def canonical(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _baseline(con: Connection, term_id: str) -> str:
    t = ds.get_term(con, term_id)
    m = ds.current_meaning(con, term_id)
    # Protect concurrent edits, including human risk decisions and related outputs.
    rows = {
        "term": t.model_dump(mode="json") if t else None,
        "meaning": m.model_dump(mode="json") if m else None,
        "translations": con.execute("SELECT lang, json, model FROM translations WHERE term_id=? ORDER BY lang", (term_id,)).fetchall(),
        "notes": con.execute("SELECT region, json, model FROM topic_notes WHERE term_id=? ORDER BY region", (term_id,)).fetchall(),
        "fit": con.execute("SELECT meaning_id, json, model FROM term_fit WHERE term_id=?", (term_id,)).fetchall(),
        "evidence": con.execute("SELECT evidence_id, json FROM evidences WHERE term_id=? ORDER BY evidence_id", (term_id,)).fetchall(),
    }
    return digest(rows)


def _validate_item(con: Connection, item: ChangeItem) -> list[str]:
    t = ds.get_term(con, item.term_id)
    m = ds.current_meaning(con, item.term_id)
    if (m.meaning_id if m else None) != item.expected_meaning_id:
        raise PublicationError("meaning_conflict")
    if t and t.status == "retired":
        raise PublicationError("human_retired")
    if ds.under_review(con, item.term_id):
        raise PublicationError("pending_review")
    if not t and not item.new_term:
        raise PublicationError("missing_term")
    if t and item.new_term:
        raise PublicationError("term_conflict")
    if not t and item.new_term:
        if any(ds.find_term(con, name) for name in (item.new_term.canonical, *item.new_term.aliases)):
            raise PublicationError("canonical_conflict")
    if item.meaning and m and m.verification == "verified_human":
        raise PublicationError("human_meaning")
    if not item.meaning and (not m or t.status != "verified" or m.verification not in ("verified_auto", "verified_human")):
        raise PublicationError("unapproved_source")
    source = item.meaning or m.model_dump(include=set(MeaningDraft.model_fields), mode="json")
    if (item.translations or item.country_notes or item.fit) and item.derived_from_sha256 != digest(source):
        raise PublicationError("derived_version_conflict")
    for lang in item.translations:
        old = con.execute("SELECT model FROM translations WHERE term_id=? AND lang=?", (item.term_id, lang)).fetchone()
        if old and old[0] == "team":
            raise PublicationError("human_translation")
    for region in item.country_notes:
        old = con.execute("SELECT model FROM topic_notes WHERE term_id=? AND region=?", (item.term_id, region)).fetchone()
        if old and old[0] == "team":
            raise PublicationError("human_derived_output")
    if item.fit and con.execute("SELECT 1 FROM term_fit WHERE term_id=? AND model='team'", (item.term_id,)).fetchone():
        raise PublicationError("human_derived_output")
    if item.meaning:
        for table in ("translations", "topic_notes", "term_fit"):
            if con.execute(f"SELECT 1 FROM {table} WHERE term_id=? AND model='team'", (item.term_id,)).fetchone():
                raise PublicationError("human_derived_output")
        definition = item.meaning.definition.strip()
        if len(definition) < 8 or guessed_meaning(definition) or vacuous_meaning(definition):
            raise PublicationError("invalid_meaning")
    evs = {e.evidence_id: e for e in ds.list_evidences(con, item.term_id)}
    for e in item.evidences:
        if e.evidence_id in evs and evs[e.evidence_id] != e:
            raise PublicationError("evidence_conflict")
        evs[e.evidence_id] = e
    if not set(item.citations).issubset({e.url for e in evs.values()}):
        raise PublicationError("missing_citation")
    if any(not set(note.evidence_ids).issubset(evs) for note in item.country_notes.values()):
        raise PublicationError("missing_note_evidence")
    from ..collectors.community import is_community_post
    from ..pipeline.match import mentions

    for note in item.country_notes.values():
        references = [evs[eid] for eid in note.evidence_ids if not is_community_post(evs[eid])]
        text = " ".join(f"{e.title} {e.excerpt}" for e in references)
        if note.self_confidence >= 0.5 and not references:
            raise PublicationError("missing_note_evidence")
        if any(not mentions(text, meme.label) for meme in note.local_memes):
            raise PublicationError("unanchored_note")
    if item.meaning:
        title = t.canonical if t else item.new_term.canonical
        aliases = t.aliases if t else item.new_term.aliases
        _, reasons = gate(title, item.meaning, list(evs.values()), m, aliases)
        return reasons
    return []


def stage(con: Connection, batch: ChangeBatch) -> dict:
    payload, checksum = canonical(batch), digest(batch)
    with con.transaction():
        con.execute("LOCK TABLE change_batches IN SHARE ROW EXCLUSIVE MODE")
        existing = con.execute("SELECT payload_sha256, status FROM change_batches WHERE batch_id=?", (batch.batch_id,)).fetchone()
        if existing:
            if existing[0] != checksum:
                raise PublicationError("batch_id_conflict")
            return {"batch_id": batch.batch_id, "payload_sha256": checksum, "status": existing[1]}
        con.execute("LOCK TABLE terms, meanings, translations, topic_notes, term_fit, evidences, review_queue IN SHARE MODE")
        validations = [(item, _validate_item(con, item), _baseline(con, item.term_id)) for item in batch.items]
        con.execute("INSERT INTO change_batches VALUES (?,?,?,?,?,?,?,NULL,NULL,NULL)",
                    (batch.batch_id, checksum, payload, batch.snapshot_id, batch.snapshot_sha256, ds.now_s(), "draft"))
        for item, reasons, baseline in validations:
            con.execute("INSERT INTO change_items VALUES (?,?,?,?,?,?)",
                        (batch.batch_id, item.term_id, digest(item), item.expected_meaning_id, baseline, canonical(reasons)))
    return {"batch_id": batch.batch_id, "payload_sha256": checksum, "status": "draft"}


def review(con: Connection, batch_id: str, payload_sha256: str, by: str, *, approve: bool,
           allow_gate_exceptions: bool = False) -> dict:
    if not by.strip():
        raise PublicationError("missing_reviewer")
    with con.transaction():
        row = con.execute("SELECT payload_sha256, status FROM change_batches WHERE batch_id=? FOR UPDATE", (batch_id,)).fetchone()
        if not row:
            raise PublicationError("missing_batch")
        if row[0] != payload_sha256:
            raise PublicationError("review_conflict")
        if row[1] != "draft":
            raise PublicationError("not_draft")
        if approve and not allow_gate_exceptions:
            reasons = con.execute("SELECT validation_json FROM change_items WHERE batch_id=?", (batch_id,)).fetchall()
            if any(json.loads(r[0]) for r in reasons):
                raise PublicationError("gate_review_required")
        state = "approved" if approve else "rejected"
        con.execute("UPDATE change_batches SET status=?, reviewed_by=?, reviewed_at=? WHERE batch_id=?",
                    (state, by, ds.now_s(), batch_id))
    return {"batch_id": batch_id, "status": state}


def inspect(con: Connection, batch_id: str) -> dict:
    row = con.execute("SELECT payload_json, payload_sha256, status, reviewed_by, reviewed_at, failure_code FROM change_batches WHERE batch_id=?", (batch_id,)).fetchone()
    if not row:
        raise PublicationError("missing_batch")
    return {"batch": json.loads(row[0]), "payload_sha256": row[1], "status": row[2], "reviewed_by": row[3],
            "reviewed_at": row[4], "failure_code": row[5], "validation": {
                tid: json.loads(reasons) for tid, reasons in con.execute("SELECT term_id, validation_json FROM change_items WHERE batch_id=?", (batch_id,))}}


def summaries(con: Connection, limit: int = 50, offset: int = 0) -> dict:
    rows = con.execute("SELECT b.batch_id, b.payload_sha256, b.status, b.created_at, b.reviewed_by, b.reviewed_at, "
                       "b.failure_code, COUNT(i.term_id) FROM change_batches b JOIN change_items i ON i.batch_id=b.batch_id "
                       "GROUP BY b.batch_id ORDER BY b.created_at DESC, b.batch_id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    keys = ("batch_id", "payload_sha256", "status", "created_at", "reviewed_by", "reviewed_at", "failure_code", "item_count")
    return {"items": [dict(zip(keys, row)) for row in rows],
            "total": con.execute("SELECT COUNT(*) FROM change_batches").fetchone()[0]}


def comparison(con: Connection, batch_id: str) -> dict:
    result = inspect(con, batch_id)
    result["current"] = {}
    for item in result["batch"]["items"]:
        tid = item["term_id"]
        term, meaning = ds.get_term(con, tid), ds.current_meaning(con, tid)
        baseline = con.execute("SELECT baseline_sha256 FROM change_items WHERE batch_id=? AND term_id=?", (batch_id, tid)).fetchone()[0]
        result["current"][tid] = {
            "term": term.model_dump(mode="json") if term else None,
            "meaning": meaning.model_dump(mode="json") if meaning else None,
            "translations": {lang: json.loads(payload) for lang, payload in con.execute("SELECT lang, json FROM translations WHERE term_id=?", (tid,))},
            "country_notes": ds.get_topic_notes(con, tid),
            "evidences": [e.model_dump(mode="json") for e in ds.list_evidences(con, tid)],
            "fit": json.loads(row[0]) if (row := con.execute("SELECT json FROM term_fit WHERE term_id=?", (tid,)).fetchone()) else None,
            "baseline_changed": baseline != _baseline(con, tid),
        }
    return result


def refresh_caches(con: Connection) -> None:
    from ..pipeline import board, dashboard, views

    ds.cache_set(con, "board", board.build(con).model_dump_json())
    dashboard._save(con, dashboard.build(con))
    views.save_term_index(con)
    con.execute("DELETE FROM board_cache WHERE key LIKE 'briefing%'")
    con.execute("DELETE FROM explain_cache")


def publish(con: Connection, batch_id: str) -> dict:
    try:
        with con.transaction():
            # All writes are excluded while validating and rebuilding the visible snapshot.
            con.execute("LOCK TABLE change_batches, terms, meanings, translations, topic_notes, term_fit, evidences, review_queue, "
                        "board_cache, explain_cache IN SHARE ROW EXCLUSIVE MODE")
            row = con.execute("SELECT payload_json, payload_sha256, status, reviewed_by FROM change_batches WHERE batch_id=? FOR UPDATE", (batch_id,)).fetchone()
            if not row:
                raise PublicationError("missing_batch")
            if row[2] == "published":
                return _result(con, batch_id)
            if row[2] not in ("approved", "failed") or not row[3]:
                raise PublicationError("not_approved")
            batch = ChangeBatch.model_validate_json(row[0])
            if digest(batch) != row[1]:
                raise PublicationError("payload_integrity")
            records = {tid: (checksum, baseline) for tid, checksum, baseline in con.execute(
                "SELECT term_id, item_sha256, baseline_sha256 FROM change_items WHERE batch_id=?", (batch_id,))}
            if set(records) != {item.term_id for item in batch.items}:
                raise PublicationError("item_integrity")
            for item in batch.items:
                _validate_item(con, item)
                if records[item.term_id] != (digest(item), _baseline(con, item.term_id)):
                    raise PublicationError("baseline_conflict")
            for item in batch.items:
                _apply(con, batch, item, row[3])
            refresh_caches(con)
            publication_id = "pub_" + hashlib.sha256(batch_id.encode()).hexdigest()[:24]
            con.execute("INSERT INTO publications VALUES (?,?,?,?,?)", (publication_id, batch_id, row[1], ds.now_s(), len(batch.items)))
            con.execute("INSERT INTO publication_state VALUES (1,?) ON CONFLICT(singleton) DO UPDATE SET publication_id=EXCLUDED.publication_id", (publication_id,))
            con.execute("UPDATE change_batches SET status='published', failure_code=NULL WHERE batch_id=?", (batch_id,))
            result = _result(con, batch_id)
        return result
    except Exception as exc:
        code = exc.code if isinstance(exc, PublicationError) else type(exc).__name__
        state = "conflict" if code in {"meaning_conflict", "baseline_conflict", "human_meaning", "human_retired", "pending_review", "human_translation", "human_derived_output", "evidence_conflict"} else "failed"
        con.execute("UPDATE change_batches SET status=?, failure_code=? WHERE batch_id=? AND status IN ('approved','failed')", (state, code, batch_id))
        con.commit()
        if isinstance(exc, PublicationError):
            raise
        raise PublicationError("publication_failed") from None


def _apply(con: Connection, batch: ChangeBatch, item: ChangeItem, reviewer: str) -> None:
    from ..pipeline import risk

    t = ds.get_term(con, item.term_id)
    if not t:
        t = Term(term_id=item.term_id, canonical=item.new_term.canonical, lang=item.new_term.lang,
                 aliases=item.new_term.aliases, status="needs_review")
        ds.upsert_term(con, t)
    ds.add_evidences(con, item.term_id, item.evidences)
    if item.meaning:
        # Invalidate every derived output tied to the old meaning, not only translations.
        m = ds.publish_fix(con, item.term_id, item.meaning, reviewer, item.citations)
        con.execute("DELETE FROM topic_notes WHERE term_id=?", (item.term_id,))
        con.execute("DELETE FROM term_fit WHERE term_id=?", (item.term_id,))
        t.status = "verified"
        ds.upsert_term(con, t, human=True)
        ds.decide_review(con, item.term_id, "approve", reviewer, kind="new")
    else:
        m = ds.current_meaning(con, item.term_id)
    for lang, text in item.translations.items():
        ds.set_translation(con, item.term_id, lang, text, batch.model_id)
    for region, note in item.country_notes.items():
        ds.set_topic_note(con, item.term_id, region, canonical(note), batch.model_id)
    if item.fit:
        ds.set_fit(con, item.term_id, m.meaning_id, item.fit, batch.model_id)
    risk.apply(con, t)


def _result(con: Connection, batch_id: str) -> dict:
    row = con.execute("SELECT publication_id, published_at, item_count FROM publications WHERE batch_id=?", (batch_id,)).fetchone()
    if not row:
        raise PublicationError("missing_publication")
    return {"publication_id": row[0], "batch_id": batch_id, "published_at": row[1], "item_count": row[2]}
