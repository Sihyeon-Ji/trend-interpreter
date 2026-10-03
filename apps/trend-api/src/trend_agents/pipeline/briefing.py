"""트렌드 브리핑 — 고른 지역의 대시보드를 마케터가 들고 갈 한 장으로. 목록과 건수는 대시보드 규칙(dashboard.split)을 그대로 쓰고,
요약 문장만 모델이 쓴다. 모델은 아래에서 넘긴 이름·건수만 보고 쓰며, 판정(써도 됨·조심·자제)을 바꾸지 않는다.

  지금 써도 되는 밈   지금 쓰이는 밈 가운데 리스크 '없음'
  조심해서 쓸 밈      지금 쓰이는 밈 가운데 '주의'
  쓰지 말 밈          사용 자제
  식어 가는 밈        대시보드의 식어 가는 밈

요약은 대시보드 갱신 시각·지역·화면 언어마다 한 번만 만든다(같은 보고서를 다시 열 때 모델을 부르지 않는다).
"""
from __future__ import annotations

import threading
from datetime import datetime

from pydantic import BaseModel

from ..config import USE_LOCAL_GEMMA
from ..storage.db import Connection
from . import dashboard
from .gemini import configured, structured
from .views import Briefing, BriefingCounts, KeywordCard

BRIEF_TOP = 5
CACHE_MAX = 64

REGION_NAME = {
    "ko": {"KR": "한국", "JP": "일본", "TW": "대만", "HK": "홍콩", "TH": "태국", "VN": "베트남", "ID": "인도네시아", "PH": "필리핀",
           "MY": "말레이시아", "SG": "싱가포르", "GLOBAL": "글로벌"},
    "en": {"KR": "Korea", "JP": "Japan", "TW": "Taiwan", "HK": "Hong Kong", "TH": "Thailand", "VN": "Vietnam", "ID": "Indonesia",
           "PH": "the Philippines", "MY": "Malaysia", "SG": "Singapore", "GLOBAL": "global"},
}

PROMPT = """너는 브랜드 마케터에게 이번 주 밈 트렌드를 알려 주는 편집자다. 아래 사실만으로 {lang} 2~3문장 요약을 써라.
- 숫자와 밈 이름은 그대로 쓰고, 아래에 없는 밈·숫자·사건을 지어내지 않는다.
- 각 밈이 어느 목록에 있는지(써도 됨·조심·쓰지 말 것·식어 감)를 바꾸지 않는다. '안전하다' 고 단정하지 않는다.
- 제목·목록·따옴표·이모지 없이 문장만.

지역: {regions}
지금 쓰이는 밈 {rising}개 가운데 리스크 문제가 없는 밈 {use_now}개, 조심해서 쓸 밈 {careful}개, 근거가 부족해 판단을 미룬 밈 {undecided}개.
쓰지 말 밈 {avoid}개, 식어 가는 밈 {fading}개.
지금 써도 되는 밈(앞에서부터): {use_names}
조심해서 쓸 밈: {careful_names}
쓰지 말 밈: {avoid_names}
식어 가는 밈: {fading_names}"""


class BriefingText(BaseModel):
    text: str


_cache: dict[tuple, tuple[str, str]] = {}
_lock = threading.Lock()


def build(con: Connection, regions: list[str] | None) -> Briefing:
    """목록·건수만 (모델 없이). 지역이 없거나 모르는 값뿐이면 목표 지역 전체 — 대시보드와 같다."""
    stored, generated_at = dashboard._loaded(con)
    chosen = dashboard.chosen_regions(regions)
    picked = [dashboard.view(s, chosen) for s in stored if set(s.card.regions) & set(chosen)]
    rising, fading, caution = dashboard.split(picked, generated_at)
    use_now = [c for c in rising if c.risk_level == "none"]
    careful = [c for c in rising if c.risk_level == "caution"]
    avoid = [c for c in caution if c.risk_level == "avoid"]
    counts = BriefingCounts(rising=len(rising), use_now=len(use_now), careful=len(careful),
                            undecided=sum(1 for c in rising if c.risk_level is None), avoid=len(avoid), fading=len(fading))
    return Briefing(generated_at=generated_at, regions=chosen, counts=counts, use_now=use_now[:BRIEF_TOP], careful=careful[:BRIEF_TOP],
                    avoid=avoid[:BRIEF_TOP], fading=fading[:BRIEF_TOP])


def model_ready() -> bool:
    return bool(USE_LOCAL_GEMMA or configured())


def _names(cards: list[KeywordCard]) -> str:
    return ", ".join(c.canonical for c in cards) or "없음"


def _key(b: Briefing, lang: str) -> tuple:
    stamp = b.generated_at.isoformat() if isinstance(b.generated_at, datetime) else str(b.generated_at)
    return (tuple(b.regions), lang, stamp)


def cached(b: Briefing, lang: str) -> tuple[str, str] | None:
    with _lock:
        return _cache.get(_key(b, lang))


def summarize(con: Connection, b: Briefing, lang: str) -> tuple[str, str]:
    """(요약, gemini·local). 실패하면 예외 — 부르는 쪽이 규칙 문장으로 대신한다. 모델이 설정되지 않았으면 부르지 않는다(부르는 쪽 책임)."""
    names = REGION_NAME["en" if lang == "en" else "ko"]
    c = b.counts
    prompt = PROMPT.format(lang="영어로" if lang == "en" else "한국어로", regions=", ".join(names.get(r, r) for r in b.regions),
                           rising=c.rising, use_now=c.use_now, careful=c.careful, undecided=c.undecided, avoid=c.avoid, fading=c.fading,
                           use_names=_names(b.use_now), careful_names=_names(b.careful), avoid_names=_names(b.avoid),
                           fading_names=_names(b.fading))
    parsed, model = structured(con, prompt, BriefingText, prefer_gemini=True, request=True)
    text = " ".join(((parsed.text if isinstance(parsed, BriefingText) else BriefingText.model_validate(parsed).text) or "").split())[:600]
    if not text:
        raise ValueError("빈 요약")
    out = (text, "local" if model.startswith("local:") else "gemini")
    with _lock:
        if len(_cache) >= CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[_key(b, lang)] = out
    return out
