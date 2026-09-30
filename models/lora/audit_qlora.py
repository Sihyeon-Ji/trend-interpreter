"""사전 감사관 QLoRA (2026-09-30). 학습 서버(서버2) 전용 — 앱에 들어가지 않는다. gemma_risk_qlora.ipynb 의 설정을 따른다.
데이터: ~/gemma-research/data/audit_sft.jsonl (apps/trend-api/scripts/audit_dataset.py 가 만든 것, 커밋하지 않음). split=train 으로 배우고 split=test 로 채점한다.
정답은 전수조사 판정(fix/ok). 시험 표제어는 학습에 없다.
  cd models/lora && CUDA_VISIBLE_DEVICES=1 uv run python audit_qlora.py --base google/gemma-4-12B-it --epochs 3 --lr 1e-4 --label-only
  (환경은 research/gemma-lora-server2 브랜치의 models/lora/pyproject.toml)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import time

import torch
from datasets import Dataset
from peft import LoraConfig
from transformers import AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

p = argparse.ArgumentParser()
p.add_argument("--base", default="google/gemma-4-12B-it")
p.add_argument("--data", default=os.path.expanduser("~/gemma-research/data/audit_sft.jsonl"))
p.add_argument("--epochs", type=float, default=3)
p.add_argument("--lr", type=float, default=2e-4)
p.add_argument("--r", type=int, default=16)
p.add_argument("--max-length", type=int, default=3072)
p.add_argument("--skip-before", action="store_true")
p.add_argument("--label-only", action="store_true", help="정답을 판정만({\"verdict\":...})으로 — 까닭 문장을 외워 한쪽만 답하던 것(1차) 막기")
a = p.parse_args()

rows = [json.loads(x) for x in open(a.data, encoding="utf-8")]
train = [r for r in rows if r["split"] == "train"]
test = [r for r in rows if r["split"] == "test"]
dtype = torch.bfloat16
model = AutoModelForImageTextToText.from_pretrained(a.base, dtype=dtype, device_map="auto", quantization_config=BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype, bnb_4bit_quant_storage=dtype))
tok = AutoTokenizer.from_pretrained(a.base)


def verdict(text: str) -> str:
    m = re.search(r'"verdict"\s*:\s*"(ok|fix)"', text)
    return m.group(1) if m else "unparsed"


def evaluate(m, name: str) -> dict:
    m.eval()
    got = []
    t0 = time.time()
    for r in test:
        inputs = tok.apply_chat_template(r["messages"][:1], add_generation_prompt=True, return_tensors="pt", return_dict=True).to(m.device)
        with torch.no_grad():
            out = m.generate(**inputs, max_new_tokens=160, do_sample=False)
        text = tok.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
        got.append({"term_id": r["term_id"], "truth": r["label"], "got": verdict(text), "text": text[:300]})
    ok = [g for g in got if g["got"] in ("ok", "fix")]
    tp = sum(g["truth"] == "fix" and g["got"] == "fix" for g in ok)
    fp = sum(g["truth"] == "ok" and g["got"] == "fix" for g in ok)
    fn = sum(g["truth"] == "fix" and g["got"] == "ok" for g in ok)
    s = {"name": name, "n": len(got), "parsed": len(ok), "accuracy": round(sum(g["truth"] == g["got"] for g in ok) / max(1, len(ok)), 3),
         "fix_precision": round(tp / max(1, tp + fp), 3), "fix_recall": round(tp / max(1, tp + fn), 3), "seconds": round(time.time() - t0)}
    print(json.dumps(s, ensure_ascii=False), flush=True)
    return {"summary": s, "rows": got}


run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M") + "_audit_" + a.base.split("/")[-1]
out_dir = os.path.expanduser(f"~/gemma-research/runs/audit/{run_id}")
os.makedirs(out_dir, exist_ok=True)
before = None if a.skip_before else evaluate(model, "before")
peft_config = LoraConfig(lora_alpha=a.r, lora_dropout=0.05, r=a.r, bias="none", target_modules="all-linear", task_type="CAUSAL_LM")
args = SFTConfig(output_dir=out_dir, max_length=a.max_length, num_train_epochs=a.epochs, per_device_train_batch_size=1, gradient_accumulation_steps=4,
                 gradient_checkpointing=True, optim="adamw_torch_fused", logging_steps=5, save_strategy="no", learning_rate=a.lr, bf16=True,
                 max_grad_norm=0.3, lr_scheduler_type="constant", report_to="none", push_to_hub=False, seed=42,
                 dataset_kwargs={"add_special_tokens": False, "append_concat_token": True})
def target(r):
    if not a.label_only:
        return r["messages"][1:]
    return [{"role": "assistant", "content": json.dumps({"verdict": r["label"]})}]


ds = Dataset.from_list([{"prompt": r["messages"][:1], "completion": target(r)} for r in train])
trainer = SFTTrainer(model=model, args=args, train_dataset=ds, peft_config=peft_config, processing_class=tok)
t0 = time.time()
trainer.train()
train_s = time.time() - t0
peak = torch.cuda.max_memory_allocated() / 2**30
trainer.model.save_pretrained(os.path.join(out_dir, "adapter"))
after = evaluate(trainer.model, "after")
json.dump({"run_id": run_id, "base": a.base, "train": len(train), "test": len(test), "epochs": a.epochs, "lr": a.lr, "r": a.r,
           "train_seconds": round(train_s), "peak_gib": round(peak, 1), "before": before, "after": after},
          open(os.path.join(out_dir, "result.json"), "w"), ensure_ascii=False, indent=1)
print("saved", out_dir, "peak", round(peak, 1), "GiB", flush=True)
