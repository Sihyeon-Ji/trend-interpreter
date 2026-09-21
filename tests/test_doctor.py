import importlib.util
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location("doctor", Path("scripts/doctor.py"))
assert spec is not None and spec.loader is not None
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


@pytest.mark.parametrize("state", ["offline", "missing_model", "installed", "malformed"])
def test_optional_model_states_do_not_fail_mock_or_send_mutations(state, capsys):
    def handler(request):
        assert request.method == "GET"
        assert not request.content
        if request.url.host == "host.docker.internal":
            if state == "offline":
                raise httpx.ConnectError("private-connection-detail")
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "test"})
            assert request.url.path == "/api/tags"
            if state == "malformed":
                return httpx.Response(200, json={"models": None, "private": "not-for-logs"})
            models = [{"name": doctor.LOCAL_MODEL}] if state == "installed" else []
            return httpx.Response(200, json={"models": models})
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"status": "ok", "provider": "mock"})
        assert request.url.path == "/api/lab/runs"
        return httpx.Response(200, json=[{"private": "not-for-logs"}])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert doctor.check_services(client)
        doctor.check_ollama(client)
    output = capsys.readouterr().out
    assert "not-for-logs" not in output and "private-connection-detail" not in output
    assert ("Local model qwen3.5:4b: installed" in output) == (state == "installed")
    if state != "installed":
        assert "OPTIONAL" in output


@pytest.mark.parametrize("failure", ["offline", "database", "wrong_provider", "invalid_response"])
def test_unready_core_services_are_distinguished_from_health_success(failure, capsys):
    def handler(request):
        assert request.method == "GET"
        if failure == "offline":
            raise httpx.ConnectError("secret")
        if failure == "invalid_response":
            return httpx.Response(200, json=None)
        if request.url.path == "/api/lab/runs":
            return httpx.Response(503, json={"error": "secret"})
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "provider": "ollama" if failure == "wrong_provider" else "mock",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert not doctor.check_services(client)
    output = capsys.readouterr().out
    assert "FAIL" in output and "secret" not in output
    if failure == "database":
        assert "PASS API" in output and "FAIL DB history read" in output
