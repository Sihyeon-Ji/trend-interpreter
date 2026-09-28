"""리스크 단계(Plan 03). 마케터가 밈을 쓰기 전에 "브랜드 공식 계정 사용 주의" 같은 경고를 받게 한다.

LLM 이 혼자 "안전함" 을 붙이지 않는다. 로컬 Gemma 는 **근거 문장 하나하나**에 뉘앙스(긍정·중립·부정)와
위험 유형(혐오·조롱·성별 갈등·정치·선정성)만 붙이고, 용어의 수준은 아래 규칙 코드가 정한다.

  사용 자제  위험 유형 근거 3건 이상 · 표제어 자체가 욕설·성적 표현 · 영상 해석이 비하·혐오 기원을 지적
  주의       부정 근거 30% 이상 · 위험 유형 근거 2건 · 확산 단계가 '식상'  (1건은 잡음이라 세지 않는다)
  없음       위 어디에도 걸리지 않고 분류된 근거가 5건 이상
  판단 보류  분류된 근거가 5건 미만 (화면에 '근거 부족')

이유는 걸린 근거 문장을 그대로 인용한다. 문장 분류는 Plan 04 대시보드의 긍정·부정 뉘앙스에도 쓴다.
로컬 모델이 없으면(기본 개발 환경) 분류는 건너뛰고 이미 있는 분류로만 판정한다.
"""
from __future__ import annotations

import re
from ..storage.db import Connection
from datetime import datetime, timezone

from ..schemas import Evidence, EvidenceLabel, ShortsInterpretation
from ..storage import dictionary_store as ds
from .gemini import local_ok, structured
from .match import same_term, unsafe
from .runs import stage

MAX_TERMS = 30            # 한 번에 분류할 용어 수 (나머지는 다음 실행)
PER_TERM = 12             # 용어당 최근 근거 문장 수
USAGE_KINDS = ("community", "news", "short")
AVOID_RISKY = 3
# 위험 근거 한 건은 잡음이다 — 커뮤니티 검색은 그 말과 상관없는 글(스팸·농담)도 가져온다(2026-09-28: DM·Du Bist Gut Genug).
CAUTION_RISKY = 2
CAUTION_NEGATIVE = 0.30
MIN_LABELED = 5
_BAD_ORIGIN = re.compile(r"비하|혐오|차별|멸칭|인종|slur|hate|derogat", re.I)

PROMPT = """아래는 인터넷 표현 '{term}' 이 들어간 문장들이다. 사전의 뜻: {definition}
문장마다 세 가지를 붙여라.
on_topic: 그 문장이 '{term}' 을 **위 뜻의 유행어로** 쓰는가. 글자만 같은 딴 이야기(정책 이름·사람 이름·다른 뜻의 낱말)면 false.
polarity: 그 문장에서 '{term}' 이 쓰인 느낌 — positive(좋게·재미있게) | neutral | negative(비꼼·조롱·불쾌)
risk: 그 문장이 드러내는 위험 — hate(혐오·차별) | mockery(특정 대상 조롱) | gender(성별 갈등) | politics(정치) | sexual(선정성) | none
문장 번호(i)를 그대로 달아라. 판단이 어려우면 neutral, none.

문장:
{items}"""


def _usage(con: Connection, term_id: str) -> list[Evidence]:
    evs = [Evidence.model_validate_json(j) for (j,) in
           con.execute("SELECT json FROM evidences WHERE term_id=?", (term_id,)).fetchall()]
    evs = [e for e in evs if e.kind in USAGE_KINDS and not e.source_domain.startswith("naver") and (e.excerpt or e.title)]
    return sorted(evs, key=lambda e: e.observed_at, reverse=True)[:PER_TERM]


def classify(con: Connection, term) -> int:
    """아직 분류하지 않은 근거 문장을 분류한다. 로컬 모델이 없으면 0."""
    if not local_ok():
        return 0
    done = ds.evidence_labels(con, term.term_id)
    todo = [e for e in _usage(con, term.term_id) if e.evidence_id not in done]
    if not todo:
        return 0
    items = "\n".join(f"{i}. {(e.excerpt or e.title)[:220]}" for i, e in enumerate(todo))
    m = ds.current_meaning(con, term.term_id)
    parsed, model = structured(con, PROMPT.format(term=term.canonical, definition=(m.definition if m else "")[:160], items=items),
                               list[EvidenceLabel])
    # 딴 이야기인 문장은 'offtopic' 으로 남겨, 다시 분류하지 않되 판정에서는 뺀다
    rows = [(todo[p.i].evidence_id, p.polarity if p.on_topic else "offtopic", p.risk if p.on_topic else "none")
            for p in (parsed or []) if 0 <= p.i < len(todo)]
    ds.set_evidence_labels(con, term.term_id, rows, model)
    return len(rows)


