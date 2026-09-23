"""로컬 LLM 으로 구조화 출력·자유 서술. USE_LOCAL_GEMMA=1 이고 로컬 모델이 떠 있으면 pipeline/gemini.py 가 텍스트 작업을 여기로 보낸다.
영상(YouTube URL)과 Google 검색 grounding 은 Gemini 전용이라 여기 없다. 실제 호출과 백엔드(Ollama/vLLM) 선택은 interpreters/local_chat.py."""
from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any, get_args, get_origin

from pydantic import TypeAdapter, create_model

from ..interpreters import local_chat

_available: tuple[bool, float] | None = None
AVAILABLE_TTL_S = 300  # --loop·API 는 몇 시간씩 살아 있다 — 로컬 서버가 죽거나 살아나면 5분 안에 반영
_stats = {"calls": 0, "seconds": 0.0}


def available() -> bool:
    global _available
    if _available is None or time.time() - _available[1] > AVAILABLE_TTL_S:
        _available = (local_chat.available(), time.time())
    return _available[0]


def stats() -> dict:
    return dict(_stats)


def _adapter(schema: Any):
    """list[Model] 은 {"items": [...]} 로 감싼다 — 구조화 출력은 최상위 객체가 안전하다."""
    if get_origin(schema) is list:
        inner = get_args(schema)[0]
        wrapper = create_model("ListWrapper", items=(list[inner], ...))  # type: ignore[valid-type]
        return TypeAdapter(wrapper), True
    return TypeAdapter(schema), False


def structured(prompt: str, schema: Any, temperature: float = 0.1) -> Any:
    adapter, wrapped = _adapter(schema)
    t0 = time.time()
    parsed = local_chat.structured(prompt + ("\n\nReturn JSON with a single key \"items\" holding the list." if wrapped else ""), adapter, temperature)
    _stats["calls"] += 1
    _stats["seconds"] += time.time() - t0
    return parsed.items if wrapped else parsed  # type: ignore[attr-defined]


def generate(prompt: str, temperature: float = 0.2) -> SimpleNamespace:
    t0 = time.time()
    text = local_chat.chat_text(prompt, temperature)
    _stats["calls"] += 1
    _stats["seconds"] += time.time() - t0
    return SimpleNamespace(text=text)
