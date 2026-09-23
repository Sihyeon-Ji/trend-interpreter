"""수요 기반 조사(hunt). **사람이 물었는데 사전에 없던 말**을 표제어로 만들어 조사 대상에 올린다.

왜 필요한가 — 지금 파이프라인은 '밀어내기' 뿐이다. 수집기가 지금 뜨는 것을 긁어오고, 거기 없으면 사전에
영영 들어오지 못한다. "에스프레쏘 어쌔씨노" 를 아홉 번 물어도 없는 이유다(2026-09-16 실측, lookups).
여기서는 반대로 '당겨온다': 못 답한 질문에서 물어본 표현을 뽑아 표제어로 세우면,
research 가 평소대로 위키백과·위키낱말사전·커뮤니티를 **그 이름으로 직접 뒤져** 근거와 뜻을 만든다.

발굴(spot)과 다르다. spot 은 남이 쓴 글에서 '뜻을 찾아볼 만한 말' 을 알아보는 일이고,
hunt 는 '우리 이용자가 이미 물어봤는데 우리가 못 답한 말' 을 좇는 일이다. 수요가 근거다.

한글로 소리 나는 대로 적은 외래어는 원어 표기를 함께 받는다 — 인터넷 자료는 원어로 적혀 있어서
"에스프레쏘 어쌔씨노" 로는 아무것도 못 찾는다. 원어를 표제어로, 한글 표기를 별칭으로 둔다.
"""
from __future__ import annotations

import sqlite3

import re

from ..schemas import DemandedTerm
from ..storage import dictionary_store as ds
from .gemini import structured
from .runs import stage

MAX_NEW = 8          # 한 번에 세울 표제어 수
MIN_ASKED = 1        # 몇 번 물어야 좇을지

PROMPT = """아래는 우리 사전이 답하지 못한 이용자 질문이다. 각 줄에서 **이용자가 뜻을 물은 표현**을 뽑아라.

term: 물어본 표현만 줄 안에 적힌 그대로. 질문 말투("뭐야", "알려줘", "이런건")와 조사만 뗀다.
  특정 표현을 묻는 줄이 아니면(목록 요청, 인사, 앞을 받는 말) term 을 빈 문자열로 둔다.
original: 그 표현이 한글로 소리 나는 대로 적은 외래어라면 원어 표기. 한국어 고유 표현이면 null.
  예: "에스프레쏘 어쌔씨노" -> "Espresso Assassino", "퉁퉁퉁 사후르" -> "Tung Tung Tung Sahur", "느좋" -> null
lang: term 의 ISO 639-1. kind: slang | meme | song | challenge (모르면 slang)

줄마다 하나씩, 줄 번호(i)를 그대로 달아라.

줄:
{items}"""

# 목록을 달라는 질문. 여기서 뽑아낸 조각("20대가 쓰는 말", "최신 밈들")은 표제어가 아니라 질문의 일부다.
_LIST_ASK = re.compile(r"정리해\s*줘|목록|리스트|뭐가\s*(떠|뜨|유행|인기)|뭐\s*떠|어떤\s*것들|"
                       r"들\s*(알려|보여|정리)|사용하는\s*(거|것|말|사전)|쓰는\s*(말|거|것)")
# 표현이 아니라 갈래를 가리키는 낱말. 표제어 안에 하나라도 들어 있으면 이름이 아니다.
_GENERIC_TOKEN = re.compile(r"밈|유행어|슬랭|속어|사전|신조어|챌린지|캐릭터|노래|단어|표현|\bmeme\b|\bslang\b|\btrend\b")
# 질문의 서술부가 딸려 온 것 — "뭐가 떠", "20대가 쓰는", "AI생성으로 만든"
_PREDICATE = re.compile(r"(뭐가|무엇이|어떤)\s|하는\s|쓰는\s|만든\s|사용|유행이|뜨고|떠$|뜨$")
# 자판을 죽 눌러 본 것 — "zxcvbn", "asdfzxcv". 조사해 봐야 근거가 없어 시간만 쓴다.
_MASH = re.compile(r"^[a-z]{4,}$", re.I)
_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890")
# 뜻을 묻는 게 아니라 문장을 풀어 달라는 부탁. 그 문장은 표제어가 아니다.
_TRANSLATE_ASK = re.compile(r"해석|번역|풀어\s*(써|줘)|무슨\s*뜻이야\s*이\s*문장|translate", re.I)
MAX_WORDS = 4


def _is_mash(term: str) -> bool:
    t = term.lower()
    return bool(_MASH.match(t)) and any(t in row or t in row[::-1] for row in _ROWS)


def _norm(s: str) -> str:
    return "".join((s or "").split()).lower()


def _known(con: sqlite3.Connection, name: str) -> bool:
    """사전에 이미 있는가. 반복·된소리를 무시하는 느슨한 대조까지 쓴다 —
    "Tung Tung Tung Tung Tung Sahur" 는 "Tung Tung Tung Sahur" 와 같은 말이다."""
    from .tools import _find

    return _find(con, name) is not None


def run(con: sqlite3.Connection, max_new: int = MAX_NEW) -> dict:
    with stage(con, "hunt") as r:
        rows = [(k, t, lg) for k, t, lg in ds.pending_lookups(con, 40)]
        if not rows:
            r.status = "zero"
            r.note = "못 답한 질문 없음"
            return {"hunt": r}

        items = "\n".join(f"{i}. {t}" for i, (_, t, _) in enumerate(rows, 1))
        parsed = structured(con, PROMPT.format(items=items), list[DemandedTerm])[0]
        found = parsed if isinstance(parsed, list) else [parsed]

        made, skipped, seen = [], 0, set()
        for d in found:
            if not (1 <= d.i <= len(rows)):
                continue
            key, question, _ = rows[d.i - 1]
            term = (d.term or "").strip()
            # 판정은 코드가 한다. 모델이 지어낸 설명("라마단 새벽밥 알리는 나무 통 캐릭터 밈")을 표제어로
            # 세우지 않도록, **질문 원문에 실제로 있는 말**만 받는다 (이 저장소의 앵커 규칙과 같다).
            if not term or _norm(term) not in _norm(question):
                continue
            if len(term) < 2 or _GENERIC_TOKEN.search(term) or _PREDICATE.search(term):
                continue
            if _is_mash(term) or len(term.split()) > MAX_WORDS:
                continue
            if _TRANSLATE_ASK.search(question) or _LIST_ASK.search(question):
                ds.delete_lookups(con, [key])   # 목록 요청은 표제어 수요가 아니다 — 소비만 하고 넘긴다
                continue
            name = (d.original or term).strip()
            alias = term if d.original and _norm(term) != _norm(name) else ""
            if not name or len(name) > 60:
                continue
            if _known(con, name) or (alias and _known(con, alias)) or _norm(name) in seen:
                seen.add(_norm(name))
                ds.delete_lookups(con, [key])     # 이미 사전에 있다 — 질문은 소비됐다
                skipped += 1
                continue
            seen.add(_norm(name))
            note = f"kind={d.kind if d.kind != 'none' else 'slang'} demand=hunt" + (f" alias={alias}" if alias else "")
            ds.upsert_candidate(con, name, d.lang or "en", None, "hunt", note=note)
            ds.delete_lookups(con, [key])
            made.append(name)
            if len(made) >= max_new:
                break

        r.count = len(made)
        r.detail = {"세운 표제어": made, "이미 있던 것": skipped, "본 질문": len(rows)}
        if not made:
            r.status = "zero"
            r.note = "좇을 표현 없음"
    return {"hunt": r}
