from unittest.mock import Mock

import pytest

from trend_agents import config, model_client


def test_mock_mode_never_creates_a_client(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(model_client.genai, "Client", factory)
    monkeypatch.setattr(config, "MODEL_PROVIDER", "mock")
    monkeypatch.setattr(config, "MODEL_REQUESTS_ENABLED", True)
    model_client.client.cache_clear()

    with pytest.raises(model_client.ModelRequestsDisabled):
        model_client.client()

    factory.assert_not_called()


def test_vertex_mode_uses_project_identity_without_api_key(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(model_client.genai, "Client", factory)
    monkeypatch.setattr(config, "MODEL_PROVIDER", "vertex")
    monkeypatch.setattr(config, "MODEL_REQUESTS_ENABLED", True)
    monkeypatch.setattr(config, "GCP_PROJECT_ID", "builder-cup-test")
    monkeypatch.setattr(config, "GOOGLE_CLOUD_LOCATION", "global")
    model_client.client.cache_clear()

    model_client.client()

    factory.assert_called_once_with(vertexai=True, project="builder-cup-test", location="global")
    model_client.client.cache_clear()
