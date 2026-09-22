import importlib.util
import json
from pathlib import Path

import pytest
from builder_cup import history
from builder_cup.config import Settings
from builder_cup.database import DatabaseUnavailable
from builder_cup.history import RunDetail
from builder_cup.providers import MockProvider, ProviderFailure

spec = importlib.util.spec_from_file_location(
    "ollama_history_lab", Path("scripts/ollama_history_lab.py")
)
assert spec is not None and spec.loader is not None
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class GemmaTestProvider(MockProvider):
    model = "gemma4:test"


@pytest.fixture
def persisted(monkeypatch):
    saved = {}

    monkeypatch.setattr(history, "start_run", lambda *_args: None)

    def finish(_settings, run, trace):
        saved[run.id] = RunDetail(
            **run.model_dump(),
            nodes=[node.model_copy(deep=True) for node in trace.nodes.values()],
        )

    monkeypatch.setattr(history, "finish_run", finish)
    monkeypatch.setattr(history, "read_run", lambda _settings, run_id: saved.get(run_id))
    return saved


async def test_report_and_history_share_run_id_without_storing_source(tmp_path, persisted):
    config = Settings(_env_file=None, model_provider="ollama")
    status, path = await lab.execute("meeting", None, config, GemmaTestProvider(), tmp_path)
    report = json.loads(path.read_text())
    assert status == 0
    assert report["run_id"] == report["history"]["id"]
    assert report["history"]["provider"] == "ollama"
    assert report["history"]["model"] == "gemma4:test"
    assert report["history"]["input_tokens"] == 0
    assert len(report["history"]["nodes"]) == 5
    assert report["case"]["text"].startswith("## 일정")
    assert report["case"]["text"] not in json.dumps(report["history"], ensure_ascii=False)


@pytest.mark.parametrize("code", ["model_unavailable", "model_timeout"])
async def test_model_failure_is_persisted_without_mock_fallback(tmp_path, persisted, code):
    class FailingProvider(GemmaTestProvider):
        async def generate(self, text):
            raise ProviderFailure(code)

    config = Settings(_env_file=None, model_provider="ollama", model_max_attempts=1)
    status, path = await lab.execute("meeting", code, config, FailingProvider(), tmp_path)
    report = json.loads(path.read_text())
    assert status == 1
    assert report["error_code"] == code
    assert report["history"]["status"] == "failed"
    assert report["history"]["provider"] == "ollama"
    assert report["history"]["nodes"][1]["error_code"] == code


async def test_start_write_failure_prevents_model_call_and_writes_failed_report(
    tmp_path, monkeypatch
):
    class UnexpectedProvider(GemmaTestProvider):
        async def generate(self, text):
            pytest.fail("model must not run before durable history start")

    monkeypatch.setattr(
        history,
        "start_run",
        lambda *_args: (_ for _ in ()).throw(DatabaseUnavailable()),
    )
    monkeypatch.setattr(history, "read_run", lambda *_args: None)
    status, path = await lab.execute(
        "meeting",
        None,
        Settings(_env_file=None, model_provider="ollama"),
        UnexpectedProvider(),
        tmp_path,
    )
    report = json.loads(path.read_text())
    assert status == 1
    assert report["error_code"] == "database_unavailable"
    assert report["history"] is None
