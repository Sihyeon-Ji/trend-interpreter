"""검증 게이트. LLM 이 '검증됨' 이라고 스스로 말할 수 없다 — 규칙이 정한다.

참고 아키텍처(MCTI)에서 이식한 두 원칙:
- 라벨 정직성 게이트: 라벨(verified)은 결정론 근거가 있을 때만. 실패는 삭제가 아니라 강등 + 사유 기록.
- 앵커 가드: 용어·풀이가 근거 '원문'에 실재할 때만 그 근거를 센다. LLM 자기검증 금지.
"""
from __future__ import annotations

from .schemas import Evidence, Meaning, MeaningDraft, Verification

MIN_INDEPENDENT_DOMAINS = 2
MIN_SELF_CONFIDENCE = 0.5
# 위키백과 문서는 사람이 쓴 백과사전 항목이라 1차 근거로 인정한다. 다만 언어판이 달라도 한 출처로 세도록
# source_domain 을 wikipedia.org 하나로 맞춰 두었다 — 영어판·한국어판을 "독립 출처 2개" 로 셈하면 자기확인이 된다.
FIRST_PARTY = {"short", "news", "datalab", "wiki"}


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def source_text(e: Evidence) -> str:
    """검증에 쓸 수 있는 '원문'만. 우리 모델이 쓴 문장(derived)은 앵커가 될 수 없다 — 그러면 사전이 스스로를 확인하게 된다.
    2026-09-16 실사고: 쇼츠 해석이 'Ganpati Bappa Morya: 가네샤 축제…구호' 를 발췌로 남겼고, 오프라인 조사가 그 문장을 그대로
    뜻·풀이로 옮겨 적었으며, 게이트의 환각 검사가 자기 문장에 앵커되어 통과했다(전통 종교 구호가 유행어로 등재됨)."""
    return e.title if getattr(e, "derived", False) else e.title + " " + e.excerpt


def anchor_hit(term: str, e: Evidence, aliases: list[str] | tuple[str, ...] = ()) -> bool:
    """용어(또는 별칭)가 근거의 원문에 실제로 있는가 (숫자꼴 용어는 밈 단서까지)."""
    from .pipeline.match import mentions  # 순환 import 방지

    return mentions(source_text(e), term, aliases)


def gate(
    term: str, draft: MeaningDraft, evidences: list[Evidence], current: Meaning | None, aliases: list[str] | tuple[str, ...] = ()
) -> tuple[Verification, list[str]]:
    """통과하면 verified_auto. 아니면 unverified + 사람 검수 큐로 갈 이유 목록."""
    reasons: list[str] = []
    # 뜻이 비었거나 표제어를 도로 옮겨 적은 것은 사전 항목이 아니다. 근거가 아무리 튼튼해도 통과시키지 않는다
    # (2026-09-16 실측: 근거 8건짜리 항목이 definition="" 으로 verified 가 됐다).
    definition = (draft.definition or "").strip()
    if len(definition) < 8 or _norm(definition) == _norm(term):
        reasons.append("뜻이 비었거나 표제어를 그대로 옮겨 적음")
    if not draft.is_expression:
        reasons.append("표현이 아니라 상품·기관·인물·일반 단어로 판단됨 — 사전 대상 아님")
    anchored = [e for e in evidences if anchor_hit(term, e, aliases)]
    # 용어가 안 들어 있는 근거는 셈에서 빠진다. 다만 **모델이 근거라며 내놓은 웹 링크**가 그렇다면
    # 환각 신호라서 차단 사유다 — 커뮤니티·검색 수집기가 긁어 온 잡음은 모델 잘못이 아니므로 조용히 뺀다.
    stray = [e for e in evidences if e.kind == "web" and e not in anchored]
    if stray:
        reasons.append(f"모델이 든 웹 근거 {len(stray)}건에 용어가 없음 — 환각 의심")
    if len({e.source_domain for e in anchored}) < MIN_INDEPENDENT_DOMAINS:
        reasons.append(f"용어가 실재하는 독립 출처 {MIN_INDEPENDENT_DOMAINS}개 미만")
    if not any(e.kind in FIRST_PARTY for e in anchored):
        reasons.append("1차 근거(쇼츠·뉴스·데이터랩) 없음 — 웹 검색만으로는 부족")
    if draft.expansion and not any(_norm(draft.expansion) in _norm(source_text(e)) for e in evidences):
        reasons.append(f"풀이 {draft.expansion!r} 가 어떤 근거 원문에도 없음 — 환각 의심")
    if draft.self_confidence < MIN_SELF_CONFIDENCE:
        reasons.append(f"모델 자기확신 {draft.self_confidence:.2f} < {MIN_SELF_CONFIDENCE}")
    if current and current.expansion and draft.expansion and current.expansion != draft.expansion:
        reasons.append(f"현행 뜻과 충돌 (v{current.version}: {current.expansion!r}) — 의미 변화 검수 필요")
    # '제외됨' 만 남고 다른 사유가 없으면 통과 (정보성 사유)
    blocking = [r for r in reasons if not r.endswith("제외됨")]
    return ("verified_auto" if not blocking else "unverified"), reasons
