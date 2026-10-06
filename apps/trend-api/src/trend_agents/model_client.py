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


def image_requests_enabled() -> bool:
    """포스터 시안(IMAGE_BACKEND)을 부를 수 있나. off(기본)면 늘 False."""
    return config.IMAGE_BACKEND == "vertex" and requests_enabled() and bool(config.GCP_PROJECT_ID)


def image_client() -> genai.Client:
    """위 client() 와 같은 Vertex 접속."""
    if not image_requests_enabled():
        raise ModelRequestsDisabled("Image requests are disabled")
    return client()
