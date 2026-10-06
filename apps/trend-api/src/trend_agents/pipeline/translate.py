"""6단계 뜻 텍스트 언어판. 검증된 현행 뜻마다 ko·en MeaningText 를 만든다. 용어 원문은 번역하지 않는다.
기본은 Gemini(예산 안에서), USE_LOCAL_GEMMA=1 이고 Ollama 가 떠 있으면 로컬 Gemma."""
from __future__ import annotations

import time

from ..config import GEMMA_LOCAL_MODEL, USE_LOCAL_GEMMA
from ..schemas import Meaning, MeaningText
from ..storage import dictionary_store as ds
from .gemini import BudgetExhausted, structured
from .runs import record_model, stage
from . import dashboard
from ..storage.db import Connection

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


def make_text(con: Connection, term: str, m: Meaning, target: str) -> tuple[MeaningText, str]:
    if USE_LOCAL_GEMMA:
        from ..interpreters import gemma_local, gemma_translate

        if gemma_local.is_available():
            base = MeaningText(**_entry(m))
            # 실제 모델 ID 를 gemini.generate 와 같은 꼴(local:<모델>)로 — 예전 'gemma-local' 은 어느 모델이 썼는지 남지 않았다(Plan 06 완료 기준 1)
            t0 = time.time()
            text, model = gemma_translate.translate_meaning(base, term, target, model=GEMMA_LOCAL_MODEL), f"local:{GEMMA_LOCAL_MODEL}"
            record_model(model, time.time() - t0)
            return text, model
    parsed, model = structured(con, PROMPT.format(term=term, target=LANG_NAME.get(target, target), **_entry(m)), MeaningText, temperature=0.2)
    return (parsed if isinstance(parsed, MeaningText) else MeaningText.model_validate(parsed)), model


def priority(con: Connection) -> list:
    """번역할 순서 — 대시보드 목록(지역마다 지금 쓰이는·주의·식어 가는 순)에 앞서 보이는 말부터, 나머지는 이름순.
    이름순으로 한 번에 12개씩만 하던 탓에 영어 화면 첫 쪽 뜻풀이의 75~85% 가 한국어 그대로였다(실데이터 10-04, 영어판 121개)."""
    terms = ds.list_terms(con, ("verified",))
    rank: dict[str, int] = {}
    loaded = dashboard._load(con)
    if loaded:
        shown = [s for s in loaded[0] if not s.held]
        for region in (*dashboard.REGIONS_FOCUS, dashboard.GLOBAL):
            rising, fading, caution = dashboard.split([dashboard.view(s, [region]) for s in shown if region in s.card.regions], loaded[1])
            for i, c in enumerate([*rising, *caution, *fading]):
                rank[c.term_id] = min(rank.get(c.term_id, i), i)
    last = len(terms) + len(rank)
    return sorted(terms, key=lambda t: (rank.get(t.term_id, last), t.canonical))


def run(con: Connection, max_calls: int = 12) -> dict:
    with stage(con, "translate") as r:
        calls = 0
        for t in priority(con):
            if calls >= max_calls:                         # 한도에 닿으면 남은 용어를 더 돌지 않는다
                r.note = "이번 실행 한도"
                break
            m = ds.current_meaning(con, t.term_id)
            if not m or m.verification not in ("verified_auto", "verified_human"):
                continue
            for lang in ("en", "ko"):                       # 영어 먼저 — 한국어 화면은 한국어 원문 뜻으로도 읽힌다
                have = ds.get_translation(con, t.term_id, lang)
                if have:
                    continue
                if calls >= max_calls:
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
