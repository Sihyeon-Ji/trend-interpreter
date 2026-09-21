"""One layer that owns every Gemini call.

Retries, surfacing the error body, and switching backends all happen here and nowhere else.
run.py (the agent loop) and ingest.py (multimodal extraction) go through the same door.

Two backends (LLM_BACKEND in .env):
  aistudio (default) — API key. For development and demos.
  vertex             — Google Cloud Vertex AI. Uses an ADC token (gcloud login), so no key
                       sits in the code. Going through Vertex earns credit in the competition,
                       so the path is open ahead of time.
                       ⚠ No GCP project yet, so this is unverified against a real call — the
                       structure is in place, nothing more.

The model name is managed in one place, GEMINI_MODEL in .env. The 2.5 line is retired for new users.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request

from pmo_agent.env import env

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_FALLBACK = "gemini-3.5-flash"  # where to go when the main model is overloaded
RETRIES = 4
RETRY_CODES = (429, 503, 500)  # overload, quota, transient. Anything else is our bug — raise it
AISTUDIO = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
VERTEX = (
    "https://{region}-aiplatform.googleapis.com/v1/projects/{project}"
    "/locations/{region}/publishers/google/models/{m}:generateContent"
)


def _log(msg: str) -> None:
    """Progress output that survives a console that cannot take Unicode (Windows cp949).

    A UnicodeEncodeError here once turned a 429 that should have been retried into a server 500.
    A progress message must never cost us the request.
    """
    try:
        print(msg, flush=True)
    except Exception:
        pass


class LLMError(RuntimeError):
    """The model call failed.

    `status` carries the HTTP status. A configuration error (no key, no project) has status None —
    fishing for "429" in the message text gets fooled by a number that happens to be in the body.
    """

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _overloaded(e: LLMError) -> bool:
    """Worth another try, or another model? A config error comes back the same either way."""
    return getattr(e, "status", None) in RETRY_CODES


def model_name() -> str:
    return env("GEMINI_MODEL", DEFAULT_MODEL)


def fallback_model() -> str:
    """The model to fall back to when the main one keeps overloading. Empty means no fallback.
    It exists so that one 503 mid-demo does not stop everything."""
    return env("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK).strip()


def backend() -> str:
    return env("LLM_BACKEND", "aistudio").strip().lower()


def _vertex_token() -> str:
    """An ADC access token, straight from the gcloud login state — no key in a file."""
    try:
        out = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=30,
            shell=True,
        )
    except Exception as e:
        raise LLMError(f"could not run gcloud: {e}") from None
    if out.returncode != 0:
        raise LLMError(
            "could not get an ADC token — run 'gcloud auth application-default login': "
            f"{out.stderr[:200]}"
        )
    return out.stdout.strip()


def _request(body: dict, model: str) -> urllib.request.Request:
    data = json.dumps(body).encode()
    if backend() == "vertex":
        project, region = env("GCP_PROJECT_ID"), env("GCP_REGION", "asia-northeast3")
        if not project:
            raise LLMError("no GCP_PROJECT_ID — the Vertex backend needs a project (SETUP.md 1-3)")
        url = VERTEX.format(region=region, project=project, m=model)
        return urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_vertex_token()}",
            },
        )
    key = env("GEMINI_API_KEY")
    if not key:
        raise LLMError("no GEMINI_API_KEY — see SETUP.md 1-1")
    return urllib.request.Request(
        AISTUDIO.format(m=model, k=key), data=data, headers={"Content-Type": "application/json"}
    )


def generate(
    body: dict, model: str | None = None, timeout: int = 180, verbose: bool = True
) -> dict:
    """The generateContent call.

    Overload (429/503) is retried with exponential backoff, then tried once more on the fallback
    model. Only when the fallback fails too does this raise LLMError.
    """
    primary = model or model_name()
    chain = [primary]
    fb = fallback_model()
    if fb and fb != primary:
        chain.append(fb)
    for i, m in enumerate(chain):
        try:
            return _attempt(body, m, timeout, verbose)
        except LLMError as e:
            # Last model, or a failure another model would not fix (config error) — raise as-is
            if i == len(chain) - 1 or not _overloaded(e):
                raise
            if verbose:
                _log(f"  ({m} unavailable - falling back to {chain[i + 1]})")
    raise LLMError("no model left to call")


def _attempt(body: dict, m: str, timeout: int, verbose: bool) -> dict:
    """The retry loop for a single model."""
    last = ""
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(_request(body, m), timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e.read()[:500].decode("utf-8", "ignore")
            if e.code in RETRY_CODES and attempt < RETRIES - 1:
                wait = 2**attempt
                if verbose:
                    _log(f"  (Gemini {e.code} - retry {attempt + 1}/{RETRIES - 1} in {wait}s)")
                time.sleep(wait)
                continue
            raise LLMError(f"Gemini {e.code}: {last}", status=e.code) from None
        except urllib.error.URLError as e:
            if attempt < RETRIES - 1:
                time.sleep(2**attempt)
                continue
            raise LLMError(f"network error: {e}") from None
    raise LLMError(f"{RETRIES} retries failed: {last}")


def text_of(resp: dict) -> str:
    """Join just the text parts of a response."""
    parts = ((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def parts_of(resp: dict) -> list:
    return ((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []


if __name__ == "__main__":
    print("backend:", backend(), "| model:", model_name())
    r = generate(
        {"contents": [{"role": "user", "parts": [{"text": "Answer in one word: ready?"}]}]}
    )
    print("response:", text_of(r)[:100])
