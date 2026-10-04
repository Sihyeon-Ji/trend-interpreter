"""메시지 해석 API 의 서버 쪽: 사전 매칭(규칙) + '쉽게 풀어 쓰면' 재작성(모델). 프론트 lib/explain.ts 의 termPattern 과 같은 규칙."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from ..config import USE_LOCAL_GEMMA
from ..schemas import Term
from ..storage import db
from ..storage import dictionary_store as ds
from .gemini import BudgetExhausted, generate
from .match import term_pattern, text_pattern  # noqa: F401  (tests 와 다른 단계가 여기서 가져간다)
from ..storage.db import Connection

def match_terms(text: str, terms: list[Term]) -> list[Term]:
    hits: list[tuple[int, Term]] = []
    for t in terms:
        best = None
        for cand in [t.canonical, *t.aliases]:
            m = text_pattern(cand).search(text)
            if m and (best is None or m.start() < best):
                best = m.start()
        if best is not None:
            hits.append((best, t))
    hits.sort(key=lambda x: x[0])
    return [t for _, t in hits]


REWRITE = """Rewrite the message below in plain everyday {lang} so someone who does not know these slang terms understands it.{audience} Keep the tone, length and emoji. Replace each slang term with what it means in context, as natural speech — do not paste dictionary definitions, do not add explanations or quotes. Return only the rewritten message.

Glossary:
{glossary}

Message:
{text}"""


REWRITE_TIMEOUT_S = 12  # 로컬 Gemma 가 파이프라인 배치에 밀려 있으면 재작성 없이 매칭 결과만 돌려준다 — 화면이 몇 분씩 멈추지 않게
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rewrite")


def _generate_apart(prompt: str):
    """작업 스레드에는 요청 맥락이 없어 요청 연결(api._con)을 쓸 수 없다. 맥락을 복사해 넘겨도 시간 초과로 요청이 먼저 끝나면 그 연결은
    풀에 돌아가 다른 요청이 쓴다. 그래서 /ask/stream 처럼 풀에서 따로 빌린다 — 풀이 차 있으면 기다리는 사이 요청이 먼저 끝나 매칭 결과만 나간다.
    전에는 요청 연결을 넘겨 장부를 읽기도 전에 RuntimeError 가 났고, 그 오류를 삼켜 API 에서 재작성이 늘 비었다(호출 0회)."""
    with db.session() as con:
        return generate(con, prompt)


def rewrite(text: str, lang: str, glossary: list[tuple[str, str]], reader: dict | None = None, timeout_s: float = REWRITE_TIMEOUT_S) -> str | None:
    if not glossary:
        return None
    g = "\n".join(f"- {t}: {m}" for t, m in glossary)
    if USE_LOCAL_GEMMA:
        from ..interpreters import gemma_local, gemma_rewrite

        if gemma_local.is_available():
            fut = _pool.submit(gemma_rewrite.rewrite_plain, text, [gemma_rewrite.GlossaryItem(term=t, meaning=m) for t, m in glossary], lang)
            try:
                return fut.result(timeout=timeout_s)
            except (FutureTimeout, Exception):  # 시간 초과·형식 실패 — Gemini 로 넘기지 않는다(generate 도 로컬로 가서 수 분 막힌다). 매칭 결과만 돌려준다
                return None
    aud = ""
    if reader and (reader.get("gen") or reader.get("region")):
        aud = f" The reader is in their {reader.get('gen') or 'unknown age'} and lives in {reader.get('region') or 'an unknown country'}; choose comparisons they would know."
    fut = _pool.submit(_generate_apart, REWRITE.format(lang={"ko": "Korean", "en": "English"}.get(lang, lang), glossary=g, text=text, audience=aud))
    try:
        resp, _ = fut.result(timeout=timeout_s)
        return (resp.text or "").strip() or None
    except (BudgetExhausted, FutureTimeout, Exception):
        return None


def explain(con: Connection, text: str, lang: str, reader: dict | None = None) -> tuple[list[str], str | None]:
    key_lang = lang + (f"|{reader.get('gen','')}|{reader.get('region','')}" if reader else "")  # 읽는 사람이 다르면 재작성도 다르다
    cached = ds.explain_cache_get(con, key_lang, text)
    if cached:
        return cached
    terms = match_terms(text, ds.list_terms(con, ("verified", "needs_review")))
    glossary = []
    for t in terms:
        tr = ds.get_translation(con, t.term_id, lang)
        m = ds.current_meaning(con, t.term_id)
        meaning = (tr.plain or tr.definition) if tr else (m.definition if m else "")
        if meaning and t.status == "verified":
            glossary.append((t.canonical, meaning))
    plain = rewrite(text, lang, glossary, reader)
    ids = [t.term_id for t in terms]
    if not terms:
        ds.log_lookup_miss(con, text, lang)  # 사전에 없는 표현일 수 있다 → 발굴(spot) 단계 재료
    if plain is not None or not glossary:  # 시간 초과로 재작성이 빠진 답은 캐시하지 않는다 — 다음엔 다시 시도
        ds.explain_cache_set(con, key_lang, text, ids, plain)
    return ids, plain
