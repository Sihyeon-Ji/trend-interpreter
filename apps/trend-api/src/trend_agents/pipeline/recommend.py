"""사진·홍보 문구로 밈 추천 (Plan 07, 사용 흐름 2단계 '추천받기').

1. 이해   사진 또는 문구 → ProductBrief (모델 한 번. Gemini, 로컬 Gemma 가 켜져 있으면 그쪽, 둘 다 없으면 고정 예시)
2. 후보   고른 지역의 확인된 표제어(대시보드 카드) 가운데 사용 자제·저속한 말투를 뺀다        — 규칙
3. 순위   분야·느낌 겹침(fit 단계가 미리 붙인 닫힌 낱말) + 퍼진 정도·생애주기·리스크 가감      — 규칙
4. 이유   상위 몇 개에 '어울리는 이유' 한 문장 (모델 한 번). 사전 뜻과 겹치는 말이 없는 이유는 버리고
          화면이 겹친 낱말로 규칙 문장을 만든다.
사진은 메모리에서만 쓰고 저장·기록하지 않는다(ADR 0002 §4).
"""
from __future__ import annotations

import re
import threading

from ..config import USE_LOCAL_GEMMA
from ..schemas import MemeFit, MemeReason, ProductBrief
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from . import dashboard
from .gemini import BudgetExhausted, configured, local_ok, structured
from .views import KeywordCard, RecommendItem, RecommendResult

TOP = 5
MIN_FIT = 2          # 분야(3)나 느낌 하나(2)는 맞아야 추천한다 — 모자라면 채우지 않는다
MIN_SCORE = 2.0      # 퍼진 정도·생애주기·리스크를 더한 뒤에도 이만큼은 돼야 한다(잠잠한 밈이 -0.5 로 추천되던 것을 막는다)
# 톤마다 허용하는 말투와 반기는 느낌. '고급스러움' 은 장난스러운 말도 뺀다.
TONES: dict[str, tuple[set[str], set[str]]] = {
    "friendly": ({"wholesome", "playful"}, {"joy", "cute", "relatable", "comfort"}),
    "witty": ({"wholesome", "playful", "edgy"}, {"funny", "sarcasm", "relatable", "surprise"}),
    "premium": ({"wholesome"}, {"cool", "pride", "romance", "nostalgia"}),
}
DIFFUSION_BONUS = {"spreading": 2.0, "underground": 1.0, "mainstream": 0.5, "fading": -2.0}
LIFECYCLE_BONUS = {"emerging": 1.0, "rising": 1.0, "peak": 0.5, "declining": -1.0, "dormant": -3.0}

# 모델이 없는 개발 환경의 고정 설명 (Plan 07: 화면과 e2e 가 모델 없이 끝까지 돌게)
SAMPLE_BRIEF = ProductBrief(product="여름 한정 아이스 흑당 라떼", category="food_drink", feelings=["joy", "relatable", "comfort"],
                            values=["시원함", "달콤함", "여름 한정"], scene="더운 오후 카페에서 한숨 돌릴 때", colors=["갈색", "흰색"], avoid=[])

BRIEF_PROMPT = """너는 광고 기획자다. 아래 {what}을 보고 제품을 설명하라. 추측이 필요하면 흔한 쪽으로 하되, 보이지 않는 성분·효능을 지어내지 마라.
category 는 food_drink · fashion_beauty · tech · game · entertainment · travel · finance · health_fitness · education · lifestyle 가운데 하나.
feelings 는 이 홍보가 전하고 싶은 느낌 1~3개를 joy · hype · cute · funny · relatable · comfort · pride · surprise · sarcasm · frustration · tired ·
romance · nostalgia · cool 가운데서. 브랜드가 피해야 할 표현·주제가 보이면 avoid 에. 글(product·values·scene·colors·avoid)은 {lang}로.
{text}"""

