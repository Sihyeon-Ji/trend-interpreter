"""Gemini 직결 에이전트 루프 (function calling). Claude/MCP 커넥터 사용 안 함.
실행: python agent/run.py "이번 주 지연 위험 있는 태스크를 찾고 원인과 확인 질문을 정리해줘"
필요: .env 의 GEMINI_API_KEY, JIRA_* (SETUP.md 1-1, 1-2)
"""

from __future__ import annotations

import json
import sys

from pmo_agent import llm
from pmo_agent.env import env
from pmo_agent.tools import DECLARATIONS, SYSTEM, dispatch

MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")
KEY = env("GEMINI_API_KEY")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
RETRIES = 4


def call_gemini(contents, tools=True):
    body = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "generationConfig": {"temperature": 0},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": DECLARATIONS}]
    return llm.generate(body)


def run(prompt: str, max_steps: int = 6, verbose=True):
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    calls_made = []
    for step in range(max_steps):
        resp = call_gemini(contents)
        cand = (resp.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        fcalls = [p["functionCall"] for p in parts if "functionCall" in p]
        texts = [p["text"] for p in parts if "text" in p]
        if fcalls:
            # 모델 파트를 '그대로' 되돌려 보낸다. Gemini 3.x 는 functionCall 에 붙은
            # thoughtSignature 를
            # 다음 턴에 그대로 요구한다 — functionCall 만 뽑아 재구성하면 400 (missing
            # thought_signature).
            contents.append({"role": "model", "parts": parts})
            responses = []
            for fc in fcalls:
                name, args = fc.get("name"), fc.get("args") or {}
                result = dispatch(name, args)
                calls_made.append({"tool": name, "args": args, "result_keys": list(result)[:6]})
                if verbose:
                    print(
                        f"  [{step}] → {name}({json.dumps(args, ensure_ascii=False)[:80]}) ⇒ "
                        f"{json.dumps(result, ensure_ascii=False)[:160]}"
                    )
                responses.append(
                    {"functionResponse": {"name": name, "response": {"result": result}}}
                )
            contents.append({"role": "user", "parts": responses})
            continue
        answer = "\n".join(texts).strip()
        return {"answer": answer, "steps": step, "tool_calls": calls_made}
    return {"answer": "(최대 단계 초과)", "steps": max_steps, "tool_calls": calls_made}


if __name__ == "__main__":
    q = (
        " ".join(sys.argv[1:])
        or "이번 주 지연 위험이 있는 태스크를 찾아 원인과 담당자에게 물을 확인 질문을 정리해줘."
    )
    out = run(q)
    print(
        "\n" + "=" * 70 + f"\n툴 호출 {len(out['tool_calls'])}회 / {out['steps']}단계\n" + "=" * 70
    )
    print(out["answer"])
    print(
        "\n(쓰기 제안은 전부 dry_run 입니다. 실제 반영은 승인 단계에서 approve=True 로 수행합니다.)"
    )
