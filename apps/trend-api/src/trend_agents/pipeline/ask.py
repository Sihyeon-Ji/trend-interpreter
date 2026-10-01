"""사전에 묻는 질문 응답 루프. MCTI 의 `lib/orchestration/query-loop.ts` 패턴을 옮겨 왔다.

자유 대화 챗봇이 아니다. 모델은 **검증된 사전과 지식그래프를 도구로만** 읽고, 도구가 돌려준 것 밖의 이야기는 하지 않는다.
사전에 없으면 모른다고 답하고 그 질문은 `lookups` 에 쌓여 발굴(spot) 단계의 재료가 된다 — 답하지 못한 질문이 다음 사전 항목이 된다.

MCTI 에서 가져온 것: 턴 루프(마지막 턴은 도구 없이 답을 강제), 연속 실패 차단기, 전체 시간 예산,
잘못된 도구 인자는 실행하지 않고 오류를 모델에 되돌려 주기. (query-loop.ts 주석: 빈 인자로 실행하면 질문과 무관한 결과가 근거로 들어간다)
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from ..interpreters import local_chat
from ..storage import dictionary_store as ds
from . import tools as T
from ..storage.db import Connection

MAX_TURNS = 4
LIVE_BUDGET_S = 8.0   # 사전에 없는 말을 지금 찾아보는 데 쓰는 전체 시간 (후보 여러 개를 합쳐서)
TOTAL_TIMEOUT_S = 90.0
BREAKER_TRIP = 3          # 모델 호출이 연속 이만큼 실패하면 이 실행에서는 더 묻지 않는다
_fails = 0

SYSTEM = """너는 검증된 유행어 사전의 안내자다. 사람들이 유행어·밈·나라별 트렌드를 물으면 답한다.

**물어본 것에만 답한다.** 도구가 돌려준 내용을 다 옮기지 말고, 질문에 해당하는 부분만 골라 쓴다.
- "무슨 뜻이야" → 뜻. 유래는 뜻을 이해하는 데 필요할 때만 한 문장.
- "누가 써 / 어느 세대" → term_usage 를 부르고 세대·나라로 답한다.
- "왜 떠 / 왜 뜨는 거야" → why_trending 을 부르고 계기와 관련 인물로 답한다.
- "어디서 왔어 / 유래" → 유래.
- "요즘 ○○에서 뭐 떠" → country_trends (검색어다, 유행어가 아니다).
- "20대가 쓰는 말 / 한국 유행어 / 요즘 밈 정리해줘" 처럼 목록을 물으면 → **list_terms**. 하나를 콕 집지 않는 질문에 "구체적인 단어를 말해 달라" 고 되묻지 마라.
- 이름을 모르고 뜻만 설명하면 → search_terms 에 그 설명을 그대로 넘긴다.
- **한글로 적은 외래어 이름이 안 나오면 원어 표기로 한 번 더 찾아라.** "에스프레쏘 어쌔씨노" → "Espresso Assassino",
  "발레리나 카푸치나" → "Ballerina Cappuccina". 사람이 소리 나는 대로 적었을 뿐이지 사전에는 원어로 올라 있을 수 있다.
- 그래도 없으면 같은 계열을 찾아 준다. 이탈리안 브레인로트 계열 이름이면 search_terms 에 "이탈리안 브레인로트" 를 넣어
  같은 계열 표제어를 보여 주고, 물어본 그 이름은 아직 사전에 없다고 밝힌다. 되묻지 말고 이만큼은 해 줘라.
- "비슷한 것도 없어?", "그럼 저건?" 처럼 앞을 받는 말이면 바로 앞 대화에서 무엇을 말하는지 찾아 그 말로 도구를 부른다. 되묻지 마라. 결과의 '가장 가까운 것' 이 답이다 — 그것을 알려 주고 확인을 구한다.