REASON_PROMPT = {
    "ko": """너는 {region} 시장의 광고 카피라이터다. 제품: {product} ({scene}). 핵심 가치: {values}.
아래 밈마다 이 제품 홍보에 어울리는 이유를 한국어 한 문장(80자 안팎)으로 써라.
- 문장에 밈 이름을 그대로 넣고, 사전 뜻의 어느 점이 이 제품과 이어지는지 말하라.
  예: '오살힘'은 하루를 버티게 하는 작은 힘이라는 뜻이라, 더운 오후의 한 잔을 그렇게 소개하기 좋다.
- **사전 뜻 안에서만** 쓴다. 뜻을 바꾸거나 새로 지어내지 마라. 어울리지 않으면 reason 을 빈 문자열로 둬라.
입력 번호를 i 로 그대로.

{items}""",
    # 영어 화면에서 한국어 지시문을 쓰면 이유가 한국어로 나왔다(2026-09-29 실측 15건 중 6건 한국어) — 지시문과 뜻풀이를 영어로 준다.
    "en": """You are an ad copywriter for the {region} market. Product: {product} ({scene}). Key values: {values}.
For each meme below, write ONE English sentence (about 20 words) on why it fits this product's promotion.
- Include the meme name exactly as written, and say which part of its dictionary meaning connects to the product.
  Example: 'Lucky Vicky' means seeing the bright side of a bad situation, so it suits turning a hot afternoon into a treat.
- Stay strictly within the dictionary meaning. Do not change or invent meanings. If it does not fit, leave reason empty.
Return the input number as i.

{items}""",
}


def score(brief: ProductBrief, fit: MemeFit, card: KeywordCard, tone: str) -> tuple[float, bool, list[str]] | None:
    """(점수, 분야가 맞았나, 겹친 느낌). 추천하면 안 되는 것은 None. 모든 판단이 규칙이다."""
    voices, liked = TONES[tone]
    if card.risk_level == "avoid" or fit.voice == "crude" or fit.voice not in voices:
        return None
    cat = brief.category in fit.fits
    shared = [f for f in brief.feelings if f in fit.feelings][:3]
    rel = (3 if cat else 1 if fit.any_category else 0) + 2 * len(shared)
    if rel < MIN_FIT:
        return None
    s = rel + sum(1 for f in fit.feelings if f in liked)
    s += DIFFUSION_BONUS.get(card.diffusion or "", 0.0) + LIFECYCLE_BONUS.get(card.lifecycle, 0.0)
    s += -2.0 if card.risk_level == "caution" else -0.5 if card.risk_level is None else 0.0
    return (s, cat, shared) if s >= MIN_SCORE else None


def rank(brief: ProductBrief, cards: list[KeywordCard], fits: dict[str, MemeFit], tone: str) -> tuple[list[tuple], int]:
    """([(점수, 카드, 분야, 느낌)] 높은 순, 비교할 수 있었던 후보 수)."""
    scored = []
    for c in cards:
        f = fits.get(c.term_id)
        got = score(brief, f, c, tone) if f else None
        if got:
            scored.append((got[0], c, got[1], got[2]))
    scored.sort(key=lambda x: (-x[0], -x[1].mentions_4w, x[1].canonical))
    return scored, sum(1 for c in cards if c.term_id in fits)


_TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z]{3,}|[぀-ヿ一-鿿]{2,}")


# 뜻풀이에 흔히 나오지만 뜻을 가르지 못하는 말 — 이것만 겹쳐서는 '뜻에 기댄 이유' 가 아니다(검토 2차: 'the'·'used' 로 통과했다)
_STOP = {"the", "and", "for", "with", "that", "this", "from", "used", "use", "using", "when", "who", "what", "your", "you", "are", "was", "can",
         "like", "its", "just", "into", "about", "more", "most", "very", "also", "meme", "slang", "term", "word", "expression", "phrase",
         "internet", "online", "people", "someone", "something", "사용", "표현", "의미", "말이", "뜻이", "경우", "사람", "인터넷", "유행어", "쓰이", "쓰는"}


def _words(text: str) -> set[str]:
    """두 글자 이상 낱말의 앞 세 글자('귀여운'·'귀여움' 같은 활용을 한 낱말로), 흔한 말 제외."""
    return {w.lower()[:3] for w in _TOKEN.findall(text) if w.lower() not in _STOP and w.lower()[:3] not in _STOP}


