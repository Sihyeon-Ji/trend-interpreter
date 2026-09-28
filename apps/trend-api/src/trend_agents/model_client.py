"""Create Gemini clients only through the infrastructure-owned Vertex AI identity."""

from functools import lru_cache

from google import genai

from . import config


class ModelRequestsDisabled(RuntimeError):
    pass


def requests_enabled() -> bool:
    return config.MODEL_PROVIDER == "vertex" and config.MODEL_REQUESTS_ENABLED


@lru_cache(maxsize=1)
def client() -> genai.Client:
    if not requests_enabled():
        raise ModelRequestsDisabled("Gemini requests are disabled")
    if not config.GCP_PROJECT_ID:
        raise ModelRequestsDisabled("GCP_PROJECT_ID is required for Vertex AI")
    return genai.Client(
        vertexai=True,
        project=config.GCP_PROJECT_ID,
        location=config.GOOGLE_CLOUD_LOCATION,
    )