def _bad_origin(con: Connection, term) -> str:
    """영상 해석이 이 용어를 담은 영상에 비하·혐오 기원을 지적했는가."""
    for (j,) in con.execute("SELECT json FROM interpretations").fetchall():
        it = ShortsInterpretation.model_validate_json(j)
        for m in it.memes:
            if same_term(m.name, term.canonical, term.aliases):
                hit = next((f for f in (it.risk_flags or []) if _BAD_ORIGIN.search(f)), "")
                if hit:
                    return hit
    return ""


def judge(con: Connection, term) -> tuple[str | None, list[str]]:
    """(수준, 이유들). 이유는 걸린 근거 문장을 인용한다."""
    labels = ds.evidence_labels(con, term.term_id)
    evs = {e.evidence_id: e for e in _usage(con, term.term_id)}
    labeled = [(evs[k], p, r) for k, (p, r) in labels.items() if k in evs and p != "offtopic"]
    offtopic = sum(1 for k, (p, _) in labels.items() if k in evs and p == "offtopic")
    risky = [(e, r) for e, _, r in labeled if r != "none"]
    negative = [e for e, p, _ in labeled if p == "negative"]

    def quote(e: Evidence) -> str:
        text = re.sub(r"^@\S+\s*·\s*\d+♥\s*—\s*", "", (e.excerpt or e.title).strip())   # 블루스카이 머리말
        return f"“{text[:90]}” ({e.source_domain})"

    if unsafe(term.canonical):
        return "avoid", ["표제어 자체가 욕설·성적 표현이다."]
    origin = _bad_origin(con, term)
    if origin:
        return "avoid", [f"영상 해석이 지적한 기원: {origin[:120]}"]
    # 한 곳(블루스카이 등)에 몰린 위험 문장은 그 커뮤니티의 말투일 수 있다 — 출처가 둘 이상일 때만 '피함'
    if len(risky) >= AVOID_RISKY and len({e.source_domain for e, _ in risky}) >= 2:
        return "avoid", [f"위험 유형이 붙은 근거 {len(risky)}건"] + [quote(e) for e, _ in risky[:2]]
    if len(labeled) < MIN_LABELED:
        extra = f" (글자만 같은 딴 이야기 {offtopic}건 제외)" if offtopic else ""
        return None, [f"그 뜻으로 쓰인 근거가 {len(labeled)}건뿐이라 판단을 보류한다{extra}."]
    reasons = []
    if len(risky) >= CAUTION_RISKY:
        reasons.append(f"위험 유형이 붙은 근거 {len(risky)}건: " + quote(risky[0][0]))
    ratio = len(negative) / len(labeled)
    if ratio >= CAUTION_NEGATIVE:
        reasons.append(f"부정적으로 쓰인 근거가 {ratio:.0%} — 예: " + quote(negative[0]))
    if term.diffusion == "fading":
        reasons.append("뉴스에 오른 뒤 언급이 줄고 있어 식상하게 보일 수 있다.")
    if reasons:
        return "caution", reasons
    return "none", [f"분류된 근거 {len(labeled)}건에 위험 신호가 없다."]


def apply(con: Connection, term) -> None:
    """규칙으로 수준을 다시 매겨 저장한다. 사람의 결정(risk_human)이 있으면 그것이 우선하고, 규칙의 이유는 참고로 남긴다."""
    level, reasons = judge(con, term)
    if term.risk_human:
        term.risk_level, term.risk_reasons = term.risk_human, ["검수자가 정한 수준"] + reasons
    else:
        term.risk_level, term.risk_reasons = level, reasons
    term.risk_checked_at = datetime.now(timezone.utc)
    ds.upsert_term(con, term)


def run(con: Connection) -> dict:
    with stage(con, "risk") as r:
        terms = ds.list_terms(con, ("verified",))
        # 분류가 안 된 용어부터. 이미 분류된 것은 규칙만 다시 적용한다(빠름).
        terms.sort(key=lambda t: len(ds.evidence_labels(con, t.term_id)))
        labeled = 0
        for n, t in enumerate(terms):
            if n < MAX_TERMS:
                try:
                    labeled += classify(con, t)
                except Exception as e:           # 한 용어의 형식 실패가 나머지를 막지 않는다
                    r.note += f"{t.canonical}:{type(e).__name__} "
            apply(con, t)
        r.count = len(terms)
        r.detail = {"분류한 문장": labeled}
    return {"risk": r}
