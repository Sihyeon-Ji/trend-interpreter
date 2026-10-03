"""Gemini 호출 공통: 하루 예산, 503/429 재시도, 모델 사슬(GEMINI_MODELS — 무료 할당량이 모델마다 따로라 끝난 모델은 그날 건너뛴다).
모든 파이프라인 단계는 이 함수로만 호출한다."""
from __future__ import annotations

import logging
import time
from typing import Any

from google.genai import errors, types

from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import (GEMINI_DAILY_BUDGET, GEMINI_FALLBACK_MODEL, GEMINI_LIMITS, GEMINI_MAX_OUTPUT_TOKENS, GEMINI_MODEL, GEMINI_MODELS,
                      GEMINI_MONTHLY_USD, GEMINI_PER_MODEL_DAILY, GEMINI_PRICES, GEMINI_RESERVE_INPUT_TOKENS, GEMINI_SEARCH_GROUNDING,
                      REQUEST_GEMINI_DAILY, USE_LOCAL_GEMMA)
from .. import model_client
from ..logging_setup import event
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from .runs import record_model

log = logging.getLogger("trend.gemini")


class BudgetExhausted(RuntimeError):
    pass


client = model_client.client


REQUEST_LEDGER = "req:"   # 이용자 요청의 장부 — 파이프라인 예산을 쓰지 않는다


def _quota_day() -> str:
    """Google 무료 할당량이 새로 차는 날(태평양 시각 자정) — 한국 시각 날짜로 세면 오후 4~5시에 풀린 몫을 못 쓴다."""
    return datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()


def _count(con: Connection, key: str) -> int:
    row = con.execute("SELECT count FROM gemini_calls WHERE day=?", (key,)).fetchone()
    return row[0] if row else 0


def _bump(con: Connection, key: str, n: int = 1) -> None:
    con.execute("INSERT INTO gemini_calls VALUES (?,?) ON CONFLICT(day) DO UPDATE SET count=gemini_calls.count+excluded.count", (key, n))
    con.commit()


def models(con: Connection, first: str | None = None, grounded: bool = False) -> list[str]:
    """오늘 아직 쓸 수 있는 모델 차례. 모델별 장부 'm:<모델>:<날>' 이 GEMINI_PER_MODEL_DAILY 에 닿았거나
    구글이 그날 끝이라고 한 모델('x:<모델>:<날>')은 뺀다. grounded 면 검색 grounding 이 그날 닫혔을 때 빈 목록."""
    day = _quota_day()
    if grounded and (not GEMINI_SEARCH_GROUNDING or _count(con, f"xs:{day}")):
        return []
    chain = list(dict.fromkeys(([first] if first else []) + GEMINI_MODELS))
    ok = [m for m in chain if not _count(con, f"x:{m}:{day}") and _count(con, f"m:{m}:{day}") < limit(m)[1]]
    now = time.time()

    def full(m: str) -> bool:      # 이 프로세스에서 지난 1분 동안 분당 몫을 다 썼다 — 기다리지 말고 여유 있는 모델부터
        return len([t for t in _last_call.get(m, []) if now - t < 60]) >= limit(m)[0]

    ready = [m for m in ok if _busy.get(m, 0) <= now and not full(m)]
    return ready + [m for m in ok if m not in ready]   # 쉬는(503)·분당 찬 모델은 맨 뒤로


def limit(model: str) -> tuple[int, int]:
    """(분당, 하루) — config.GEMINI_LIMITS(AI Studio 화면 값)."""
    return GEMINI_LIMITS.get(model, (5, GEMINI_PER_MODEL_DAILY))


_last_call: dict[str, list[float]] = {}
_busy: dict[str, float] = {}       # 503(용량 부족)을 낸 모델 → 다시 써 볼 시각


