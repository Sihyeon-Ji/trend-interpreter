"""리서치 에이전트: 후보 용어의 뜻·유래를 Google Search grounding 으로 조사한다.

2단계로 나눈다 — (1) 검색 도구를 켠 자유 서술 호출에서 본문 + grounding 출처 URL 을 받고,
(2) 도구 없는 구조화 호출로 MeaningDraft JSON 으로 옮긴다. (도구 + JSON 모드 동시 사용 제약을 피함)
grounding: 월 5,000회 무료, 이후 $14/1,000.
"""
from __future__ import annotations

from typing import Any, Callable

from google.genai import types

from ..config import GEMINI_MAX_OUTPUT_TOKENS, GEMINI_MODEL
from .. import model_client
from ..schemas import MeaningDraft

RESEARCH_PROMPT = """'{term}' 라는 표현을 조사하라. 어느 언어·국가의 인터넷 유행어/밈/줄임말일 수 있다. 원어 표기와 로마자 표기를 모두 검색하라.
알아낼 것: (1) 뜻 (2) 줄임말이면 풀이 (3) 유래 — 어디서, 언제, 어떤 계기로 시작됐나 (4) 주로 쓰는 세대·커뮤니티·국가
(5) 뉘앙스와 사용 시 주의점 (6) 최근 뜻이나 쓰임이 바뀌었는지.
검색 결과에 없는 내용은 만들지 말고 '확인되지 않음' 이라고 적어라. 출처가 서로 다르게 말하면 둘 다 적어라."""

STRUCTURE_PROMPT = """아래 조사 메모를 JSON 으로 구조화하라. 메모에 없는 사실을 추가하지 마라.
self_confidence 는 메모의 출처 일치도와 구체성으로 0~1 로 매겨라.
is_expression 은 이 항목이 유행어·밈·줄임말·챌린지·노래 후렴처럼 '요즘 생겨나 퍼진 표현'이면 true, 상품·기관·인물·정책·일반 단어, 그리고 전통 구호·종교 기도문·명절 인사·오래된 관용구면 false.

용어: {term}
조사 메모:
{notes}"""


_client = model_client.client


def research_term(term: str, model: str = GEMINI_MODEL, charge: Callable[[str, Any], None] | None = None) -> tuple[MeaningDraft, list[str], str]:
    """(초안, 출처 URL 목록, 원본 조사 메모). charge(모델, 응답)는 호출마다 실제 사용량을 금액 장부에 더한다."""
    c = _client()
    r1 = c.models.generate_content(
        model=model,
        contents=RESEARCH_PROMPT.format(term=term),
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.2,
                                           max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS),
    )
    if charge:
        charge(model, r1)
    notes = r1.text or ""
    urls: list[str] = []
    gm = r1.candidates[0].grounding_metadata if r1.candidates else None
    for ch in (gm.grounding_chunks or []) if gm else []:
        if ch.web and ch.web.uri:
            urls.append(ch.web.uri)
    r2 = c.models.generate_content(
        model=model,
        contents=STRUCTURE_PROMPT.format(term=term, notes=notes),
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=MeaningDraft, temperature=0.1,
                                           max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS),
    )
    if charge:
        charge(model, r2)
    draft = r2.parsed if isinstance(r2.parsed, MeaningDraft) else MeaningDraft.model_validate(r2.parsed)
    return draft, urls, notes
