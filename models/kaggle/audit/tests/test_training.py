import json

import pytest
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import GPT2Config, GPT2LMHeadModel, TrainingArguments, set_seed

from train import callbacks, checkpoint_path, completion_trainer, load_inputs, metrics, sha256, tokenize_rows


def test_resume_preserves_optimizer_scheduler_rng_and_final_weights(tmp_path):
    torch.set_num_threads(1)
    contract = {"signature": "synthetic-cpu-checkpoint-test"}
    dataset = Dataset.from_list([{"input_ids": [1, 3, 4, 5, 2], "labels": [-100, -100, 4, 5, 2]}] * 8)

    def run(name, stop_after=None, resume=None):
        set_seed(42)
        model = get_peft_model(GPT2LMHeadModel(GPT2Config(
            vocab_size=32, n_positions=16, n_embd=16, n_layer=1, n_head=2,
            bos_token_id=1, eos_token_id=2, pad_token_id=0)),
            LoraConfig(r=2, lora_alpha=2, lora_dropout=0.1, target_modules=["c_attn"], task_type="CAUSAL_LM"))
        args = TrainingArguments(output_dir=str(tmp_path / name), use_cpu=True, max_steps=4,
                                 per_device_train_batch_size=1, learning_rate=0.001, save_steps=1,
                                 save_strategy="steps", save_only_model=False, save_total_limit=2,
                                 report_to="none", disable_tqdm=True, seed=42, dataloader_num_workers=0)
        trainer = completion_trainer(model=model, args=args, train_dataset=dataset,
                                     callbacks=callbacks(contract, stop_after))
        trainer.train(resume_from_checkpoint=str(resume) if resume else None)
        return trainer

    uninterrupted = run("full")
    stopped = run("stop", stop_after=2)
    assert stopped.state.global_step == 2
    checkpoint = checkpoint_path(tmp_path / "stop" / "checkpoint-2", contract)
    resumed = run("resumed", resume=checkpoint)
    assert resumed.state.global_step == uninterrupted.state.global_step == 4
    for name, weight in uninterrupted.model.state_dict().items():
        torch.testing.assert_close(resumed.model.state_dict()[name], weight, rtol=0, atol=0)
    for full, restored in zip(uninterrupted.optimizer.state.values(), resumed.optimizer.state.values()):
        for key in full:
            torch.testing.assert_close(restored[key], full[key], rtol=0, atol=0)
    assert resumed.lr_scheduler.state_dict() == uninterrupted.lr_scheduler.state_dict()
    with pytest.raises(ValueError, match="different inputs"):
        checkpoint_path(checkpoint, {"signature": "different"})
    (checkpoint / "optimizer.pt").unlink()
    with pytest.raises(ValueError, match="lacks"):
        checkpoint_path(checkpoint, contract)


class Tokenizer:
    eos_token = "<end>"

    def apply_chat_template(self, messages, **options):
        return [1, 2]

    def __call__(self, content, **options):
        assert content.endswith("<turn|>")
        return {"input_ids": [3, 4]}


def test_prompt_is_masked_and_completion_is_not_truncated():
    rows = [{"messages": [{"role": "user", "content": "synthetic"}, {"role": "assistant", "content": "ok"}]}]
    assert tokenize_rows(rows, Tokenizer(), 4)[0]["labels"] == [-100, -100, 3, 4]
    with pytest.raises(ValueError, match="refusing to truncate"):
        tokenize_rows(rows, Tokenizer(), 3)


def test_format_failures_count_as_misses():
    result = metrics([{"label": "fix", "prediction": "unparsed"}, {"label": "ok", "prediction": "ok"}])
    assert result["accuracy"] == 0.5
    assert result["fix_recall"] == 0
    assert result["format_failures"] == 1


@pytest.mark.parametrize("leak", [False, True])
def test_input_hashes_and_split_separation(tmp_path, leak):
    objects = []
    for name, rows in {
        "audit_sft_v5.jsonl": [
            {"term_id": "train", "split": "train", "label": "ok"},
            {"term_id": "train" if leak else "evaluation", "split": "test", "label": "fix"}],
        "audit_holdout_sft.jsonl": [{"term_id": "holdout", "split": "test", "label": "ok"}],
    }.items():
        for row in rows:
            row["messages"] = [{"role": "user", "content": "synthetic"}, {"role": "assistant", "content": "ok"}]
        path = tmp_path / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        objects.append({"name": name, "size": path.stat().st_size, "sha256": sha256(path), "rows": len(rows)})
    (tmp_path / "audit-v5-baseline.json").write_text(json.dumps({"objects": objects}))
    if leak:
        with pytest.raises(ValueError, match="leakage"):
            load_inputs(tmp_path)
    else:
        assert len(load_inputs(tmp_path)[0]) == 1
        (tmp_path / "audit_sft_v5.jsonl").write_text("changed")
        with pytest.raises(ValueError, match="hash mismatch"):
            load_inputs(tmp_path)


