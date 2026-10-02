"""Exercise selective DVC pulls and old-version restoration without cloud credentials."""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is required by DVC")
def test_two_readers_and_old_version_have_identical_selected_input(tmp_path):
    environment = {**os.environ, "DVC_NO_ANALYTICS": "1"}

    def dvc(directory, *arguments):
        subprocess.run([sys.executable, "-m", "dvc", *arguments], cwd=directory,
                       env=environment, check=True, capture_output=True, text=True)

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    dvc(source, "init")
    dvc(source, "remote", "add", "-d", "test", str(tmp_path / "remote"))
    original = b'{"term_id":"synthetic-example","split":"train"}\n'
    (source / "selected.jsonl").write_bytes(original)
    (source / "unselected.jsonl").write_bytes(b"synthetic unselected data\n")
    dvc(source, "add", "selected.jsonl", "unselected.jsonl")
    dvc(source, "push")
    previous = (source / "selected.jsonl.dvc").read_bytes()
    expected = hashlib.sha256(original).hexdigest()
    for name in ("reader-one", "reader-two"):
        reader = tmp_path / name
        reader.mkdir()
        subprocess.run(["git", "init", "-q", str(reader)], check=True)
        shutil.copytree(source / ".dvc", reader / ".dvc", ignore=shutil.ignore_patterns("cache", "tmp"))
        shutil.copy(source / "selected.jsonl.dvc", reader)
        shutil.copy(source / "unselected.jsonl.dvc", reader)
        dvc(reader, "pull", "selected.jsonl.dvc")
        assert hashlib.sha256((reader / "selected.jsonl").read_bytes()).hexdigest() == expected
        assert not (reader / "unselected.jsonl").exists()
    (source / "selected.jsonl").write_bytes(b'{"term_id":"second-version"}\n')
    dvc(source, "add", "selected.jsonl")
    dvc(source, "push", "selected.jsonl.dvc")
    (source / "selected.jsonl.dvc").write_bytes(previous)
    (source / "selected.jsonl").unlink()
    shutil.rmtree(source / ".dvc" / "cache")
    dvc(source, "pull", "selected.jsonl.dvc")
    assert hashlib.sha256((source / "selected.jsonl").read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("overlap", [False, True])
def test_selected_dataset_rejects_term_leakage(tmp_path, overlap):
    import json
    from scripts.snapshot import hashes
    from scripts.verify_dataset import verify

    files = {
        "audit_sft_v5.jsonl": [{"term_id": "train", "split": "train", "label": "ok"},
                               {"term_id": "train" if overlap else "eval", "split": "test", "label": "fix"}],
        "audit_holdout_sft.jsonl": [{"term_id": "holdout", "split": "test", "label": "ok"}],
    }
    objects = []
    for name, rows in files.items():
        path = tmp_path / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        objects.append({"name": name, "rows": len(rows), **hashes(path)})
    manifest = {"dataset_id": "synthetic", "objects": objects,
                "split_summary": {"human_ground_truth": "not-attested"}}
    if overlap:
        with pytest.raises(ValueError, match="term overlap"):
            verify(manifest, tmp_path)
    else:
        assert verify(manifest, tmp_path)["train_terms"] == 1
