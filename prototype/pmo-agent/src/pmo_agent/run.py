"""The agent loop, talking straight to Gemini (function calling). No Claude/MCP connector.

Run: python -m pmo_agent.run "find the tasks at risk of slipping this week"
Needs: GEMINI_API_KEY and JIRA_* in .env (SETUP.md 1-1, 1-2)
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
            # Echo the model's parts back *verbatim*. Gemini 3.x requires the
            # thoughtSignature attached to a functionCall to come back on the
            # next turn — rebuilding from functionCall alone answers 400 (missing
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
    return {"answer": "(step limit reached)", "steps": max_steps, "tool_calls": calls_made}


if __name__ == "__main__":
    q = (
        " ".join(sys.argv[1:])
        or "Find the tasks at risk of slipping this week, why, and what to ask their owners."
    )
    out = run(q)
    print(
        "\n"
        + "=" * 70
        + f"\n{len(out['tool_calls'])} tool calls / {out['steps']} steps\n"
        + "=" * 70
    )
    print(out["answer"])
    print("\n(Every write proposal is a dry run. Applying one needs approve=True at the gate.)")
