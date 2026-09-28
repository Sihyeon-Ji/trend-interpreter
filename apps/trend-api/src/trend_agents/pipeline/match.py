"""용어 매칭 규칙 한 곳. 프론트 lib/explain.ts 의 termPattern 과 같은 규칙이고, 근거를 용어에 붙일 때는 mentions() 로 판단한다."""
from __future__ import annotations

import re

HANGUL = re.compile(r"[ᄀ-ᇿ㄰-㆏가-힯]")
# 숫자꼴 용어('6-7')는 점수·날짜·시간과 글자만으로는 구별되지 않는다 → 이런 단서가 같이 있어야 '그 밈'을 말한 것으로 본다
CUES = re.compile(r"meme|slang|viral|trend|brainrot|gen ?alpha|gen ?z|tiktok|shorts|mean(?:s|ing)?|what (?:is|does)|explained|origin|밈|유행어|신조어|챌린지|틱톡|쇼츠|뜻|의미|유래|정체", re.I)


def term_pattern(candidate: str) -> re.Pattern:
    toks = [re.escape(t) for t in candidate.strip().split()]
    if HANGUL.search(candidate):
        return re.compile(r"\s*".join(toks), re.I)
    body = r"\s+".join(toks)
    # 경계는 ASCII 글자·숫자만 본다(프론트 JS 의 \w 와 같다). 파이썬 \w 는 한자·가나도 포함해서 'iPhone Duoは' 같은 붙여쓰기를 놓친다
    return re.compile(rf"(?<![A-Za-z0-9_-]){body}(?![A-Za-z0-9_-])", re.I)


def numeric_like(term: str) -> bool:
    core = re.sub(r"[\W_]+", "", term)
    return bool(core) and core.isdigit()


def mentions(text: str, canonical: str, aliases: list[str] | tuple[str, ...] = ()) -> bool:
    """텍스트가 용어를 실제로 말하는가. 글자가 있는 표기가 맞으면 그대로 참, 숫자꼴 표기만 맞으면 밈 단서가 함께 있어야 한다."""
    cands = [c for c in (canonical, *aliases) if c and c.strip()]
    hit = [c for c in cands if term_pattern(c).search(text)]
    if not hit:
        return False
    if all(numeric_like(c) for c in hit):
        return bool(CUES.search(text))
    return True


def same_term(name: str, canonical: str, aliases: list[str] | tuple[str, ...] = ()) -> bool:
    """이름 하나(쇼츠 해석의 MemeRef.name 등)가 이 용어인가 — 공백·기호를 뺀 표기가 같으면 참. 이미 밈으로 분류된 이름이라 밈 단서는 보지 않는다."""
    n = _strip(name)
    return bool(n) and n in {_strip(c) for c in (canonical, *aliases) if c}


def _strip(s: str) -> str:
    return re.sub(r"[\W_]+", "", s).lower()


# ---------- 느슨한 찾기 (사람이 친 대로 맞춰 주기) ----------
# 2026-09-16 실측: 별칭이 '퉁퉁퉁퉁 사후르' 인데 사람은 '퉁퉁퉁퉁퉁퉁싸후르' 라고 친다.
# 반복 횟수와 된소리가 다를 뿐 같은 말이다. 뜻을 지어내는 것과 별개로, 찾는 것은 더 잘해야 한다.

_TENSE = {1: 0, 4: 3, 8: 7, 10: 9, 13: 12}   # ㄲ→ㄱ ㄸ→ㄷ ㅃ→ㅂ ㅆ→ㅅ ㅉ→ㅈ (초성 인덱스)


def _soften(ch: str) -> str:
    """된소리 초성을 예사소리로. 싸 → 사, 꾸 → 구."""
    o = ord(ch) - 0xAC00
    if not 0 <= o < 11172:
        return ch
    lead, rest = divmod(o, 588)
    return chr(0xAC00 + _TENSE.get(lead, lead) * 588 + rest)


def loose_key(s: str) -> str:
    """찾기 전용 키. 공백·기호를 빼고, 된소리를 풀고, 같은 글자가 이어지면 하나로 줄인다.
    게이트(mentions)에는 쓰지 않는다 — 근거 판정은 엄격해야 한다."""
    out: list[str] = []
    for ch in re.sub(r"[\W_]+", "", s).lower():
        ch = _soften(ch)
        if not out or out[-1] != ch:
            out.append(ch)
    # 낱말 단위 반복도 줄인다: tung tung tung sahur → tungsahur (한 글자 반복은 위에서 이미 줄었다)
    return re.sub(r"(.{2,8}?)\1+", r"\1", "".join(out))


def keywords(s: str) -> list[str]:
    """뜻으로 찾을 때 쓸 낱말. 조사·물음말은 빼고 두 글자 이상만."""
    stop = {"무슨", "뜻이", "뜻은", "뭐야", "뭔가", "인가", "이야", "그거", "저거", "이런", "저런", "같은", "하는", "라는",
            "알려", "설명", "찾아", "어떤", "관련", "표현", "단어", "유행어", "what", "does", "mean", "that", "this", "the", "with", "about"}
    toks = [t for t in re.split(r"[\s,·/]+", s.strip()) if len(t) >= 2]
    return [t for t in (re.sub(r"[?!.。,]+$", "", x) for x in toks) if t and t.lower() not in stop][:8]


_PARTICLES = ("이랑", "라는", "라고", "에서", "한테", "께서", "이가", "가", "이", "은", "는", "을", "를", "의", "도", "만", "와", "과", "랑", "요")


def strip_particle(s: str) -> list[str]:
    """'퉁퉁퉁싸후르가' → ['퉁퉁퉁싸후르가', '퉁퉁퉁싸후르']. 모델이 조사를 붙인 채로 도구를 부를 때 쓴다."""
    s = s.strip()
    out = [s]
    for p in _PARTICLES:
        if len(s) > len(p) + 1 and s.endswith(p):
            out.append(s[: -len(p)].strip())
            break
    return out


# 목록·후보로 내보내면 안 되는 말 — 욕설·성적 표현. 직접 물으면 사전은 답하되, 둘러보기 목록에는 올리지 않는다
# (2026-09-28 검토: "10대 유행어" 목록에 '아헤가오' 가 나왔다).
# 목표 지역(대만·홍콩)의 중국어도 거른다. 뜻이 하나뿐인 말만 — '穴'·'エロ' 처럼 흔히 다른 뜻으로 쓰이는 글자는 넣지 않는다.
UNSAFE = re.compile(r"시발|씨발|ㅅㅂ|좆|병신|섹스|야동|아헤가오|보지|자지|fuck|shit|porn|hentai|ahegao|nsfw|goatse|"
                    r"性侵|強姦|强奸|色情|做愛|做爱|幹你娘|干你娘|肏|屄", re.I)


def unsafe(text: str) -> bool:
    return bool(UNSAFE.search(text or ""))
