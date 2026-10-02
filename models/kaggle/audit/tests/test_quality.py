import copy
import csv
import json

import pytest
from quality import (
    compare,
    digest,
    item_hash,
    load_gold,
    review_fields,
    score,
    seal,
    source_key,
)


@pytest.fixture
def pack(tmp_path):
    folder = tmp_path / "pack"
    folder.mkdir()
    cases = []
    for index in range(20):
        case = {
            "term_id": f"t{index}",
            "canonical": f"case{index}",
            "aliases": [],
            "definition": "synthetic definition",
            "origin": "synthetic origin",
            "nuance": "synthetic nuance",
            "prompt": "synthetic audit prompt",
            "documents": [
                {
                    "url": f"https://example.test/wiki/case{index}",
                    "excerpt": "synthetic evidence",
                }
            ],
        }
        cases.append({**case, "case_id": item_hash(case)})
    (folder / "cases.jsonl").write_text(
        "".join(json.dumps(case) + "\n" for case in cases)
    )
    inventory = {
        "term_ids": ["trained"],
        "term_keys": ["trainedalias"],
        "source_keys": ["example.test/wiki/trained"],
        "unmapped_training_terms": [],
    }
    (folder / "inventory.json").write_text(json.dumps(inventory))
    manifest = {
        "schema_version": 1,
        "evaluation_id": "synthetic-evaluation",
        "case_count": 20,
        "files": {
            name: digest(folder / name) for name in ("cases.jsonl", "inventory.json")
        },
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with (folder / "review.csv").open("w", newline="") as target:
        fields = list(review_fields(cases[0])) + [
            "label",
            "reason",
            "reviewer",
            "reviewed_at",
        ]
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for index, case in enumerate(cases):
            writer.writerow(
                {
                    **review_fields(case),
                    "label": "ok" if index < 10 else "fix",
                    "reason": "synthetic human reason",
                    "reviewer": "synthetic reviewer",
                    "reviewed_at": "2026-10-02T12:00:00+09:00",
                }
            )
    (folder / "attestation.json").write_text(
        json.dumps(
            {
                "inventory_sha256": manifest["files"]["inventory.json"],
                "training_source_inventory_complete": True,
                "confirmed_by": "synthetic source owner",
                "confirmed_at": "2026-10-02T12:00:00+09:00",
            }
        )
    )
    return folder


def gold(pack):
    path = pack / "gold.json"
    seal(pack, pack / "review.csv", pack / "attestation.json", path)
    return path


def run_for(gold_path, candidate=False):
    document, identity = load_gold(gold_path)
    return {
        "evaluation_sha256": identity,
        "model_id": "synthetic-model",
        "model_revision": "a" * 40,
        "adapter_config_sha256": "f" * 64 if candidate else None,
        "adapter_sha256": "b" * 64 if candidate else None,
        "parser_policy": "json-object-verdict-ok-fix",
        "inference_contract": {
            **{
                key: "d" * 64
                for key in (
                    "train_sha256",
                    "quality_sha256",
                    "lock_sha256",
                    "chat_template_sha256",
                )
            },
            "max_new_tokens": 160,
            "do_sample": False,
            "enable_thinking": False,
            "dtype": "bfloat16",
        },
        "predictions": [
            {
                "case_id": case["case_id"],
                "prediction": case["human_review"]["label"] if candidate else "ok",
                "latency_seconds": 0.2,
            }
            for case in document["cases"]
        ],
    }


def test_source_identity_removes_transport_fragment_and_wiki_aliases():
    assert source_key("http://www.example.test/wiki/A_B#section") == source_key(
        "https://example.test/wiki/A%20B?tracking=1"
    )
    assert source_key("https://example.test/w/index.php?title=A_B") == source_key(
        "https://example.test/wiki/A_B"
    )
    with pytest.raises(ValueError):
        source_key("javascript:alert(1)")


def test_healthy_comparison_is_a_proposal_not_a_promotion(pack):
    path = gold(pack)
    base, candidate = run_for(path), run_for(path, True)
    (pack / "base.json").write_text(json.dumps(base))
    (pack / "candidate.json").write_text(json.dumps(candidate))
    result = compare(path, pack / "base.json", pack / "candidate.json")
    assert result["recommended_for_human_approval"] is True
    assert result["promotion_eligible"] is False
    assert result["candidate"]["accuracy"] == 1
    candidate["predictions"][10]["prediction"] = "unparsed"
    scored = score(*load_gold(path), candidate)
    assert (
        scored["missed_fixes"] == 1
        and scored["format_failures"] == 1
        and scored["n"] == 20
    )
    (pack / "candidate.json").write_text(json.dumps(candidate))
    assert (
        compare(path, pack / "base.json", pack / "candidate.json")[
            "recommended_for_human_approval"
        ]
        is False
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("label", ""),
        ("reason", ""),
        ("reviewer", ""),
        ("reviewed_at", "invalid"),
        ("definition", "changed"),
    ],
)
def test_seal_rejects_unreviewed_or_changed_inputs(pack, field, value):
    with (pack / "review.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    rows[0][field] = value
    with (pack / "review.csv").open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        seal(pack, pack / "review.csv", pack / "attestation.json", pack / "gold.json")
    assert not (pack / "gold.json").exists()


@pytest.mark.parametrize(
    "kind",
    ["unconfirmed", "wrong-hash", "unmapped", "term", "alias", "source", "case-tamper"],
)
def test_pack_and_source_gates(pack, kind):
    assertion = json.loads((pack / "attestation.json").read_text())
    inventory = json.loads((pack / "inventory.json").read_text())
    cases = [
        json.loads(line) for line in (pack / "cases.jsonl").read_text().splitlines()
    ]
    if kind == "unconfirmed":
        assertion["training_source_inventory_complete"] = False
    if kind == "wrong-hash":
        assertion["inventory_sha256"] = "c" * 64
    if kind == "unmapped":
        inventory["unmapped_training_terms"] = ["trained"]
    if kind == "term":
        inventory["term_ids"].append(cases[0]["term_id"])
    if kind == "alias":
        inventory["term_keys"].append(cases[0]["canonical"])
    if kind == "source":
        inventory["source_keys"].append(source_key(cases[0]["documents"][0]["url"]))
    if kind == "case-tamper":
        cases[0]["prompt"] = "different prompt"
    (pack / "cases.jsonl").write_text(
        "".join(json.dumps(case) + "\n" for case in cases)
    )
    (pack / "inventory.json").write_text(json.dumps(inventory))
    manifest = json.loads((pack / "manifest.json").read_text())
    manifest["files"] = {
        name: digest(pack / name) for name in ("cases.jsonl", "inventory.json")
    }
    (pack / "manifest.json").write_text(json.dumps(manifest))
    if kind not in ("wrong-hash", "unconfirmed"):
        assertion["inventory_sha256"] = manifest["files"]["inventory.json"]
    (pack / "attestation.json").write_text(json.dumps(assertion))
    with pytest.raises(ValueError):
        seal(pack, pack / "review.csv", pack / "attestation.json", pack / "gold.json")


@pytest.mark.parametrize(
    "failure",
    ["missing", "duplicate", "data", "parser", "nan", "infinite", "boolean", "adapter"],
)
def test_model_report_gates(pack, failure):
    path = gold(pack)
    document, identity = load_gold(path)
    run = run_for(path, True)
    if failure == "missing":
        run["predictions"].pop()
    if failure == "duplicate":
        run["predictions"][1] = copy.deepcopy(run["predictions"][0])
    if failure == "data":
        run["evaluation_sha256"] = "c" * 64
    if failure == "parser":
        run["parser_policy"] = "regex"
    if failure == "nan":
        run["predictions"][0]["latency_seconds"] = float("nan")
    if failure == "infinite":
        run["predictions"][0]["latency_seconds"] = float("inf")
    if failure == "boolean":
        run["predictions"][0]["latency_seconds"] = True
    if failure == "adapter":
        run["adapter_sha256"] = "unknown"
    with pytest.raises(ValueError):
        score(document, identity, run)


def test_comparison_rejects_changed_inference_contract(pack):
    path = gold(pack)
    base, candidate = run_for(path), run_for(path, True)
    candidate["inference_contract"]["chat_template_sha256"] = "e" * 64
    (pack / "base.json").write_text(json.dumps(base))
    (pack / "candidate.json").write_text(json.dumps(candidate))
    with pytest.raises(ValueError, match="contracts differ"):
        compare(path, pack / "base.json", pack / "candidate.json")


def test_gold_rejects_changed_inventory(pack):
    path = gold(pack)
    document = json.loads(path.read_text())
    document["inventory"]["source_keys"] = []
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="inventory was changed"):
        load_gold(path)


def test_uncertain_cases_cannot_fill_minimum_gold_count(pack):
    with (pack / "review.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    rows[0]["label"] = "unsure"
    with (pack / "review.csv").open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="20 decisive"):
        seal(pack, pack / "review.csv", pack / "attestation.json", pack / "gold.json")
