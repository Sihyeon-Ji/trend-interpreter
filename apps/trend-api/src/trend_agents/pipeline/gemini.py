"""Gemini 호출 공통: 하루 예산, 503/429 재시도, 3.8 → 3.5 폴백. 모든 파이프라인 단계는 이 함수로만 호출한다."""
from __future__ import annotations

import time
from typing import Any

from google.genai import errors, types

from ..config import GEMINI_DAILY_BUDGET, GEMINI_FALLBACK_MODEL, GEMINI_MODEL, USE_LOCAL_GEMMA
from .. import model_client
from ..storage import dictionary_store as ds
from ..storage.db import Connection

class BudgetExhausted(RuntimeError):
    pass


client = model_client.client


def budget_left(con: Connection) -> int:
    return ds.gemini_budget_left(con, GEMINI_DAILY_BUDGET)


def configured() -> bool:
    """Gemini(Vertex)를 부를 수 있게 설정돼 있나. 기본 개발 환경(MODEL_REQUESTS_ENABLED=false)은 아니다."""
    return model_client.requests_enabled()


def local_ok() -> bool:
    """텍스트 작업을 로컬 Gemma 로 보낼 수 있는가 (USE_LOCAL_GEMMA=1 + Ollama 에 모델 있음)."""
    if not USE_LOCAL_GEMMA:
        return False
    from . import local_llm

    return local_llm.available()


def generate(con: Connection, contents: Any, config: types.GenerateContentConfig | None = None,
             model: str | None = None, tries: int = 3, allow_fallback: bool = True) -> tuple[Any, str]:
    """(응답, 실제로 쓴 모델). 예산이 없으면 BudgetExhausted. 텍스트 전용 호출은 로컬 Gemma 가 켜져 있으면 그쪽으로."""
    if local_ok() and isinstance(contents, str):
        from . import local_llm

        return local_llm.generate(contents), f"local:{__import__('trend_agents.config', fromlist=['GEMMA_LOCAL_MODEL']).GEMMA_LOCAL_MODEL}"
    if budget_left(con) <= 0:
        raise BudgetExhausted(f"오늘 Gemini 예산 {GEMINI_DAILY_BUDGET}회 소진")
    primary = model or GEMINI_MODEL
    models = [primary] + ([GEMINI_FALLBACK_MODEL] if allow_fallback and primary != GEMINI_FALLBACK_MODEL else [])
    last: Exception | None = None
    for m in models:
        for attempt in range(tries):
            try:
                ds.gemini_spend(con, 1)
                return client().models.generate_content(model=m, contents=contents, config=config), m
            except errors.APIError as e:  # 503 용량 / 429 쿼터 → 잠시 후 재시도, 다 실패하면 폴백 모델
                last = e
                if e.code in (429, 503):
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
    assert last is not None
    raise last


def structured(con: Connection, prompt: str, schema: Any, temperature: float = 0.1, model: str | None = None,
               image: tuple[bytes, str] | None = None, prefer_gemini: bool = False) -> tuple[Any, str]:
    """image 는 (바이트, MIME) 한 장. 로컬 Gemma 가 켜져 있으면 그쪽이 그림까지 읽고, 아니면 Gemini 가 읽는다.
    prefer_gemini: 생성처럼 Gemini 가 맡는 일(ADR 0002 §3) — Gemini 가 설정돼 있고 예산이 남았으면 로컬 Gemma 보다 먼저 쓴다."""
    if prefer_gemini and configured() and budget_left(con) > 0:
        contents0: Any = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt] if image else prompt
        resp, used = generate(con, contents0, types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                                                          temperature=temperature), model=model)
        return resp.parsed, used
    if local_ok():
        from . import local_llm
        from ..config import GEMMA_LOCAL_MODEL

        return local_llm.structured(prompt, schema, temperature, image=image), f"local:{GEMMA_LOCAL_MODEL}"
    contents: Any = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt] if image else prompt
    resp, used = generate(con, contents, types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=temperature), model=model)
    return resp.parsed, used
