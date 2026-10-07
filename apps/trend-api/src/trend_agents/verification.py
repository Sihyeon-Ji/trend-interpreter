"""검증 게이트. LLM 이 '검증됨' 이라고 스스로 말할 수 없다 — 규칙이 정한다.

참고 아키텍처(MCTI)에서 이식한 두 원칙:
- 라벨 정직성 게이트: 라벨(verified)은 결정론 근거가 있을 때만. 실패는 삭제가 아니라 강등 + 사유 기록.
- 앵커 가드: 용어·풀이가 근거 '원문'에 실재할 때만 그 근거를 센다. LLM 자기검증 금지.

사전 등재 기준(ADR 0003, 2026-09-29): 자동으로 싣는 말은 유래를 적는 참고 문서(나무위키·위키백과·Know Your Meme·
pixiv 백과사전·萌娘百科)에 표제어가 든 문서가 있어야 한다. 커뮤니티·SNS 글은 쓰임을 재는 지표일 뿐 뜻의 근거가 아니다.
문서가 없으면 검수 대기로 가고, 사람이 승인하면 실린다(그런 문서가 드문 지역의 예외 길).

2026-09-30 사용자 결정: **참고 문서에 표제어가 든 문서가 있으면 그것만으로 싣는다.** 독립 출처 2곳·1차 근거(쇼츠·뉴스)·모델 자기확신은
참고 문서가 없을 때만 본다 — 커뮤니티 글을 근거에서 빼자(ADR 0003) 한 곳짜리 밈이 모두 막혔다(나무위키만 있는 한국 밈).
커뮤니티·SNS 글은 어떤 셈에도 들어가지 않는다. 내용 검사(빈 뜻·모델이 든 링크에 표제어 없음·풀이가 원문에 없음)는 그대로다.
위키 밈 분류에 든 말(catalogued)은 편집자가 밈으로 분류했으므로 모델의 '표현이 아님' 판단으로 막지 않는다.
"""
from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit, urlunsplit

from .schemas import Evidence, Meaning, MeaningDraft, Term, Verification


PUBLIC_VERIFICATIONS = frozenset({"verified_auto", "verified_human"})


def is_public_entry(term: Term | None, meaning: Meaning | None) -> bool:
    """Only a verified entry with an approved current meaning may be read publicly."""
    return bool(term and term.status == "verified" and meaning and meaning.verification in PUBLIC_VERIFICATIONS)

MIN_INDEPENDENT_DOMAINS = 2
MIN_SELF_CONFIDENCE = 0.5
# 위키백과 문서는 사람이 쓴 백과사전 항목이라 1차 근거로 인정한다. 다만 언어판이 달라도 한 출처로 세도록
# source_domain 을 wikipedia.org 하나로 맞춰 두었다 — 영어판·한국어판을 "독립 출처 2개" 로 셈하면 자기확인이 된다.
FIRST_PARTY = {"short", "news", "datalab", "wiki"}
# 참고 문서가 있는 곳(하위 도메인 포함 — ko.wikipedia.org 등). 니코니코 대백과는 이 서버를 막고, pixiv 백과사전은 대부분 봇 확인 뒤에 있다.
# 2026-09-30 더함: 니코니코 대백과(위키데이터 ID 로만 안다 — 이 서버 요청을 막는다), PTT鄉民百科(대만)·香港網絡大典(홍콩, Fandom API), 리브레 위키(한국)
REFERENCE_DOMAINS = ("namu.wiki", "wikipedia.org", "knowyourmeme.com", "dic.pixiv.net", "zh.moegirl.org.cn",
                     "dic.nicovideo.jp", "pttpedia.fandom.com", "evchk.fandom.com", "librewiki.net", "maily.so")
