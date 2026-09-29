"""Gemini 호출 공통: 하루 예산, 503/429 재시도, 3.8 → 3.5 폴백. 모든 파이프라인 단계는 이 함수로만 호출한다."""
from __future__ import annotations

import time
from typing import Any

from google.genai import errors, types

from ..config import GEMINI_DAILY_BUDGET, GEMINI_FALLBACK_MODEL, GEMINI_MODEL, REQUEST_GEMINI_DAILY, USE_LOCAL_GEMMA
from .. import model_client
from ..storage import dictionary_store as ds
from ..storage.db import Connection

class BudgetExhausted(RuntimeError):
    pass


client = model_client.client


REQUEST_LEDGER = "req:"   # 이용자 요청의 장부 — 파이프라인 예산을 쓰지 않는다


def budget_left(con: Connection, request: bool = False) -> int:
    if request:
        return ds.gemini_budget_left(con, REQUEST_GEMINI_DAILY, REQUEST_LEDGER)
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
             model: str | None = None, tries: int = 3, allow_fallback: bool = True,
             allow_local: bool = True, request: bool = False) -> tuple[Any, str]:
    """(응답, 실제로 쓴 모델). 예산이 없으면 BudgetExhausted. 텍스트 전용 호출은 로컬 Gemma 가 켜져 있으면 그쪽으로.
    request=True 면 이용자 요청의 장부(REQUEST_GEMINI_DAILY)로 센다. 사람이 기다리는 요청이라 모델마다 한 번만 시도하고 기다리지 않으며,
    429·503 으로 거절된 시도는 장부에서 돌려놓는다 — 거절도 한 번으로 세어 503 이 몰린 순간 요청 하나가 하루 몫의 절반을 썼다(검토 3차)."""
    if allow_local and local_ok() and isinstance(contents, str):
        from . import local_llm

        return local_llm.generate(contents), f"local:{__import__('trend_agents.config', fromlist=['GEMMA_LOCAL_MODEL']).GEMMA_LOCAL_MODEL}"
    if budget_left(con, request) <= 0:
        raise BudgetExhausted(f"오늘 Gemini 예산 {REQUEST_GEMINI_DAILY if request else GEMINI_DAILY_BUDGET}회 소진")
    primary = model or GEMINI_MODEL
    models = [primary] + ([GEMINI_FALLBACK_MODEL] if allow_fallback and primary != GEMINI_FALLBACK_MODEL else [])
    ledger = REQUEST_LEDGER if request else ""
    last: Exception | None = None
    for m in models:
        for attempt in range(1 if request else tries):
            try:
                ds.gemini_spend(con, 1, ledger)
                return client().models.generate_content(model=m, contents=contents, config=config), m
            except errors.APIError as e:  # 503 용량 / 429 쿼터 → 잠시 후 재시도, 다 실패하면 폴백 모델
                last = e
                if e.code in (429, 503):
                    if request:
                        ds.gemini_spend(con, -1, ledger)   # 거절된 시도는 부른 것이 아니다
                    else:
                        time.sleep(3 * (attempt + 1))
                    continue
                raise
    assert last is not None
    raise last


def structured(con: Connection, prompt: str, schema: Any, temperature: float = 0.1, model: str | None = None,
               image: tuple[bytes, str] | None = None, prefer_gemini: bool = False, request: bool = False) -> tuple[Any, str]:
    """image 는 (바이트, MIME) 한 장. 로컬 Gemma 가 켜져 있으면 그쪽이 그림까지 읽고, 아니면 Gemini 가 읽는다.
    prefer_gemini: 생성처럼 Gemini 가 맡는 일(ADR 0002 §3) — Gemini 가 설정돼 있고 예산이 남았으면 로컬 Gemma 보다 먼저 쓴다.
    request: 이용자 요청 — Gemini 는 요청 장부로 세고, 그 한도가 끝나면 로컬 Gemma 로(없으면 BudgetExhausted).
    prefer_gemini 에서 Gemini 가 실패하거나(장애·한도) 형식을 못 맞추면 로컬 Gemma 가 있을 때만 그쪽으로 — 없으면 그 오류를 그대로 낸다."""
    if prefer_gemini and configured() and budget_left(con, request) > 0:
        contents0: Any = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt] if image else prompt
        try:
            resp, used = generate(con, contents0, types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                                                              temperature=temperature), model=model, allow_local=False, request=request)
        except (errors.APIError, BudgetExhausted):
            if not local_ok():
                raise
        else:
            if resp.parsed is not None or not local_ok():
                return resp.parsed, used
    if local_ok():
        from . import local_llm
        from ..config import GEMMA_LOCAL_MODEL

        return local_llm.structured(prompt, schema, temperature, image=image), f"local:{GEMMA_LOCAL_MODEL}"
    contents: Any = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt] if image else prompt
    resp, used = generate(con, contents, types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=temperature),
                          model=model, request=request)
    return resp.parsed, used