def _pace(model: str) -> None:
    """분당 한도를 넘지 않게 이 프로세스 안에서 간격을 둔다(3.x Flash 는 분당 5 — 몰아 부르면 429 로 하루 몫이 깎인다)."""
    rpm = limit(model)[0]
    now = time.time()
    recent = [t for t in _last_call.get(model, []) if now - t < 60]
    if len(recent) >= rpm:
        time.sleep(max(0.0, 60 - (now - recent[0])) + 0.5)
    _last_call[model] = recent[-(rpm - 1):] + [time.time()] if rpm > 1 else [time.time()]


def note_call(con: Connection, model: str, n: int = 1) -> None:
    _bump(con, f"m:{model}:{_quota_day()}", n)


def note_quota(con: Connection, model: str, e: Exception, grounded: bool = False) -> bool:
    """429 를 읽어 그날 닫을 것을 닫는다. 닫았으면 True(같은 모델로 다시 해 봐야 소용없다).
    - 모델별 하루 몫(PerDay…PerModel) → 그 모델만
    - 검색 grounding 호출의 이름 없는 429 → grounding 전체(모델을 바꿔도 같다)"""
    msg = str(e)
    if getattr(e, "code", None) != 429:
        return False
    day = _quota_day()
    if "PerDay" in msg:
        _bump(con, f"x:{model}:{day}")
        return True
    if grounded and "quotaId" not in msg:
        _bump(con, f"xs:{day}")
        return True
    return False


MICRO_USD = 1_000_000


def _month_key() -> str:
    return "usd:" + datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m")


def _cost(model: str, input_tokens: int, output_tokens: int) -> int:
    """마이크로달러. 단가가 100만 토큰당 달러라 토큰 수 × 단가가 곧 마이크로달러다."""
    price_in, price_out = GEMINI_PRICES[model]
    return round(input_tokens * price_in + output_tokens * price_out)


def _reserve(model: str) -> int:
    return _cost(model, GEMINI_RESERVE_INPUT_TOKENS, GEMINI_MAX_OUTPUT_TOKENS)


def spent_usd(con: Connection) -> float:
    """이번 달(태평양 시각) 실제 사용량으로 센 Gemini 금액."""
    return _count(con, _month_key()) / MICRO_USD


def affordable(con: Connection, model: str) -> bool:
    """이번 달 금액 상한 안에서 이 모델로 최악의 호출 한 번을 더 할 수 있나. 상한이 꺼져 있으면 늘 True."""
    if GEMINI_MONTHLY_USD <= 0:
        return True
    return model in GEMINI_PRICES and _count(con, _month_key()) + _reserve(model) <= GEMINI_MONTHLY_USD * MICRO_USD


