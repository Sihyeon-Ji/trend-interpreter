import csv
import gzip
import json
import sqlite3

import pytest

from models.kaggle.audit.quality import load_pack
from scripts import snapshot
from scripts.prepare_audit_review import prepare


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / "snapshot"
    source.mkdir()
    database = source / "trend.db"
    with sqlite3.connect(database) as con:
        con.execute("CREATE TABLE terms (term_id TEXT, json TEXT)")
        con.execute("CREATE TABLE meanings (term_id TEXT, version INTEGER, json TEXT)")
        con.execute(
            "CREATE TABLE evidences (evidence_id TEXT, term_id TEXT, json TEXT)"
        )
        for index in range(21):
            tid, name = f"term-{index}", f"case{index}"
            url = f"https://namu.wiki/w/{name}"
            term = {"term_id": tid, "canonical": name, "status": "verified"}
            meaning = {
                "term_id": tid,
                "meaning_id": f"meaning-{index}",
                "version": 1,
                "definition": "synthetic definition",
                "origin": "synthetic origin",
                "nuance": "synthetic nuance",
                "generations": [],
                "regions": ["KR"],
                "self_confidence": 0.8,
                "confidence": 0.8,
                "valid_from": "2026-10-01T00:00:00+09:00",
                "citations": [url],
            }
            evidence = {
                "evidence_id": f"evidence-{index}",
                "kind": "wiki",
                "title": name,
                "url": url,
                "source_domain": "namu.wiki",
                "excerpt": "synthetic evidence",
                "observed_at": "2026-10-01T00:00:00+09:00",
            }
            con.execute("INSERT INTO terms VALUES (?,?)", (tid, json.dumps(term)))
            con.execute(
                "INSERT INTO meanings VALUES (?,1,?)", (tid, json.dumps(meaning))
            )
            con.execute(
                "INSERT INTO evidences VALUES (?,?,?)",
                (evidence["evidence_id"], tid, json.dumps(evidence)),
            )
    with gzip.open(source / snapshot.FILES[0], "wb") as target:
        target.write(database.read_bytes())
    (source / "table-counts.txt").write_text("terms 21\nmeanings 21\nevidences 21\n")
    (source / "updated_at.txt").write_text(
        "2026-10-01T22:45:11+09:00 e56b90d terms=21\n"
    )
    manifest = {
        "manifest_version": 1,
        "snapshot_id": "synthetic-test",
        "state": "captured",
        **snapshot.inspect_database(source),
        "objects": [
            {
                "name": name,
                "uri": f"{snapshot.ROOT}/db/latest/{name}",
                "generation": "1",
                **snapshot.hashes(source / name),
            }
            for name in snapshot.FILES
        ],
    }
    (source / "manifest.json").write_text(json.dumps(manifest))
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    objects = []
    for name in ("audit_sft_v5.jsonl", "audit_holdout_sft.jsonl"):
        row = {
            "term_id": "term-0",
            "messages": [{"role": "user", "content": "synthetic prompt"}],
        }
        (dataset / name).write_text(json.dumps(row) + "\n")
        objects.append(
            {
                "name": name,
                "rows": 1,
                "sha256": snapshot.hashes(dataset / name)["sha256"],
            }
        )
    (dataset / "audit-v5-baseline.json").write_text(json.dumps({"objects": objects}))
    return source, dataset


def test_export_is_blind_disjoint_and_reproducible(inputs, tmp_path):
    source, dataset = inputs
    first = prepare(source, dataset, tmp_path / "first")
    second = prepare(source, dataset, tmp_path / "second")
    assert first["files"] == second["files"]
    _, cases, inventory = load_pack(tmp_path / "first")
    assert len(cases) == 20
    assert "term-0" not in {case["term_id"] for case in cases}
    assert inventory["term_ids"] == ["term-0"]
    assert inventory["training_source_inventory_complete"] is False
    assert not any("label" in case or "human_review" in case for case in cases)
    with (tmp_path / "first/review.csv").open(encoding="utf-8-sig", newline="") as file:
        assert all(
            not row["label"] and not row["reviewer"] for row in csv.DictReader(file)
        )
    assert first["promotion_eligible"] is False


def test_corrupt_snapshot_is_rejected_before_export(inputs, tmp_path):
    source, dataset = inputs
    (source / "table-counts.txt").write_text("terms 99\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        prepare(source, dataset, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_corrupt_prior_dataset_is_rejected_before_export(inputs, tmp_path):
    source, dataset = inputs
    (dataset / "audit_sft_v5.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        prepare(source, dataset, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_missing_prior_dataset_file_cannot_weaken_exclusions(inputs, tmp_path):
    source, dataset = inputs
    path = dataset / "audit-v5-baseline.json"
    manifest = json.loads(path.read_text())
    manifest["objects"].pop()
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="both original files"):
        prepare(source, dataset, tmp_path / "output")
    assert not (tmp_path / "output").exists()
