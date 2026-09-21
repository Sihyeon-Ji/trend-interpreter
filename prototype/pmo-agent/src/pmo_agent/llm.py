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
import re
import subprocess
import time
import urllib.error
import urllib.request

from pmo_agent.env import env

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_FALLBACK = "gemini-3.5-flash"  # where to go when the main model is overloaded
RETRIES = 4
RETRY_CODES = (429, 503, 500)  # overload, quota, transient. Anything else is our bug — raise it
MAX_WAIT = 8  # seconds we will sit still on the provider's say-so before trying another model
BODY_MAX = 4000  # of an error body; `details` sits past the first 500 characters
SHOWN = 500  # of it in the message we raise
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

    `daily` says the allowance that ran out was a per-day one, which will not come back
    before tomorrow. It rides here rather than being read back out of the message, because
    the message is truncated for display and the part that says so is at the end of it.
    """

    def __init__(self, message: str, status: int | None = None, daily: bool = False):
        super().__init__(message)
        self.status = status
        self.daily = daily


def _wait_hint(raw: str) -> float | None:
    """How long the provider asked us to wait, from the RetryInfo it sends back.

    Guessing with exponential backoff when the answer is in the response is silly in both
    directions: too short and every retry is wasted, too long and we sat there for nothing.
    A real 429 body carries `"retryDelay": "21s"`.
    """
    found = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', raw or "")
    return float(found.group(1)) if found else None


def _daily_quota(raw: str) -> bool:
    """Whether what was hit is a *daily* allowance, which no amount of waiting fixes today.

    Google says which quota in `quotaId`, and the two kinds want opposite responses. A
    per-minute burst limit clears in under a minute and is worth waiting out. A free-tier
    day limit — 20 requests on gemini-3.6-flash — does not come back until tomorrow, and
    the only useful move is the fallback model, which has an allowance of its own.

    Before this, a used-up daily quota cost seven seconds of certain-to-fail retries per
    model, in the middle of a demo.
    """
    return "PerDay" in (raw or "")


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
                why = "daily quota used up" if getattr(e, "daily", False) else "unavailable"
                _log(f"  ({m} {why} - falling back to {chain[i + 1]})")
    raise LLMError("no model left to call")


def _attempt(body: dict, m: str, timeout: int, verbose: bool) -> dict:
    """The retry loop for a single model."""
    last = ""
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(_request(body, m), timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # Read enough to *understand* the error, show only enough to report it.
            # Truncating at 500 first cut the body off before `details`, where the quota
            # id and the retry delay live — so every 429 looked like one with no advice
            # attached, and the retries went ahead regardless of what the provider said.
            last = e.read()[:BODY_MAX].decode("utf-8", "ignore")
            if e.code in RETRY_CODES and attempt < RETRIES - 1 and not _daily_quota(last):
                asked = _wait_hint(last)
                if asked is None or asked <= MAX_WAIT:
                    wait = asked if asked is not None else float(2**attempt)
                    if verbose:
                        _log(
                            f"  (Gemini {e.code} - retry {attempt + 1}/{RETRIES - 1} in {wait:g}s)"
                        )
                    time.sleep(wait)
                    continue
                # The provider named a wait longer than we will sit for. Another model now.
                if verbose:
                    _log(f"  (Gemini {e.code} - asked for {asked:g}s, not waiting)")
            raise LLMError(
                f"Gemini {e.code}: {last[:SHOWN]}", status=e.code, daily=_daily_quota(last)
            ) from None
        except urllib.error.URLError as e:
            if attempt < RETRIES - 1:
                time.sleep(2**attempt)
                continue
            raise LLMError(f"network error: {e}") from None
    raise LLMError(f"{RETRIES} retries failed: {last[:SHOWN]}")


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
