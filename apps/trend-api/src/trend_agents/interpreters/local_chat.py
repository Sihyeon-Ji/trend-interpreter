"""로컬 LLM 호출 한 곳 — Ollama(Gemma 4) 또는 OpenAI 호환 서버(vLLM 등). 다른 모듈은 여기만 부른다.

- 백엔드는 .env 로 고른다. LOCAL_LLM_BASE_URL 이 비어 있으면 Ollama(localhost:11434), 있으면 그 주소의 /chat/completions.
  모델 이름은 둘 다 GEMMA_LOCAL_MODEL (vLLM 은 --served-model-name).
- 구조화 출력은 서버의 스키마 강제(Ollama format / vLLM guided decoding)에 기대지 않는다. 스키마를 프롬프트에 넣고,
  응답에서 JSON 을 꺼내 pydantic 으로 검증하고, 틀리면 한 번 다시 묻는다.
  이유: Ollama 0.20 + gemma4:e4b 는 format 을 주면 짧은 답은 펜스·키 이름이 바뀌고, 15건 배열처럼 긴 답은 1,400자 부근에서 JSON 이
  깨진다(2026-09-15 실측, format 없이 같은 프롬프트는 정상). 그래서 Ollama 에도 format 을 보내지 않는다. vLLM guided decoding 은
  Qwen FP8 에서 CUDA 크래시로 EngineCore 를 죽인 전례가 있다(MCTI lib/llm-client.ts 가드, 2026-06-11).
- thinking 은 끈다. Gemma 4 는 think=False(켜면 50초, 끄면 7초, 답은 같음), Qwen3 계열은 chat_template_kwargs.enable_thinking=false.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx
import ollama
from pydantic import TypeAdapter, ValidationError

from ..config import GEMMA_LOCAL_MODEL, LOCAL_LLM_BASE_URL

NUM_CTX = 8192  # Ollama 기본 컨텍스트가 크면(이 서버는 131k) KV 캐시가 VRAM 을 먹어 GPU 에 덜 올라간다
TIMEOUT = 180.0
MAX_TOKENS = 2048  # 폭주 방지(재질문에서 2만 자를 뱉은 실측). 구조화 출력은 이보다 훨씬 짧다

_JSON_RULE = "\n\n아래 모양대로 키 이름과 값 종류를 그대로 지켜 JSON 하나만 출력하라. 모든 키를 넣는다. null 은 모양에 |null 이 있는 키에만 쓰고, 그 외 키는 모르면 빈 문자열 \"\" 이나 빈 배열 [] 로 채운다. 설명이나 코드 펜스는 쓰지 않는다.\n모양: {schema}"
_RETRY_RULE = "\n\n직전 응답은 위 모양과 맞지 않았다({error}). 같은 내용을 위 모양 그대로, 항목 수를 바꾸지 말고 다시 답하라."
# Ollama 기본 클라이언트는 시간 제한이 없다 — 모델이 멈추면 요청을 받은 작업 스레드가 끝없이 묶였다(검토 3차)
_OLLAMA = ollama.Client(timeout=TIMEOUT)
_HOSTS: dict[str, ollama.Client] = {}


def _client(host: str | None) -> ollama.Client:
    """host 를 주면 그 Ollama(예: 감사관을 다른 GPU 서버에서, AUDIT_OLLAMA_HOST). 없으면 기본."""
    if not host:
        return _OLLAMA
    if host not in _HOSTS:
        _HOSTS[host] = ollama.Client(host=host, timeout=TIMEOUT)
    return _HOSTS[host]


def available(model: str = GEMMA_LOCAL_MODEL) -> bool:
    """모델이 서버에 실제로 있는가. 서버가 없으면 False."""
    try:
        if LOCAL_LLM_BASE_URL:
            r = httpx.get(f"{LOCAL_LLM_BASE_URL}/models", timeout=5)
            r.raise_for_status()
            return any(m.get("id") == model for m in r.json().get("data", []))
        return any(m.model == model for m in ollama.Client(timeout=5).list().models)
    except Exception:
        return False


def chat_text(prompt: str, temperature: float = 0.2, model: str = GEMMA_LOCAL_MODEL) -> str:
    return _chat(prompt, temperature, model)


def structured(prompt: str, schema: Any, temperature: float = 0.1, model: str = GEMMA_LOCAL_MODEL, image: tuple[bytes, str] | None = None, host: str | None = None) -> Any:
    """schema(pydantic 모델 클래스 또는 TypeAdapter)로 검증된 값을 돌려준다. 두 번 틀리면 ValueError.
    image 는 (바이트, MIME) — 사진 한 장을 함께 본다(Gemma 4 는 그림을 읽는다). 메모리에서만 쓰고 어디에도 남기지 않는다."""
    adapter = schema if isinstance(schema, TypeAdapter) else TypeAdapter(schema)
    js = adapter.json_schema()
    ask = prompt + _JSON_RULE.format(schema=describe_schema(js))
    error = ""
    for _ in range(2):
        text = _chat(ask + (_RETRY_RULE.format(error=error) if error else ""), temperature, model, json_schema=js, **({"image": image} if image else {}),
                     host=host)
        try:
            return adapter.validate_json(extract_json(text))
        except (ValidationError, ValueError) as e:
            error = _problem(e)
            partial = _valid_items(adapter, js, text)
            if partial is not None:
                return partial  # 틀린 항목만 버리고 나머지는 살린다 — 호출부(classify 등)가 매핑 비율로 배치 폐기를 판단한다
    raise ValueError(f"로컬 LLM 구조화 출력 실패 ({model}): {error}")


def _problem(e: Exception) -> str:
    """재질문에 넣을 짧은 오류 — 어느 키가 틀렸는지. '4 validation errors' 만 알려 주면 작은 모델이 같은 자리(최상위 thumbnail 을
    script 안에 넣기)를 또 틀렸다(2026-09-29 실측)."""
    if isinstance(e, ValidationError):
        return "; ".join(f"{'.'.join(map(str, x['loc'])) or '(전체)'}: {x['msg']}" for x in e.errors()[:4])[:300]
    return str(e).splitlines()[0][:200]


def _valid_items(adapter: TypeAdapter, js: dict, text: str):
    """{"items": [...]} 꼴 스키마에서 항목별로 검증해 맞는 것만 남긴다. 그런 꼴이 아니거나 맞는 항목이 하나도 없으면 None."""
    props = js.get("properties", {})
    if list(props) != ["items"] or props["items"].get("type") != "array":
        return None
    try:
        data = json.loads(extract_json(text))
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return None
    except ValueError:
        return None
    keep = []
    for it in items:
        try:
            adapter.validate_python({"items": [it]})
            keep.append(it)
        except ValidationError:
            continue
    return adapter.validate_python({"items": keep}) if keep else None


def extract_json(text: str) -> str:
    """코드 펜스와 앞뒤 설명을 벗기고 첫 JSON 객체(또는 배열)만 남긴다."""
    t = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if not starts:
        raise ValueError(f"JSON 이 없음: {text[:80]!r}")
    i = min(starts)
    j = t.rfind("}" if t[i] == "{" else "]")
    cand = t[i : j + 1] if j >= i else t[i:]
    try:
        json.loads(cand)
        return cand
    except ValueError:
        # gemma4:e4b 실측 두 가지: 끝의 ]} 를 안 닫고 멈춤 / }}] 처럼 닫는 순서가 어긋남. 꼬리의 닫는 괄호를 걷어내고 스택대로 다시 닫는다.
        fixed = _close_brackets(t[i:].rstrip().rstrip("]}, \n\t"))
        json.loads(fixed)
        return fixed


def _close_brackets(t: str) -> str:
    """문자열 밖에서 열린 { [ 를 세어 닫아 준다. 열린 문자열도 닫는다."""
    stack: list[str] = []
    in_str = esc = False
    for ch in t:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    return t + ('"' if in_str else "") + "".join(reversed(stack))


def describe_schema(js: dict) -> str:
    """JSON 스키마를 모델이 따라 쓰기 쉬운 모양으로 압축한다: {"items": [{"i": int, "kind": "a"|"b", "x": str|null}, ...]}.
    스키마 원문을 그대로 넣으면 gemma4:e4b 가 긴 배열 끝을 닫지 않고 멈춘다(09-15 실측). enum 값은 전부 나열한다."""
    defs = js.get("$defs", {})

    def render(node: dict) -> str:
        if "$ref" in node:
            node = defs[node["$ref"].rsplit("/", 1)[-1]]
        if "anyOf" in node:
            return "|".join(dict.fromkeys(render(n) for n in node["anyOf"]))
        if "enum" in node:
            return "|".join(json.dumps(v, ensure_ascii=False) for v in node["enum"])
        if "const" in node:
            return json.dumps(node["const"], ensure_ascii=False)
        t = node.get("type")
        if t == "object":
            return "{" + ", ".join(f'"{k}": {render(v)}' for k, v in node.get("properties", {}).items()) + "}"
        if t == "array":
            return "[" + render(node.get("items", {})) + ", ...]"
        return {"string": "str", "integer": "int", "number": "float", "boolean": "true|false", "null": "null"}.get(t, "any")

    return render(js)


def _chat(prompt: str, temperature: float, model: str, json_schema: dict | None = None, image: tuple[bytes, str] | None = None,
          host: str | None = None) -> str:
    messages: list[dict] = [{"role": "user", "content": prompt}]
    if image and LOCAL_LLM_BASE_URL:   # OpenAI 호환: 글과 그림을 한 메시지의 조각으로
        data = base64.b64encode(image[0]).decode()
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt},
                                                 {"type": "image_url", "image_url": {"url": f"data:{image[1]};base64,{data}"}}]}]
    elif image:                        # Ollama: 메시지에 images 로
        messages[0]["images"] = [image[0]]
    if LOCAL_LLM_BASE_URL:
        # response_format(guided decoding) 은 보내지 않는다 — 모듈 주석 참조.
        body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": MAX_TOKENS,
                "chat_template_kwargs": {"enable_thinking": False}}
        r = httpx.post(f"{LOCAL_LLM_BASE_URL}/chat/completions", json=body, timeout=TIMEOUT)
        r.raise_for_status()
        choice = r.json()["choices"][0]
        content = choice["message"].get("content") or ""
        if not content:
            if choice.get("finish_reason") == "length":
                raise RuntimeError(f"로컬 LLM 응답이 잘림 ({model}): thinking 이 max_tokens 를 소진")
            content = choice["message"].get("reasoning_content") or ""
        return content
    # Ollama: format(스키마 강제)은 보내지 않는다 — 모듈 주석의 실측. 스키마는 이미 프롬프트에 있다.
    r = _client(host).chat(model=model, messages=messages, think=False,
                    options={"temperature": temperature, "num_ctx": NUM_CTX, "num_predict": MAX_TOKENS})
    return r.message.content


# ---------- 도구 호출 (질문 응답 루프용) ----------
# Ollama 는 arguments 를 딕셔너리로, OpenAI 호환(vLLM)은 JSON 문자열로 준다. 여기서 한 모양으로 맞춘다.
# 대화 메시지도 백엔드마다 키가 달라(tool_name vs tool_call_id) 이 함수가 흡수한다.

@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


def chat_with_tools(messages: list[dict], tools: list[dict], temperature: float = 0.2,
                    model: str = GEMMA_LOCAL_MODEL, timeout: float = TIMEOUT) -> tuple[str, list[ToolCall]]:
    """(본문, 도구 호출 목록). tools 가 비면 도구 없이 답만 받는다 — 루프의 마지막 턴이 그렇게 쓴다."""
    if LOCAL_LLM_BASE_URL:
        return _tools_openai(messages, tools, temperature, model, timeout)
    return _tools_ollama(messages, tools, temperature, model, timeout)


def _tools_openai(messages, tools, temperature, model, timeout):
    body = {"model": model, "messages": [_openai_msg(m) for m in messages], "temperature": temperature,
            "max_tokens": MAX_TOKENS, "chat_template_kwargs": {"enable_thinking": False}}
    if tools:
        body["tools"] = tools
    r = httpx.post(f"{LOCAL_LLM_BASE_URL}/chat/completions", json=body, timeout=timeout)
    r.raise_for_status()
    m = r.json()["choices"][0]["message"]
    calls = []
    for tc in m.get("tool_calls") or []:
        fn = tc.get("function", {})
        calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), args=_args(fn.get("arguments"))))
    return (m.get("content") or ""), calls


def _tools_ollama(messages, tools, temperature, model, timeout):
    body = {"model": model, "messages": [_ollama_msg(m) for m in messages], "think": False, "stream": False,
            "options": {"temperature": temperature, "num_ctx": NUM_CTX, "num_predict": MAX_TOKENS}}
    if tools:
        body["tools"] = tools
    r = httpx.post("http://127.0.0.1:11434/api/chat", json=body, timeout=timeout)
    r.raise_for_status()
    m = r.json()["message"]
    calls = []
    for i, tc in enumerate(m.get("tool_calls") or []):
        fn = tc.get("function", {})
        calls.append(ToolCall(id=tc.get("id") or f"call_{i}", name=fn.get("name", ""), args=_args(fn.get("arguments"))))
    return (m.get("content") or ""), calls


def _args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def _openai_msg(m: dict) -> dict:
    if m["role"] == "tool":
        return {"role": "tool", "content": m["content"], "tool_call_id": m.get("id", "")}
    if m.get("calls"):
        return {"role": "assistant", "content": m.get("content", ""),
                "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.args, ensure_ascii=False)}} for c in m["calls"]]}
    return {"role": m["role"], "content": m.get("content", "")}


def _ollama_msg(m: dict) -> dict:
    if m["role"] == "tool":
        return {"role": "tool", "content": m["content"], "tool_name": m.get("name", "")}
    if m.get("calls"):
        return {"role": "assistant", "content": m.get("content", ""),
                "tool_calls": [{"function": {"name": c.name, "arguments": c.args}} for c in m["calls"]]}
    return {"role": m["role"], "content": m.get("content", "")}


_BYTE_TOKEN = re.compile(r"(?:<0x[0-9A-Fa-f]{2}>)+")


def sanitize(text: str) -> str:
    """모델이 한글 한 글자를 <0xEB><0x9D><0x95> 처럼 바이트 토큰으로 흘릴 때가 있다(gemma4:e4b 실측).
    화면에 그대로 나가면 글자가 깨져 보이므로 붙어 있는 바이트들을 모아 UTF-8 로 되돌린다. 못 되돌리면 지운다."""

    def fix(m: re.Match) -> str:
        raw = bytes(int(h, 16) for h in re.findall(r"<0x([0-9A-Fa-f]{2})>", m.group(0)))
        return raw.decode("utf-8", errors="ignore")

    return _BYTE_TOKEN.sub(fix, text)
