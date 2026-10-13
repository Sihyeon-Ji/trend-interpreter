"""사진·홍보 문구로 밈 추천 (Plan 07, 사용 흐름 2단계 '추천받기').

1. 이해   사진 또는 문구 → ProductBrief. 요청 때 부르는 모델은 이것 한 번(Gemini. 모델이 아예 없는 개발 환경은 고정 예시)
2. 후보   고른 지역의 확인된 표제어(대시보드 카드) 가운데 사용 자제·저속한 말투를 뺀다        — 규칙
3. 순위   분야·느낌 겹침(fit 단계가 미리 붙인 닫힌 낱말) + 퍼진 정도·생애주기·리스크 가감      — 규칙
4. 이유   모델이 쓰지 않는다. 게시된 사전 뜻, 그 나라에서의 쓰임(topics 단계의 국가별 해석), 점수의 근거(겹친 분야·느낌)로
          화면이 구성한다 — 요청마다 개발자 PC 의 Gemma 에 기대지 않는다(ADR 0002 §3, 2026-09-28 Gemma 로컬 편집 결정).
          예전에는 이유 한 문장을 모델에게 따로 받았는데, 뜻과 상관없는 광고 문구가 낱말 겹침 검사를 쉽게 통과했다(검토 3차: 145개 중 79개).
사진은 메모리에서만 쓰고 저장·기록하지 않는다(ADR 0002 §4).
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone

from ..collectors.community import is_community_post
from ..config import USE_LOCAL_GEMMA
from ..schemas import MemeFit, ProductBrief, Text2
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from . import dashboard
from .risk import sensitive_topic
from .gemini import BudgetExhausted, configured, structured
from .generate import REGION_LANG, in_ui_language, relanguage, writable
from .views import ExcludedItem, KeywordCard, RecommendItem, RecommendResult
from ..ui_lang import NAME_KO, rule

TOP = 5
EXCLUDED_PER_REGION = 4   # 만들기 화면의 '뺀 말' — 시장마다 이만큼
MIN_FIT = 2          # 분야(3)나 느낌 하나(2)는 맞아야 추천한다 — 모자라면 채우지 않는다
NICHE_OK = {"entertainment", "game"}   # 특정 작품·팬덤 안에서만 통하는 밈을 권하는 제품 분야
MIN_SCORE = 2.0      # 퍼진 정도·생애주기·리스크를 더한 뒤에도 이만큼은 돼야 한다(잠잠한 밈이 -0.5 로 추천되던 것을 막는다)
# 톤마다 허용하는 말투와 반기는 느낌. '고급스러움' 은 장난스러운 말도 뺀다.
TONES: dict[str, tuple[set[str], set[str]]] = {
    "friendly": ({"wholesome", "playful"}, {"joy", "cute", "relatable", "comfort"}),
    "witty": ({"wholesome", "playful", "edgy"}, {"funny", "sarcasm", "relatable", "surprise"}),
    "premium": ({"wholesome"}, {"cool", "pride", "romance", "nostalgia"}),
}
DIFFUSION_BONUS = {"spreading": 2.0, "underground": 1.0, "mainstream": 0.5, "fading": -2.0}
LIFECYCLE_BONUS = {"emerging": 1.0, "rising": 1.0, "peak": 0.5, "declining": -1.0, "dormant": -3.0}
POPULARITY_WEIGHT = 0.5  # 퍼진 정도·생애주기는 순위를 가르는 보조 — 제품과 맞는 정도(분야 3·느낌 2)를 넘지 않게. 1.0 이면 몇 개가 모든 제품의 윗줄을 차지했다(09-30)

# 모델이 없는 개발 환경의 고정 설명 (Plan 07: 화면과 e2e 가 모델 없이 끝까지 돌게)
SAMPLE_BRIEF = ProductBrief(product="여름 한정 아이스 흑당 라떼", category="food_drink", feelings=["joy", "relatable", "comfort"],
                            values=["시원함", "달콤함", "여름 한정"], scene="더운 오후 카페에서 한숨 돌릴 때", colors=["갈색", "흰색"], avoid=[])

BRIEF_PROMPT = """너는 광고 기획자다. 아래 {what}을 보고 제품을 설명하라. 추측이 필요하면 흔한 쪽으로 하되, 보이지 않는 성분·효능을 지어내지 마라.
category 는 food_drink · fashion_beauty · tech · game · entertainment · travel · finance · health_fitness · education · lifestyle 가운데 하나.
feelings 는 이 홍보가 전하고 싶은 느낌 1~3개를 joy · hype · cute · funny · relatable · comfort · pride · surprise · sarcasm · frustration · tired ·
romance · nostalgia · cool 가운데서. 브랜드가 피해야 할 표현·주제가 보이면 avoid 에. 글(product·values·scene·colors·avoid)은 {lang}로.
{lang_rule}{text}"""

def blocked(fit: MemeFit, card: KeywordCard, tone: str) -> str | None:
    """제품과 상관없이 권하지 않는 이유(ExcludedItem.code) — 없으면 None. 화면의 '뺀 말' 이 이 값을 그대로 보인다."""
    if card.risk_level == "avoid":
        return "avoid"
    if fit.voice == "crude":
        return "crude"
    if fit.voice not in TONES[tone][0]:
        return "tone"
    # 식어 가는 밈(대시보드와 같은 기준)과, 리스크를 아직 판단하지 않았는데 민감한 소재(자살·정치 등)인 밈은 권하지 않는다 —
    # 라떼 광고에 저메추·점메추(줄어드는 중)와 '죽고 싶지만 떡볶이는 먹고 싶어'(판단 전)가 들었다(실데이터 10-04)
    if dashboard._is_fading(card, datetime.now(timezone.utc)):
        return "fading"
    if card.risk_level is None and sensitive_topic(f"{card.canonical} {card.gloss_ko}"):
        return "sensitive"
    return None


def related(brief: ProductBrief, fit: MemeFit) -> bool:
    """제품과 이어지는 데가 있나 — 분야가 맞거나, 어디에나 쓰는 반응이거나, 느낌이 하나라도 겹친다. '뺀 말' 에는 이런 것만 보인다
    (제품과 아무 상관 없는 수백 개를 '뺐다' 고 늘어놓지 않게)."""
    return brief.category in fit.fits or fit.any_category or any(f in fit.feelings for f in brief.feelings)


def score(brief: ProductBrief, fit: MemeFit, card: KeywordCard, tone: str) -> tuple[float, bool, list[str]] | None:
    """(점수, 분야가 맞았나, 겹친 느낌). 추천하면 안 되는 것은 None. 모든 판단이 규칙이다."""
    _, liked = TONES[tone]
    if blocked(fit, card, tone):
        return None
    if fit.kind == "topic":
        return None                   # 밈의 소재(인물·작품·노래)는 이름만으로 밈이 아니다 — 밈 여부 라벨에서 화면 첫 쪽의 1/4(10-09)
    if fit.audience == "niche" and brief.category not in NICHE_OK:
        return None                   # 서브컬처 캐릭터 밈(いまいち萌えない娘)이 화장품·러닝화에 나왔다(사람 판정 10-09)
    cat = brief.category in fit.fits
    if fit.kind == "word" and not cat:
        return None                   # 일반 낱말은 그 분야 제품에만 — lol·xD 가 라떼 카피 끝마다 붙어 못 쓸 카피가 됐다(FOMO 는 금융에, 10-09 판정)
    if fit.fits and not cat and not fit.any_category:
        return None                   # 분야가 정해진 밈은 그 분야 제품에만(팬덤 말 推し活 을 카드 광고에 — 09-30 실측)
    shared = [f for f in brief.feelings if f in fit.feelings][:3]
    if not cat and not fit.any_category and len(shared) < 2:
        return None                   # 분야도 없고 어디에나 쓰는 반응도 아니면 느낌이 둘은 겹쳐야 한다
    rel = (3 if cat else 1 if fit.any_category else 0) + 2 * len(shared)
    if rel < MIN_FIT:
        return None
    s = rel + sum(1 for f in shared if f in liked)          # 톤이 반기는 느낌은 제품과 겹친 것만 — 제품과 무관한 가산이 순위를 정하지 않게
    s += POPULARITY_WEIGHT * (DIFFUSION_BONUS.get(card.diffusion or "", 0.0) + LIFECYCLE_BONUS.get(card.lifecycle, 0.0))
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


class Unavailable(RuntimeError):
    """모델이 설정돼 있는데 지금 읽지 못했다(예산·장애). 예시로 대신하면 남의 제품으로 추천하게 되므로 오류로 알린다."""


def understand(con: Connection, text: str = "", image: tuple[bytes, str] | None = None, lang: str = "ko") -> tuple[ProductBrief, str]:
    """(제품 설명, 어디서 만들었나: gemini·local·sample). 모델이 아예 **설정되지 않은** 개발 환경만 고정 예시를 쓴다 —
    로컬 모델이 설정돼 있는데 꺼져 있으면 예시로 대신하지 않고 오류로 알린다(남의 제품으로 추천하지 않게, 검토 2차)."""
    if not (USE_LOCAL_GEMMA or configured()):
        return SAMPLE_BRIEF, "sample"
    # 같은 입력은 처음 읽은 결과를 다시 쓴다 — 같은 문구라도 실행마다 느낌 태그가 달라져 추천이 바뀌었다(10-09: 러닝화가 '편안함·공감' →
    # '편안함·멋짐' 이 되자 '인정' 이 빠졌다). 키는 입력의 해시뿐이라 원문을 남기지 않고, 이용자 입력 표(explain_cache)에 두어 7일 뒤 지운다
    key = "brief:" + hashlib.sha256(lang.encode() + b"\0" + text[:500].encode() + b"\0" + (image[0] if image else b"")).hexdigest()
    if (hit := ds.brief_cache_get(con, key)):
        cached = json.loads(hit)
        return ProductBrief.model_validate(cached["brief"]), cached["source"]
    what = ("제품 사진" + (" 과 홍보 문구" if text else "")) if image else "홍보 문구"
    prompt = BRIEF_PROMPT.format(what=what, text=f"홍보 문구: {text[:500]}" if text else "", lang=NAME_KO.get(lang, "한국어"),
                                lang_rule=rule(lang, "product・values・scene・colors・avoid") if lang == "ja" else "")
    try:
        # 요청 때의 사진·문구 이해는 Gemini 가 맡는다(2026-09-28 결정). 로컬 Gemma 는 Gemini 가 없는 개발 PC 에서만
        parsed, model = structured(con, prompt, ProductBrief, image=image, prefer_gemini=True, request=True)
    except BudgetExhausted as e:
        raise Unavailable("오늘 사진·문구 읽기 한도를 다 썼습니다") from e
    except Exception as e:
        raise Unavailable("지금은 사진·문구를 읽지 못했습니다") from e
    if parsed is None:                 # Gemini 가 형식을 못 맞추면 parsed 가 비어 온다
        raise Unavailable("지금은 사진·문구를 읽지 못했습니다")
    brief = parsed if isinstance(parsed, ProductBrief) else ProductBrief.model_validate(parsed)
    if lang != "ko":   # 화면 언어가 아닌 칸만 옮긴다 — 영어로 넣은 제품의 요약이 일본어 화면에 한국어로 나왔다(10-13 시험, Flash Lite)
        slots = [("product", None), ("scene", None)] + [("values", i) for i in range(len(brief.values))]
        texts = [getattr(brief, f) if i is None else brief.values[i] for f, i in slots]
        bad = [k for k, x in enumerate(texts) if x and not in_ui_language(x, lang, [])]
        got = relanguage(con, [texts[k] for k in bad], lang, []) if bad else None
        for k, new in zip(bad, got or []):
            if new:
                f, i = slots[k]
                if i is None:
                    setattr(brief, f, new)
                else:
                    brief.values[i] = new
    source = "local" if model.startswith("local:") else "gemini"
    ds.brief_cache_set(con, key, json.dumps({"brief": brief.model_dump(), "source": source}, ensure_ascii=False))
    return brief, source


def ready(con: Connection, regions: list[str]) -> int:
    """고른 지역에서 비교할 수 있는(쓰임 낱말이 붙은) 후보 수. 0 이면 사진·문구를 읽기 전에 알린다 — 모델 호출을 아낀다(검토 2차)."""
    fits = ds.all_fits(con)
    return sum(1 for c in dashboard.cards(con, regions) if c.term_id in fits)


def _links(con: Connection, c: KeywordCard) -> list:
    """추천마다 근거 링크 두 건 — 쓰임 글(뉴스·쇼츠)이 먼저, 설명 문서는 그다음. 커뮤니티·SNS 글은 링크로 내지 않는다(ADR 0003).
    같은 주소는 한 번만 (위키백과 문서가 web·wiki 로 두 번 들어와 같은 링크가 둘 나왔다, 검토 3차). 고른 지역의 근거가 없으면
    모든 지역 것으로 — 링크 없는 추천을 내지 않는다(ADR 0001 근거 규칙)."""
    def pick(evs):
        seen: set[str] = set()
        out = [e for e in sorted((e for e in evs if e.kind != "datalab" and not is_community_post(e)), key=lambda e: e.kind not in dashboard.USAGE_KINDS)
               if not (e.url in seen or seen.add(e.url))]
        return out[:2]

    got = pick(c.evidences)
    if not got and (everywhere := dashboard.card(con, c.term_id)):
        got = pick(everywhere.evidences)
    return got


def local_context(con: Connection, term_id: str, chosen: list[str]) -> tuple[str, Text2] | None:
    """고른 나라 가운데 이 밈의 국가별 해석이 있는 첫 나라와 '그 나라에서는 무엇이 달라졌나'. 국가별 해석은 파이프라인(topics 단계)이
    근거로 미리 써 둔 것이고 확신 0.5 이상만 쓴다(지도 보드와 같은 기준). 요청 때 모델을 부르지 않는다."""
    notes = ds.get_topic_notes(con, term_id)
    for r in chosen:
        n = notes.get(r)
        if n and n.get("self_confidence", 0) >= 0.5 and n.get("what_changed"):
            return r, Text2(**n["what_changed"])
    return None


def recommend(con: Connection, brief: ProductBrief, brief_source: str, regions: list[str], tone: str, pin: str | None = None) -> RecommendResult:
    """순위와 이유의 재료는 모두 저장된 데이터와 규칙이다 — 이 함수는 모델을 부르지 않는다.
    pin 은 사전 항목에서 사람이 먼저 고른 밈 — 순위(TOP) 밖이어도 목록 끝에 넣는다. 고른 지역의 카드가 아니거나 사용 자제·저속한 말투이거나
    근거 링크가 없으면 넣지 않는다(순위 규칙의 문턱만 건너뛴다)."""
    chosen = dashboard.chosen_regions(regions)
    cards = dashboard.cards(con, chosen)             # 표시 목록(30개씩)이 아니라 고른 지역의 모든 카드
    fits = {tid: f for tid, (_, f) in ds.all_fits(con).items()}
    scored, comparable = rank(brief, cards, fits, tone)
    # 시장마다 그 시장 말로 쓸 수 있는 것 가운데 상위 TOP 개씩(근거 링크가 없는 것은 추천하지 않는다). 셋을 통틀어 TOP 개만 뽑으면
    # 언급이 많은 한국 말이 다 차지해 일본·영어권이 늘 비었다(10-06 실데이터, 만들기 화면)
    def writes(c, r: str) -> bool:
        t = ds.get_term(con, c.term_id)
        return bool(t) and r in REGION_LANG and writable(t, r, dashboard.regions_for(con, t))     # 아래 write_regions 와 같은 값

    linked = [p for p in scored if _links(con, p[1])]
    picked = []
    for r in chosen:
        picked += [p for p in linked if r in p[1].regions and writes(p[1], r) and p not in picked][:TOP]
    picked.sort(key=lambda p: (-p[0], -p[1].mentions_4w, p[1].canonical))
    if pin and all(c.term_id != pin for _, c, _, _ in picked):
        card = next((c for c in cards if c.term_id == pin), None)
        fit = fits.get(pin)
        if card and card.risk_level != "avoid" and not (fit and fit.voice == "crude") and _links(con, card):
            got = next((p for p in scored if p[1].term_id == pin), None)
            picked.append(got or (0.0, card, False, []))
    items = []
    for s, c, cat, feel in picked:
        ctx = local_context(con, c.term_id, chosen)
        term = ds.get_term(con, c.term_id)
        regions = dashboard.regions_for(con, term) if term else []     # 만들기(generate.run)와 같은 값 — 대시보드·사전 항목과 같은 규칙
        items.append(RecommendItem(term_id=c.term_id, canonical=c.canonical, lang=c.lang, gloss_ko=c.gloss_ko, gloss_en=c.gloss_en, en_pending=c.en_pending, ko_pending=c.ko_pending,
                                   gloss_ja=c.gloss_ja, ja_pending=c.ja_pending, readings=c.readings, names=c.names, regions=c.regions,
                                   diffusion=c.diffusion, lifecycle=c.lifecycle, risk_level=c.risk_level, risk_reasons=c.risk_reasons,
                                   risk_checked_at=c.risk_checked_at, matched_category=cat,
                                   any_category=bool(fits.get(c.term_id) and fits[c.term_id].any_category),
                                   matched_feelings=feel, local_region=ctx[0] if ctx else None, local_note=ctx[1] if ctx else None,
                                   write_regions=[r for r in chosen if r in REGION_LANG and term and writable(term, r, regions)],
                                   score=round(s, 2), evidences=_links(con, c), pinned=c.term_id == pin))
    # 뺀 말 — 제품과 이어지는데 규칙이 막은 것(만들기 화면의 '뺀 말', Plan 20). 시장마다 언급이 많은 것부터 몇 개만
    shown = {i.term_id for i in items}
    excluded = sorted(((code, c) for c in cards if c.term_id not in shown and (f := fits.get(c.term_id)) and related(brief, f)
                       and (code := blocked(f, c, tone))), key=lambda x: (-x[1].mentions_4w, x[1].canonical))
    out: list[ExcludedItem] = []
    for r in chosen:
        out += [ExcludedItem(term_id=c.term_id, canonical=c.canonical, lang=c.lang, regions=c.regions, code=code)  # type: ignore[arg-type]
                for code, c in excluded if r in c.regions and all(o.term_id != c.term_id for o in out)][:EXCLUDED_PER_REGION]
    return RecommendResult(brief=brief, brief_source=brief_source, regions=chosen, tone=tone, items=items,
                           considered=len(scored), untagged=len(cards) - comparable, excluded=out,
                           pool={r: sum(1 for c in cards if r in c.regions) for r in chosen},
                           considered_by_region={r: sum(1 for _, c, _, _ in scored if r in c.regions) for r in chosen})


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

