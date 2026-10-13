"""카피 검사 — 마케터가 쓴 문구에 든 밈을 사전으로 찾아, 고른 시장에서 써도 되는지 규칙으로 알린다.
'사전 뜻에 맞게 썼나' 는 규칙으로 볼 수 없어 모델 의견으로만 붙인다(fit). 입력 문구는 저장하지 않고 기록에도 남기지 않는다.

  avoid          리스크 '사용 자제'
  crude          쓰임 낱말의 말투가 '저속'(MemeFit.voice) — 추천이 후보에서 빼는 말(recommend.blocked)
  caution        리스크 '주의' — 이유는 generate.caution_note(근거 글은 인용하지 않는다)
  sensitive      리스크를 아직 판단하지 않았는데 민감한 소재(risk.sensitive_topic) — 추천이 빼는 기준과 같다
  undecided      리스크를 검사했는데 근거가 모자라 판단 보류
  fading         대시보드 규칙으로 식어 가는 밈
  not_in_region  고른 시장에서 쓰이는 말이 아니다(dashboard.regions_for)
  no_script      그 시장에서 쓰이지만 그 말의 글자로 쓴 표기가 없다(generate.writable)

초안의 문구 여럿은 check_all 로 한 번에 본다 — 사전을 한 번만 읽고, AI 의견은 시장마다 한 문구에만 받는다(모델 호출을 늘리지 않는다).
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
from .generate import caution_note, in_ui_language, relanguage, writable, x_length
from .match import text_pattern, unsafe
from .risk import sensitive_topic
from .views import CopyCheck, CopyIssue, CopyMeme
from ..ui_lang import NAME_KO

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
        m = text_pattern(cand).search(text)
        if m:
            return m.group(0)
    return t.canonical


def check(con: Connection, text: str, region: str, vocab: list | None = None, fits: dict | None = None,
          memo: dict | None = None) -> tuple[CopyCheck, list]:
    """(규칙 검사 결과, 찾은 용어들). 모델은 부르지 않는다 — 뜻 검사는 fit() 이 따로.
    vocab·fits 는 확인된 표제어와 쓰임 낱말, memo 는 용어마다의 카드·지역·조심 안내 — 여러 문구를 볼 때 한 번만 읽는다(check_all).
    같은 밈이 초안의 문구 넷에 모두 들어 있다."""
    vocab = ds.list_terms(con, ("verified",)) if vocab is None else vocab
    fits = ds.all_fits(con) if fits is None else fits
    memo = {} if memo is None else memo
    terms = match_terms(text, vocab)[:MAX_MEMES]
    now = datetime.now(timezone.utc)
    memes: list[CopyMeme] = []
    for t in terms:
        if t.term_id not in memo:
            memo[t.term_id] = (dashboard.card(con, t.term_id, [region]), dashboard.regions_for(con, t),
                               caution_note(con, t) if t.risk_level == "caution" else "")
        card, regions, careful = memo[t.term_id]
        issues: list[CopyIssue] = []
        if t.risk_level == "avoid":
            issues.append(CopyIssue(code="avoid"))
        elif t.risk_level == "caution":
            issues.append(CopyIssue(code="caution", note=careful))
        elif t.risk_level is None and t.risk_checked_at:
            issues.append(CopyIssue(code="undecided"))
        if t.term_id in fits and fits[t.term_id][1].voice == "crude":
            issues.append(CopyIssue(code="crude"))
        if t.risk_level is None and sensitive_topic(f"{t.canonical} {card.gloss_ko if card else ''}"):
            issues.append(CopyIssue(code="sensitive"))
        if card and dashboard._is_fading(card, now):
            issues.append(CopyIssue(code="fading"))
        if region not in regions:
            issues.append(CopyIssue(code="not_in_region"))
        elif not writable(t, region, regions):
            issues.append(CopyIssue(code="no_script"))
        memes.append(CopyMeme(term_id=t.term_id, canonical=t.canonical, lang=t.lang or "", matched=_matched(text, t),
                              gloss_ko=card.gloss_ko if card else "", gloss_en=card.gloss_en if card else "",
                              en_pending=card.en_pending if card else True, ko_pending=card.ko_pending if card else False,
                              gloss_ja=card.gloss_ja if card else "", ja_pending=card.ja_pending if card else True, regions=regions,
                              lifecycle=card.lifecycle if card else t.lifecycle, diffusion=card.diffusion if card else t.diffusion,
                              risk_level=t.risk_level, risk_checked_at=t.risk_checked_at, issues=issues))
    out = CopyCheck(region=region, memes=memes, unsafe=unsafe(text), x_length=x_length(text), fit_source="none")
    return out, terms


def check_all(con: Connection, texts: list[str], region: str) -> list[tuple[CopyCheck, list]]:
    """문구마다 (규칙 검사 결과, 찾은 용어들) — 초안 한 시장의 문구 모두. 사전·쓰임 낱말은 한 번만 읽는다. 모델은 부르지 않는다."""
    vocab, fits, memo = ds.list_terms(con, ("verified",)), ds.all_fits(con), {}
    return [check(con, text, region, vocab, fits, memo) for text in texts]


def fit(con: Connection, text: str, result: CopyCheck, terms: list, lang: str) -> CopyCheck:
    """모델 의견(뜻에 맞게 썼나)을 붙인다. 실패하면 예외 — 부르는 쪽이 fit_source 를 failed 로 둔다."""
    lines = []
    for t in terms:
        tr = ds.get_translation(con, t.term_id, "ko") or ds.current_meaning(con, t.term_id)
        lines.append(f"- {t.term_id} | {t.canonical}: {(tr.definition if tr else '')[:200]} (뉘앙스: {(tr.nuance if tr else '')[:120]})")
    prompt = FIT_PROMPT.format(lang=NAME_KO.get(lang, "한국어"), text=text[:MAX_TEXT], memes="\n".join(lines))
    parsed, model = structured(con, prompt, FitResult, prefer_gemini=True, request=True)
    got = parsed if isinstance(parsed, FitResult) else FitResult.model_validate(parsed)
    by_id = {i.term_id: i for i in got.items}
    for m in result.memes:
        i = by_id.get(m.term_id)
        if i:
            m.fit, m.fit_note = i.fit, " ".join(i.note.split())[:300] or None
    if lang != "ko":
        # 의견 문장이 화면 언어가 아니면 한 번 옮기고, 그래도 아니면 비운다(판정은 그대로) — 로컬 Gemma 가 일본어 화면의 의견을 한국어로 썼다(10-13 시험)
        names = [n for t in terms for n in (t.canonical, *t.aliases) if n]
        bad = [m for m in result.memes if m.fit_note and not in_ui_language(m.fit_note, lang, names)]
        got_lines = relanguage(con, [m.fit_note for m in bad], lang, names) if bad else None
        for k, m in enumerate(bad):
            new = got_lines[k] if got_lines else None
            m.fit_note = new or (m.fit_note if lang == "ja" and in_ui_language(m.fit_note, "en", names) else None)
    result.fit_source = "local" if model.startswith("local:") else "gemini"
    return result