지켜야 할 것:
- 도구가 돌려준 내용만 말한다. 도구에 없는 뜻·유래·숫자를 지어내지 않는다.
- lookup_term 이 "정확히 같은 표제어는 없습니다" 라며 비슷한 것을 주면, 그 이름으로 한 번 더 찾아본 뒤 답한다.
- 그래도 없으면 "사전에 아직 없습니다" 라고 분명히 말한다. 추측하지 않는다.
- 근거는 표제어 이름과 근거 건수로 적는다. 도구 이름(lookup_term 같은 것)은 적지 않는다.
- 한국어로, 군더더기 없이 3문장 안에. 유행어 원문은 번역하지 않고 그대로 쓴다."""


def _tool(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc,
                                             "parameters": {"type": "object", "properties": props, "required": required}}}


TOOLS = [
    _tool("lookup_term", "검증된 사전에서 표제어 하나를 찾아 뜻·유래·뉘앙스·근거 수·생애주기를 돌려준다",
          {"term": {"type": "string", "description": "찾을 표현 (조사 없이)"}}, ["term"]),
    _tool("search_terms", "표제어·별칭·뜻에서 말을 찾아 후보 목록을 돌려준다. 정확한 표제어를 모를 때 먼저 쓴다",
          {"query": {"type": "string"}}, ["query"]),
    _tool("why_trending", "어떤 검색어가 특정 나라에서 왜 지금 뜨는지 — 계기·관련 인물·근거 수",
          {"term": {"type": "string"}, "region": {"type": "string", "description": "ISO 2글자 국가코드, 예: KR"}}, ["term"]),
    _tool("country_trends", "한 나라에서 지금 뜨는 것들",
          {"region": {"type": "string", "description": "ISO 2글자 국가코드"}}, ["region"]),
    _tool("term_usage", "이 표현을 어느 세대·어느 나라가 쓰는지, 최근 언급 추세가 오르는지",
          {"term": {"type": "string"}}, ["term"]),
    _tool("list_terms", "사전 표제어를 조건으로 둘러본다. '20대가 쓰는 말', '한국 유행어', '요즘 밈' 처럼 하나를 콕 집지 않는 질문은 이 도구로 답한다",
          {"generation": {"type": "string", "enum": ["10s", "20s", "30s", "40s", "50s+"]},
           "region": {"type": "string", "description": "ISO 2글자 국가코드, 예: KR"},
           "category": {"type": "string", "enum": ["slang_meme", "song_challenge", "fashion_beauty", "food", "product", "people_content"]}}, []),
    _tool("content_memes", "드라마·영화·게임 같은 작품 하나에서 나라마다 파생된 밈과, 나라마다 이름이 다른 같은 밈. '오징어 게임 밈 뭐 있어?' 같은 질문",
          {"content": {"type": "string", "description": "작품 이름(어느 말로든)"},
           "region": {"type": "string", "description": "ISO 2글자 국가코드(선택)"}}, ["content"]),
    _tool("read_web", "사전·조사 결과에 없을 때만: 나무위키·위키백과·Know Your Meme 문서를 직접 열어 읽는다. 읽은 내용은 '위키 문서에 따르면' 으로 밝힌다",
          {"title": {"type": "string", "description": "문서 제목"}, "site": {"type": "string", "enum": ["namu", "wikipedia", "kym"]},
           "lang": {"type": "string", "description": "위키백과 언어 코드(ko·en·ja…)"}, "section": {"type": "string", "description": "읽을 절 이름(선택)"}},
          ["title"]),
]


@dataclass
class Answer:
    text: str
    used: list[str] = field(default_factory=list)      # 부른 도구 이름
    term_ids: list[str] = field(default_factory=list)  # 답의 근거가 된 표제어
    turns: int = 0
    seconds: float = 0.0
    fallback: str | None = None                        # 루프를 못 돌린 이유
    cards: list[dict] = field(default_factory=list)    # 화면이 그리는 조각 (표제어·목록·비중·트렌드)


_TOOL_CITE = None  # 아래에서 도구 이름으로 만든다


# 도구가 모델에게 준 지시("이 목록에 있는 이름만 말하라")를 모델이 그대로 답에 옮겨 적는다(09-16 실측).
_GUARD_LEAK = re.compile(r"[^.!?\n]*(지어내지|목록에 있는 이름만|사전에 없다고만 답)[^.!?\n]*[.!?]?")
# 화면은 평문이라 마크다운 강조가 별표 그대로 보인다. 모델에게 쓰지 말라고 하고, 그래도 쓰면 여기서 뗀다.
_MD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", re.S)


def _tidy(text: str) -> str:
    """작은 모델이 근거로 도구 이름을 적는다("(근거: term_usage)"). 사람에게는 뜻 없는 말이라 지운다.
    도구에 적어 둔 지시문이 답에 섞여 나오는 것도 함께 지운다."""
    global _TOOL_CITE
    if _TOOL_CITE is None:      # 모듈 맨 위의 re 를 쓴다 — 여기서 import 하면 함수 안의 re 를 가려 버린다
        names = "|".join(t["function"]["name"] for t in TOOLS)
        _TOOL_CITE = re.compile(rf"\s*[（(][^)）]*(?:{names})[^)）]*[)）]\s*$")
    out = _GUARD_LEAK.sub("", _TOOL_CITE.sub("", text))
    if _TOOL_LIST.search(out):
        out = " ".join(x for x in re.split(r"(?<=[.!?。])\s+", out) if not _TOOL_LIST.search(x))
    return _MD.sub(lambda m: m.group(1) or m.group(2) or m.group(3) or "", out).strip()


# gemma4:e4b 가 도구 호출 형식을 깨뜨려 본문으로 흘릴 때가 있다(2026-09-16 실측):
#   search_terms{query:<|"|>AI 생성 캐릭터<|"|>}<tool_call|>
# 그대로 두면 이 문자열이 답으로 화면에 나간다. 이름과 인자를 읽어 낼 수 있으면 제대로 부른 것으로 보고 실행한다.
_LEAK = re.compile(r"([a-z_]+)\s*[\{(]\s*([a-z_]+)\s*[:=]\s*(.+?)\s*[\})]", re.S)
_NOISE = re.compile(r"<\|?[^<>|]{0,20}\|?>")
_DENIES = re.compile(r"사전에\S*\s*(아직\s*)?없|찾을 수 없|찾기\s*어렵|정보(는|가)?\s*없|알 수 없|없습니다\.?$|"
                     r"not in the dictionary", re.I)
# "이 계열의 표제어들을 보여드릴까요?" — 이미 찾아 놓고 되묻는다. 사용자가 싫어한 그 버릇이다(2026-09-16).
# 찾은 것이 있으면 되묻지 말고 그것을 내보낸다.
# 도구가 뱉은 목록 줄이 그대로 답으로 나온 꼴 — "사전에 12개 (최근 본 순):\n- 무공해: ..."
_DUMPED = re.compile(r"^\s*사전에 \d+개|^\s*-\s+\S+:\s", re.M)
# "무슨 도구 쓸 수 있어?" 처럼 속을 묻는 말. 도구 이름·프롬프트는 이용자 화면에 낼 내용이 아니다
# (CLAUDE.md: 이용자 화면에 내부 용어를 내지 않는다. 사용자 지적 2026-09-16).
_META_ASK = re.compile(r"(사용\s*가능한|쓸\s*수\s*있는|어떤)\s*(도구|기능|툴)|"
                       r"(너|당신|넌)\s*(는|은)?\s*(뭘|무엇을|어떤\s*걸)\s*(할\s*수|도와|해\s*줄)|"
                       r"기능(이|을)?\s*(뭐|무엇|알려)|what (tools|can you do)", re.I)
CAN_DO = {
    "ko": ("요즘 말과 밈을 찾아 드립니다. 말뜻과 어디서 나왔는지 알려드리고, 이름이 기억나지 않으면 "
           "설명만으로도 찾아드립니다. 어느 세대가 어느 나라에서 쓰는지도 볼 수 있고, "
           "사전에 없는 말은 지금 인터넷에서 찾아 대강의 뜻을 알려드립니다."),
    "en": ("I look up current slang and memes. I can tell you what a word means and where it came from, "
           "find it from a description when you forget the name, show who uses it and where, "
           "and search the web on the spot for anything not in the dictionary yet."),
}
# 도구 이름이 둘 이상 적힌 답은 속을 그대로 내보인 것이다
_TOOL_LIST = re.compile(r"(lookup_term|search_terms|why_trending|country_trends|term_usage|list_terms)")
_ASKS_BACK = re.compile(r"(보여|알려|찾아|검색해|정리해)\s*(드릴|줄)(까요|\s*수\s*있)|말씀해\s*주(세요|시면|시겠)|"
                        r"어떤\s*\S{0,14}(단어|표현|밈|유행어|말|것|분야|주제|목록)|무엇을\s*(찾|알|원하)|"
                        r"원하시나요|알고\s*싶으신가요|궁금하신가요|구체적인\s*\S{0,6}(을|를|이|가)?\s*(말씀|알려)")
# "대신 같은 계열의 표제어로는 'Espresso' 가 있으며" — 사전에 없는 이름을 있다고 지어낸다(2026-09-16 실측).
# 인용으로 먹고사는 제품이라 없는 표제어를 있다고 말하면 안 된다.
_QUOTED = re.compile(r"['\"“”‘’]([^'\"“”‘’\n]{2,40})['\"“”‘’]")
# 표제어가 "있다" 고 말하는 문장만 본다. 개념을 따옴표로 인용한 것까지 잡으면 멀쩡한 답을 버린다.
_CLAIMS = re.compile(r"(사전|표제어|등재|수록|계열)[^.!?\n]{0,40}(있으며|있습니다|있어요|올라\s*있)|등재|수록")


_GEN_WORD = {"10대": "10s", "20대": "20s", "30대": "30s", "40대": "40s", "50대": "50s+", "십대": "10s", "이십대": "20s"}
_REGION_WORD = {"한국": "KR", "국내": "KR", "일본": "JP", "미국": "US", "인도네시아": "ID", "베트남": "VN", "태국": "TH",
                "대만": "TW", "홍콩": "HK", "필리핀": "PH", "말레이시아": "MY", "싱가포르": "SG"}


def _list_args(question: str) -> dict:
    """'20대가 쓰는 말', '한국 유행어' 에서 세대·나라를 읽어 낸다. 못 읽으면 조건 없이 전체."""
    out: dict = {}
    for word, code in _GEN_WORD.items():
        if word in question:
            out["generation"] = code
            break
    for word, code in _REGION_WORD.items():
        if word in question:
            out["region"] = code
            break
    return out


LIST_SUM_PROMPT = """아래는 우리 사전에서 찾은 표현 목록이다. 이용자의 물음에 맞춰 두세 문장으로 답하라.

