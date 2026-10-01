"""ADK 에이전트 팀. 역할을 나눈 네 에이전트가 순서대로 도구(결정론 단계)를 부르고 보고서를 남긴다.

collector → investigator → lexicographer → publisher (SequentialAgent)
- 에이전트는 상태(verified 등)를 직접 쓰지 않는다. 도구가 규칙으로 정한 결과를 읽고 요약만 한다.
- 모든 모델 호출은 before_model_callback 에서 하루 예산을 차감한다(pipeline/gemini.py 와 같은 장부).
- 에이전트 자신의 모델은 기본 Gemini. `ADK_MODEL=local` 이면 파이프라인과 같은 로컬 모델을 LiteLLM 으로 쓴다
  (LOCAL_LLM_BASE_URL 있으면 OpenAI 호환 vLLM, 없으면 Ollama). Gemini 무료 등급(모델당 하루 20회)은 에이전트 한 바퀴(약 17회)로 소진된다.
"""
from __future__ import annotations

import os

from google.adk.agents import LlmAgent, SequentialAgent

from ..config import GCP_PROJECT_ID, GEMINI_DAILY_BUDGET, GEMINI_MODEL, GEMMA_LOCAL_MODEL, GOOGLE_CLOUD_LOCATION, LOCAL_LLM_BASE_URL
from ..model_client import requests_enabled
from ..storage import dictionary_store as ds
from . import tools

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
if GCP_PROJECT_ID:
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", GCP_PROJECT_ID)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", GOOGLE_CLOUD_LOCATION)
MODEL_NAME = os.getenv("ADK_MODEL", GEMINI_MODEL)
LOCAL = MODEL_NAME == "local"


def _model():
    if not LOCAL:
        return MODEL_NAME
    from google.adk.models.lite_llm import LiteLlm

    if LOCAL_LLM_BASE_URL:  # thinking 은 끈다 (interpreters/local_chat.py 와 같은 이유)
        return LiteLlm(model=f"openai/{GEMMA_LOCAL_MODEL}", api_base=LOCAL_LLM_BASE_URL, api_key="local",
                       extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    return LiteLlm(model=f"ollama_chat/{GEMMA_LOCAL_MODEL}", think=False)


MODEL = _model()


def _budget_guard(callback_context, llm_request):
    """모델 호출마다 예산 1 차감. 소진되면 모델을 부르지 않고 짧은 응답으로 대체한다. 로컬 모델은 예산이 없다."""
    if LOCAL:
        return None
    if not requests_enabled():
        from google.adk.models import LlmResponse
        from google.genai import types

        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Gemini requests are disabled.")]))
    con = tools._con
    if ds.gemini_budget_left(con, GEMINI_DAILY_BUDGET) <= 0:
        from google.adk.models import LlmResponse
        from google.genai import types

        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Gemini daily budget exhausted; tool results stand as the report.")]))
    ds.gemini_spend(con, 1)
    return None


COMMON = ("You are one agent in a pipeline that maintains a verified dictionary of slang and memes across generations and countries. "
          "Only call the tools you are given, in the order described, and report the numbers the tools return. Never invent counts, never claim a term is verified "
          "unless a tool says so, and keep the report under 120 words.")

collector = LlmAgent(
    name="collector", model=MODEL, description="Collects fresh signals from all sources and labels new search queries.",
    instruction=COMMON + " Steps: 1) run_collect 2) run_classify 3) pipeline_health. Report counts per source and any stage with status zero or warn.",
    tools=[tools.run_collect, tools.run_classify, tools.pipeline_health], output_key="collect_report", before_model_callback=_budget_guard,
)
investigator = LlmAgent(
    name="investigator", model=MODEL, description="Finds sudden surges and explains why they are trending, with anchored actors.",
    instruction=COMMON + " Step: run_spikes. Report which surges got an explanation (trigger, confidence, actors) and which lacked evidence.",
    tools=[tools.run_spikes], output_key="spike_report", before_model_callback=_budget_guard,
)
lexicographer = LlmAgent(
    name="lexicographer", model=MODEL, description="Grows the dictionary: interpret shorts, extract candidates, research, gate, track, translate.",
    instruction=COMMON + " Steps in order: run_interpret, run_candidates, run_research, run_track, run_naver, run_translate. "
                "Report how many terms were verified automatically vs sent to human review, and why the reviewed ones failed the gate.",
    tools=[tools.run_interpret, tools.run_candidates, tools.run_research, tools.run_track, tools.run_naver, tools.run_translate, tools.dictionary_lookup],
    output_key="dictionary_report", before_model_callback=_budget_guard,
)
publisher = LlmAgent(
    name="publisher", model=MODEL, description="Rebuilds the public board and writes the operations report for the admin.",
    instruction=COMMON + " Steps: run_board, then review_queue_summary. Then write the final operations report combining these earlier reports: "
                "{collect_report} | {spike_report} | {dictionary_report}. End with the list of items waiting for human review.",
    tools=[tools.run_board, tools.review_queue_summary], output_key="ops_report", before_model_callback=_budget_guard,
)

def _research_model():
    """조사 에이전트의 모델. 로컬이면 학습 서버의 Gemma(AUDIT_OLLAMA_HOST, 콘텐츠 조사 에이전트와 같은 곳) — 이 서버 GPU 는 여유가 적다."""
    if not LOCAL:
        return MODEL_NAME
    from google.adk.models.lite_llm import LiteLlm

    from ..config import AUDIT_OLLAMA_HOST, RESEARCH_MODEL

    if AUDIT_OLLAMA_HOST:
        return LiteLlm(model=f"ollama_chat/{RESEARCH_MODEL}", api_base=AUDIT_OLLAMA_HOST, think=False)
    return MODEL


def meme_researcher():
    """위키를 직접 읽는 조사 에이전트 — 도구는 MCP 서버(trend_agents.mcp_server)에서 받는다. 사전·조사 결과를 먼저 보고,
    없으면 허용한 위키 문서를 열어 절을 읽고 출처 주소와 함께 답한다. 사전에 쓰지는 않는다."""
    import sys

    from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
    from mcp import StdioServerParameters

    mcp = McpToolset(connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(command=sys.executable, args=["-m", "trend_agents.mcp_server"]), timeout=120))
    return LlmAgent(
        name="meme_researcher", model=_research_model(), description="Answers questions about memes derived from a show or film, reading allowed wikis directly.",
        instruction=("You research internet memes. First call content_memes or lookup_term. If the answer is not there, open the relevant wiki page "
                     "(namu.wiki for Korea, the local-language Wikipedia, Know Your Meme for English) with open_page, then read_section for the section about memes or impact. "
                     "Only state what the tools returned, cite the page URL for every claim, and answer in the user's language in under 120 words."),
        tools=[mcp], before_model_callback=_budget_guard)


pipeline_agent = SequentialAgent(name="trend_pipeline", description="Daily trend-dictionary pipeline: collect → investigate → lexicography → publish.",
                                 sub_agents=[collector, investigator, lexicographer, publisher])
