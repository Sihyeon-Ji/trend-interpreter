"""Gemini 호출을 한 군데로 모은 계층.

재시도·오류 본문 노출·백엔드 전환을 전부 여기서만 다룬다.
run.py(에이전트 루프)와 ingest.py(멀티모달 추출)가 같은 입구를 쓴다.

백엔드 두 가지 (.env 의 LLM_BACKEND):
  aistudio (기본) — API 키. 개발·데모용.
  vertex          — Google Cloud Vertex AI. ADC(gcloud 로그인) 토큰을 쓰고 키를 코드에 두지 않는다.
                    공모전 제출 시 Vertex 경유가 가점 요건이라 경로를 미리 열어 둔다.
                    ⚠ GCP 프로젝트가 아직 없어 실호출 미검증 — 구조만 준비된 상태다.

모델 이름은 .env 의 GEMINI_MODEL 하나로 관리한다. 2.5 계열은 신규 사용자에게 종료됐다.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request

from pmo_agent.env import env

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_FALLBACK = "gemini-3.5-flash"  # 주 모델이 과부하일 때 넘어갈 곳
RETRIES = 4
RETRY_CODES = (429, 503, 500)  # 과부하·쿼터·일시 오류. 그 외는 코드 문제라 바로 올린다.
AISTUDIO = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
VERTEX = (
    "https://{region}-aiplatform.googleapis.com/v1/projects/{project}"
    "/locations/{region}/publishers/google/models/{m}:generateContent"
)


def _log(msg: str) -> None:
    """진행 안내. 콘솔 인코딩이 유니코드를 못 받는 환경(Windows cp949 등)에서도 죽지 않는다.

    예전에 여기서 UnicodeEncodeError 가 나서, 재시도로 회복됐어야 할 429 가
    서버 500 으로 바뀌는 일이 있었다. 안내 문구 때문에 요청을 잃지 않는다.
    """
    try:
        print(msg, flush=True)
    except Exception:
        pass


class LLMError(RuntimeError):
    """모델 호출 실패.

    status 에 HTTP 상태를 싣는다. 설정 오류(키 없음·프로젝트 없음)는 status 가 None 이다 —
    문자열에서 '429' 같은 숫자를 찾아 판단하면 응답 본문에 우연히 낀 숫자에 속는다.
    """

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _overloaded(e: LLMError) -> bool:
    """모델을 바꾸거나 다시 시도해 볼 만한 실패인가. 설정 오류는 바꿔봐야 같다."""
    return getattr(e, "status", None) in RETRY_CODES


def model_name() -> str:
    return env("GEMINI_MODEL", DEFAULT_MODEL)


def fallback_model() -> str:
    """주 모델이 계속 과부하면 넘어갈 모델. 빈 값이면 폴백하지 않는다.
    데모 도중 503 하나로 전체가 멈추는 것을 막기 위한 장치다."""
    return env("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK).strip()


def backend() -> str:
    return env("LLM_BACKEND", "aistudio").strip().lower()


def _vertex_token() -> str:
    """ADC 액세스 토큰. gcloud 로그인 상태를 그대로 쓴다 — 키를 파일에 두지 않는다."""
    try:
        out = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=30,
            shell=True,
        )
    except Exception as e:
        raise LLMError(f"gcloud 실행 실패: {e}") from None
    if out.returncode != 0:
        raise LLMError(
            f"ADC 토큰 발급 실패 — 'gcloud auth application-default login' 필요: {out.stderr[:200]}"
        )
    return out.stdout.strip()


def _request(body: dict, model: str) -> urllib.request.Request:
    data = json.dumps(body).encode()
    if backend() == "vertex":
        project, region = env("GCP_PROJECT_ID"), env("GCP_REGION", "asia-northeast3")
        if not project:
            raise LLMError(
                "GCP_PROJECT_ID 없음 — Vertex 백엔드에는 프로젝트가 필요하다 (SETUP.md 1-3)"
            )
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
        raise LLMError("GEMINI_API_KEY 없음 — SETUP.md 1-1 참고")
    return urllib.request.Request(
        AISTUDIO.format(m=model, k=key), data=data, headers={"Content-Type": "application/json"}
    )


def generate(
    body: dict, model: str | None = None, timeout: int = 180, verbose: bool = True
) -> dict:
    """generateContent 호출.

    과부하(429/503)는 지수 백오프로 재시도하고, 그래도 안 되면 대체 모델로 한 번 더 시도한다.
    대체 모델까지 실패해야 LLMError 를 올린다.
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
            # 마지막 모델이거나, 모델을 바꿔도 소용없는 실패(설정 오류 등)면 그대로 올린다
            if i == len(chain) - 1 or not _overloaded(e):
                raise
            if verbose:
                _log(f"  ({m} unavailable - falling back to {chain[i + 1]})")
    raise LLMError("호출할 모델이 없다")


def _attempt(body: dict, m: str, timeout: int, verbose: bool) -> dict:
    """모델 하나에 대한 재시도 루프."""
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
            raise LLMError(f"네트워크 오류: {e}") from None
    raise LLMError(f"재시도 {RETRIES}회 실패: {last}")


def text_of(resp: dict) -> str:
    """응답에서 텍스트 파트만 이어붙인다."""
    parts = ((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def parts_of(resp: dict) -> list:
    return ((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []


if __name__ == "__main__":
    print("backend:", backend(), "| model:", model_name())
    r = generate({"contents": [{"role": "user", "parts": [{"text": "한 단어로 대답: 준비됐니?"}]}]})
    print("응답:", text_of(r)[:100])
