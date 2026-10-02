"""Seal blind human audit labels and compare models on the same frozen holdout."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

MIN_CASES = 20
LABELS = {"ok", "fix", "unsure"}


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def term_key(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    compact = "".join(character for character in value if character.isalnum())
    return compact or "".join(value.split())


def source_key(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Invalid reference URL")
    host = parsed.hostname.casefold().removeprefix("www.")
    path = unquote(parsed.path).rstrip("/")
    title = parse_qs(parsed.query).get("title")
    if path == "/w/index.php" and title:
        path = "/wiki/" + title[0]
    path = unicodedata.normalize("NFKC", path).replace("_", " ").casefold()
    return host + path


def item_hash(case: dict) -> str:
    return hashlib.sha256(
        json.dumps(case, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def sheet_text(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def review_fields(case: dict) -> dict:
    return {
        "case_id": case["case_id"],
        **{
            key: sheet_text(case[key])
            for key in ("canonical", "definition", "origin", "nuance")
        },
        "reference_urls": "\n".join(doc["url"] for doc in case["documents"]),
        "reference_excerpts": sheet_text(
            "\n\n".join(doc["excerpt"] for doc in case["documents"])
        ),
    }


def load_pack(directory: Path) -> tuple[dict, list, dict]:
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported review pack")
    for name in ("cases.jsonl", "inventory.json"):
        if digest(directory / name) != manifest["files"][name]:
            raise ValueError("Review pack checksum mismatch")
    cases = [
        json.loads(line)
        for line in (directory / "cases.jsonl").read_text().splitlines()
    ]
    inventory = json.loads((directory / "inventory.json").read_text())
    if len(cases) != manifest["case_count"] or len(cases) < MIN_CASES:
        raise ValueError("Holdout has too few cases")
    validate_cases(cases, inventory)
    return manifest, cases, inventory


def validate_cases(cases: list, inventory: dict) -> None:
    blocked_ids = set(inventory["term_ids"])
    blocked_names = set(inventory["term_keys"])
    blocked_sources = set(inventory["source_keys"])
    seen_ids, seen_names, seen_sources = set(), set(), set()
    for case in cases:
        identities = {
            term_key(value) for value in [case["canonical"], *case["aliases"]]
        }
        sources = {source_key(document["url"]) for document in case["documents"]}
        if (
            not identities
            or "" in identities
            or not sources
            or not case["prompt"].strip()
        ):
            raise ValueError("Incomplete evaluation case")
        if case["term_id"] in blocked_ids | seen_ids or identities & (
            blocked_names | seen_names
        ):
            raise ValueError("Evaluation term overlap")
        if sources & (blocked_sources | seen_sources):
            raise ValueError("Evaluation source overlap")
        if case["case_id"] != item_hash(
            {
                key: value
                for key, value in case.items()
                if key not in ("case_id", "human_review")
            }
        ):
            raise ValueError("Evaluation case identity mismatch")
        seen_ids.add(case["term_id"])
        seen_names.update(identities)
        seen_sources.update(sources)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate case identity")


def seal(directory: Path, annotations: Path, attestation: Path, output: Path) -> dict:
    manifest, cases, inventory = load_pack(directory)
    assertion = json.loads(attestation.read_text())
    if (
        assertion.get("inventory_sha256") != manifest["files"]["inventory.json"]
        or assertion.get("training_source_inventory_complete") is not True
        or not isinstance(assertion.get("confirmed_by"), str)
        or not assertion["confirmed_by"].strip()
        or not isinstance(assertion.get("confirmed_at"), str)
        or not assertion["confirmed_at"].strip()
    ):
        raise ValueError("Training source lineage needs explicit human confirmation")
    if inventory.get("unmapped_training_terms"):
        raise ValueError("Training source inventory has unmapped terms")
    if datetime.fromisoformat(assertion["confirmed_at"]).tzinfo is None:
        raise ValueError("Source confirmation needs a timezone")
    with annotations.open(newline="", encoding="utf-8-sig") as source:
        reviews = list(csv.DictReader(source))
    expected = {case["case_id"] for case in cases}
    if (
        len(reviews) != len(expected)
        or {row.get("case_id") for row in reviews} != expected
    ):
        raise ValueError("Missing, extra or duplicate human reviews")
    by_id = {}
    original = {case["case_id"]: review_fields(case) for case in cases}
    for row in reviews:
        if any(
            row.get(key) != value for key, value in original[row["case_id"]].items()
        ):
            raise ValueError("Read-only review inputs were changed")
        if row.get("label") not in LABELS or any(
            not row.get(key, "").strip()
            for key in ("reason", "reviewer", "reviewed_at")
        ):
            raise ValueError(
                "All cases need a human label, reason, reviewer and review time"
            )
        if datetime.fromisoformat(row["reviewed_at"]).tzinfo is None:
            raise ValueError("Human review time needs a timezone")
        by_id[row["case_id"]] = {
            key: row[key].strip()
            for key in ("label", "reason", "reviewer", "reviewed_at")
        }
    ready = [case for case in cases if by_id[case["case_id"]]["label"] != "unsure"]
    if len(ready) < MIN_CASES or {
        by_id[case["case_id"]]["label"] for case in ready
    } != {"ok", "fix"}:
        raise ValueError("Need at least 20 decisive cases containing both labels")
    result = {
        "schema_version": 1,
        "evaluation_id": manifest["evaluation_id"],
        "cases_sha256": manifest["files"]["cases.jsonl"],
        "inventory_sha256": manifest["files"]["inventory.json"],
        "annotations_sha256": digest(annotations),
        "source_attestation": assertion,
        "inventory": inventory,
        "inventory_content_sha256": item_hash(inventory),
        "cases": [{**case, "human_review": by_id[case["case_id"]]} for case in ready],
        "excluded_unsure": len(cases) - len(ready),
        "promotion_eligible": False,
    }
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def load_gold(path: Path) -> tuple[dict, str]:
    gold = json.loads(path.read_text())
    if gold.get("schema_version") != 1 or len(gold.get("cases", [])) < MIN_CASES:
        raise ValueError("Missing independent human evaluation set")
    cases = gold["cases"]
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate gold case")
    if {case["human_review"]["label"] for case in cases} != {"ok", "fix"}:
        raise ValueError("Gold set must contain both decisive human labels")
    if (
        gold.get("source_attestation", {}).get("training_source_inventory_complete")
        is not True
    ):
        raise ValueError("Unconfirmed source lineage")
    assertion = gold["source_attestation"]
    if (
        assertion.get("inventory_sha256") != gold["inventory_sha256"]
        or not assertion.get("confirmed_by")
        or not assertion.get("confirmed_at")
    ):
        raise ValueError("Missing human source confirmation provenance")
    if gold["inventory"].get("unmapped_training_terms"):
        raise ValueError("Training source inventory is incomplete")
    if gold.get("inventory_content_sha256") != item_hash(gold["inventory"]):
        raise ValueError("Sealed source inventory was changed")
    if datetime.fromisoformat(assertion["confirmed_at"]).tzinfo is None:
        raise ValueError("Source confirmation needs a timezone")
    validate_cases(cases, gold["inventory"])
    for case in cases:
        if any(
            not case["human_review"].get(key)
            for key in ("reviewer", "reviewed_at", "reason")
        ):
            raise ValueError("Missing human label provenance")
        if datetime.fromisoformat(case["human_review"]["reviewed_at"]).tzinfo is None:
            raise ValueError("Human review time needs a timezone")
    return gold, digest(path)


def score(gold: dict, gold_hash: str, run: dict) -> dict:
    if (
        run.get("evaluation_sha256") != gold_hash
        or run.get("parser_policy") != "json-object-verdict-ok-fix"
        or not run.get("model_id")
        or not run.get("model_revision")
    ):
        raise ValueError("Model run uses different evaluation data or lacks provenance")
    if not re.fullmatch(r"[a-f0-9]{40}", run["model_revision"]):
        raise ValueError("Model revision must be a commit digest")
    if run.get("adapter_sha256") and not re.fullmatch(
        r"[a-f0-9]{64}", run["adapter_sha256"]
    ):
        raise ValueError("Adapter identity must be a SHA-256 digest")
    contract = run.get("inference_contract", {})
    for key in (
        "train_sha256",
        "quality_sha256",
        "lock_sha256",
        "chat_template_sha256",
    ):
        if not re.fullmatch(r"[a-f0-9]{64}", contract.get(key, "")):
            raise ValueError("Missing inference contract digest")
    if (
        contract.get("max_new_tokens") != 160
        or contract.get("do_sample") is not False
        or contract.get("enable_thinking") is not False
        or contract.get("dtype") not in {"bfloat16", "float16"}
    ):
        raise ValueError("Unexpected inference settings")
    if run.get("adapter_sha256") and not re.fullmatch(
        r"[a-f0-9]{64}", run.get("adapter_config_sha256", "")
    ):
        raise ValueError("Missing adapter configuration checksum")
    predictions = run["predictions"]
    expected = {case["case_id"] for case in gold["cases"]}
    if (
        len(predictions) != len(expected)
        or {row["case_id"] for row in predictions} != expected
    ):
        raise ValueError("Model run omitted, duplicated or added cases")
    by_id = {row["case_id"]: row for row in predictions}
    counts = {"correct": 0, "tp": 0, "fp": 0, "fn": 0, "format_failures": 0}
    times = []
    for case in gold["cases"]:
        row = by_id[case["case_id"]]
        value = row["prediction"]
        if value not in {"ok", "fix", "unparsed"}:
            raise ValueError("Unknown prediction status")
        latency = row["latency_seconds"]
        if (
            isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or not math.isfinite(latency)
            or latency < 0
        ):
            raise ValueError("Invalid model timing")
        times.append(latency)
        label = case["human_review"]["label"]
        counts["correct"] += value == label
        counts["tp"] += label == value == "fix"
        counts["fp"] += label == "ok" and value == "fix"
        counts["fn"] += label == "fix" and value != "fix"
        counts["format_failures"] += value == "unparsed"
    n = len(expected)
    return {
        "n": n,
        "accuracy": counts["correct"] / n,
        "fix_precision": counts["tp"] / max(1, counts["tp"] + counts["fp"]),
        "fix_recall": counts["tp"] / max(1, counts["tp"] + counts["fn"]),
        "false_positives": counts["fp"],
        "missed_fixes": counts["fn"],
        "format_failures": counts["format_failures"],
        "latency_p50_seconds": statistics.median(times),
        "latency_max_seconds": max(times),
    }


def compare(gold_path: Path, baseline_path: Path, candidate_path: Path) -> dict:
    gold, gold_hash = load_gold(gold_path)
    baseline = json.loads(baseline_path.read_text())
    candidate = json.loads(candidate_path.read_text())
    first, second = score(gold, gold_hash, baseline), score(gold, gold_hash, candidate)
    if baseline.get("adapter_sha256") or not candidate.get("adapter_sha256"):
        raise ValueError("Compare the base model against a versioned adapter candidate")
    if (baseline["model_id"], baseline["model_revision"]) != (
        candidate["model_id"],
        candidate["model_revision"],
    ):
        raise ValueError("Model lineage differs between runs")
    if baseline["inference_contract"] != candidate["inference_contract"]:
        raise ValueError("Inference contracts differ between runs")
    recommended = (
        second["accuracy"] > first["accuracy"]
        and second["fix_recall"] >= first["fix_recall"]
        and second["false_positives"] <= first["false_positives"]
        and second["format_failures"] <= first["format_failures"]
    )
    return {
        "evaluation_sha256": gold_hash,
        "baseline": first,
        "candidate": second,
        "candidate_adapter_sha256": candidate["adapter_sha256"],
        "candidate_adapter_config_sha256": candidate["adapter_config_sha256"],
        "recommended_for_human_approval": recommended,
        "promotion_eligible": False,
        "human_promotion_approval_required": True,
    }


def predict(
    gold_path: Path, output: Path, adapter: Path | None, adapter_hash: str | None
) -> dict:
    gold, gold_hash = load_gold(gold_path)
    if output.exists():
        raise ValueError("Model run output already exists")
    if adapter_hash and not adapter:
        raise ValueError("Adapter checksum requires an adapter directory")
    if adapter and (
        not adapter_hash
        or digest(adapter / "adapter_model.safetensors") != adapter_hash
    ):
        raise ValueError("Candidate adapter checksum mismatch")
    import time

    import torch
    from train import BASE_MODEL, BASE_REVISION, evaluate
    from transformers import AutoModelForMultimodalLM, AutoTokenizer, BitsAndBytesConfig

    if not torch.cuda.is_available():
        raise RuntimeError("Prediction requires CUDA")
    if adapter:
        config = json.loads((adapter / "adapter_config.json").read_text())
        if (
            config.get("base_model_name_or_path") != BASE_MODEL
            or config.get("revision") != BASE_REVISION
        ):
            raise ValueError("Candidate base model revision is not pinned")
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, revision=BASE_REVISION)
    model = AutoModelForMultimodalLM.from_pretrained(
        BASE_MODEL,
        revision=BASE_REVISION,
        dtype=dtype,
        device_map={"": 0},
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        ),
    )
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter)
    predictions = []
    for case in gold["cases"]:
        row = {
            "term_id": case["term_id"],
            "messages": [{"role": "user", "content": case["prompt"]}],
            "label": case["human_review"]["label"],
        }
        started = time.monotonic()
        result = evaluate(model, tokenizer, [row])["predictions"][0]
        predictions.append(
            {
                "case_id": case["case_id"],
                "prediction": result["prediction"],
                "latency_seconds": time.monotonic() - started,
            }
        )
    run = {
        "evaluation_sha256": gold_hash,
        "model_id": BASE_MODEL,
        "model_revision": BASE_REVISION,
        "adapter_sha256": adapter_hash if adapter else None,
        "adapter_config_sha256": digest(adapter / "adapter_config.json")
        if adapter
        else None,
        "parser_policy": "json-object-verdict-ok-fix",
        "inference_contract": {
            "train_sha256": digest(Path(__file__).with_name("train.py")),
            "quality_sha256": digest(Path(__file__)),
            "lock_sha256": digest(Path(__file__).with_name("uv.lock")),
            "chat_template_sha256": hashlib.sha256(
                tokenizer.get_chat_template().encode()
            ).hexdigest(),
            "max_new_tokens": 160,
            "do_sample": False,
            "enable_thinking": False,
            "dtype": str(dtype).removeprefix("torch."),
        },
        "predictions": predictions,
    }
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(run, indent=2) + "\n")
    return score(gold, gold_hash, run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("inspect")
    command.add_argument("--pack", type=Path, required=True)
    command = commands.add_parser("seal")
    for name in ("pack", "annotations", "attestation", "output"):
        command.add_argument("--" + name, type=Path, required=True)
    command = commands.add_parser("predict")
    for name in ("gold", "output"):
        command.add_argument("--" + name, type=Path, required=True)
    command.add_argument("--adapter", type=Path)
    command.add_argument("--adapter-sha256")
    command = commands.add_parser("compare")
    for name in ("gold", "baseline", "candidate", "output"):
        command.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == "inspect":
        manifest, cases, inventory = load_pack(args.pack)
        print(
            json.dumps(
                {
                    "evaluation_id": manifest["evaluation_id"],
                    "cases": len(cases),
                    "excluded_prior_terms": len(inventory["term_ids"]),
                    "excluded_source_keys": len(inventory["source_keys"]),
                    "source_lineage_confirmation": "human-confirmation-required",
                    "human_review": "required",
                    "promotion_eligible": False,
                }
            )
        )
    elif args.command == "seal":
        result = seal(args.pack, args.annotations, args.attestation, args.output)
        print(
            json.dumps(
                {
                    "evaluation_id": result["evaluation_id"],
                    "cases": len(result["cases"]),
                    "promotion_eligible": False,
                }
            )
        )
    elif args.command == "predict":
        print(
            json.dumps(
                predict(args.gold, args.output, args.adapter, args.adapter_sha256)
            )
        )
    else:
        result = compare(args.gold, args.baseline, args.candidate)
        with args.output.open("x", encoding="utf-8") as target:
            target.write(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 – Keep private inputs out of error logs.
        print(json.dumps({"error_code": type(error).__name__}))
        raise SystemExit(1) from None
