"""ADK 에이전트 팀으로 파이프라인을 돌린다 (모델이 도구 순서를 부르고 보고서를 쓴다).

사용: uv run scripts/run_agents.py            # 실행 + 운영 보고
      uv run scripts/run_agents.py --dry      # 에이전트·도구 구성만 출력 (모델 호출 없음)
      ADK_MODEL=gemini-3.5-flash uv run scripts/run_agents.py   # 3.8 할당량이 막혔을 때
      ADK_MODEL=local uv run scripts/run_agents.py              # 파이프라인과 같은 로컬 모델(Ollama/vLLM)로 — 예산 소모 없음
"""
from __future__ import annotations

import asyncio
import sys

from google.genai import types

from trend_agents.agents.team import MODEL_NAME, pipeline_agent


def dry() -> None:
    print(f"{pipeline_agent.name} (model {MODEL_NAME})")
    for a in pipeline_agent.sub_agents:
        names = [getattr(t, "__name__", getattr(t, "name", str(t))) for t in a.tools]  # type: ignore[attr-defined]
        print(f"  → {a.name:13} tools={names}")


async def main() -> None:
    from google.adk.runners import InMemoryRunner

    runner = InMemoryRunner(agent=pipeline_agent, app_name="trend-agents")
    session = await runner.session_service.create_session(app_name="trend-agents", user_id="ops")
    msg = types.Content(role="user", parts=[types.Part(text="Run today's pipeline and give me the operations report.")])
    async for ev in runner.run_async(user_id="ops", session_id=session.id, new_message=msg):
        author = getattr(ev, "author", "?")
        if ev.content and ev.content.parts:
            for p in ev.content.parts:
                if p.function_call:
                    print(f"[{author}] → {p.function_call.name}()")
                elif p.function_response:
                    r = p.function_response.response or {}
                    brief = {k: (v.get("count") if isinstance(v, dict) else v) for k, v in list(r.items())[:6]} if isinstance(r, dict) else r
                    print(f"[{author}] ← {p.function_response.name}: {brief}")
                elif p.text and ev.is_final_response():
                    print(f"\n[{author}]\n{p.text.strip()}\n")


if __name__ == "__main__":
    if "--dry" in sys.argv:
        dry()
    else:
        try:
            asyncio.run(main())
        except Exception as e:  # 무료 등급 할당량(모델당 하루 20회) 등 — 도구 결과는 이미 DB 에 남아 있다
            msg = str(e)
            print(f"[run_agents] 중단: {type(e).__name__}: {msg[:300]}")
            if "429" in msg:
                print("무료 등급은 모델당 하루 20회 한도입니다. 결제(Tier 1) 연결 후 다시 실행하세요. 파이프라인 단계 결과는 data/trend.db 에 그대로 남았습니다.")
            sys.exit(2)
