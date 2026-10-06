"""시장별 포스터 시안 (Plan 20 — 한국·일본·미국 캠페인 초안).

1. 구성안  plan()      제품 설명(ProductBrief) + 고른 밈의 느낌·말투(MemeFit, 닫힌 낱말) + 시장 → 지시문      — 규칙(모델 없음)
2. 그림    generate()  지시문(+ 올린 제품 사진)으로 이미지 모델 한 번 → PNG·JPEG·WebP                        — pipeline/gemini.py 를 거친다

이미지에는 글자를 넣지 않는다. 포스터 문구는 카피 검사를 통과한 것을 화면이 그 위에 얹는다 — 모델이 그린 글자는 검사할 수 없고
철자도 틀린다. 밈 이름과 사람 이름은 지시문에 넣지 않는다: 밈 이름이 곧 실존 인물인 말이 있다('장원영 같다', 10-06).
밈은 이름이 아니라 fit 단계가 붙인 닫힌 낱말(느낌·말투)로만 그림에 들어간다. 사진은 메모리에서만 쓰고 저장·기록하지 않는다(ADR 0002 §4).
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from google.genai import types

from .. import model_client
from ..config import IMAGE_DAILY, IMAGE_MODEL
from ..schemas import MemeFit, ProductBrief
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from . import gemini
from .recommend import sniff_image
from .views import PosterPlan

IMAGE_LEDGER = "img:"     # 이미지 생성 장부 — 이용자 요청 장부(req:)와 같은 표에 따로 센다
MARKETS = {"KR": "South Korea", "JP": "Japan", "US": "the United States"}
ASPECT = "4:5"            # 인스타그램 세로 피드

# 닫힌 낱말 → 그림의 분위기. 밈 이름 대신 이것만 지시문에 들어간다
FEELING_MOOD = {
    "joy": "bright and cheerful", "hype": "energetic and dynamic", "cute": "soft and cute", "funny": "playful and lighthearted",
    "relatable": "everyday and familiar", "comfort": "cozy and calm", "pride": "confident and bold", "surprise": "unexpected and vivid",
    "sarcasm": "dry and witty", "frustration": "tense, high-contrast", "tired": "slow and relaxed", "romance": "warm and romantic",
    "nostalgia": "nostalgic, retro", "cool": "cool and sleek",
}
VOICE_STYLE = {"wholesome": "friendly, clean styling", "playful": "fun, casual styling", "edgy": "bold, graphic styling"}  # crude 는 넣지 않는다
MARKET_LOOK = {   # 시장마다 광고 사진의 흔한 결 — 인물·문화 상징(국기·전통 의상 등) 없이 화면 구성만
    "KR": "clean, bright social-media product shot with soft daylight",
    "JP": "airy, minimal print-ad composition with gentle natural light",
    "US": "bold, high-contrast lifestyle ad composition",
}

RULES = (
    ("Do not put any text, letters, words, numbers, logos or watermarks anywhere in the image. Leave clean empty space in the upper third "
     "for a headline that will be added later."),
    "Do not show any people: no real persons, no celebrities, no faces, hands or bodies.",
    "Do not draw meme characters, mascots, cartoon characters or any copyrighted or trademarked characters.",
)


class NotConfigured(RuntimeError):
    """IMAGE_BACKEND=off(기본) 이거나 접속 설정이 비어 있다. 화면은 구성안만 보인다."""


class Unavailable(RuntimeError):
    """설정은 돼 있는데 지금 만들지 못했다(하루 한도·장애·그림 없는 응답)."""


def enabled() -> bool:
    return model_client.image_requests_enabled()


def _names(memes: Sequence[tuple[Sequence[str], MemeFit | None]]) -> list[str]:
    """지울 이름: 밈 표제어·별칭과 그 낱말(두 글자 이상) — '장원영 같다' 의 '장원영' 이 제품 설명에 따로 나와도 지운다. 긴 것부터."""
    out: set[str] = set()
    for names, _ in memes:
        for n in names:
            n = (n or "").strip()
            if n:
                out.add(n)
                out.update(w for w in re.split(r"\s+", n) if len(w) >= 2)
    return sorted(out, key=len, reverse=True)


def _scrub(text: str, names: list[str]) -> str:
    for n in names:
        text = re.sub(re.escape(n), " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" ,·")


def plan(brief: ProductBrief, market: str, memes: Sequence[tuple[Sequence[str], MemeFit | None]] = ()) -> PosterPlan:
    """구성안과 지시문. 모두 규칙이다 — 같은 입력이면 같은 지시문. memes 는 [(표제어·별칭, MemeFit 또는 None)]: 이름은 지우는 데만 쓰고(낱말이 아직 없는 밈도 이름은 지운다),
    그림에는 느낌·말투만 간다. 고른 밈이 없거나 느낌이 비면 제품 설명의 느낌으로."""
    if market not in MARKETS:
        raise ValueError("시장은 KR·JP·US 가운데 하나입니다")
    names = _names(memes)
    feelings = list(dict.fromkeys(f for _, fit in memes if fit for f in fit.feelings)) or list(brief.feelings)
    voices = list(dict.fromkeys(fit.voice for _, fit in memes if fit and fit.voice in VOICE_STYLE))
    mood = [FEELING_MOOD[f] for f in feelings if f in FEELING_MOOD][:3] + [VOICE_STYLE[v] for v in voices][:1]
    product = _scrub(brief.product, names)
    scene = _scrub(brief.scene, names)
    colors = [c for c in (_scrub(c, names) for c in brief.colors) if c][:3]
    values = [v for v in (_scrub(v, names) for v in brief.values) if v][:3]
    avoid = [a for a in (_scrub(a, names) for a in brief.avoid) if a][:3]
    lines = [
        f"Create a promotional poster image for a product campaign in {MARKETS[market]}, aspect ratio {ASPECT}.",
        f"Product: {product}." if product else "Product: the product in the attached photo.",
        ("If a product photo is attached, keep that product exactly as it is – same shape, label, colors and proportions; do not redraw, "
         "restyle, replace or cover it. Change only the background, lighting, mood, color palette and composition around it."),
        f"Look: {MARKET_LOOK[market]}.",
    ]
    if scene:
        lines.append(f"Setting: {scene}.")
    if mood:
        lines.append(f"Mood: {', '.join(mood)}.")
    if values:
        lines.append(f"Convey: {', '.join(values)}.")
    if colors:
        lines.append(f"Color palette: {', '.join(colors)}.")
    if avoid:
        lines.append(f"Avoid themes: {', '.join(avoid)}.")
    lines += [f"Rule: {r}" for r in RULES]
    return PosterPlan(market=market, product=product, scene=scene, mood=mood, colors=colors, aspect_ratio=ASPECT, prompt="\n".join(lines))  # type: ignore[arg-type]


def generate(con: Connection, poster: PosterPlan, photo: bytes | None = None) -> list[bytes]:
    """이미지 모델 한 번 → 그림 바이트 목록(PNG·JPEG·WebP). pipeline/gemini.py 의 generate 로 부른다(이용자 요청 장부·금액 상한·호출 기록).
    그와 따로 하루 IMAGE_DAILY 회의 이미지 장부를 센다. 사진은 Part 로만 넘기고 파일로 쓰지 않는다. 결과도 저장하지 않는다.
    문구는 그리지 않는다 — 검사한 문구는 화면이 얹는다."""
    if not enabled():
        raise NotConfigured("이미지 생성이 꺼져 있습니다(IMAGE_BACKEND)")
    if ds.gemini_budget_left(con, IMAGE_DAILY, IMAGE_LEDGER) <= 0:
        raise Unavailable("오늘 포스터 시안 한도를 다 썼습니다")
    contents: list = []
    if photo:
        mime = sniff_image(photo)
        if not mime:
            raise ValueError("JPEG·PNG·WebP 사진만 받습니다")
        contents.append(types.Part.from_bytes(data=photo, mime_type=mime))
    contents.append(poster.prompt)
    cfg = types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio=poster.aspect_ratio))
    ds.gemini_spend(con, 1, IMAGE_LEDGER)      # 먼저 잡아 둔다 — 동시에 온 요청이 함께 한도를 넘지 않게. 보내지 못했거나 거절되면 돌려놓는다
    try:
        resp, _ = gemini.generate(con, contents, cfg, model=IMAGE_MODEL, allow_fallback=False, allow_local=False, request=True,
                                  make_client=model_client.image_client)
    except model_client.ModelRequestsDisabled as e:
        ds.gemini_spend(con, -1, IMAGE_LEDGER)
        raise NotConfigured("이미지 생성이 꺼져 있습니다(IMAGE_BACKEND)") from e
    except gemini.BudgetExhausted as e:
        ds.gemini_spend(con, -1, IMAGE_LEDGER)
        raise Unavailable("오늘 포스터 시안 한도를 다 썼습니다") from e
    except Exception as e:
        ds.gemini_spend(con, -1, IMAGE_LEDGER)
        raise Unavailable("지금은 포스터 시안을 만들지 못했습니다") from e
    images = [p.inline_data.data for c in (resp.candidates or []) for p in ((c.content.parts if c.content else None) or [])
              if p.inline_data and sniff_image(p.inline_data.data or b"")]      # 모델이 JPEG 로 줄 수도 있다 — 그림이면 받는다
    if not images:          # 응답은 왔다(과금됐다) — 장부는 그대로 둔다
        raise Unavailable("지금은 포스터 시안을 만들지 못했습니다")
    return images