- 목록을 그대로 다시 나열하지 마라. 표는 화면에 따로 나간다.
- 물음이 '왜 떴는지' 를 물으면 **유래**를 근거로 공통점이나 눈에 띄는 사례를 짚어라.
- 물음이 그냥 목록을 달라는 것이면 무엇들이 있는지 한 문장으로 간추리고, 지금 살아 있는 것과 잠잠한 것을 갈라 말하라.
- 목록에 없는 사실은 만들지 마라. 유래가 비어 있는 항목은 모른다고 두고 넘어가라.
- 세 문장을 넘기지 마라.
- 평문으로 써라. **굵게**·목록 기호 같은 마크다운을 쓰지 마라 — 화면이 글자 그대로 보여 준다.

이용자의 물음: {question}

목록:
{items}"""


# "6-7이 뭐야?" 처럼 한 낱말을 물었는데 모델이 lookup_term 대신 list_terms 를 부르면 '못 찾았다' 기록이
# 남지 않아 실시간 찾아보기가 돌지 않는다(사용자 지적 09-16). 질문에서 직접 확인한다.
_ONE_WORD_ASK = re.compile(r"^\s*(.{1,30}?)\s*(?:이|가|은|는)?\s*(뭐야|뭔데|무슨\s*뜻|뜻이\s*뭐|알려\s*줘|설명해\s*줘)"
                           r"[?？!.\s]*$")


def _recover_by_meaning(con: Connection, ctx: "T.Ctx", question: str) -> None:
    """이름을 모르고 뜻만 설명한 질문인데 모델이 엉뚱한 도구를 불렀을 때, 설명으로 직접 찾아 준다.

    "AI로 만든 이탈리아 캐릭터 밈 이름이 뭐였지?" 에 list_terms 를 부르고 '목록에 없다' 고 답하던 문제
    (2026-09-16 평가에서 발견). 도구는 제대로 찾는다 — 부르는 쪽이 틀렸을 뿐이다.
    """
    if any(c.get("type") == "term" for c in ctx.cards) or _asked_word(question) or ctx.content:
        return                                  # 이미 찾았거나, 한 낱말을 물은 것이다
    from .hunt import _LIST_ASK

    if _LIST_ASK.search(question):
        return                                  # 목록을 달라는 말은 list_terms 몫이다
    ctx.say("tool", "설명으로 사전을 훑는 중")
    T.search_terms(ctx, {"query": question.strip()[:200]})


def _asked_word(question: str) -> str:
    """질문이 '한 낱말' 을 물었으면 그 낱말. 목록을 달라는 질문이면 빈 문자열."""
    from .hunt import _GENERIC_TOKEN, _LIST_ASK, _PREDICATE

    m = _ONE_WORD_ASK.match(question.strip())
    if not m:
        return ""
    w = re.sub(r"\s*(뜻|의미|유래)$", "", m.group(1).strip().strip("'\"“”‘’")).strip()
    if len(w) < 2 or _GENERIC_TOKEN.search(w) or _PREDICATE.search(w) or _LIST_ASK.search(question):
        return ""
    return w


def _check_asked_word(con: Connection, ctx: "T.Ctx", question: str) -> None:
    """질문이 한 낱말을 물었으면 코드가 직접 확인한다.

    사전에 있으면 그 표제어를 내놓고(모델이 도구를 안 불러 '없다' 고 답하는 일이 잦다),
    없으면 '못 찾았다' 로 적어 둔다 — 그래야 실시간 찾아보기가 돈다.
    도구는 제대로 찾는데 모델이 부르지 않는 게 문제였다(2026-09-16 평가에서 확인).
    """
    word = _asked_word(question)
    if not word:
        return
    if T._find(con, word) or T._romanized_find(ctx, word):
        if not any(c.get("type") == "term" for c in ctx.cards):
            ctx.say("tool", f"사전에서 '{word}' 확인하는 중")
            T.lookup_term(ctx, {"term": word})       # 카드를 만들어 답이 사전에 근거하게
    elif not ctx.tried:
        ctx.missed(word)


def _sum_list(con: Connection, question: str, card: dict) -> str:
    """목록을 사람 말로 간추린다. 도구가 뱉은 줄을 그대로 답으로 내보내면 표를 두 번 읽히는 꼴이 된다
    (사용자 지적 09-16: "너무 답변이 단조로워")."""
    from .gemini import generate

    # 프롬프트를 짧게 유지한다. 열두 항목에 유래까지 다 넣으면 입력이 길어져 답이 느려진다
    # (공유 GPU 라 경합까지 겹치면 20초를 넘겼다 — 2026-09-16 평가에서 확인).
    lines = []
    for it in card["items"][:8]:
        why = f" · 유래: {it['origin'][:70]}" if it.get("origin") else ""
        lines.append(f"- {it['canonical']} ({it.get('lifecycle','')}): {it.get('definition','')[:60]}{why}")
    try:
        text = (generate(con, LIST_SUM_PROMPT.format(question=question.strip()[:200], items="\n".join(lines)))[0].text or "").strip()
    except Exception:
        text = ""
    if len(text) < 20:      # 모델이 못 쓰면 이름만이라도
        names = ", ".join(i["canonical"] for i in card["items"][:8])
        return f"{card['title']} {len(card['items'])}개: {names}"
    return _tidy(local_chat.sanitize(text))[:700]


def _live_answer(con: Connection, ctx: "T.Ctx", lang: str) -> str:
    """사전에 없는 말을 그 자리에서 찾아보고 알려 준다. 사전 답과 섞이지 않게 카드로 따로 낸다."""
    from . import live

    import time as _t

    deadline = _t.time() + LIVE_BUDGET_S
    word = ctx.tried[0]
    roman = ctx.romanized(word) if _t.time() < deadline else ""
    for cand in ([word, roman] if roman and roman != word else [word]):
        if _t.time() >= deadline:
            break                                # 채팅은 기다려 주지 않는다
        try:
            r = live.look_up(con, cand, lang, deadline=deadline, say=ctx.say)
        except Exception:
            continue
        if not r.found:
            continue
        ctx.card({"type": "live", "term": cand, "summary": r.summary,
                  "sources": [{"domain": e.source_domain, "url": e.url, "title": e.title or e.excerpt[:70]}
                              for e in r.evidences[:5]],
                  "seconds": round(r.seconds, 1)})
        live.queue_for_research(con, cand, lang if cand == word else "en",
                                alias=word if cand != word else "")
        return _tidy(local_chat.sanitize(f"사전에는 아직 없습니다. 지금 찾아보니 {r.summary}"))
    # 사전에도 없고 지금 찾아봐도 없다. 후보로도 넘기지 않는다 — 인터넷에 흔적이 없는 말은 조사할 거리가
    # 아니고, 넘기면 오타·헛소리가 사전 대기열을 채운다(2026-09-16 실측: 시험용으로 친 말이 표제어가 됐다).
    # 모델이 지어낸 말을 내보내느니 없다고 하는 게 낫다.
    return ""


def _drop_invented(con: Connection, text: str, question: str) -> str:
    """사전에 없는 이름을 '있다' 고 말하는 문장을 지운다. 사용자가 말한 이름은 그대로 둔다(되풀이일 뿐)."""
    if not text:
        return text
    asked = question.lower()
    kept = []
    for sent in re.split(r"(?<=[.!?。])\s+", text):
        bad = any(
            name.lower() not in asked and not T._find(con, name)
            for name in _QUOTED.findall(sent)
        ) and _CLAIMS.search(sent)
        if not bad:
            kept.append(sent)
    return " ".join(kept).strip() or ""
_PROMISES = re.compile(r"(lookup_term|search_terms|why_trending|country_trends|term_usage)[^\n]{0,30}(사용|호출|불러|찾아보|해서|하겠)")


def _leaked_call(text: str) -> local_chat.ToolCall | None:
    names = {t["function"]["name"] for t in TOOLS}
    for m in _LEAK.finditer(text or ""):
        name, key, val = m.group(1), m.group(2), _NOISE.sub("", m.group(3)).strip().strip("\"'" )
        if name in names and val:
            return local_chat.ToolCall(id=f"leak_{name}", name=name, args={key: val})
    return None


def reset_breaker() -> None:
    global _fails
    _fails = 0


def _chat(con: Connection, messages: list[dict], tools: list[dict]):
    """CHAT_BACKEND=gemini 면 Gemini(이용자 요청 장부), 그날 몫이 끝났거나 실패하면 로컬 Gemma. 기본은 로컬."""
    from ..config import CHAT_BACKEND
    from . import gemini

    if CHAT_BACKEND == "gemini" and gemini.configured():
        try:
            return gemini.chat_with_tools(con, messages, tools)
        except Exception:
            pass                       # 한도·장애 — 같은 루프를 로컬 Gemma 로 이어 간다
    return local_chat.chat_with_tools(messages, tools)


def run(con: Connection, question: str, lang: str = "ko", history: list[dict] | None = None,
        progress=None, log_miss: bool = True) -> Answer:
    """질문 하나에 답한다. 실패하면 Answer.fallback 에 이유를 담아 돌려준다 — 화면은 규칙 기반 해석으로 물러선다."""
    global _fails
    t0 = time.time()
    if _fails >= BREAKER_TRIP:
        return Answer(text="", fallback=f"모델 연속 실패 {_fails}회 — 이번에는 건너뜀")

    ctx = T.Ctx(con, lang=lang if lang in ("ko", "en") else "ko", progress=progress)
    if _META_ASK.search(question):
        # 무엇을 할 수 있냐는 물음. 모델을 거치면 도구 이름을 늘어놓거나 답이 비어 버린다.
        return Answer(text=CAN_DO.get(lang, CAN_DO["ko"]), seconds=time.time() - t0)
    ctx.say("start", "사전을 보는 중")
    # 바로 앞 대화를 함께 넘긴다 — "비슷한 것도 없어?" 처럼 앞을 받는 말이 오면 무엇을 묻는지 알아야 한다.
    messages: list[dict] = [{"role": "system", "content": SYSTEM}]
    for h in (history or [])[-4:]:
        role = "assistant" if h.get("role") == "assistant" else "user"
        text = str(h.get("content", "")).strip()[:400]
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": question.strip()})
    used: list[str] = []
    last_text = ""

    for turn in range(MAX_TURNS):
        if time.time() - t0 > TOTAL_TIMEOUT_S * 0.8:
            return Answer(text=last_text, used=used, term_ids=ctx.term_ids, turns=turn, seconds=time.time() - t0,
                          fallback=f"시간 초과 {time.time() - t0:.0f}초")
        last_turn = turn == MAX_TURNS - 1          # 마지막 턴에는 도구를 주지 않는다 — 답을 내게 한다
        try:
            text, calls = _chat(con, messages, [] if last_turn else TOOLS)
            _fails = 0
        except Exception as e:
            _fails += 1
            return Answer(text=last_text, used=used, term_ids=ctx.term_ids, turns=turn, seconds=time.time() - t0,
                          fallback=f"{type(e).__name__}: {str(e)[:80]}")

        if not calls:
            leaked = _leaked_call(text) if not last_turn else None
            if leaked:                      # 형식만 깨졌을 뿐 부르려던 도구가 보인다 — 제대로 부른 것으로 처리한다
                calls = [leaked]
            else:
                clean = _NOISE.sub("", text or "").strip()
                # "…를 사용해 찾아보겠습니다" 처럼 부르겠다고 말만 한 경우, 또는 찾아보지도 않고 없다고 한 경우 → 한 번 더 시킨다
                if not last_turn and (_PROMISES.search(clean) or (not used and _DENIES.search(clean))):
                    messages.append({"role": "assistant", "content": clean})
                    messages.append({"role": "user", "content": "설명하지 말고 도구를 실제로 호출해라. 질문에 나온 표현을 그대로 lookup_term 의 term 인자로 넣어라."})
                    continue
                last_text = _tidy(local_chat.sanitize(clean))
                break

        messages.append({"role": "assistant", "content": text or "", "calls": calls})
        for c in calls:
            used.append(c.name)
            messages.append({"role": "tool", "id": c.id, "name": c.name, "content": T.run_tool(ctx, c.name, c.args)})

    # 도구를 한 번도 안 불렀으면 그 답은 사전에 근거하지 않은 말이다 — 코드가 직접 찾아서 다시 답하게 한다.
    # 판정은 데이터가 한다. 사전에 있는 항목이 모델의 게으름으로 없어지면 안 된다.
    if not used:
        for w in [question, *T.keywords(question)]:
            hit = T._find(con, w)
            if hit:
                ctx.say("tool", f"사전에서 '{hit.canonical}' 찾는 중")
                found = T.lookup_term(ctx, {"term": hit.canonical})
                used.append("lookup_term")
                try:
                    text, _ = _chat(con,
                        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question.strip()},
                         {"role": "user", "content": f"사전에서 찾은 내용이다. 이것만 보고 질문에 답해라.\n\n{found}"}], [])
                    last_text = _tidy(local_chat.sanitize(_NOISE.sub("", text or "").strip()))
                except Exception:
                    last_text = ""
                break

    if len(set(_TOOL_LIST.findall(last_text or ""))) >= 2:
        return Answer(text=CAN_DO.get(lang, CAN_DO["ko"]), used=used, term_ids=[], turns=turn + 1,
                      seconds=time.time() - t0)
    last_text = _drop_invented(con, last_text, question)
    # 목록을 물었는데 되묻기만 하면, 되묻지 말고 직접 목록을 뽑아 준다.
    if last_text and _ASKS_BACK.search(last_text) and not ctx.cards:
        if "없습니다" not in T.list_terms(ctx, _list_args(question)):
            last_text = ""      # 아래에서 목록 카드를 보고 사람 말로 간추린다
    # 도구가 찾은 것이 있는데 모델이 "없다" 고 하거나 아무 말도 못 하면, 찾은 것을 그대로 내보낸다.
    # 코드가 먼저 확인한다 — 모델이 도구를 안 불렀거나 엉뚱한 걸 불렀을 수 있다.
    # 답 문장을 정하기 전에 해야 한다. 나중에 하면 찾아 놓고도 쓰지 못한다(2026-09-16 평가에서 확인).
    _check_asked_word(con, ctx, question)
    _recover_by_meaning(con, ctx, question)
    # 조건이 읽히는 목록 질문("한국 …", "20대 …")인데 아무것도 못 뽑았으면 코드가 직접 뽑는다.
    # 모델이 list_terms 를 부를 때도 있고 안 부를 때도 있어서 답이 들쭉날쭉했다.
    if not ctx.cards and _list_args(question):
        ctx.say("tool", "조건에 맞는 표제어 모으는 중")
        T.list_terms(ctx, _list_args(question))

    # 목록을 뽑아 놓았으면 사람 말로 간추린다. 도구가 뱉은 줄을 그대로 내보내면 표를 두 번 읽히는 꼴이고,
    # 하나만 집어 말하면 "정리해줘" 에 대한 답이 아니다.
    listed = next((c for c in reversed(ctx.cards) if c.get("type") == "list" and c.get("items")), None)
    if listed:
        ctx.say("write", "찾은 것들을 간추리는 중")
    if listed and (not last_text or _DENIES.search(last_text) or _ASKS_BACK.search(last_text) or _DUMPED.search(last_text)):
        last_text = _sum_list(con, question, listed)
    elif not last_text or _DENIES.search(last_text) or _ASKS_BACK.search(last_text):
        if ctx.best:
            name, defn = ctx.best
            last_text = f"찾으시는 게 '{name}' 인 것 같습니다. {defn}".strip()
    # 사전이 답하지 못했다. 여기서 끝내지 말고 **지금 인터넷에서 찾아본다** — 대신 검증 전이라고 밝힌다.
    # 찾아본 말은 후보로 넘겨, 뒤에서 research 가 근거를 모으고 게이트가 사전에 올릴지 정한다.
    # ctx.tried 는 '물어본 말을 사전에서 못 찾았다' 는 기록이다. 다른 목록이 곁들여 나왔더라도
    # 물어본 그 말에는 답을 못 한 것이므로 지금 찾아본다.
    if ctx.tried:
        live_text = _live_answer(con, ctx, lang)
        if live_text:
            last_text = live_text
        elif not ctx.best and not ctx.cards:
            # 사전에도 없고 지금 찾아봐도 없다. 모델이 제 말로 둘러대게 두지 않는다 —
            # 없을 때는 늘 같은 문장으로 답해야 사람이 상태를 알아본다.
            last_text = "사전에 아직 없습니다. 지금 인터넷에서도 찾지 못했습니다."
    if not last_text and not ctx.best:
        last_text = "사전에 아직 없습니다."     # 찾아봤는데 정말 없다 — 지어내지 않는다
    if not last_text:
        return Answer(text="", used=used, term_ids=ctx.term_ids, turns=MAX_TURNS, seconds=time.time() - t0,
                      fallback="도구만 부르고 답을 내지 않음", cards=ctx.cards)
    if not ctx.term_ids and log_miss:
        ds.log_lookup_miss(con, question.strip()[:200], lang)   # 사전이 답하지 못한 질문 → 발굴 단계 재료
    return Answer(text=last_text, used=used, term_ids=ctx.term_ids, turns=turn + 1, seconds=time.time() - t0,
                  cards=ctx.cards)