def _charge(con: Connection, model: str, resp: Any) -> None:
    """성공한 호출(Vertex 는 200 응답만 과금한다)의 실제 사용량을 금액 장부에 더한다. 사용량이 없으면 최악 비용으로 센다."""
    if model not in GEMINI_PRICES:
        return
    usage = getattr(resp, "usage_metadata", None)
    if usage is None:
        cost = _reserve(model)
    else:
        prompt = (getattr(usage, "prompt_token_count", 0) or 0) + (getattr(usage, "tool_use_prompt_token_count", 0) or 0)
        output = (getattr(usage, "candidates_token_count", 0) or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
        cost = _cost(model, prompt, output)
    _bump(con, _month_key(), cost)


def _bounded(config: types.GenerateContentConfig | None) -> types.GenerateContentConfig:
    """출력 상한을 건다. 호출부가 더 작게 정했으면 그대로 둔다."""
    if config is None:
        return types.GenerateContentConfig(max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS)
    if config.max_output_tokens and config.max_output_tokens <= GEMINI_MAX_OUTPUT_TOKENS:
        return config
    return config.model_copy(update={"max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS})


def budget_left(con: Connection, request: bool = False) -> int:
    if request:
        return ds.gemini_budget_left(con, REQUEST_GEMINI_DAILY, REQUEST_LEDGER)
    return ds.gemini_budget_left(con, GEMINI_DAILY_BUDGET)


def configured() -> bool:
    """Gemini(Vertex)를 부를 수 있게 설정돼 있나. 기본 개발 환경(MODEL_REQUESTS_ENABLED=false)은 아니다."""
    return model_client.requests_enabled()


def _called(model: str, ledger: str, outcome: str, code: int | None = None) -> None:
    """Vertex 에 요청을 보낼 때마다 한 줄(event=gemini_call): 모델·장부·결과(ok·rejected·error)·HTTP 코드. 로그 기반 지표가 이것을 세면
    MODEL_REQUESTS_ENABLED=false 로 배포한 뒤 호출이 0회인지 볼 수 있다(Plan 05). 거절(429·503)도 보낸 요청이다. 프롬프트·응답은 넣지 않는다."""
    fields: dict = {"model": model, "ledger": "request" if ledger else "pipeline", "outcome": outcome}
    if code is not None:
        fields["code"] = code
    event(log, "gemini_call", logging.INFO if outcome == "ok" else logging.WARNING, **fields)


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

        out, name = local_llm.generate(contents), f"local:{__import__('trend_agents.config', fromlist=['GEMMA_LOCAL_MODEL']).GEMMA_LOCAL_MODEL}"
        record_model(name)
        return out, name
    if budget_left(con, request) <= 0:
        raise BudgetExhausted(f"오늘 Gemini 예산 {REQUEST_GEMINI_DAILY if request else GEMINI_DAILY_BUDGET}회 소진")
    grounded = bool(config and any(getattr(t, "google_search", None) for t in (config.tools or [])))
    chain = models(con, model or GEMINI_MODEL, grounded) if allow_fallback else [model or GEMINI_MODEL]
    priced = [m for m in chain if affordable(con, m)]
    if chain and not priced:
        raise BudgetExhausted(f"이번 달 Gemini 금액 상한 ${GEMINI_MONTHLY_USD:g} 에 닿았다")
    chain = priced
    if request:
        chain = chain[:2]         # 사람이 기다린다 — 쓸 수 있는 앞의 두 모델만(끝난 모델은 이미 빠졌다)
    if not chain:
        raise BudgetExhausted("오늘 쓸 수 있는 Gemini 모델(또는 검색 grounding) 몫이 끝났다")
    config = _bounded(config)
    ledger = REQUEST_LEDGER if request else ""
    c = client()  # 호출이 꺼져 있으면 여기서 끝난다 — 보내지 않은 요청으로 장부를 깎거나 이벤트를 남기지 않는다
    last: Exception | None = None
    for m in chain:
        for attempt in range(1 if request else tries):
            if not request:
                _pace(m)
            ds.gemini_spend(con, 1, ledger)
            note_call(con, m)
            try:
                resp = c.models.generate_content(model=m, contents=contents, config=config)
            except errors.APIError as e:  # 503 용량 / 429 쿼터 → 잠시 후 재시도, 그날 끝난 모델이면 바로 다음 모델
                last = e
                retry = e.code in (429, 503)
                _called(m, ledger, "rejected" if retry else "error", e.code)
                if retry:
                    if request:
                        ds.gemini_spend(con, -1, ledger)   # 거절된 시도는 부른 것이 아니다
                    if e.code == 503:
                        # 용량 부족은 같은 모델을 다시 두드려도 몇 분은 같다 — 재시도가 분당 몫(3.x Flash 는 5)을 채웠다(10-01 AI Studio 5/5).
                        # 그 모델은 5분 쉬게 하고 바로 다음 모델로. 하루 몫(RPD)엔 넣지 않는다
                        _busy[m] = time.time() + 300
                        note_call(con, m, -1)
                        if m != chain[-1]:
                            break
                    if note_quota(con, m, e, grounded):
                        if grounded and _count(con, f"xs:{_quota_day()}"):
                            raise BudgetExhausted("오늘 검색 grounding 몫이 끝났다") from e
                        break
                    if not request:
                        time.sleep(3 * (attempt + 1))
                    continue
                if e.code == 500 and m != chain[-1]:   # 서버 쪽 오류(Gemma 4 31B 에서 잦았다) — 다음 모델로
                    note_call(con, m, -1)
                    break
                raise
            except Exception:
                _called(m, ledger, "error")
                raise
            _called(m, ledger, "ok")
            _charge(con, m, resp)
            record_model(m)
            return resp, m
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

        parsed = local_llm.structured(prompt, schema, temperature, image=image)
        record_model(f"local:{GEMMA_LOCAL_MODEL}")
        return parsed, f"local:{GEMMA_LOCAL_MODEL}"
    contents: Any = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt] if image else prompt
    resp, used = generate(con, contents, types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=temperature),
                          model=model, request=request)
    return resp.parsed, used


# ── 도구 호출 대화(사전에 묻기) ───────────────────────────────────────────────
# ask.py 의 루프는 OpenAI 꼴 메시지·도구 정의를 쓴다. 같은 루프를 Gemini 로 돌리려고 여기서 옮긴다.
# Gemini 3 은 함수 호출에 'thought signature' 를 붙여 보내고, 다음 턴에 그 부분을 그대로 돌려받아야 한다 —
# 그래서 모델이 낸 내용(Content)을 호출 id 로 기억해 두었다가 그대로 다시 넣는다.
_RAW_TURNS: dict[str, Any] = {}


def chat_with_tools(con: Connection, messages: list[dict], tools: list[dict], request: bool = True):
    """(본문, [ToolCall]) — local_chat.chat_with_tools 와 같은 꼴. 이용자 요청 장부로 센다."""
    from ..interpreters.local_chat import ToolCall

    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    contents: list[types.Content] = []
    for m in messages:
        if m["role"] == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=m["content"])]))
        elif m["role"] == "assistant":
            calls = m.get("calls") or []
            raw = _RAW_TURNS.get(calls[0].id) if calls else None
            if raw is not None:
                contents.append(raw)
            else:
                parts = ([types.Part(text=m["content"])] if m.get("content") else []) + \
                        [types.Part(function_call=types.FunctionCall(name=c.name, args=c.args)) for c in calls]
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
        elif m["role"] == "tool":
            part = types.Part.from_function_response(name=m["name"], response={"result": m["content"]})
            if contents and contents[-1].role == "user" and all(p.function_response for p in contents[-1].parts):
                contents[-1].parts.append(part)          # 한 턴의 여러 도구 결과는 한 묶음으로
            else:
                contents.append(types.Content(role="user", parts=[part]))
    decl = [types.FunctionDeclaration(name=t["function"]["name"], description=t["function"]["description"],
                                      parameters_json_schema=t["function"]["parameters"]) for t in tools]
    cfg = types.GenerateContentConfig(system_instruction=system or None, temperature=0.2,
                                      tools=[types.Tool(function_declarations=decl)] if decl else None,
                                      automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
    from ..config import CHAT_MODEL

    resp, _used = generate(con, contents, cfg, model=CHAT_MODEL, allow_local=False, request=request)
    cand = resp.candidates[0] if resp.candidates else None
    parts = (cand.content.parts or []) if cand and cand.content else []
    calls = [ToolCall(id=f"g{id(cand)}_{i}", name=p.function_call.name, args=dict(p.function_call.args or {}))
             for i, p in enumerate(parts) if p.function_call]
    if calls:
        _RAW_TURNS[calls[0].id] = cand.content
        while len(_RAW_TURNS) > 200:
            _RAW_TURNS.pop(next(iter(_RAW_TURNS)))
    text = "".join(p.text for p in parts if p.text and not getattr(p, "thought", False))
    return text, calls
