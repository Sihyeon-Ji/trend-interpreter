"""Producer resume rejects a mixed input before starting GPU inference."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("translation_producer", Path(__file__).resolve().parents[3] /
                                           "models/kaggle/translate/translate_meanings.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_resume_rejects_old_unversioned_or_changed_inputs_before_starting_gpu(monkeypatch, tmp_path):
    src, out = tmp_path / "input", tmp_path / "output"
    code = src / "trend_agents/interpreters/gemma_translate.py"
    code.parent.mkdir(parents=True)
    code.write_text("fixed prompt code")
    out.mkdir()
    source = {"term_id": "t_one", "term": "one", "entry": {"definition": "private source"},
              "expected_meaning_id": "m_one", "derived_from_sha256": "a" * 64}
    (src / "terms.jsonl").write_text(json.dumps(source) + "\n")
    prior = {"term_id": "t_one", "source": source["entry"], "model": runner.MODEL,
             "gemma_translate_sha256": hashlib.sha256(code.read_bytes()).hexdigest()}
    (out / "translations.jsonl").write_text(json.dumps(prior) + "\n")
    monkeypatch.setattr(runner, "OUT", out)
    monkeypatch.setattr(runner, "find_input", lambda: src)
    monkeypatch.setattr(runner, "start_ollama", lambda: pytest.fail("mixed resume started GPU"))
    with pytest.raises(SystemExit, match="translation_resume_source_conflict"):
        runner.main()


def test_producer_carries_original_version_and_model_provenance_without_logging_text(monkeypatch, tmp_path, capsys):
    from trend_agents.interpreters import gemma_translate
    from trend_agents.schemas import MeaningText

    src, out = tmp_path / "input", tmp_path / "output"
    code = src / "trend_agents/interpreters/gemma_translate.py"
    code.parent.mkdir(parents=True)
    code.write_text("fixed prompt code")
    out.mkdir()
    source = {"term_id": "t_one", "term": "PRIVATE TERM", "entry": {
        "definition": "PRIVATE SOURCE", "origin": "origin", "nuance": "nuance", "expansion": None},
              "expected_meaning_id": "m_one", "derived_from_sha256": "a" * 64}
    (src / "terms.jsonl").write_text(json.dumps(source) + "\n")
    monkeypatch.setattr(runner, "OUT", out)
    monkeypatch.setattr(runner, "find_input", lambda: src)
    monkeypatch.setattr(runner, "start_ollama", lambda: ("test-version", "b" * 64))
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="synthetic-gpu"))
    monkeypatch.setattr(gemma_translate, "translate_meaning", lambda *a, **kw:
                        MeaningText(definition="PRIVATE TRANSLATION", origin="origin", nuance="nuance"))
    original_path = runner.sys.path[:]
    try:
        runner.main()
    finally:
        runner.sys.path[:] = original_path
    result = json.loads((out / "translations.jsonl").read_text())
    run = json.loads((out / "run.json").read_text())
    assert result["expected_meaning_id"] == "m_one" and result["derived_from_sha256"] == "a" * 64
    assert result["input_sha256"] == run["input_sha256"]
    assert result["model_digest"] == run["model_digest"] == "b" * 64
    assert result["gemma_translate_sha256"] == run["gemma_translate_sha256"]
    assert result["source"] == source["entry"] and result["en"]["definition"] == "PRIVATE TRANSLATION"
    assert "PRIVATE" not in capsys.readouterr().out


def test_glossary_is_appended_only_when_given(monkeypatch):
    from trend_agents.interpreters import gemma_translate
    from trend_agents.schemas import MeaningText

    prompts = []
    monkeypatch.setattr(gemma_translate.local_chat, "structured",
                        lambda prompt, *a, **kw: prompts.append(prompt) or MeaningText(definition="English text", origin="o", nuance="n"))
    entry = MeaningText(definition="우루사 광고에서 나온 말", origin="origin", nuance="nuance")
    gemma_translate.translate_meaning(entry, "간 때문이야", "en")
    gemma_translate.translate_meaning(entry, "간 때문이야", "en", glossary={"우루사": "URSA"})
    plain = gemma_translate.PROMPT.format(target="English", term="간 때문이야", entry=entry.model_dump_json(indent=2))
    assert prompts[0] == plain                                       # 표기 목록이 없으면 예전 지시문 그대로
    assert prompts[1].startswith(plain) and "- 우루사 → URSA" in prompts[1]
