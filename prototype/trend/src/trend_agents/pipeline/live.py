"""실시간 찾아보기(live). 사전에 없는 말을 **그 자리에서** 몇 군데 찾아보고 대강의 뜻을 알려 준다.

왜 따로 두는가 — 사전(research)은 근거를 모으고 게이트를 거쳐 판을 남기는 느린 일이다(한 건에 수십 초).
채팅은 5초 안에 답해야 한다. 그래서 일을 둘로 가른다:

  지금 이 자리   여기(live). 빠른 출처 몇 곳만 동시에 훑어 '이런 말인 것 같다' 를 알려 준다. **검증 전**이라고 밝힌다.
  그다음        후보로 넘긴다. research 가 평소대로 근거를 모으고 게이트가 사전에 올릴지 정한다.

지키는 것은 사전과 같다. 찾아온 글에 그 말이 **실제로 들어 있어야** 쓰고, 읽은 곳을 함께 보여 주고,
여기서 만든 문장은 사전에 바로 들어가지 않는다 — 사전에 올리는 것은 게이트만 한다.
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ..schemas import Evidence
from ..storage import dictionary_store as ds
from .gemini import generate
from .match import mentions

TIMEOUT_S = 4.0        # 출처 하나가 늦으면 버린다. 채팅은 기다려 주지 않는다
MAX_SNIPPETS = 6

PROMPT = """아래는 '{term}' 에 대해 방금 인터넷에서 찾아온 글 조각이다. 이것만 보고 이 말이 무엇인지 한두 문장으로 알려 줘라.

- 조각에 없는 사실은 만들지 마라. 확실하지 않으면 "~인 것 같다" 로 적어라.
- 조각이 이 말을 설명하지 못하면 "무엇인지 알 수 없다" 한 문장만 답하라.
- 사전 뜻풀이처럼 딱딱하게 쓰지 말고, 아는 사람이 옆에서 알려 주듯 짧게.

조각:
{snippets}"""


@dataclass
class LiveResult:
    term: str
    summary: str = ""
    evidences: list[Evidence] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def found(self) -> bool:
        return bool(self.summary and self.evidences)


def _sources(term: str, lang: str) -> list:
    """빠른 것만. 느린 조사(위키 본문·네이버·유튜브)는 뒤쪽 research 가 맡는다."""
    from ..collectors import community, wikipedia_search, wiktionary

    def wiki(lg: str):
        sm = wikipedia_search.summary(lg, term)
        if not sm:
            titles = wikipedia_search.search(lg, term, limit=1)
            sm = wikipedia_search.summary(lg, titles[0]) if titles else None
        if not sm or not sm.get("extract"):
            return []
        from datetime import datetime, timezone

        return [Evidence(evidence_id=ds.new_id("e", sm.get("url") or sm["title"]), kind="wiki",
                         url=sm.get("url") or f"https://{lg}.wikipedia.org/wiki/{sm['title']}",
                         title=sm["title"][:200], source_domain="wikipedia.org",
                         observed_at=datetime.now(timezone.utc), excerpt=sm["extract"][:300])]

    return [lambda: wiki(lang), lambda: wiki("en") if lang != "en" else [],
            lambda: wiktionary.lookup(term, lang),
            lambda: community.lemmy_search(term, 5),
            lambda: community.bluesky_search(term, 5)]


def look_up(con: sqlite3.Connection, term: str, lang: str = "ko", deadline: float | None = None,
            say=None) -> LiveResult:
    """지금 찾아본다. 찾은 글에 그 말이 실제로 들어 있는 것만 쓴다. deadline 을 넘기면 있는 것만 가지고 끝낸다."""
    import time

    t0 = time.time()
    stop = deadline if deadline is not None else t0 + TIMEOUT_S
    got: list[Evidence] = []
    if say:
        say("live", f"사전에 없어서 지금 찾아보는 중: 위키백과 · 위키낱말사전 · Lemmy · 블루스카이")
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fn) for fn in _sources(term, lang)]
        for f in futures:
            left = min(stop, t0 + TIMEOUT_S) - time.time()   # 남은 시간만큼만
            try:
                got += f.result(timeout=max(0.2, left)) or []
            except Exception:
                continue

    keep = [e for e in got if mentions(f"{e.title} {e.excerpt}", term)][:MAX_SNIPPETS]
    if not keep:
        return LiveResult(term=term, seconds=time.time() - t0)

    if say:
        say("live", f"{len(keep)}곳에서 찾았다 — 읽고 정리하는 중")
    snippets = "\n".join(f"- [{e.source_domain}] {(e.excerpt or e.title)[:220]}" for e in keep)
    try:
        summary = (generate(con, PROMPT.format(term=term, snippets=snippets))[0].text or "").strip()
    except Exception:
        summary = ""
    if "알 수 없다" in summary:
        summary = ""
    return LiveResult(term=term, summary=summary[:400], evidences=keep, seconds=time.time() - t0)


def queue_for_research(con: sqlite3.Connection, term: str, lang: str, alias: str = "") -> None:
    """뒤에서 제대로 조사하도록 후보로 넘긴다. 사전에 올릴지는 게이트가 정한다."""
    if ds.find_term(con, term):
        return
    note = "kind=slang demand=live" + (f" alias={alias}" if alias else "")
    ds.upsert_candidate(con, term, lang, None, "hunt", note=note)