def test_package_is_private_and_includes_only_pinned_inputs(tmp_path, monkeypatch):
    import ast
    import zipfile
    from prepare import build
    monkeypatch.setattr("prepare.subprocess.check_output", lambda args, **kwargs:
                        "a" * 40 if args[1] == "rev-parse" else "modified")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    objects = []
    for name, rows in {
        "audit_sft_v5.jsonl": [{"term_id": "train", "split": "train", "label": "ok"},
                               {"term_id": "evaluation", "split": "test", "label": "fix"}],
        "audit_holdout_sft.jsonl": [{"term_id": "holdout", "split": "test", "label": "ok"}],
    }.items():
        for row in rows:
            row["messages"] = [{"role": "user", "content": "synthetic"}, {"role": "assistant", "content": "ok"}]
        path = inputs / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        objects.append({"name": name, "size": path.stat().st_size, "sha256": sha256(path), "rows": len(rows)})
    (inputs / "audit-v5-baseline.json").write_text(json.dumps({"objects": objects}))
    (inputs / ".env").write_text("synthetic secret that must stay out")
    prepared = tmp_path / "prepared"
    result = build(inputs, prepared, "synthetic-user")
    assert result["dataset"] == "synthetic-user/trend-audit-v5-baseline"
    assert not (prepared / "dataset" / ".env").exists()
    with zipfile.ZipFile(prepared / "dataset" / "runtime.zip") as archive:
        assert set(archive.namelist()) == {"train.py", "pyproject.toml", "uv.lock", "bundle.json"}
    for folder in prepared.glob("trend-audit-*"):
        metadata = json.loads((folder / "kernel-metadata.json").read_text())
        assert metadata["is_private"] is True
        notebook = json.loads((folder / "audit_qlora.ipynb").read_text())
        assert notebook["cells"][1]["outputs"] == []
        ast.parse("".join(notebook["cells"][1]["source"]))


def test_completion_logits_match_full_masked_loss_and_gradients(tmp_path):
    set_seed(42)
    model = GPT2LMHeadModel(GPT2Config(vocab_size=32, n_positions=16, n_embd=16,
                                     n_layer=1, n_head=2, pad_token_id=0))
    model.eval()
    inputs = {"input_ids": torch.tensor([[1, 3, 4, 5, 6, 2]]),
              "attention_mask": torch.ones(1, 6, dtype=torch.long),
              "labels": torch.tensor([[-100, -100, -100, 5, 6, 2]])}
    full_loss = model(**inputs).loss
    full_loss.backward()
    expected_gradients = {name: parameter.grad.clone() for name, parameter in model.named_parameters()
                          if parameter.grad is not None}
    model.zero_grad(set_to_none=True)
    trainer = completion_trainer(model=model, args=TrainingArguments(
        output_dir=str(tmp_path), use_cpu=True, report_to="none"))
    selected_loss, outputs = trainer.compute_loss(model, inputs, return_outputs=True)
    assert outputs.logits.shape == (1, 3, 32)
    torch.testing.assert_close(selected_loss, full_loss)
    selected_loss.backward()
    for name, parameter in model.named_parameters():
        if parameter.grad is not None:
            torch.testing.assert_close(parameter.grad, expected_gradients[name], rtol=1e-4, atol=1e-6)


def test_fp16_resume_requires_saved_gradient_scaler(tmp_path):
    path = tmp_path / "checkpoint-2"
    path.mkdir()
    contract = {"dtype": "torch.float16"}
    for name in ("adapter_model.safetensors", "adapter_config.json", "optimizer.pt", "scheduler.pt", "rng_state.pth"):
        (path / name).write_bytes(b"synthetic state")
    (path / "trainer_state.json").write_text(json.dumps({"global_step": 2}))
    (path / "run-contract.json").write_text(json.dumps(contract))
    with pytest.raises(ValueError, match="precision scaler"):
        checkpoint_path(path, contract)
    (path / "scaler.pt").write_bytes(b"synthetic scaler state")
    assert checkpoint_path(path, contract) == path


def test_nonfinite_training_does_not_publish_a_checkpoint(tmp_path):
    model = GPT2LMHeadModel(GPT2Config(vocab_size=32, n_positions=16, n_embd=16,
                                     n_layer=1, n_head=2, pad_token_id=0))
    with torch.no_grad():
        model.get_input_embeddings().weight.fill_(float('nan'))
    trainer = completion_trainer(
        model=model,
        args=TrainingArguments(output_dir=str(tmp_path), use_cpu=True, max_steps=1,
                               logging_steps=1, save_steps=1, save_strategy='steps',
                               report_to='none', disable_tqdm=True),
        train_dataset=Dataset.from_list([{'input_ids':[1,3,4,2], 'labels':[-100,-100,4,2]}]),
        callbacks=callbacks({'signature':'nonfinite-regression'}))
    with pytest.raises(FloatingPointError, match='Non-finite'):
        trainer.train()
    assert not list(tmp_path.glob('checkpoint-*'))


@pytest.mark.parametrize('text,expected', [
    ('{"verdict":"ok"}', 'ok'),
    ('{"verdict":"fix","reason":"synthetic"}', 'fix'),
    ('INVALID JSON "verdict": "fix" trailing prose', 'unparsed'),
    ('[{"verdict":"fix"}]', 'unparsed'),
    ('{"verdict":"fix","reason":"truncated', 'unparsed'),
    ('{"verdict":["fix"]}', 'unparsed'),
])
def test_verdict_requires_a_valid_json_object(text, expected):
    from train import verdict
    assert verdict(text) == expected