# 도메인 전체가 아니라 이 경로만 참고 문서인 곳 — maily.so 는 뉴스레터 호스팅이라 Trend A Word(신조어를 하루 하나씩 정리) 만(2026-09-30 사용자 요청)
REFERENCE_PATHS = {"maily.so": "/trendaword/posts/"}
_EMPTY_MEANING = __import__("re").compile(r"근거 부족|확인되지 않(음|았)|정보가 (부족|없)|명확한 (사전적 )?(정의|의미)(는|가)? ?없|알 수 없는 표현")
# 뜻 칸에 남은 조사 모델의 메모 — '근거에 밈으로 쓰이는 구체적인 설명은 없음' 처럼 근거를 두고 한 말. 화면에 뜻으로 나갔다
# (실데이터 10-03, 확인된 뜻 7,666개 중 162개). '근거'에 조사(에·는·가·만으로는)가 붙고 쓰임을 가리키는 말과 부정이 가까이 있을 때만 —
# 뜻 자체가 '근거 없는 자신감'(근자감)·'근거 없는 호들갑'(근들갑)·'법적 근거 없이' 인 말은 걸리지 않는다.
_KW = r"(?:밈|쓰임|사용|설명|예시|언급|뜻|정의|의미|내용|맥락)"
_NEG = r"(?:없|않|부족|제시되지|명시되지|제공되지)"
_EVIDENCE_NOTE = __import__("re").compile(
    rf"{_KW}[^.()]{{0,30}}?근거(?:에는|에|는|가|만으로는)\s?[^.()]{{0,12}}?{_NEG}"
    rf"|{_KW}[^.()]{{0,30}}?근거\s?없음"
    rf"|근거(?:에는|에|는|가|만으로는)\s?[^.()]{{0,40}}?{_KW}[^.()]{{0,25}}?{_NEG}"
    rf"|해당 근거(?:는|만으로는)|위키 문서에 [^.()]{{0,30}}밈[^.()]{{0,30}}(?:설명|언급)은 없")
NO_REFERENCE = "참고 문서(나무위키·위키백과·Know Your Meme 등)에 유래가 없어 사람이 확인한 뒤에만 실립니다"


# '인터넷 밈으로 사용됨.' 처럼 밈이라는 말 말고는 내용이 없는 뜻(실데이터 10-04, 확인된 뜻 56개). 상투적인 '밈으로 사용됨' 마디와
# 군말을 지우고 남는 글자가 거의 없을 때만 — 'PSY의 싱글 곡 제목이자, 인터넷 밈으로 사용됨'·'의인화된 박제 여우의 이미지' 처럼
# 대상을 말한 뜻은 걸리지 않는다.
_GENERIC_USE = __import__("re").compile(
    r"(?:인터넷(?:에서|상에서|상)?\s?)?['\"]?(?:밈|유행어)['\"]?(?:이나|나|으로|로|/유행어|\s?또는\s?유행어|의|과|와)?[^.,]{0,14}?"
    r"(?:사용|분류|쓰이|쓰|언급|재조명)[가-힣]*")
_FILLER = __import__("re").compile(r"관련하여|관련된|관련|에서|형태로|맥락에서|한 종류로|일부로|대한|설명이 필요함|이다|입니다|이며|되며|됨|된|되는|"
                                   r"표현|단어|이름|제목|노래|작품|캐릭터|챌린지|존재|것|에|의|으로|로|은|는|이|가|을|를|와|과|및|또는|그|한|이자")


def vacuous_meaning(text: str) -> bool:
    """뜻이 '밈으로 사용됨' 말고는 아무것도 말하지 않나."""
    import re

    rest = _GENERIC_USE.sub(" ", text or "")
    if rest == (text or ""):
        return False
    return len(re.sub(r"[\s\W_]+", "", _FILLER.sub(" ", rest))) < 5


# 모델이 뜻을 모르고 짐작한 문장('퇴사를 의미하는 것으로 보이며', '구체적인 의미는 명확하지 않으며'), 밈이 아닌 낱말 본뜻이라고
# 스스로 밝힌 문장('일반적 의미로 사용됨'), 뜻 대신 '…에 대한 설명이 필요함' 으로 끝난 메모. 확인된 뜻인데도 대시보드
# '바로 써도 됨'에 TOESA·Trippi Troppi·대박이 올랐다(실데이터 10-05). '실제 외모를 알 수 없는 익명성'·'합쳐진 것으로 추정' 처럼
# 뜻 안에서 쓴 말, '…에서 유래한 것으로 보인다' 처럼 유래만 짐작한 말은 걸리지 않게 한다.
_GUESSED = __import__("re").compile(
    r"(?:것|말)으?로 보(?:인다|이며|이고|임)|(?:의미|뜻)[는은가이]? (?:명확하지|분명하지|불분명)|일반적(?:인)? (?:의미|뜻)(?:로|를|으로)"
    r"|설명이 필요(?:함|하다)\.?\s*$")
