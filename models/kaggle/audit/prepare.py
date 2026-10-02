"""Prepare a private Dataset and separate stop/resume Kaggle notebooks without uploading."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from train import HERE, INPUT_FILES, load_inputs, sha256

UV_URL = "https://files.pythonhosted.org/packages/1e/fd/432451d732917c49152a291de3ef171aa6b0f1a22d39780fb2c1f085ca4c/uv-0.12.15-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
UV_SHA256 = "aee9802f46bae436bd91751bb33ddeb379ef1596b5c19df193219d545d244b60"

BOOTSTRAP = '''import hashlib, io, json, os, subprocess, urllib.request, zipfile
from pathlib import Path

inputs = list(Path("/kaggle/input").rglob("audit-v5-baseline.json"))
if len(inputs) != 1:
    raise ValueError("Expected exactly one private audit input Dataset")
input_dir = inputs[0].parent
if hashlib.sha256(inputs[0].read_bytes()).hexdigest() != INPUT_MANIFEST_SHA256:
    raise ValueError("Unexpected Dataset version")
runtime = input_dir / "runtime"
bundle_path = runtime / "bundle.json"
if hashlib.sha256(bundle_path.read_bytes()).hexdigest() != BUNDLE_SHA256:
    raise ValueError("Unexpected training bundle")
bundle = json.loads(bundle_path.read_text())
project = Path("/tmp/trend-audit-runtime")
project.mkdir(exist_ok=False)
expected = {"train.py", "pyproject.toml", "uv.lock", "bundle.json"}
if {path.name for path in runtime.iterdir()} != expected:
    raise ValueError("Unexpected runtime file inventory")
for name in expected:
    content = (runtime / name).read_bytes()
    if name != "bundle.json" and hashlib.sha256(content).hexdigest() != bundle["files"][name]:
        raise ValueError("Training runtime file checksum mismatch")
    (project / name).write_bytes(content)
wheel = urllib.request.urlopen(UV_URL).read()
if hashlib.sha256(wheel).hexdigest() != UV_SHA256:
    raise ValueError("uv bootstrap checksum mismatch")
uv = Path("/tmp/trend-audit-uv")
with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
    uv.write_bytes(archive.read("uv-0.12.15.data/scripts/uv"))
uv.chmod(0o700)
environment = {**os.environ, "HF_HOME": "/tmp/trend-audit-hf", "UV_CACHE_DIR": "/tmp/trend-audit-uv-cache",
               "UV_PROJECT_ENVIRONMENT": "/tmp/trend-audit-venv", "TOKENIZERS_PARALLELISM": "false",
               "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0").split(",")[0]}
subprocess.run([str(uv), "sync", "--project", str(project), "--locked", "--extra", "gpu", "--no-dev"],
               env=environment, check=True)
arguments = [str(uv), "run", "--project", str(project), "--locked", "--extra", "gpu", "--no-dev",
             "python", str(project / "train.py"), "--input-dir", str(input_dir),
             "--output-dir", "/kaggle/working/" + OUTPUT_NAME, "--max-steps", "4"]
if RESUME:
    candidates = [path for path in Path("/kaggle/input").rglob("checkpoint-2")
                  if (path / "run-contract.json").is_file()]
    if len(candidates) != 1:
        raise ValueError("Expected exactly one previous checkpoint-2")
    arguments += ["--resume-from", str(candidates[0])]
else:
    arguments += ["--stop-after", "2"]
subprocess.run(arguments, env=environment, check=True)
result = json.loads((Path("/kaggle/working") / OUTPUT_NAME / "result.json").read_text())
expected_step = 4 if RESUME else 2
if result["global_step"] != expected_step or (RESUME and result["resumed_from_step"] != 2):
    raise ValueError("Training did not stop or resume at the expected step")
print(json.dumps({key: result[key] for key in ("global_step", "resumed_from_step", "train_seconds", "peak_vram_gib")}))
'''


def build(input_dir: Path, destination: Path, owner: str) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,49}", owner):
        raise ValueError("Invalid Kaggle owner")
    load_inputs(input_dir)
    destination.mkdir(parents=True, exist_ok=False)
    dataset = destination / "dataset"
    dataset.mkdir()
    for name in INPUT_FILES | {"audit-v5-baseline.json"}:
        shutil.copyfile(input_dir / name, dataset / name)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()
    committed = not subprocess.check_output(["git", "status", "--porcelain", "--", str(HERE)], cwd=HERE, text=True).strip()
    bundle = {"code_commit": commit, "source_is_committed": committed,
              "files": {name: sha256(HERE / name) for name in ("train.py", "pyproject.toml", "uv.lock")}}
    with zipfile.ZipFile(dataset / "runtime.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(bundle["files"]):
            item = zipfile.ZipInfo(name)
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, (HERE / name).read_bytes())
        archive.writestr(zipfile.ZipInfo("bundle.json"), json.dumps(bundle, sort_keys=True))
    dataset_id = f"{owner}/trend-audit-v5-baseline"
    metadata = {"id": dataset_id, "title": "Trend audit v5 private baseline", "licenses": [{"name": "unknown"}],
                "description": "Private team research. Original source licenses are not yet consolidated; no new reuse rights are granted. "
                               "Labels are model judgments, not human ground truth. Existing holdout overlaps test2. "
                               "Short training runs cannot establish model quality or authorize deployment."}
    (dataset / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    runtime_hash = sha256(dataset / "runtime.zip")
    manifest_hash = sha256(dataset / "audit-v5-baseline.json")
    notebooks = {}
    for resume in (False, True):
        slug = "trend-audit-qlora-resume" if resume else "trend-audit-qlora-smoke"
        folder = destination / slug
        folder.mkdir()
        settings = {"RESUME": resume, "OUTPUT_NAME": "audit-resumed" if resume else "audit-stop",
                    "INPUT_MANIFEST_SHA256": manifest_hash,
                    "BUNDLE_SHA256": hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest(),
                    "UV_URL": UV_URL, "UV_SHA256": UV_SHA256}
        source = "\n".join(f"{name} = {value!r}" for name, value in settings.items()) + "\n\n" + BOOTSTRAP
        notebook = {"nbformat": 4, "nbformat_minor": 5,
                    "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}},
                    "cells": [{"id": "audit-scope", "cell_type": "markdown", "metadata": {},
                               "source": ["# Audit QLoRA stop/resume smoke\n", "Private research only. This is not an independent quality evaluation.\n"]},
                              {"id": "audit-run", "cell_type": "code", "metadata": {}, "execution_count": None,
                               "outputs": [], "source": source.splitlines(keepends=True)}]}
        (folder / "audit_qlora.ipynb").write_text(json.dumps(notebook, indent=2) + "\n")
        kernel = {"id": f"{owner}/{slug}", "title": slug, "code_file": "audit_qlora.ipynb", "language": "python",
                  "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_internet": True,
                  "machine_shape": "NvidiaTeslaT4", "dataset_sources": [dataset_id], "competition_sources": [],
                  "kernel_sources": [f"{owner}/trend-audit-qlora-smoke"] if resume else []}
        (folder / "kernel-metadata.json").write_text(json.dumps(kernel, indent=2) + "\n")
        notebooks[slug] = kernel["id"]
    return {"dataset": dataset_id, "runtime_sha256": runtime_hash, "notebooks": notebooks, **bundle}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.input_dir, args.destination, args.owner), indent=2))
