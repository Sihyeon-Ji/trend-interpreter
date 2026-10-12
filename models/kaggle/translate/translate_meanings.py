"""Kaggle GPU에서 밀린 사전 뜻 영어판(TRANSLATE_TARGET=ja 면 일본어판)을 로컬 Gemma로 시험 번역한다(Plan 02 10-06 데모 준비도).

입력은 비공개 Dataset 하나다: `terms.jsonl`(term_id·term·entry)과 저장소의 `trend_agents` 일부.
번역은 저장소의 `interpreters.gemma_translate.translate_meaning`을 그대로 부른다(프롬프트·재질문·Ollama 호출 옵션이 같다).
결과는 `/kaggle/working/translations.jsonl`과 `run.json`에만 남긴다. 운영·수집 DB에는 쓰지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GEMMA_LOCAL_MODEL", "gemma4:12b")
TARGET = os.environ.get("TRANSLATE_TARGET", "en")   # 결과 행의 언어 칸 – pack-translations --lang 과 같게(en·ja)
OLLAMA_PIN = os.environ.get("OLLAMA_PIN", "")
OUT = Path("/kaggle/working")
HANGUL = re.compile("[가-힣]")


def sh(cmd: str) -> None:
    print("$", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def find_input() -> Path:
    hits = sorted(Path("/kaggle/input").rglob("terms.jsonl"))
    if len(hits) != 1:
        raise SystemExit(f"terms.jsonl 이 하나여야 한다: {hits}")
    return hits[0].parent


def start_ollama() -> tuple[str, str]:
    sh("apt-get -qq update > /dev/null && apt-get -qq install -y zstd > /dev/null")
    sh(f"curl -fsSL https://ollama.com/install.sh | {'OLLAMA_VERSION=' + OLLAMA_PIN + ' ' if OLLAMA_PIN else ''}sh > /dev/null")
    sh("pip -q install ollama httpx python-dotenv")
    log = open("/tmp/ollama.log", "w")
    subprocess.Popen(["ollama", "serve"], stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "OLLAMA_HOST": "127.0.0.1:11434"})
    for _ in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=2) as r:
                version = json.load(r)["version"]
            break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit("ollama serve 가 뜨지 않았다")
    t0 = time.time()
    sh(f"ollama pull {MODEL} > /dev/null")
    print(f"pull {time.time() - t0:.0f}s", flush=True)
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags") as r:
        digest = next((m["digest"] for m in json.load(r)["models"] if m["model"] == MODEL), "")
    return version, digest


def main() -> None:
    src = find_input()
    input_hash = hashlib.sha256((src / "terms.jsonl").read_bytes()).hexdigest()
    code_hash = hashlib.sha256((src / "trend_agents" / "interpreters" / "gemma_translate.py").read_bytes()).hexdigest()
    rows = [json.loads(line) for line in (src / "terms.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or len({r["term_id"] for r in rows}) != len(rows):
        raise SystemExit("invalid_translation_inputs")
    done = OUT / "translations.jsonl"
    prior = [json.loads(line) for line in done.read_text(encoding="utf-8").splitlines() if line.strip()] if done.exists() else []
    indexed = {r["term_id"]: r for r in rows}
    seen = set()
    for result in prior:
        source = indexed.get(result.get("term_id"))
        if (not source or result["term_id"] in seen or result.get("source") != source["entry"]
                or result.get("expected_meaning_id") != source.get("expected_meaning_id")
                or result.get("derived_from_sha256") != source.get("derived_from_sha256")
                or result.get("model") != MODEL or result.get("gemma_translate_sha256") != code_hash
                or result.get("input_sha256") != input_hash or result.get("target", "en") != TARGET):
            raise SystemExit("translation_resume_source_conflict")
        seen.add(result["term_id"])
    version, digest = start_ollama()
    if any(result.get("model_digest") != digest for result in prior):
        raise SystemExit("translation_resume_model_conflict")
    sys.path.insert(0, str(src))
    os.environ["GEMMA_LOCAL_MODEL"] = MODEL
    from trend_agents.interpreters import gemma_translate
    from trend_agents.schemas import MeaningText

    times, failures, still_korean = [], 0, 0
    with done.open("a", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            if r["term_id"] in seen:
                continue
            t0 = time.time()
            try:
                out = gemma_translate.translate_meaning(MeaningText(**r["entry"]), r["term"], TARGET, model=MODEL,
                                                       glossary=r.get("glossary") or None)
                result, error = out.model_dump(), None
                if HANGUL.search(out.definition or ""):
                    still_korean += 1
            except Exception as e:           # 형식 실패도 결과로 남긴다
                result, error = None, type(e).__name__
                failures += 1
            dt = time.time() - t0
            times.append(dt)
            f.write(json.dumps({"term_id": r["term_id"], "term": r["term"], "source": r["entry"], TARGET: result, "target": TARGET,
                                "expected_meaning_id": r.get("expected_meaning_id"), "derived_from_sha256": r.get("derived_from_sha256"),
                                "model": MODEL, "model_digest": digest, "gemma_translate_sha256": code_hash,
                                "input_sha256": input_hash,
                                "error": error, "seconds": round(dt, 1)}, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i}/{len(rows)}] {dt:.1f}s{' FAIL' if error else ''}", flush=True)
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    meta = {"model": MODEL, "model_digest": digest, "ollama": version, "gpu": gpu, "python": platform.python_version(),
            "target": TARGET, "terms": len(rows), "translated_now": len(times), "failures": failures, "definition_still_korean": still_korean,
            "seconds_total": round(sum(times), 1), "seconds_median": round(sorted(times)[len(times) // 2], 1) if times else None,
            "input_sha256": input_hash, "gemma_translate_sha256": code_hash}
    (OUT / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