def anchored(reason: str, meaning: str, canonical: str) -> bool:
    """이유가 사전 뜻에 기대고 있나 — 표제어 이름이 들어 있고, 뜻풀이의 낱말(흔한 말·표제어 자체는 빼고) 하나는 겹쳐야 한다.
    이름만 넣으면 통과하던 것을 막는다(검토 2차: 이름 + 지어낸 뜻이 그대로 나갔다). Plan 07 5번 '사전 뜻을 벗어난 이유는 버린다'."""
    if not reason.strip() or canonical.lower() not in reason.lower():
        return False
    body = reason.lower().replace(canonical.lower(), " ")
    return bool(_words(body) & (_words(meaning) - _words(canonical)))


class Unavailable(RuntimeError):
    """모델이 설정돼 있는데 지금 읽지 못했다(예산·장애). 예시로 대신하면 남의 제품으로 추천하게 되므로 오류로 알린다."""


def wrong_language(text: str, lang: str, canonical: str) -> bool:
    """화면 언어와 다른 말로 쓴 이유 — 밈 이름과 따옴표 안은 빼고 본다. 버리면 화면이 그 언어로 규칙 문장을 만든다."""
    body = re.sub(r"'[^']*'|\"[^\"]*\"|‘[^’]*’|“[^”]*”", "", text.replace(canonical, ""))
    hangul = len(re.findall(r"[가-힣]", body))
    latin = len(re.findall(r"[A-Za-z]", body))
    return hangul > latin if lang == "en" else latin > 3 * max(1, hangul)


def understand(con: Connection, text: str = "", image: tuple[bytes, str] | None = None, lang: str = "ko") -> tuple[ProductBrief, str]:
    """(제품 설명, 어디서 만들었나: gemini·local·sample). 모델이 아예 **설정되지 않은** 개발 환경만 고정 예시를 쓴다 —
    로컬 모델이 설정돼 있는데 꺼져 있으면 예시로 대신하지 않고 오류로 알린다(남의 제품으로 추천하지 않게, 검토 2차)."""
    if not (USE_LOCAL_GEMMA or configured()):
        return SAMPLE_BRIEF, "sample"
    what = ("제품 사진" + (" 과 홍보 문구" if text else "")) if image else "홍보 문구"
    prompt = BRIEF_PROMPT.format(what=what, text=f"홍보 문구: {text[:500]}" if text else "", lang="한국어" if lang == "ko" else "영어")
    try:
        parsed, model = structured(con, prompt, ProductBrief, image=image, request=True)
    except BudgetExhausted as e:
        raise Unavailable("오늘 사진·문구 읽기 한도를 다 썼습니다") from e
    except Exception as e:
        raise Unavailable("지금은 사진·문구를 읽지 못했습니다") from e
    if parsed is None:                 # Gemini 가 형식을 못 맞추면 parsed 가 비어 온다
        raise Unavailable("지금은 사진·문구를 읽지 못했습니다")
    brief = parsed if isinstance(parsed, ProductBrief) else ProductBrief.model_validate(parsed)
    return brief, "local" if model.startswith("local:") else "gemini"


def write_reasons(con: Connection, brief: ProductBrief, picked: list[tuple], lang: str, regions: list[str]) -> dict[str, str]:
    """{term_id: 이유}. 사전 뜻과 겹치지 않는 이유는 버린다. 모델이 없으면 빈 dict — 화면이 규칙 문장을 쓴다."""
    if not picked or not local_ok():
        return {}
    lines = []
    meanings: dict[int, str] = {}
    for i, (_, c, _, _) in enumerate(picked):
        m = ds.current_meaning(con, c.term_id)
        ko, en = ds.get_translation(con, c.term_id, "ko"), ds.get_translation(con, c.term_id, "en")
        # 이유가 기댈 뜻풀이 — 한국어판·영어판·원문을 모두 본다(영어로 쓴 이유가 한국어 뜻과만 비교돼 다 버려졌다)
        meaning = " ".join(x for t in (ko, en) if t for x in (t.definition, t.nuance)) + " " + (f"{m.definition} {m.nuance}" if m else "")
        meanings[i] = meaning
        shown = (en if lang == "en" else ko) or m
        lines.append(f"{i}. {c.canonical} — {'meaning' if lang == 'en' else '뜻'}: {(shown.definition if shown else '')[:140]}")
    try:
        parsed, _ = structured(con, REASON_PROMPT["en" if lang == "en" else "ko"].format(
            region=", ".join(regions), product=brief.product, scene=brief.scene or "-", values=", ".join(brief.values) or "-",
            items="\n".join(lines)), list[MemeReason], request=True)
    except Exception:
        return {}
    avoid = [a for a in brief.avoid if a]
    out = {}
    for r in parsed or []:
        if not 0 <= r.i < len(picked):
            continue
        c = picked[r.i][1]
        text = r.reason.strip()
        if (len(text) > 200 or any(a in text for a in avoid) or not anchored(text, meanings[r.i], c.canonical)
                or wrong_language(text, lang, c.canonical)):
            continue
        out[c.term_id] = text
    return out