_ORIGIN_GUESS = __import__("re").compile(r"유래한|비롯된|영향을 받은|줄임말")


# 뜻이 대상(게임·로켓·회사·인물·음식)을 설명할 뿐 '어떻게 쓰이는지' 를 한마디도 하지 않는다 — 위키의 '인터넷 밈' 분류가 밈이 된 대상의
# 문서까지 담아, 김치·칠레·누리호·지뢰 찾기·KD 운송그룹의 백과사전식 설명이 확인된 뜻으로 들어왔다(실데이터 10-06: '쓰이는 중' 283개 중
# 100개). 쓰임을 말하는 낱말(쓰다·부르다·가리키다·표현·비유·밈·유행·속어…)이 하나라도 있으면 통과. '설명할 때 사용됨' 처럼 쓰임 낱말은
# 있어도 빈 뜻은 vacuous_meaning 몫이다. 사람이 판정한 16개로 맞춰 보니 나쁜 뜻 8개 중 4개를 잡고 좋은 뜻 8개는 잡지 않았다(Plan 16).
_USAGE_WORD = __import__("re").compile(
    r"쓰[이인는다며고여]|쓴다|사용[되하된됨]|부르|부름|가리키|가리킨|일컫|일컬|표현|비꼬|비꼼|드립|유행|밈|빗대|비유|칭하|속어|은어|신조어|"
    r"말이다|말로|하는 말|감탄사|대명사")


def no_usage_meaning(text: str) -> bool:
    """뜻이 쓰임을 한마디도 말하지 않고 대상만 설명하나(_USAGE_WORD 가 없음). 한국어로 쓴 뜻만 본다 — 쓰임 낱말이 한국어라
    일본어·영어로만 쓴 뜻(확인된 뜻 7,451개 중 101개)은 가를 수 없다."""
    t = text or ""
    return bool(__import__("re").search("[가-힣]", t)) and not _USAGE_WORD.search(t)


def guessed_meaning(text: str) -> bool:
    """뜻이 짐작이거나 낱말의 일반 뜻이라고 스스로 밝혔나(_GUESSED)."""
    text = text or ""
    return any(not _ORIGIN_GUESS.search(text[max(0, m.start() - 8):m.start()]) for m in _GUESSED.finditer(text))


def evidence_note(text: str) -> bool:
    """뜻 칸에 뜻이 아니라 근거를 두고 한 메모가 들어 있나(_EVIDENCE_NOTE)."""
    return bool(_EVIDENCE_NOTE.search(text or ""))


def normalize_url(url: str) -> str:
    """문서 주소를 한 꼴로 — 스킴·호스트는 소문자, 경로·질의는 퍼센트 인코딩한 꼴, 조각(#)은 뺀다. 한글을 그대로 쓴 주소와
    인코딩한 주소가 같은 문서로 보이게 한다(같은 문서가 근거·문서 목록에 두 번 들어가지 않게). 스킴이 없으면 그대로 돌려준다."""
    raw = (url or "").strip()
    u = urlsplit(raw)
    if not u.scheme or not u.netloc:
        return raw
    path = unquote(u.path)
    host = (u.hostname or "").lower()
    if (host == "wikipedia.org" or host.endswith(".wikipedia.org")) and path.startswith("/wiki/"):
        path = path.replace(" ", "_")                # 위키백과(MediaWiki)는 문서 이름의 띄어쓰기를 밑줄로 쓴다 — Aura farming = Aura_farming
    path = quote(path, safe="/:@!$&'()*+,;=~") or "/"
    query = quote(unquote(u.query), safe="/:@!$&'()*+,;=?~") if u.query else ""
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), path, query, ""))


