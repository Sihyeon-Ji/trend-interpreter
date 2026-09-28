"""사전 뜻 번역 (로컬 Gemma, 호출은 local_chat). 용어 원문은 그대로 두고 뜻·유래·뉘앙스·쉬운 표현만 대상 언어로.

- 화면 문구는 사전식 고정 번역(apps/trend-web/lib/i18n.ts), 유행어 자체는 항상 원문. 이 모듈은 그 사이의 '설명 텍스트'만 맡는다.
- 번역은 저장 시점에 언어별로 만들어 두고(Meaning 에 translations 컬럼 예정), 요청마다 돌리지 않는다.
"""
from __future__ import annotations

from ..config import GEMMA_LOCAL_MODEL
from ..schemas import MeaningText
from . import local_chat

LANG_NAME = {"ko": "Korean", "en": "English", "ja": "Japanese", "th": "Thai", "id": "Indonesian", "vi": "Vietnamese"}

PROMPT = """Translate this dictionary entry into {target}. Every field you return must be written in {target}.
Do NOT copy the entry back unchanged — that is the most common failure and it is wrong.
Rules:
- The term itself, "{term}", must stay exactly as written (do not translate or transliterate it). Same for any other slang terms quoted inside the text.
- "expansion": if the entry has one, you MUST return it (never null): the original spelled-out form exactly as given, then " — ", then a short {target} gloss in quotes (e.g. "자연스러운 만남 추구 — 'seeking natural encounters'"). Only if the entry's expansion is null, return null.
- Translate meaning, origin and nuance naturally for a {target} reader. Keep names, years and platforms accurate.
- "plain" is a short everyday {target} phrase a reader could use instead of the term. Keep null if the term has no real meaning (pure exclamation).
- Return JSON only.

Entry:
{entry}"""


# 대상 언어로 쓰였는지 확인하는 글자 범위. 작은 모델이 입력을 그대로 돌려보내는 일이 잦다(2026-09-16 실측:
# 일본어 뜻 9건이 번역 없이 그대로 저장됐다). 돌려받은 글이 대상 언어 글자를 담고 있는지 보고, 아니면 한 번 더 시킨다.
SCRIPT = {"ko": "\uac00-\ud7a3", "ja": "\u3041-\u309f\u30a0-\u30ff", "th": "\u0e00-\u0e7f"}


def _in_target(text: str, target: str) -> bool:
    import re

    rng = SCRIPT.get(target)
    if rng:
        return bool(re.search(f"[{rng}]", text))
    return bool(re.search(r"[A-Za-z]", text))       # en 등 로마자


def translate_meaning(text: MeaningText, term: str, target: str, model: str = GEMMA_LOCAL_MODEL) -> MeaningText:
    prompt = PROMPT.format(target=LANG_NAME.get(target, target), term=term, entry=text.model_dump_json(indent=2))
    out = local_chat.structured(prompt, MeaningText, temperature=0.1, model=model)
    if _in_target(out.definition or "", target):
        return out
    # 그대로 돌려줬다 — 표제어 규칙을 빼고 뜻 한 줄만 다시 시킨다
    retry = (f"Translate the following sentence into {LANG_NAME.get(target, target)}. "
             f"Answer with the translated sentence only, nothing else.\n\n{text.definition}")
    again = local_chat.chat_text(retry, temperature=0.1).strip().splitlines()
    line = next((x.strip() for x in again if x.strip()), "")
    if line and _in_target(line, target):
        out.definition = line[:600]
    return out
