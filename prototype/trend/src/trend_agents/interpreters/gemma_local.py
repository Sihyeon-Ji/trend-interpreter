"""로컬 Gemma 4 — 텍스트 한 조각의 세대 판정. 쿼터·비용이 없는 단계에 쓴다. 호출·백엔드 선택은 local_chat.

역할 후보:
- 텍스트 한 조각의 세대 판정 (붙여넣은 메시지 → 어느 세대 표현인가)
- 수집 아이템 1차 분류·중복 제거 (Gemini 로 보내기 전 필터 → 쿼터 절약)
- 사용자가 붙여넣은 대화의 개인정보 마스킹 (온디바이스에서 처리 후 클라우드로 = 'why Gemma')
"""
from __future__ import annotations

from ..config import GEMMA_LOCAL_MODEL
from ..schemas import GenerationRead
from . import local_chat

READ_PROMPT = """다음 텍스트(어느 언어든 가능)를 읽고 JSON 으로 답하라. 설명은 한국어로 쓰되 원어 표현은 그대로 남겨라.
- detected_generation: 이 표현을 주로 쓰는 세대 (10s / 20s / 30s / 40s / 50s+ / all 중 하나)
- slang_terms: 텍스트 안의 유행어·줄임말·밈 표현 목록 (원문 그대로)
- plain_explanation: 그 세대가 아닌 사람에게 뜻과 뉘앙스를 2~3문장으로 설명
- confidence: 0~1
모르는 표현은 지어내지 말고 confidence 를 낮춰라.

텍스트: {text}"""


def is_available(model: str = GEMMA_LOCAL_MODEL) -> bool:
    return local_chat.available(model)


def read_generation(text: str, model: str = GEMMA_LOCAL_MODEL) -> GenerationRead:
    return local_chat.structured(READ_PROMPT.format(text=text), GenerationRead, temperature=0.1, model=model)