def reference_doc(e: Evidence) -> bool:
    """참고 문서의 한 쪽인가 — 위키·웹 근거이고 주소가 참고 문서 도메인의 문서일 때만.
    나무위키 실시간 검색어(datalab, 주소는 홈페이지)나 홈페이지 주소뿐인 근거는 문서가 아니다."""
    if e.kind not in ("wiki", "web"):
        return False
    u = urlsplit(e.url or "")
    host = (u.hostname or "").lower()
    domain = next((d for d in REFERENCE_DOMAINS if host == d or host.endswith("." + d)), None)
    if not domain or u.path in ("", "/"):
        return False
    return u.path.startswith(REFERENCE_PATHS[domain]) if domain in REFERENCE_PATHS else True


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def source_text(e: Evidence) -> str:
    """검증에 쓸 수 있는 '원문'만. 우리 모델이 쓴 문장(derived)은 앵커가 될 수 없다 — 그러면 사전이 스스로를 확인하게 된다.
    2026-09-16 실사고: 쇼츠 해석이 'Ganpati Bappa Morya: 가네샤 축제…구호' 를 발췌로 남겼고, 오프라인 조사가 그 문장을 그대로
    뜻·풀이로 옮겨 적었으며, 게이트의 환각 검사가 자기 문장에 앵커되어 통과했다(전통 종교 구호가 유행어로 등재됨)."""
    return e.title if getattr(e, "derived", False) else e.title + " " + e.excerpt


def _sq(s: str) -> str:
    import re
    import unicodedata

    t = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[\s\W_]+", "", t) or re.sub(r"\s+", "", t)       # 기호만 있는 표제어('$$$$', '+1')는 기호를 남긴다


def doc_titled(term: str, e: Evidence, aliases: list[str] | tuple[str, ...] = ()) -> bool:
    """참고 문서가 이 표제어의 문서인가 — 근거 제목(사이트 이름 앞머리·라이선스 꼬리·구분 꼬리를 뗀 것) 또는 주소의 문서 이름이 표제어·별칭과 같을 때.
    엉뚱한 문서('Aura Monster' 에 리제로 캐릭터 문서, 목록 문서)가 참고 문서로 세지던 것(2026-09-30 품질 점검, 130건)을 막는다."""
    import re

    names = {_sq(n) for n in (term, *aliases) if n}
    title = re.sub(r"^[^:：]{1,40}[:：]\s*", "", e.title or "")
    title = re.sub(r"\s*\((?:CC[^)]*)\)\s*$", "", title)
    cands = [title, re.sub(r"\s*\([^)]*\)$", "", title)]
    path = unquote(urlsplit(e.url or "").path)
    name = path.split("/w/", 1)[-1] if "/w/" in path else path.split("/wiki/", 1)[-1] if "/wiki/" in path else ""
    name = name.replace("_", " ")
    cands += [name, re.sub(r"\s*\([^)]*\)$", "", name)]
    # 제목이 표제어로 시작하면 인정한다('을용타/여담', '럭키비키 문서'). 제목이 아예 다른 문서('Sonic X', 'Subaru Natsuki', 목록 문서)는 빠진다
    return any(_sq(c).startswith(n) for c in cands if c for n in names if len(n) >= 2)


def anchor_hit(term: str, e: Evidence, aliases: list[str] | tuple[str, ...] = ()) -> bool:
    """용어(또는 별칭)가 근거의 원문에 실제로 있는가 (숫자꼴 용어는 밈 단서까지)."""
    from .pipeline.match import mentions  # 순환 import 방지

    return mentions(source_text(e), term, aliases)


