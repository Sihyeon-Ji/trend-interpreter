"""카피 검사 — 마케터가 쓴 문구에 든 밈을 사전으로 찾아, 고른 시장에서 써도 되는지 규칙으로 알린다.
'사전 뜻에 맞게 썼나' 는 규칙으로 볼 수 없어 모델 의견으로만 붙인다(fit). 입력 문구는 저장하지 않고 기록에도 남기지 않는다.

  avoid          리스크 '사용 자제'
  caution        리스크 '주의' — 이유는 generate.caution_note(근거 글은 인용하지 않는다)
  undecided      리스크를 검사했는데 근거가 모자라 판단 보류
  fading         대시보드 규칙으로 식어 가는 밈
  not_in_region  고른 시장에서 쓰이는 말이 아니다(dashboard.regions_for)
  no_script      그 시장에서 쓰이지만 그 말의 글자로 쓴 표기가 없다(generate.writable)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from ..config import USE_LOCAL_GEMMA
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from . import dashboard
from .explain import match_terms
from .gemini import configured, structured
from .generate import caution_note, writable, x_length
from .match import term_pattern, unsafe
from .views import CopyCheck, CopyIssue, CopyMeme

MAX_TEXT = 1000
MAX_MEMES = 8

FIT_PROMPT = """아래 마케팅 문구에 들어간 밈(유행어)마다, 문구가 그 밈을 사전 뜻에 맞게 썼는지 판단하라.
- ok: 사전 뜻과 맞게 썼다. off: 뜻과 다르게 썼거나 어색하다. unsure: 문구만으로는 알 수 없다.
- note 는 {lang} 한 문장. off 면 무엇이 다른지와 고칠 방향, ok 면 어떻게 맞는지.
- 리스크(써도 되는지)는 판단하지 않는다. 뜻에 맞는지만 본다.

문구:
{text}

밈과 사전 뜻:
{memes}"""


class FitItem(BaseModel):
    term_id: str
    fit: Literal["ok", "off", "unsure"]
    note: str = ""


class FitResult(BaseModel):
    items: list[FitItem]


def model_ready() -> bool:
    return bool(USE_LOCAL_GEMMA or configured())


def _matched(text: str, t) -> str:
    for cand in (t.canonical, *t.aliases):
        m = term_pattern(cand).search(text)
        if m:
            return m.group(0)
    return t.canonical


def check(con: Connection, text: str, region: str) -> tuple[CopyCheck, list]:
    """(규칙 검사 결과, 찾은 용어들). 모델은 부르지 않는다 — 뜻 검사는 fit() 이 따로."""
    terms = match_terms(text, ds.list_terms(con, ("verified",)))[:MAX_MEMES]
    now = datetime.now(timezone.utc)
    memes: list[CopyMeme] = []
    for t in terms:
        card = dashboard.card(con, t.term_id, [region])
        regions = dashboard.regions_for(con, t)
        issues: list[CopyIssue] = []
        if t.risk_level == "avoid":
            issues.append(CopyIssue(code="avoid"))
        elif t.risk_level == "caution":
            issues.append(CopyIssue(code="caution", note=caution_note(con, t)))
        elif t.risk_level is None and t.risk_checked_at:
            issues.append(CopyIssue(code="undecided"))
        if card and dashboard._is_fading(card, now):
            issues.append(CopyIssue(code="fading"))
        if region not in regions:
            issues.append(CopyIssue(code="not_in_region"))
        elif not writable(t, region, regions):
            issues.append(CopyIssue(code="no_script"))
        memes.append(CopyMeme(term_id=t.term_id, canonical=t.canonical, lang=t.lang or "", matched=_matched(text, t),
                              gloss_ko=card.gloss_ko if card else "", gloss_en=card.gloss_en if card else "", regions=regions,
                              lifecycle=card.lifecycle if card else t.lifecycle, diffusion=card.diffusion if card else t.diffusion,
                              risk_level=t.risk_level, risk_checked_at=t.risk_checked_at, issues=issues))
    out = CopyCheck(region=region, memes=memes, unsafe=unsafe(text), x_length=x_length(text), fit_source="none")
    return out, terms


def fit(con: Connection, text: str, result: CopyCheck, terms: list, lang: str) -> CopyCheck:
    """모델 의견(뜻에 맞게 썼나)을 붙인다. 실패하면 예외 — 부르는 쪽이 fit_source 를 failed 로 둔다."""
    lines = []
    for t in terms:
        tr = ds.get_translation(con, t.term_id, "ko") or ds.current_meaning(con, t.term_id)
        lines.append(f"- {t.term_id} | {t.canonical}: {(tr.definition if tr else '')[:200]} (뉘앙스: {(tr.nuance if tr else '')[:120]})")
    prompt = FIT_PROMPT.format(lang="영어" if lang == "en" else "한국어", text=text[:MAX_TEXT], memes="\n".join(lines))
    parsed, model = structured(con, prompt, FitResult, prefer_gemini=True, request=True)
    got = parsed if isinstance(parsed, FitResult) else FitResult.model_validate(parsed)
    by_id = {i.term_id: i for i in got.items}
    for m in result.memes:
        i = by_id.get(m.term_id)
        if i:
            m.fit, m.fit_note = i.fit, " ".join(i.note.split())[:300] or None
    result.fit_source = "local" if model.startswith("local:") else "gemini"
    return result