def ready(con: Connection, regions: list[str]) -> int:
    """고른 지역에서 비교할 수 있는(쓰임 낱말이 붙은) 후보 수. 0 이면 사진·문구를 읽기 전에 알린다 — 모델 호출을 아낀다(검토 2차)."""
    fits = ds.all_fits(con)
    return sum(1 for c in dashboard.cards(con, regions) if c.term_id in fits)


def _links(con: Connection, c: KeywordCard) -> list:
    """추천마다 근거 링크 두 건. 고른 지역의 쓰임 근거가 없으면 모든 지역 것으로 — 링크 없는 추천을 내지 않는다(ADR 0001 근거 규칙)."""
    evs = [e for e in c.evidences if e.kind != "datalab"]
    if not evs and (everywhere := dashboard.card(con, c.term_id)):
        evs = [e for e in everywhere.evidences if e.kind != "datalab"]
    return evs[:2]


def recommend(con: Connection, brief: ProductBrief, brief_source: str, regions: list[str], tone: str, lang: str = "ko") -> RecommendResult:
    chosen = dashboard.chosen_regions(regions)
    cards = dashboard.cards(con, chosen)             # 표시 목록(30개씩)이 아니라 고른 지역의 모든 카드
    fits = {tid: f for tid, (_, f) in ds.all_fits(con).items()}
    scored, comparable = rank(brief, cards, fits, tone)
    picked = [p for p in scored if _links(con, p[1])][:TOP]      # 근거 링크가 없는 것은 추천하지 않는다
    reasons = write_reasons(con, brief, picked, lang, chosen)
    items = [RecommendItem(term_id=c.term_id, canonical=c.canonical, gloss_ko=c.gloss_ko, gloss_en=c.gloss_en, regions=c.regions,
                           diffusion=c.diffusion, lifecycle=c.lifecycle, risk_level=c.risk_level, risk_reasons=c.risk_reasons,
                           risk_checked_at=c.risk_checked_at, matched_category=cat, any_category=fits[c.term_id].any_category,
                           matched_feelings=feel, reason=reasons.get(c.term_id), score=round(s, 2), evidences=_links(con, c))
             for s, c, cat, feel in picked]
    return RecommendResult(brief=brief, brief_source=brief_source, regions=chosen, tone=tone, items=items,
                           considered=len(scored), untagged=len(cards) - comparable)


# 사진 입력 검사 — MIME 은 바이트 머리로 판단한다(업로드가 주장하는 Content-Type 은 믿지 않는다)
MAX_IMAGE = 5 * 1024 * 1024


def sniff_image(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class RateLimit:
    """인스턴스 하나의 분당 요청 수 제한 (Plan 07). 모델 두 번을 부르는 요청이라 한 사람이 예산을 다 쓰지 못하게."""

    def __init__(self, per_minute: int = 20):
        self.per_minute = per_minute
        self.hits: list[float] = []
        self.lock = threading.Lock()   # 동기 엔드포인트는 작업 스레드 여럿에서 동시에 돈다

    def allow(self, now: float) -> bool:
        with self.lock:
            self.hits = [t for t in self.hits if now - t < 60]
            if len(self.hits) >= self.per_minute:
                return False
            self.hits.append(now)
            return True

