"""Gemini 가 쇼츠를 YouTube URL 로 직접 보고 구조화된 해석을 낸다.

- 영상 다운로드 없음. 공개(public) 영상만 가능. 프리뷰 기능, 현재 무료.
- 무료 티어: 하루 8시간 분량. 요청당 최대 10개 영상(Gemini 2.5+).
- 토큰: 기본 해상도 ≈ 100 tok/초 → 60초 쇼츠 ≈ 6k 토큰. low 해상도로 더 줄인다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from google.genai import types

from ..config import GEMINI_MODEL
from .. import model_client
from ..schemas import ShortsInterpretation

PROMPT = """You are a cross-generational, cross-cultural trend interpreter covering every country and language.
Watch each YouTube Short carefully: visuals, on-screen text, audio, captions, comments style.
For EACH video, in the same order as given, return one object:
- url: the exact URL given
- language: main spoken/written language (ISO code)
- summary: what literally happens, 2 sentences
- memes: every slang term, meme format, song, drama/anime reference, dance or news event used.
  For each: kind, origin_hypothesis (where/when it started; be specific or say 'unknown'), confidence 0-1.
  quote: the exact line spoken, sung or shown on screen where it appears, in the original language, under 120 characters.
  Transcribe only what is actually said or shown; use '' if it is not said or shown.
- target_generation: which age groups this is made for / resonates with
- why_viral: the mechanism (relatability, remix, shock, nostalgia, in-group signal...)
- explain_for_outsider: explain the context to someone from another generation or country, 3-4 sentences.
  Write it in Korean for now (the product will use the reader's language); keep original-language terms as-is with a gloss.
- risk_flags: reasons a brand or public institution should NOT casually reuse this expression
  (mockery of a group, politics, slur origin, already dying trend...). Empty list if none.
Be honest about uncertainty. Never invent origins."""


@dataclass
class InterpretResult:
    items: list[ShortsInterpretation] = field(default_factory=list)
    dropped: int = 0  # 어느 영상인지 붙일 수 없어 버린 해석 수
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


_client = model_client.client


def interpret_shorts(urls: list[str], model: str = GEMINI_MODEL, low_res: bool = True) -> InterpretResult:
    """urls 1~10개를 요청 하나로 보낸다."""
    if not 1 <= len(urls) <= 10:
        raise ValueError("요청당 1~10개 URL")
    parts = [types.Part(file_data=types.FileData(file_uri=u)) for u in urls]
    parts.append(types.Part(text=PROMPT))
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=list[ShortsInterpretation],
        temperature=0.2,
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW if low_res else None,
    )
    resp = _client().models.generate_content(
        model=model, contents=types.Content(role="user", parts=parts), config=cfg
    )
    parsed = resp.parsed or []
    items = [p if isinstance(p, ShortsInterpretation) else ShortsInterpretation.model_validate(p) for p in parsed]
    items, dropped = _attribute(items, urls)
    um = resp.usage_metadata
    return InterpretResult(
        items=items,
        dropped=dropped,
        input_tokens=getattr(um, "prompt_token_count", 0) or 0,
        output_tokens=getattr(um, "candidates_token_count", 0) or 0,
        model=model,
    )


def video_id(url: str) -> str:
    """YouTube URL 에서 영상 id. storage.save_interpretations 와 같은 규칙."""
    return url.split("v=")[-1].split("&")[0].split("/")[-1]


def _attribute(items: list[ShortsInterpretation], urls: list[str]) -> tuple[list[ShortsInterpretation], int]:
    """해석을 실제 입력 영상에 붙인다. 어느 영상인지 알 수 없는 항목은 버린다.

    모델이 url 필드를 지어낸다("…/shorts/example", "video1" 실측). 개수가 같으면 순서가 곧 대응이라 입력 URL 로 덮어쓰고,
    개수가 다르면 순서를 믿을 수 없으므로 모델이 돌려준 id 가 입력 중에 있는 것만 남긴다. 2026-09-16 실사고: 8개를 보내고
    7개가 돌아와 순서 매핑이 건너뛰어졌고 'video1'~'video6' 으로 저장돼, 영상과 연결되지 않는 해석과 가짜 인용 링크가 생겼다."""
    if len(items) == len(urls):
        for it, u in zip(items, urls):
            it.url = u
        return items, 0
    by_id = {video_id(u): u for u in urls}
    kept = []
    for it in items:
        u = by_id.get(video_id(it.url))
        if u:
            it.url = u
            kept.append(it)
    return kept, len(items) - len(kept)
