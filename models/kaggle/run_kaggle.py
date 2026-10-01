"""Push the risk-labeling notebook to the caller's own Kaggle account, wait for it and download the output.

Each teammate runs this with their own Kaggle API token, so the notebook, its GPU quota and its output
belong to that account. The notebook in Git is never edited: run settings are written into a temporary copy.

  python3 models/kaggle/run_kaggle.py --synthetic                      # smoke run, no data needed
  python3 models/kaggle/run_kaggle.py --dataset builder-cup-risk-sample --max-terms 5
  python3 models/kaggle/run_kaggle.py --dataset builder-cup-risk-sample --variants baseline v2_term_vs_tone
  python3 models/kaggle/run_kaggle.py --synthetic --dry-run            # build the push folder only

Output (it contains sample sentences) goes to artifacts/kaggle/<slug>/, which Git ignores.
Requires the Kaggle CLI (`uv tool install kaggle`) and ~/.kaggle/access_token.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOTEBOOK = HERE / "gemma_risk_labeling.ipynb"
TERMINAL = ("complete", "error", "cancel")


def kaggle(*args: str) -> str:
    result = subprocess.run(["kaggle", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"kaggle {args[0]} {args[1]} failed: {(result.stderr or result.stdout).strip()[:300]}")
    return result.stdout


def username() -> str:
    match = re.search(r"^- username: (\S+)", kaggle("config", "view"), re.MULTILINE)
    if not match or match.group(1) == "None":
        sys.exit("Kaggle username not found. Put your API token in ~/.kaggle/access_token first")
    return match.group(1)


def configure(notebook: dict, settings: dict[str, object]) -> None:
    """Rewrite top-level assignments in the settings cell (the one defining USE_SYNTHETIC_SAMPLE)."""
    cell = next(c for c in notebook["cells"] if c["cell_type"] == "code" and "USE_SYNTHETIC_SAMPLE =" in "".join(c["source"]))
    source = "".join(cell["source"])
    for name, value in settings.items():
        source, count = re.subn(rf"^{name} = .*$", f"{name} = {value!r}", source, count=1, flags=re.MULTILINE)
        if count != 1:
            sys.exit(f"{name} is not assigned in the notebook settings cell")
    lines = source.split("\n")
    cell["source"] = [line + "\n" for line in lines[:-1]] + [lines[-1]]


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up even when piped to a file
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", default="gemma-risk-labeling", help="notebook name in your Kaggle account")
    p.add_argument("--dataset", action="append", default=[], help="private dataset slug or owner/slug; repeatable")
    p.add_argument("--synthetic", action="store_true", help="five synthetic sentences instead of a dataset")
    p.add_argument("--max-terms", type=int)
    p.add_argument("--variants", nargs="+")
    p.add_argument("--accelerator", default="NvidiaTeslaT4")
    p.add_argument("--timeout", type=int, default=3 * 3600, help="seconds to wait for the run")
    p.add_argument("--dry-run", action="store_true", help="build the push folder, print it and stop")
    a = p.parse_args()
    if not a.synthetic and not a.dataset:
        p.error("give --dataset <slug> or --synthetic")

    user = username()
    kernel_id = f"{user}/{a.slug}"
    datasets = [d if "/" in d else f"{user}/{d}" for d in a.dataset]

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    settings: dict[str, object] = {"USE_SYNTHETIC_SAMPLE": a.synthetic}
    if a.max_terms is not None:
        settings["MAX_TERMS"] = a.max_terms
    if a.variants:
        settings["VARIANTS"] = a.variants
    configure(notebook, settings)

    metadata = {"id": kernel_id, "title": a.slug, "code_file": NOTEBOOK.name, "language": "python",
                "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_internet": True,
                "machine_shape": a.accelerator, "dataset_sources": datasets,
                "competition_sources": [], "kernel_sources": []}

    folder = Path(tempfile.mkdtemp(prefix="kaggle-push-"))
    try:
        (folder / NOTEBOOK.name).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (folder / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print("kernel", kernel_id, "| settings", settings, "| datasets", datasets or "none")
        if a.dry_run:
            print("dry run, push folder kept at", folder)
            return
        kaggle("kernels", "push", "-p", str(folder), "--accelerator", a.accelerator)
    finally:
        if not a.dry_run:
            shutil.rmtree(folder, ignore_errors=True)
    print(f"pushed, https://www.kaggle.com/code/{kernel_id}")

    started = time.time()
    status = ""
    while time.time() - started < a.timeout:
        time.sleep(30)
        done = subprocess.run(["kaggle", "kernels", "status", kernel_id], capture_output=True, text=True, check=False)
        if done.returncode != 0:            # 몇 시간 기다리는 동안의 일시적인 네트워크 오류로 끝내지 않는다
            print(f"{int(time.time() - started):>5}s status check failed, retrying: {(done.stderr or done.stdout).strip()[:120]}", flush=True)
            continue
        line = done.stdout.strip()
        status = line.rsplit(" ", 1)[-1].strip('"').lower()
        print(f"{int(time.time() - started):>5}s {status}")
        if any(word in status for word in TERMINAL):
            break
    else:
        sys.exit(f"still running after {a.timeout}s, check https://www.kaggle.com/code/{kernel_id}")

    out = ROOT / "artifacts" / "kaggle" / a.slug
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    kaggle("kernels", "output", kernel_id, "-p", str(out))
    print("output in", out.relative_to(ROOT))
    for run in sorted(out.glob("runs/*/run.json")):
        meta = json.loads(run.read_text(encoding="utf-8"))
        print("run", meta.get("run_id"), "| gpu", str(meta.get("gpu", "?")).replace("\n", ", "), "| model", meta.get("model"), str(meta.get("model_digest", ""))[:12])
    calls = sorted(out.glob("runs/*/calls.csv"))
    if calls:
        print(calls[-1].read_text(encoding="utf-8-sig").strip())
    if "complete" not in status:
        sys.exit(f"run ended with status {status}, see the log in {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
