"""MCP 서버 (2026-10-01). 콘텐츠 조사 에이전트·사전에 묻기가 쓰는 도구를 MCP 로도 연다 —
ADK 에이전트(agents/team.py 의 McpToolset), Claude·Gemini CLI 같은 다른 에이전트가 같은 도구로 위키를 읽고 사전을 본다.

도구는 전부 읽기 전용이다. 웹은 허용한 위키(나무위키·위키백과·Know Your Meme·Fandom·Trend A Word)만 열고 본문은 저장하지 않는다.
사전에 무엇을 싣는지는 여기서 정하지 않는다(검증 게이트·사람 검수).
  uv run python -m trend_agents.mcp_server            # stdio
  uv run python -m trend_agents.mcp_server --http 8765 # streamable HTTP
"""
from __future__ import annotations

import sys

from mcp.server.mcpserver import MCPServer

from .pipeline import content_agent
from .pipeline import tools as T
from .pipeline import web_tools as W
from .storage import store as db

server = MCPServer("trend-agents", instructions="밈·유행어 사전과 허용된 위키를 읽는 도구. 사전에 없는 것은 위키 문서로 확인하고 출처 주소를 함께 말한다.")
_con = None


def _ctx() -> T.Ctx:
    global _con
    if _con is None:
        _con = db.connect()
    return T.Ctx(con=_con)


@server.tool()
def open_page(url: str, section: str = "", offset: int = 0) -> dict:
    """허용한 위키 문서 한 쪽(2,500자)을 연다. section 은 절 이름 일부, offset 은 이어 읽기. 절 목록·하위 문서·링크를 함께 준다."""
    return W.open_page(url, section, offset)


@server.tool()
def read_section(url: str, section: str) -> str:
    """문서의 절 하나를 끝까지 읽는다(최대 10,000자)."""
    return W.section_text(url, section) or f"'{section}' 절이 없다"


@server.tool()
def wiki_search(query: str, site: str = "wikipedia", lang: str = "ko") -> dict:
    """위키백과(lang 판) 검색 또는 나무위키 같은 이름 문서."""
    return W.search(site, query, lang)


@server.tool()
def kym_children(slug: str) -> dict:
    """Know Your Meme 갈래(subcultures/<slug>) 아래 밈 항목의 제목·주소."""
    return W.kym_children(slug)


@server.tool()
def lookup_term(term: str) -> str:
    """검증된 사전에서 표제어 하나 — 뜻·유래·근거 수·생애주기."""
    return T.lookup_term(_ctx(), {"term": term})


@server.tool()
def search_terms(query: str) -> str:
    """표제어·별칭·뜻에서 찾기."""
    return T.search_terms(_ctx(), {"query": query})


@server.tool()
def content_memes(content: str, region: str = "") -> str:
    """작품 하나에서 나라마다 파생된 밈(조사 에이전트가 위키를 읽고 규칙 확인을 거친 것)과 나라 사이 같은 밈 짝."""
    return T.content_memes(_ctx(), {"content": content, "region": region})


@server.tool()
def researched_contents() -> list[dict]:
    """밈을 조사해 둔 작품 목록."""
    return content_agent.contents(_ctx().con)


if __name__ == "__main__":
    if "--http" in sys.argv:
        server.run("streamable-http", port=int(sys.argv[sys.argv.index("--http") + 1]))
    else:
        server.run("stdio")
