"""6단계 뜻 텍스트 언어판. 검증된 현행 뜻마다 ko·en MeaningText 를 만든다. 용어 원문은 번역하지 않는다.
기본은 Gemini(예산 안에서), USE_LOCAL_GEMMA=1 이고 Ollama 가 떠 있으면 로컬 Gemma."""
from __future__ import annotations

import sqlite3

from ..config import USE_LOCAL_GEMMA
from ..schemas import Meaning, MeaningText
from ..storage import dictionary_store as ds
from .gemini import BudgetExhausted, structured
from .runs import stage

LANG_NAME = {"ko": "Korean", "en": "English"}
PROMPT = """Rewrite this dictionary entry about the internet slang term "{term}" in {target}. Return JSON with keys definition, expansion, origin, nuance, plain.
Rules: never translate or transliterate the term "{term}" or other quoted slang. "expansion": keep the original spelled-out form and add a short {target} gloss in parentheses; null if there is none.
"plain": a short everyday {target} phrase that could replace the term (null if it is a pure exclamation). Do not add facts that are not in the entry.

definition: {definition}
expansion: {expansion}
origin: {origin}
nuance: {nuance}"""


def _entry(m: Meaning) -> dict:
    return {"definition": m.definition, "expansion": m.expansion, "origin": m.origin, "nuance": m.nuance}


def make_text(con: sqlite3.Connection, term: str, m: Meaning, target: str) -> tuple[MeaningText, str]:
    if USE_LOCAL_GEMMA:
        from ..interpreters import gemma_local, gemma_translate

        if gemma_local.is_available():
            base = MeaningText(**_entry(m))
            return gemma_translate.translate_meaning(base, term, target), "gemma-local"
    parsed, model = structured(con, PROMPT.format(term=term, target=LANG_NAME.get(target, target), **_entry(m)), MeaningText, temperature=0.2)
    return (parsed if isinstance(parsed, MeaningText) else MeaningText.model_validate(parsed)), model


def run(con: sqlite3.Connection, max_calls: int = 12) -> dict:
    with stage(con, "translate") as r:
        calls = 0
        for t in ds.list_terms(con, ("verified",)):
            m = ds.current_meaning(con, t.term_id)
            if not m or m.verification not in ("verified_auto", "verified_human"):
                continue
            for lang in ("ko", "en"):
                have = ds.get_translation(con, t.term_id, lang)
                if have:
                    continue
                if calls >= max_calls:
                    r.note = "이번 실행 한도"
                    break
                try:
                    text, model = make_text(con, t.canonical, m, lang)
                except BudgetExhausted as e:
                    r.note = str(e)
                    break
                except Exception as e:  # 한 항목의 형식 실패가 나머지를 막지 않는다
                    r.note += f"{t.canonical}/{lang}:{type(e).__name__} "
                    continue
                ds.set_translation(con, t.term_id, lang, text, model)
                calls += 1
                r.count += 1
    return {"translate": r}
