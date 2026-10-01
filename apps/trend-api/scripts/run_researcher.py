"""위키를 직접 읽는 ADK 조사 에이전트(도구는 MCP 서버)를 한 번 돌린다.
  ADK_MODEL=local uv run scripts/run_researcher.py "인도네시아에서 오징어 게임으로 생긴 밈 뭐 있어?"
"""
from __future__ import annotations

import asyncio
import sys

from google.genai import types

from trend_agents.agents.team import MODEL_NAME, meme_researcher


async def main(q: str) -> None:
    from google.adk.runners import InMemoryRunner

    agent = meme_researcher()
    runner = InMemoryRunner(agent=agent, app_name="trend-research")
    session = await runner.session_service.create_session(app_name="trend-research", user_id="ops")
    print(f"{agent.name} (model {MODEL_NAME})")
    async for ev in runner.run_async(user_id="ops", session_id=session.id, new_message=types.Content(role="user", parts=[types.Part(text=q)])):
        for p in (ev.content.parts if ev.content else []) or []:
            if p.function_call:
                print(f"→ {p.function_call.name}({dict(p.function_call.args or {})})")
            elif p.function_response:
                print(f"← {p.function_response.name}: {str(p.function_response.response)[:160]}")
            elif p.text and ev.is_final_response():
                print("\n" + p.text.strip())


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "인도네시아에서 오징어 게임으로 생긴 밈 뭐 있어?"))
