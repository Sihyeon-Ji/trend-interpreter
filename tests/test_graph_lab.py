import asyncio
import json
import threading
from pathlib import Path

import pytest
from builder_cup import graph_lab
from builder_cup.config import Settings
from builder_cup.main import create_app
from builder_cup.providers import Generation, MockProvider, ProviderFailure
from builder_cup.schemas import Usage
from fastapi.testclient import TestClient
from pydantic import ValidationError

CASES = json.loads(Path("evaluation-cases/workflow-lab.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_routing_and_join_order(case):
    result = await graph_lab.run_graph(
        case["text"], "test-run", MockProvider(), Settings(_env_file=None)
    )
    assert result.decision.outcome == case["expected_outcome"]
    assert result.decision.reason_codes == case["expected_reason_codes"]
    assert result.document_checks.character_count == len(case["text"])
    events = [(event.node, event.state) for event in result.events]
    assert events.index(("join", "started")) > events.index(("extract", "completed"))
    assert events.index(("join", "started")) > events.index(("inspect_document", "completed"))
    assert events.index(("route", "started")) > events.index(("join", "completed"))
    assert len(events) == 10


@pytest.mark.parametrize("text", ["", "   ", "x" * 8001], ids=["empty", "blank", "too-long"])
async def test_invalid_input_does_not_call_provider(text):
    class UnexpectedProvider(MockProvider):
        async def generate(self, text):
            pytest.fail("Provider must not be called for invalid input")

    with pytest.raises(ValidationError):
        await graph_lab.run_graph(text, "test-run", UnexpectedProvider(), Settings(_env_file=None))


async def test_branches_are_scheduled_concurrently(monkeypatch):
    inspection_started = asyncio.Event()
    loop = asyncio.get_running_loop()
    original = graph_lab.inspect_document

    def notify_inspection(text):
        loop.call_soon_threadsafe(inspection_started.set)
        return original(text)

    class WaitingProvider(MockProvider):
        calls = 0

        async def generate(self, text):
            self.calls += 1
            await asyncio.wait_for(inspection_started.wait(), timeout=2)
            return await super().generate(text)

    monkeypatch.setattr(graph_lab, "inspect_document", notify_inspection)
    provider = WaitingProvider()
    config = Settings(_env_file=None, model_max_attempts=1)
    result = await graph_lab.run_graph(CASES[0]["text"], "test-run", provider, config)
    assert provider.calls == 1
    assert result.decision.outcome == "accepted"


async def test_invalid_model_result_never_reaches_join():
    class InvalidProvider(MockProvider):
        async def generate(self, text):
            return Generation("not-json", Usage())

    with pytest.raises(ProviderFailure, match="invalid_model_response"):
        await graph_lab.run_graph(
            CASES[0]["text"], "test-run", InvalidProvider(), Settings(_env_file=None)
        )


async def test_inspection_failure_cancels_pending_extraction(monkeypatch):
    model_started = threading.Event()
    model_cancelled = asyncio.Event()

    class PendingProvider(MockProvider):
        async def generate(self, text):
            model_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                model_cancelled.set()
            return await super().generate(text)

    def fail_inspection(text):
        assert model_started.wait(timeout=2)
        raise RuntimeError("inspection failed")

    monkeypatch.setattr(graph_lab, "inspect_document", fail_inspection)
    with pytest.raises(RuntimeError, match="inspection failed"):
        await graph_lab.run_graph(
            CASES[0]["text"], "test-run", PendingProvider(), Settings(_env_file=None)
        )
    assert model_cancelled.is_set()


def test_workflow_api_works_without_database_lab():
    config = Settings(_env_file=None, workflow_lab_enabled=True)
    with TestClient(create_app(config)) as client:
        response = client.post("/api/lab/workflow", json={"text": CASES[0]["text"]})
        assert response.status_code == 200
        result = response.json()
        assert result["decision"]["outcome"] == "accepted"
        assert result["analysis"]["request_id"] == response.headers["X-Request-ID"]
        assert client.post("/api/lab/records").status_code == 404


def test_workflow_api_is_disabled_by_default():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.post("/api/lab/workflow", json={"text": CASES[0]["text"]}).status_code == 404


def test_workflow_lab_rejects_cloud_run(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "builder-cup")
    config = Settings(_env_file=None, workflow_lab_enabled=True, demo_api_key="test-only")
    with pytest.raises(RuntimeError, match="Workflow lab is only available in local mock mode"):
        create_app(config)
