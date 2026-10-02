"""Train and resume the audit adapter with pinned inputs and full Trainer state."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import re
import time
from pathlib import Path

BASE_MODEL = "google/gemma-4-12B-it"
BASE_REVISION = "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"
INPUT_FILES = {"audit_sft_v5.jsonl", "audit_holdout_sft.jsonl"}
END_OF_TURN = "<turn|>"
IGNORE_INDEX = -100
HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_inputs(directory: Path) -> tuple[list, list, dict]:
    manifest_path = directory / "audit-v5-baseline.json"
    manifest = json.loads(manifest_path.read_text())
    objects = manifest["objects"]
    if len(objects) != len(INPUT_FILES) or {item["name"] for item in objects} != INPUT_FILES:
        raise ValueError("Unexpected input inventory")
    rows_by_name = {}
    for item in objects:
        path = directory / item["name"]
        if path.stat().st_size != item["size"] or sha256(path) != item["sha256"]:
            raise ValueError("Input hash mismatch")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != item["rows"] or not rows:
            raise ValueError("Input row count mismatch")
        for row in rows:
            if row["label"] not in {"ok", "fix"} or not row["term_id"]:
                raise ValueError("Invalid audit label")
            messages = row["messages"]
            if len(messages) != 2 or [message["role"] for message in messages] != ["user", "assistant"]:
                raise ValueError("Expected one user prompt and one assistant answer")
            if any(not isinstance(message["content"], str) or not message["content"].strip() for message in messages):
                raise ValueError("Empty or non-text audit message")
        rows_by_name[item["name"]] = rows
    rows = rows_by_name["audit_sft_v5.jsonl"]
    if any(row["split"] not in {"train", "test", "test2"} for row in rows):
        raise ValueError("Unknown input split")
    train = [row for row in rows if row["split"] == "train"]
    evaluation = [row for row in rows if row["split"] == "test"]
    train_ids = {row["term_id"] for row in train}
    held_out = {row["term_id"] for row in rows if row["split"] != "train"}
    held_out.update(row["term_id"] for row in rows_by_name["audit_holdout_sft.jsonl"])
    if not train or not evaluation or train_ids & held_out:
        raise ValueError("Missing split or training/evaluation term leakage")
    return train, evaluation, manifest


def tokenize_rows(rows, tokenizer, max_length: int) -> list[dict]:
    encoded = []
    for row in rows:
        prompt = tokenizer.apply_chat_template(row["messages"][:1], tokenize=True,
                                               add_generation_prompt=True, enable_thinking=False, return_dict=False)
        completion = tokenizer(row["messages"][1]["content"].strip() + END_OF_TURN,
                               add_special_tokens=False)["input_ids"]
        complete = prompt + completion
        if len(complete) > max_length:
            raise ValueError("Input exceeds max_length; refusing to truncate its answer")
        if len(complete) <= len(prompt):
            raise ValueError("No completion tokens")
        encoded.append({"input_ids": complete, "attention_mask": [1] * len(complete),
                        "labels": [IGNORE_INDEX] * len(prompt) + complete[len(prompt):]})
    return encoded


def metrics(predictions: list[dict]) -> dict:
    count = len(predictions)
    parsed = sum(row["prediction"] in {"ok", "fix"} for row in predictions)
    tp = sum(row["label"] == row["prediction"] == "fix" for row in predictions)
    fp = sum(row["label"] == "ok" and row["prediction"] == "fix" for row in predictions)
    fn = sum(row["label"] == "fix" and row["prediction"] != "fix" for row in predictions)
    return {"n": count, "parsed": parsed, "format_failures": count - parsed,
            "accuracy": sum(row["label"] == row["prediction"] for row in predictions) / max(1, count),
            "fix_precision": tp / max(1, tp + fp), "fix_recall": tp / max(1, tp + fn)}


def checkpoint_path(path: Path, contract: dict) -> Path:
    match = re.fullmatch(r"checkpoint-([1-9]\d*)", path.name)
    if not match:
        raise ValueError("Expected a numbered Trainer checkpoint")
    required = {"adapter_model.safetensors", "adapter_config.json", "optimizer.pt", "scheduler.pt",
                "rng_state.pth", "trainer_state.json", "run-contract.json"}
    if contract.get("dtype") == "torch.float16":
        required.add("scaler.pt")
    if any(not (path / name).is_file() for name in required):
        raise ValueError("Checkpoint lacks weights, optimizer, scheduler, RNG, precision scaler or contract")
    if json.loads((path / "run-contract.json").read_text()) != contract:
        raise ValueError("Checkpoint belongs to different inputs, code, libraries or training options")
    if json.loads((path / "trainer_state.json").read_text())["global_step"] != int(match[1]):
        raise ValueError("Checkpoint step does not match Trainer state")
    return path


def callbacks(contract: dict, stop_after: int | None = None):
    from transformers import TrainerCallback

    class SaveContract(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            for name in ("loss", "grad_norm"):
                if logs and name in logs and not math.isfinite(float(logs[name])):
                    raise FloatingPointError("Non-finite training values; refusing to save a checkpoint")

        def on_save(self, args, state, control, **kwargs):
            path = Path(args.output_dir) / f"checkpoint-{state.global_step}" / "run-contract.json"
            path.write_text(json.dumps(contract, indent=2) + "\n")

        def on_step_end(self, args, state, control, **kwargs):
            if stop_after is not None and state.global_step >= stop_after:
                control.should_save = True
                control.should_training_stop = True
            return control

    return [SaveContract()]


def completion_trainer(**kwargs):
    import torch
    from transformers import Trainer

    class CompletionTrainer(Trainer):
        def __init__(self, **options):
            super().__init__(**options)
            self.model_accepts_loss_kwargs = False

        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            labels = inputs["labels"]
            positions = (labels[:, 1:] != IGNORE_INDEX).any(dim=0).nonzero(as_tuple=True)[0]
            model_inputs = {name: value for name, value in inputs.items() if name != "labels"}
            outputs = model(**model_inputs, logits_to_keep=positions, use_cache=False)
            targets = labels[:, positions + 1].to(outputs.logits.device)
            loss = torch.nn.functional.cross_entropy(
                outputs.logits.float().reshape(-1, outputs.logits.shape[-1]), targets.reshape(-1),
                ignore_index=IGNORE_INDEX)
            return (loss, outputs) if return_outputs else loss

    return CompletionTrainer(**kwargs)


def verdict(text: str) -> str:
    try:
        response = json.loads(text)
    except json.JSONDecodeError:
        return "unparsed"
    if not isinstance(response, dict):
        return "unparsed"
    value = response.get("verdict")
    return value if value in ("ok", "fix") else "unparsed"


def evaluate(model, tokenizer, rows) -> dict:
    import torch

    predictions = []
    model.eval()
    for row in rows:
        inputs = tokenizer.apply_chat_template(row["messages"][:1], tokenize=True, enable_thinking=False,
                                               add_generation_prompt=True, return_dict=True,
                                               return_tensors="pt").to(model.device)
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=160, do_sample=False)
        text = tokenizer.decode(output[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
        prediction = verdict(text)
        predictions.append({"term_id": row["term_id"], "label": row["label"], "prediction": prediction})
    return {"summary": metrics(predictions), "predictions": predictions}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--max-steps", type=int, default=4)
    parser.add_argument("--stop-after", type=int)
    parser.add_argument("--max-length", type=int, default=3072)
    parser.add_argument("--train-rows", type=int, default=8)
    parser.add_argument("--eval-rows", type=int, default=2)
    args = parser.parse_args()
    if min(args.max_steps, args.max_length, args.train_rows, args.eval_rows) <= 0:
        parser.error("Step, length and row limits must be positive")
    if args.stop_after is not None and not 0 < args.stop_after < args.max_steps:
        parser.error("stop-after must be between zero and max-steps")
    train, evaluation, input_manifest = load_inputs(args.input_dir)

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForMultimodalLM, AutoTokenizer, BitsAndBytesConfig,
                              DataCollatorForSeq2Seq, TrainingArguments, set_seed)

    if not torch.cuda.is_available():
        raise RuntimeError("GPU training requires a CUDA device")
    set_seed(42)
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, revision=BASE_REVISION)
    train = train[:args.train_rows]
    evaluation = evaluation[:args.eval_rows]
    encoded = tokenize_rows(train, tokenizer, args.max_length)
    template = tokenizer.get_chat_template()
    bundle = json.loads((HERE / "bundle.json").read_text())
    if any(sha256(HERE / name) != value for name, value in bundle["files"].items()):
        raise ValueError("Training source differs from its packaged provenance")
    contract = {"version": 1, "base_model": BASE_MODEL, "base_revision": BASE_REVISION,
                "code_commit": bundle["code_commit"], "source_is_committed": bundle["source_is_committed"],
                "dataset_manifest_sha256": sha256(args.input_dir / "audit-v5-baseline.json"),
                "code_sha256": sha256(HERE / "train.py"), "lock_sha256": sha256(HERE / "uv.lock"),
                "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest(),
                "prompt_sha256": hashlib.sha256(json.dumps([row["messages"][0] for row in train], sort_keys=True).encode()).hexdigest(),
                "evaluation_sha256": hashlib.sha256(json.dumps(evaluation, sort_keys=True).encode()).hexdigest(),
                "max_steps": args.max_steps, "max_length": args.max_length,
                "train_rows": len(train), "evaluation_rows": len(evaluation), "seed": 42,
                "dtype": str(dtype), "learning_rate": 0.0001, "lora_r": 16, "lora_alpha": 16,
                "gpu_count": torch.cuda.device_count(),
                "gradient_accumulation_steps": 4, "batch_size": 1, "enable_thinking": False,
                "completion_end_token": END_OF_TURN,
                "loss_policy": "completion-logits-only",
                "label_source": input_manifest["label_source"], "promotion_eligible": False,
                "libraries": {name: importlib.metadata.version(name) for name in
                              ("torch", "transformers", "peft", "accelerate", "datasets", "bitsandbytes")}}
    resume = checkpoint_path(args.resume_from, contract) if args.resume_from else None
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError("Use a new output directory; previous results are not overwritten")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "run-contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    model = AutoModelForMultimodalLM.from_pretrained(
        BASE_MODEL, revision=BASE_REVISION, dtype=dtype, device_map={"": 0},
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_use_double_quant=True,
                                              bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype),
        attn_implementation="eager")
    model.config.use_cache = False
    before = evaluate(model, tokenizer, evaluation)
    (args.output_dir / "before.json").write_text(json.dumps(before, indent=2) + "\n")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=16, lora_dropout=0.05, bias="none",
                                           target_modules="all-linear", task_type="CAUSAL_LM"))
    model.peft_config["default"].revision = BASE_REVISION
    training = TrainingArguments(
        output_dir=str(args.output_dir), max_steps=args.max_steps, per_device_train_batch_size=1,
        gradient_accumulation_steps=4, gradient_checkpointing=True, learning_rate=0.0001,
        lr_scheduler_type="constant", optim="adamw_torch", max_grad_norm=0.3,
        bf16=dtype == torch.bfloat16, fp16=dtype == torch.float16, save_strategy="steps", save_steps=1,
        save_total_limit=2, save_only_model=False, logging_steps=1, report_to="none", seed=42,
        data_seed=42, dataloader_num_workers=0, disable_tqdm=True, push_to_hub=False)
    trainer = completion_trainer(
        model=model, args=training, train_dataset=Dataset.from_list(encoded),
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=IGNORE_INDEX),
        callbacks=callbacks(contract, args.stop_after))
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    trainer.train(resume_from_checkpoint=str(resume) if resume else None)
    elapsed = time.monotonic() - started
    optimizer_updates = min((int(value["step"]) for value in trainer.optimizer.state.values()
                             if "step" in value), default=0)
    if optimizer_updates != trainer.state.global_step:
        raise FloatingPointError("Optimizer skipped updates; training is not complete")
    model.save_pretrained(args.output_dir / "adapter")
    tokenizer.save_pretrained(args.output_dir / "adapter")
    model.config.use_cache = True
    after = evaluate(model, tokenizer, evaluation)
    checkpoints = sorted(args.output_dir.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1]))
    for checkpoint in checkpoints:
        checkpoint_path(checkpoint, contract)
    result = {"global_step": trainer.state.global_step, "max_steps": args.max_steps,
              "optimizer_updates": optimizer_updates,
              "stopped_early": trainer.state.global_step < args.max_steps,
              "resumed_from_step": json.loads((resume / "trainer_state.json").read_text())["global_step"] if resume else None,
              "train_seconds": round(elapsed, 3), "peak_vram_gib": torch.cuda.max_memory_allocated() / 2**30,
              "gpu": torch.cuda.get_device_name(0), "before": before, "after": after,
              "checkpoints": [path.name for path in checkpoints], "promotion_eligible": False}
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("global_step", "stopped_early", "train_seconds", "peak_vram_gib")}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"error_code": type(error).__name__}))
        raise SystemExit(1) from None
