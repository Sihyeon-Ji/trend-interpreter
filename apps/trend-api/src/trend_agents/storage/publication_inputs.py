"""Versioned translation inputs and immutable review batches from Kaggle outputs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import Field, model_validator

from ..schemas import MeaningDraft, MeaningText
from ..verification import is_public_entry
from . import dictionary_store as ds
from .db import Connection
from .publications import ChangeBatch, ChangeItem, PublicationError, SHA, StrictModel, canonical, digest


class TranslationInput(StrictModel):
    term_id: str
    term: str
    expected_meaning_id: str
    derived_from_sha256: str = Field(pattern=SHA)
    snapshot_id: str = Field(min_length=1, max_length=120)
    snapshot_sha256: str = Field(pattern=SHA)
    meaning_source: MeaningDraft
    entry: MeaningText
    # 사람이 정한 고유명사 표기(원문 표기 → 대상 언어 표기). 입력 해시에 들어가 번역 출처와 함께 남는다(10-09)
    glossary: dict[str, str] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def consistent_source(self):
        if (digest(self.meaning_source) != self.derived_from_sha256
                or self.entry != MeaningText.model_validate(self.meaning_source.model_dump())):
            raise ValueError("Translation text must match the versioned meaning source")
        text = self.term + self.entry.model_dump_json()
        if any(not 0 < len(k) <= 80 or not 0 < len(v) <= 80 or k not in text for k, v in self.glossary.items()):
            raise ValueError("Glossary keys must appear in the entry")
        return self


def translation_inputs(con: Connection, term_ids: list[str], snapshot_id: str, snapshot_sha256: str,
                       glossary: dict[str, dict[str, str]] | None = None) -> bytes:
    glossary = glossary or {}
    if not term_ids or len(term_ids) > 1000 or len(set(term_ids)) != len(term_ids):
        raise PublicationError("invalid_term_selection")
    if not set(glossary) <= set(term_ids):
        raise PublicationError("glossary_term_unknown")
    rows = []
    # The caller must use connect_read_only(); one snapshot keeps IDs and contents consistent.
    with con.transaction():
        con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        for tid in sorted(term_ids):
            term, meaning = ds.get_term(con, tid), ds.current_meaning(con, tid)
            if not is_public_entry(term, meaning):
                raise PublicationError("unapproved_source")
            source = MeaningDraft.model_validate(meaning.model_dump(include=set(MeaningDraft.model_fields)))
            entry = MeaningText.model_validate(source.model_dump())
            row = TranslationInput(term_id=tid, term=term.canonical, expected_meaning_id=meaning.meaning_id,
                                   derived_from_sha256=digest(source), meaning_source=source, entry=entry,
                                   snapshot_id=snapshot_id, snapshot_sha256=snapshot_sha256,
                                   glossary=glossary.get(tid, {}))
            rows.append(canonical(row))
    return ("\n".join(rows) + "\n").encode()


TRANSLATION_LANGS = ("en", "ja")   # 번역 생산자가 만드는 언어판(결과 행의 칸 이름). 일본어판은 10-12에 열었다


def pack_translations(input_bytes: bytes, output_bytes: bytes, run: dict, batch_id: str, *, skip_failed: bool = False,
                      exclude: frozenset[str] = frozenset(), lang: str = "en") -> tuple[ChangeBatch, int]:
    """exclude: 사람이 번역 검토에서 뺀 표제어. 계보 검사는 다른 행과 똑같이 거치고 배치에만 넣지 않는다 –
    모델 실패(skip_failed)와 섞지 않는다. 뺀 건수는 부르는 쪽이 len(exclude)로 기록한다.
    lang: 결과 행에서 읽을 언어판(생산자의 TRANSLATE_TARGET). 그 언어 칸이 없는 결과는 형식 오류다."""
    if lang not in TRANSLATION_LANGS:
        raise PublicationError("invalid_translation_language")
    try:
        inputs = [TranslationInput.model_validate_json(line) for line in input_bytes.splitlines() if line.strip()]
        outputs = [json.loads(line) for line in output_bytes.splitlines() if line.strip()]
    except Exception:
        raise PublicationError("invalid_translation_files") from None
    if not inputs or len(inputs) > 1000 or len({i.term_id for i in inputs}) != len(inputs):
        raise PublicationError("invalid_translation_inputs")
    if run.get("input_sha256") != hashlib.sha256(input_bytes).hexdigest():
        raise PublicationError("translation_input_hash_conflict")
    if len({(i.snapshot_id, i.snapshot_sha256) for i in inputs}) != 1:
        raise PublicationError("mixed_snapshots")
    try:
        model = run["model"]
        revision = run["model_digest"]
        prompt_hash = run["gemma_translate_sha256"]
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_./:-]{1,40}", model):
            raise ValueError()
        if not all(isinstance(value, str) and re.fullmatch(SHA, value) for value in (revision, prompt_hash)):
            raise ValueError()
    except Exception:
        raise PublicationError("missing_translation_provenance") from None
    indexed = {i.term_id: i for i in inputs}
    if not exclude <= set(indexed):
        raise PublicationError("translation_exclude_unknown")
    seen, items, failures = set(), [], 0
    for result in outputs:
        if not isinstance(result, dict) or not isinstance(result.get("term_id"), str):
            raise PublicationError("invalid_translation_output")
        tid = result["term_id"]
        if tid not in indexed or tid in seen:
            raise PublicationError("translation_term_conflict")
        seen.add(tid)
        source = indexed[tid]
        # Do not bind old unversioned experiments to today's meaning ID.
        if (result.get("expected_meaning_id") != source.expected_meaning_id
                or result.get("derived_from_sha256") != source.derived_from_sha256
                or result.get("term") != source.term
                or result.get("source") != source.entry.model_dump(mode="json")
                or digest(source.meaning_source) != source.derived_from_sha256):
            raise PublicationError("translation_source_conflict")
        if (result.get("model") != model or result.get("model_digest") != revision
                or result.get("input_sha256") != run["input_sha256"]
                or result.get("gemma_translate_sha256") != prompt_hash):
            raise PublicationError("translation_model_conflict")
        if tid in exclude:
            continue
        if result.get("error") is not None:
            failures += 1
            if not skip_failed:
                raise PublicationError("translation_failed_rows")
            continue
        try:
            translated = MeaningText.model_validate(result[lang])
            # 원문에 있는 칸만 번역에도 있어야 한다 – 원문 뉘앙스가 빈 말('인정' 등)은 번역 뉘앙스도 비어 있다(10-09)
            if not translated.definition.strip() or any(getattr(source.entry, field).strip() and not getattr(translated, field).strip()
                                                       for field in ("origin", "nuance")):
                raise ValueError()
        except Exception:
            raise PublicationError("invalid_translation_output") from None
        items.append(ChangeItem(term_id=tid, expected_meaning_id=source.expected_meaning_id,
                                derived_from_sha256=source.derived_from_sha256, translations={lang: translated}))
    if seen != set(indexed):
        raise PublicationError("incomplete_translation_output")
    if not items:
        raise PublicationError("empty_translation_batch")
    first = inputs[0]
    try:
        batch = ChangeBatch(batch_id=batch_id, snapshot_id=first.snapshot_id, snapshot_sha256=first.snapshot_sha256,
                            model_id=f"local:{model}@sha256:{revision}", prompt_version=f"sha256:{prompt_hash}",
                            rule_version="sha256:" + hashlib.sha256(Path(__file__).with_name("publications.py").read_bytes()).hexdigest(),
                            items=sorted(items, key=lambda item: item.term_id))
    except Exception:
        raise PublicationError("invalid_translation_batch") from None
    return batch, failures
