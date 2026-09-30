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

from .schemas import Evidence, Meaning, MeaningDraft, Verification

MIN_INDEPENDENT_DOMAINS = 2
MIN_SELF_CONFIDENCE = 0.5
# 위키백과 문서는 사람이 쓴 백과사전 항목이라 1차 근거로 인정한다. 다만 언어판이 달라도 한 출처로 세도록
# source_domain 을 wikipedia.org 하나로 맞춰 두었다 — 영어판·한국어판을 "독립 출처 2개" 로 셈하면 자기확인이 된다.
FIRST_PARTY = {"short", "news", "datalab", "wiki"}
# 참고 문서가 있는 곳(하위 도메인 포함 — ko.wikipedia.org 등). 니코니코 대백과는 이 서버를 막고, pixiv 백과사전은 대부분 봇 확인 뒤에 있다.
REFERENCE_DOMAINS = ("namu.wiki", "wikipedia.org", "knowyourmeme.com", "dic.pixiv.net", "zh.moegirl.org.cn")
NO_REFERENCE = "참고 문서(나무위키·위키백과·Know Your Meme 등)에 유래가 없어 사람이 확인한 뒤에만 실립니다"


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
    return u.path not in ("", "/") and any(host == d or host.endswith("." + d) for d in REFERENCE_DOMAINS)


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
    if not draft.is_expression and not catalogued:
        reasons.append("표현이 아니라 상품·기관·인물·일반 단어로 판단됨 — 사전 대상 아님")
    from .collectors.community import is_community_post

    evidences = [e for e in evidences if not is_community_post(e)]      # 커뮤니티·SNS 글은 어떤 셈에도 넣지 않는다(ADR 0003)
    anchored = [e for e in evidences if anchor_hit(term, e, aliases)]
    documented = any(reference_doc(e) for e in anchored)
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
