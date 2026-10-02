"""Verify selected DVC payloads against their private intake manifest."""
import argparse
import json
from pathlib import Path

from scripts.snapshot import hashes

FILES = {"audit_sft_v5.jsonl", "audit_holdout_sft.jsonl"}


def verify(manifest: dict, directory: Path) -> dict:
    objects = manifest["objects"]
    if len(objects) != len(FILES) or {item["name"] for item in objects} != FILES:
        raise ValueError("Invalid dataset object inventory")
    datasets = {}
    for item in objects:
        path = directory / item["name"]
        if hashes(path) != {key: item[key] for key in ("size", "sha256", "crc32c")}:
            raise ValueError("Dataset checksum mismatch")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != item["rows"] or not rows:
            raise ValueError("Dataset row count mismatch")
        if any(row["label"] not in {"ok", "fix"} or not row["term_id"] for row in rows):
            raise ValueError("Invalid audit label or term")
        datasets[item["name"]] = rows
    training = datasets["audit_sft_v5.jsonl"]
    if any(row["split"] not in {"train", "test", "test2"} for row in training):
        raise ValueError("Invalid training split")
    train_ids = {row["term_id"] for row in training if row["split"] == "train"}
    evaluation_ids = {row["term_id"] for row in training if row["split"] != "train"}
    holdout_ids = {row["term_id"] for row in datasets["audit_holdout_sft.jsonl"]}
    if not train_ids or not evaluation_ids or train_ids & (evaluation_ids | holdout_ids):
        raise ValueError("Missing split or training/evaluation term overlap")
    return {"dataset_id": manifest["dataset_id"], "train_terms": len(train_ids),
            "evaluation_terms": len(evaluation_ids), "holdout_terms": len(holdout_ids),
            "human_ground_truth": manifest["split_summary"]["human_ground_truth"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(json.loads(args.manifest.read_text()), args.directory)))
    except Exception as error:
        print(json.dumps({"error_code": type(error).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