def gate(
    term: str, draft: MeaningDraft, evidences: list[Evidence], current: Meaning | None, aliases: list[str] | tuple[str, ...] = (),
    *, catalogued: bool = False,
) -> tuple[Verification, list[str]]:
    """통과하면 verified_auto. 아니면 unverified + 사람 검수 큐로 갈 이유 목록."""
    reasons: list[str] = []
    # 뜻이 비었거나 표제어를 도로 옮겨 적은 것은 사전 항목이 아니다. 근거가 아무리 튼튼해도 통과시키지 않는다
    # (2026-09-16 실측: 근거 8건짜리 항목이 definition="" 으로 verified 가 됐다).
    definition = (draft.definition or "").strip()
    if len(definition) < 8 or _norm(definition) == _norm(term):
        reasons.append("뜻이 비었거나 표제어를 그대로 옮겨 적음")
    if _EMPTY_MEANING.search(definition):
        reasons.append("뜻이 '근거 부족'·'정의 없음' 같은 빈말이다")
    elif evidence_note(definition):
        reasons.append("뜻 칸에 근거에 대한 메모('근거에 쓰임 설명이 없음')가 들어 있다")
    elif vacuous_meaning(definition):
        reasons.append("뜻이 '인터넷 밈으로 사용됨' 말고는 내용이 없다")
    elif guessed_meaning(definition):
        reasons.append("뜻이 '…인 것으로 보인다' 같은 짐작이거나 낱말의 일반 뜻이다")
    if not draft.is_expression and not catalogued:
        reasons.append("표현이 아니라 상품·기관·인물·일반 단어로 판단됨 — 사전 대상 아님")
    from .collectors.community import is_community_post

    evidences = [e for e in evidences if not is_community_post(e)]      # 커뮤니티·SNS 글은 어떤 셈에도 넣지 않는다(ADR 0003)
    anchored = [e for e in evidences if anchor_hit(term, e, aliases)]
    documented = any(reference_doc(e) and doc_titled(term, e, aliases) for e in anchored)
    # 이미 실린 말(현행 뜻이 확인됨)을 다시 조사할 때는 출처 규칙으로 강등하지 않는다 — 커뮤니티 글을 셈에서 뺀 탓에 예전 항목이
    # 한꺼번에 내려가지 않게. 기존 항목은 문서 대조(Plan 12)의 '문서 없음 14일' 규칙으로 사람이 정리한다.
    listed = current is not None and current.verification in ("verified_auto", "verified_human")
    # 용어가 안 들어 있는 근거는 셈에서 빠진다. 다만 **모델이 근거라며 내놓은 웹 링크**가 그렇다면
    # 환각 신호라서 차단 사유다 — 커뮤니티·검색 수집기가 긁어 온 잡음은 모델 잘못이 아니므로 조용히 뺀다.
    stray = [e for e in evidences if e.kind == "web" and e not in anchored]
    if stray:
        reasons.append(f"모델이 든 웹 근거 {len(stray)}건에 용어가 없음 — 환각 의심")
    if not documented and not listed and len({e.source_domain for e in anchored}) < MIN_INDEPENDENT_DOMAINS:
        reasons.append(f"용어가 실재하는 독립 출처 {MIN_INDEPENDENT_DOMAINS}개 미만")
    if not documented and not listed and not any(e.kind in FIRST_PARTY for e in anchored):
        reasons.append("1차 근거(쇼츠·뉴스·데이터랩) 없음 — 웹 검색만으로는 부족")
    # 참고 문서 규칙(ADR 0003). 이미 실린 말(현행 뜻이 확인됨)을 다시 조사할 때는 이 규칙으로 강등하지 않는다 —
    # 기존 항목은 문서 대조(Plan 12)를 거쳐 사람이 확인한 뒤에 정리한다.
    if not listed and not documented:
        reasons.append(NO_REFERENCE)
    if draft.expansion and not any(_norm(draft.expansion) in _norm(source_text(e)) for e in evidences):
        reasons.append(f"풀이 {draft.expansion!r} 가 어떤 근거 원문에도 없음 — 환각 의심")
    if not documented and draft.self_confidence < MIN_SELF_CONFIDENCE:
        reasons.append(f"모델 자기확신 {draft.self_confidence:.2f} < {MIN_SELF_CONFIDENCE}")
    if current and current.expansion and draft.expansion and current.expansion != draft.expansion:
        reasons.append(f"현행 뜻과 충돌 (v{current.version}: {current.expansion!r}) — 의미 변화 검수 필요")
    # '제외됨' 만 남고 다른 사유가 없으면 통과 (정보성 사유)
    blocking = [r for r in reasons if not r.endswith("제외됨")]
    return ("verified_auto" if not blocking else "unverified"), reasons
