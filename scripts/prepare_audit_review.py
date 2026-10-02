"""Prepare blind audit cases from a verified SQLite intake without changing service data."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/trend-api/src"))

from trend_agents.pipeline.audit import SIMPLE_PROMPT
from trend_agents.schemas import Evidence, Meaning, Term
from trend_agents.verification import doc_titled, reference_doc

from models.kaggle.audit.quality import (
    digest,
    item_hash,
    load_pack,
    review_fields,
    source_key,
    term_key,
)
from scripts.snapshot import verify

MAX_DOCUMENTS = 2
EXCERPT_LIMIT = 1500


def prepare(snapshot: Path, dataset: Path, output: Path, count: int = 20) -> dict:
    snapshot_manifest = json.loads((snapshot / "manifest.json").read_text())
    verify(snapshot_manifest, snapshot)
    dataset_manifest = json.loads((dataset / "audit-v5-baseline.json").read_text())
    objects = dataset_manifest["objects"]
    if len(objects) != 2 or {item["name"] for item in objects} != {
        "audit_sft_v5.jsonl",
        "audit_holdout_sft.jsonl",
    }:
        raise ValueError("Prior dataset must include both original files exactly once")
    used = set()
    prompt_urls = set()
    for item in dataset_manifest["objects"]:
        if item["name"] not in {"audit_sft_v5.jsonl", "audit_holdout_sft.jsonl"}:
            raise ValueError("Unexpected prior dataset file")
        path = dataset / item["name"]
        if digest(path) != item["sha256"]:
            raise ValueError("Prior dataset checksum mismatch")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != item["rows"]:
            raise ValueError("Prior dataset row count mismatch")
        used.update(row["term_id"] for row in rows)
        for row in rows:
            for url in re.findall(
                r'https?://[^\s<>"\]]+', row["messages"][0]["content"]
            ):
                prompt_urls.add(source_key(url))
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "snapshot.db"
        with (
            gzip.open(snapshot / "trend-latest.db.gz", "rb") as source,
            path.open("wb") as target,
        ):
            shutil.copyfileobj(source, target)
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        try:
            terms = {
                row[0]: json.loads(row[1])
                for row in con.execute("SELECT term_id, json FROM terms")
            }
            if used - set(terms):
                raise ValueError("Prior training terms are missing from the snapshot")
            meanings, documents, urls = {}, {}, {}
            for tid, data in con.execute(
                "SELECT term_id, json FROM meanings ORDER BY version"
            ):
                meaning = json.loads(data)
                urls.setdefault(tid, set()).update(meaning.get("citations", []))
                if meaning.get("valid_to") is None:
                    meanings[tid] = meaning
            for tid, data in con.execute(
                "SELECT term_id, json FROM evidences ORDER BY evidence_id"
            ):
                evidence = json.loads(data)
                urls.setdefault(tid, set()).add(evidence["url"])
                documents.setdefault(tid, []).append(evidence)
        finally:
            con.close()
    excluded_names = {
        term_key(name)
        for tid in used
        for name in [terms[tid]["canonical"], *terms[tid].get("aliases", [])]
    }
    excluded_sources = set(prompt_urls)
    unmapped = []
    for tid in used:
        keys = set()
        for url in urls.get(tid, set()):
            try:
                keys.add(source_key(url))
            except ValueError:
                continue
        if not keys:
            unmapped.append(tid)
        excluded_sources.update(keys)
    inventory = {
        "term_ids": sorted(used),
        "term_keys": sorted(excluded_names),
        "source_keys": sorted(excluded_sources),
        "unmapped_training_terms": sorted(unmapped),
        "method": "all-snapshot-evidence-and-meaning-citations-plus-prompt-urls",
        "training_source_inventory_complete": False,
    }
    candidates = []
    for tid, data in terms.items():
        if (
            tid in used
            or data["status"] not in {"verified", "needs_review"}
            or tid not in meanings
        ):
            continue
        identities = {
            term_key(name) for name in [data["canonical"], *data.get("aliases", [])]
        }
        if identities & excluded_names:
            continue
        term = Term.model_validate(data)
        meaning = Meaning.model_validate(meanings[tid])
        selected = {}
        for raw in documents.get(tid, []):
            evidence = Evidence.model_validate(raw)
            if (
                evidence.derived
                or not evidence.excerpt.strip()
                or not reference_doc(evidence)
                or not doc_titled(term.canonical, evidence, term.aliases)
            ):
                continue
            key = source_key(evidence.url)
            if key in excluded_sources:
                continue
            selected.setdefault(
                key,
                {
                    "url": evidence.url,
                    "title": evidence.title,
                    "excerpt": evidence.excerpt[:EXCERPT_LIMIT],
                    "observed_at": evidence.observed_at.isoformat(),
                },
            )
        refs = [selected[key] for key in sorted(selected)][:MAX_DOCUMENTS]
        if not refs:
            continue
        text = "\n\n".join(
            f"{index}. {doc['title']}\n{doc['excerpt']}"
            for index, doc in enumerate(refs, 1)
        )
        case = {
            "term_id": tid,
            "canonical": term.canonical,
            "aliases": term.aliases,
            "lang": term.lang,
            "meaning_id": meaning.meaning_id,
            "meaning_version": meaning.version,
            "definition": meaning.definition,
            "origin": meaning.origin,
            "nuance": meaning.nuance,
            "documents": refs,
            "prompt": SIMPLE_PROMPT.format(
                term=term.canonical,
                definition=meaning.definition,
                origin=meaning.origin,
                nuance=meaning.nuance,
                docs=text,
            ),
        }
        candidates.append({**case, "case_id": item_hash(case)})
    # Stable language round-robin prevents the largest language from taking every slot.
    groups = {}
    for case in sorted(candidates, key=lambda case: case["case_id"]):
        groups.setdefault(case["lang"], []).append(case)
    cases, seen_names, seen_sources = [], set(excluded_names), set(excluded_sources)
    while len(cases) < count and any(groups.values()):
        for language in sorted(groups):
            if not groups[language] or len(cases) == count:
                continue
            case = groups[language].pop(0)
            names = {term_key(name) for name in [case["canonical"], *case["aliases"]]}
            sources = {source_key(doc["url"]) for doc in case["documents"]}
            if names & seen_names or sources & seen_sources:
                continue
            cases.append(case)
            seen_names.update(names)
            seen_sources.update(sources)
    if len(cases) != count:
        raise ValueError("Not enough disjoint audit candidates")
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases.jsonl").write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases)
    )
    (output / "inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
    )
    with (output / "review.csv").open("w", newline="", encoding="utf-8-sig") as target:
        fields = [
            "case_id",
            "canonical",
            "definition",
            "origin",
            "nuance",
            "reference_urls",
            "reference_excerpts",
            "label",
            "reason",
            "reviewer",
            "reviewed_at",
        ]
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow(review_fields(case))
    manifest = {
        "schema_version": 1,
        "evaluation_id": "audit-human-" + snapshot_manifest["snapshot_id"],
        "case_count": len(cases),
        "files": {
            name: digest(output / name) for name in ("cases.jsonl", "inventory.json")
        },
        "snapshot_manifest_sha256": digest(snapshot / "manifest.json"),
        "prior_dataset_manifest_sha256": digest(dataset / "audit-v5-baseline.json"),
        "prompt_template_sha256": hashlib.sha256(SIMPLE_PROMPT.encode()).hexdigest(),
        "excluded_prior_terms": len(used),
        "excluded_source_keys": len(excluded_sources),
        "unmapped_training_terms": len(unmapped),
        "candidate_count": len(candidates),
        "human_review_status": "pending",
        "source_lineage_confirmation": "pending",
        "promotion_eligible": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    load_pack(output)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    if args.count < 20:
        parser.error("At least 20 cases are required")
    try:
        print(json.dumps(prepare(args.snapshot, args.dataset, args.output, args.count)))
    except Exception as error:  # noqa: BLE001 – Keep private inputs out of error logs.
        print(json.dumps({"error_code": type(error).__name__}))
        raise SystemExit(1) from None
