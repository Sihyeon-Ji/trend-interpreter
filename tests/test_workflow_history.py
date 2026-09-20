import asyncio
from uuid import uuid4

import pytest
from builder_cup import history
from builder_cup.config import Settings
from builder_cup.database import DatabaseUnavailable
from builder_cup.providers import Generation, MockProvider, ProviderFailure
from builder_cup.schemas import Usage

SAMPLE_TEXT = "## 일정\n금요일 회의\n## 준비\n자료 준비 - source-must-not-be-stored"


@pytest.fixture
def captured(monkeypatch):
    data = {}

    def start(settings, run, trace):
        data["start"] = run.model_copy(deep=True)

    def finish(settings, run, trace):
        data["finish"] = history.RunDetail(
            **run.model_dump(), nodes=[node.model_copy(deep=True) for node in trace.nodes.values()]
        )

    monkeypatch.setattr(history, "start_run", start)
    monkeypatch.setattr(history, "finish_run", finish)
    return data


async def test_completed_history_contains_only_metadata(captured):
    result = await history.run_with_history(
        SAMPLE_TEXT, str(uuid4()), MockProvider(), Settings(_env_file=None)
    )
    saved = captured["finish"]
    assert captured["start"].status == "running"
    assert saved.status == "completed"
    assert saved.outcome == "accepted"
    assert saved.input_tokens == saved.output_tokens == 0
    assert saved.attempts == 1
    assert len(saved.nodes) == 5
    assert all(node.status == "completed" for node in saved.nodes)
    assert all(node.duration_ms >= 0 for node in saved.nodes)
    assert saved.finished_at >= saved.started_at
    assert "source-must-not-be-stored" not in saved.model_dump_json()
    assert "source-must-not-be-stored" in result.analysis.result.summary


async def test_invalid_input_is_recorded_without_model_calls(captured):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        await history.run_with_history(" ", str(uuid4()), MockProvider(), Settings(_env_file=None))
    saved = captured["finish"]
    assert saved.status == "failed"
    assert saved.error_code == "invalid_input"
    assert saved.attempts == 0
    assert saved.nodes[0].status == "failed"
    assert all(node.status == "skipped" for node in saved.nodes[1:])


async def test_timeout_records_attempts_and_unknown_usage(captured):
    class TimeoutProvider(MockProvider):
        async def generate(self, text):
            raise ProviderFailure("model_timeout")

    with pytest.raises(ProviderFailure):
        await history.run_with_history(
            SAMPLE_TEXT, str(uuid4()), TimeoutProvider(), Settings(_env_file=None)
        )
    saved = captured["finish"]
    assert saved.status == "failed"
    assert saved.error_code == "model_timeout"
    assert saved.attempts == 1
    assert saved.input_tokens is None and saved.output_tokens is None
    assert saved.nodes[1].status == "failed"
    assert saved.nodes[1].error_code == "model_timeout"
    assert saved.nodes[-1].status == "skipped"


async def test_success_without_usage_stays_unknown(captured):
    class UnreportedProvider(MockProvider):
        async def generate(self, text):
            return Generation('{"summary":"Summary","key_points":["Point"]}', Usage())

    config = Settings(_env_file=None, input_price_per_million=1, output_price_per_million=1)
    result = await history.run_with_history(SAMPLE_TEXT, str(uuid4()), UnreportedProvider(), config)
    assert result.analysis.estimated_cost_usd is None
    assert captured["finish"].input_tokens is None
    assert captured["finish"].nodes[1].output_tokens is None


async def test_retry_count_is_stored(captured):
    class RetryProvider(MockProvider):
        calls = 0

        async def generate(self, text):
            self.calls += 1
            if self.calls == 1:
                raise ProviderFailure("model_unavailable", retryable=True)
            return await super().generate(text)

    await history.run_with_history(
        SAMPLE_TEXT, str(uuid4()), RetryProvider(), Settings(_env_file=None)
    )
    assert captured["finish"].attempts == 2
    assert captured["finish"].nodes[1].attempts == 2


async def test_database_failure_prevents_model_call(monkeypatch):
    def unavailable(*args):
        raise DatabaseUnavailable("database_unavailable")

    class UnexpectedProvider(MockProvider):
        async def generate(self, text):
            pytest.fail("Model called before durable run creation")

    monkeypatch.setattr(history, "start_run", unavailable)
    with pytest.raises(DatabaseUnavailable):
        await history.run_with_history(
            SAMPLE_TEXT, str(uuid4()), UnexpectedProvider(), Settings(_env_file=None)
        )


async def test_finish_failure_does_not_return_success(captured, monkeypatch):
    def unavailable(*args):
        raise DatabaseUnavailable("database_unavailable")

    monkeypatch.setattr(history, "finish_run", unavailable)
    with pytest.raises(DatabaseUnavailable):
        await history.run_with_history(
            SAMPLE_TEXT, str(uuid4()), MockProvider(), Settings(_env_file=None)
        )
    assert captured["start"].status == "running"


async def test_cancelled_execution_is_recorded(captured):
    started = asyncio.Event()

    class WaitingProvider(MockProvider):
        async def generate(self, text):
            started.set()
            await asyncio.Event().wait()
            return await super().generate(text)

    task = asyncio.create_task(
        history.run_with_history(
            SAMPLE_TEXT, str(uuid4()), WaitingProvider(), Settings(_env_file=None)
        )
    )
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert captured["finish"].status == "cancelled"
    assert captured["finish"].nodes[1].status == "cancelled"


async def test_unexpected_failure_does_not_store_exception_text(captured, monkeypatch):
    def fail(text):
        raise RuntimeError("secret-must-not-be-stored")

    monkeypatch.setattr("builder_cup.graph_lab.inspect_document", fail)
    with pytest.raises(RuntimeError):
        await history.run_with_history(
            SAMPLE_TEXT, str(uuid4()), MockProvider(), Settings(_env_file=None)
        )
    saved = captured["finish"]
    assert saved.error_code == "workflow_failed"
    assert "secret-must-not-be-stored" not in saved.model_dump_json()
