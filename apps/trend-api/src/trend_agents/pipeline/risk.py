"""리스크 단계(Plan 03). 마케터가 밈을 쓰기 전에 "브랜드 공식 계정 사용 주의" 같은 경고를 받게 한다.

LLM 이 혼자 "안전함" 을 붙이지 않는다. 로컬 Gemma 는 **근거 문장 하나하나**에 뉘앙스(긍정·중립·부정)와
위험 유형(혐오·조롱·성별 갈등·정치·선정성)만 붙이고, 용어의 수준은 아래 규칙 코드가 정한다.

  사용 자제  위험 유형 근거 3건 이상(출처 두 곳 이상) · 표제어 자체가 욕설·성적 표현 · 영상 해석이 비하·혐오 기원을 지적
  주의       부정 근거 30% 이상 · 위험 유형 근거 2건 · 사전 뉘앙스에 적힌 주의점(욕설·비하·선정…)  (1건은 잡음이라 세지 않는다)
  없음       위 어디에도 걸리지 않고 분류된 근거가 5건 이상
  판단 보류  분류된 근거가 5건 미만 (화면에 '근거 부족')
'식상' 은 리스크가 아니다 — 확산 단계와 대시보드의 '식어 가는 밈' 이 따로 보인다(2026-09-29 검토: 주의 43개 중 25개가 식상 하나로 주의였고,
화면은 그것을 '민감한 맥락' 이라고 설명했다).

이유는 걸린 기사·쇼츠 문장을 인용한다. 커뮤니티·SNS 글은 판정에는 세지만 인용하지도 사이트 이름을 대지도 않고 건수로만 적는다
(ADR 0003 — 이유는 사전 항목·추천 화면에 그대로 나간다). 문장 분류는 Plan 04 대시보드의 긍정·부정 뉘앙스에도 쓴다.
로컬 모델이 없으면(기본 개발 환경) 분류는 건너뛰고 이미 있는 분류로만 판정한다.
"""
from __future__ import annotations

import re
from collections import Counter
from ..storage.db import Connection
from datetime import datetime, timezone

from ..collectors.community import is_community_post
from ..schemas import Evidence, EvidenceLabel, ShortsInterpretation
from ..storage import dictionary_store as ds
from .gemini import local_ok, structured
from .match import evidence_mentions, same_term, unsafe
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
# 조사 단계가 뜻풀이에 적어 둔 주의점(Plan 03 재료 '뉘앙스'). 예: 샤갈 "순화형이지만 뿌리는 욕설이다" — 근거 문장이 모자라도 사전이 이미 경고한다.
_NUANCE_WARN = re.compile(r"욕설|비속어|(?<!자기)(?<!자기 )비하|멸칭|혐오|차별(?!화)|조롱|선정적|음란|저속|모욕|"
                          # '성적' 은 낱말 앞머리일 때 '성적으로·성적인·성적 ○○(농담·표현·대상화…)' 만 — 이성적·감성적·시험 성적은 아니다(검토 2·3차)
                          r"(?<![가-힣])성적(?:으로|인|\s*(?:농담|표현|의미|함의|뉘앙스|대상|행위|묘사|암시|은어|금욕|코드|맥락|희롱|드립|비하|수치|착취))|"
                          r"profan|vulgar|slur|derogat|offensive|obscene|sexual|insult", re.I)   # '이성적'·'차별화'·'시험 성적' 은 경고가 아니다(검토 2차)
# 민감한 소재(2026-09-30): 위키에서 들어온 말은 쓰임 문장이 없어 판단 보류로만 남았다 — 'Diddy Heil Epstein'(나치 경례·성범죄 소재)
# 같은 것도. 뜻 칸까지 보고 이 소재면 '주의'. 소재를 다룬다는 뜻일 뿐 표현이 나쁘다는 판정은 아니다.
# 자살·자해(10-04): '죽고 싶지만 떡볶이는 먹고 싶어' 가 리스크 판단 전이라 라떼 광고 추천에 들었다
# 낱말 속 글자는 소재가 아니다(10-09 운영 사본): '지나치게'의 나치 60건, '참가자'·'지나가자'의 가자 40여 건이 '주의'를 만들었다
_SENSITIVE = re.compile(r"(?<![가-힣])신?나치|히틀러|홀로코스트|학살|테러|가자\s?(?:지구|지역|전쟁|주민)|팔레스타인|이스라엘|우크라이나 침공|성범죄|성폭력|아동 성|인종차별|혐오|정치인|대통령|선거|"
                        r"자살|자해|극단적 선택|죽고 싶|"
                        r"nazi|hitler|holocaust|genocide|terror|gaza|palestin|sex offender|epstein|racis|suicid|self-harm", re.I)


def sensitive_topic(text: str) -> str:
    """민감한 소재 낱말(없으면 빈 문자열). 소재를 다룬다는 뜻일 뿐 표현이 나쁘다는 판정은 아니다."""
    m = _SENSITIVE.search(text or "")
    return m.group(0) if m else ""   # '전쟁' 하나로는 잡지 않는다(きのこたけのこ戦争)
SENSITIVE_GENRES = {"정치 및 사회", "종교", "정치인", "종교인"}      # 나무위키가 이렇게 분류한 밈 — 브랜드가 쓰기 조심스러운 소재
_NEGATED_AFTER = re.compile(r"^[^.。!?]{0,12}(없|아니|않)")      # '비하하는 뜻은 없다'
_NEGATED_BEFORE = re.compile(r"(not|no|non-?)\s*$", re.I)       # 'not offensive'
RISK_KO = {"hate": "혐오·차별", "mockery": "조롱", "gender": "성별 갈등", "politics": "정치", "sexual": "선정성"}


def _quotable(e: Evidence) -> bool:
    """이유에 인용할 수 있는 근거 — 기사·쇼츠·문서. 커뮤니티·SNS 글과 네이버 검색 결과(표시 전용)는 인용하지 않는다(ADR 0003)."""
    return e.kind in ("news", "short", "wiki", "web") and not e.source_domain.startswith("naver") and not is_community_post(e)


def _posts_line(risky: list[tuple[Evidence, str]]) -> str:
    """커뮤니티 글에 붙은 위험을 건수로만 — 글을 옮기거나 사이트 이름을 대지 않는다."""
    kinds = ", ".join(RISK_KO.get(r, r) for r, _ in Counter(r for _, r in risky).most_common())
    return f"커뮤니티 글에서 {kinds} 맥락으로 쓰인 경우 {len(risky)}건"


def nuance_warning(text: str) -> str:
    """뜻풀이 문장에서 부정되지 않은 주의 낱말이 든 문장. 없으면 빈 문자열."""
    for m in _NUANCE_WARN.finditer(text or ""):
        if _NEGATED_AFTER.search(text[m.end():]) or _NEGATED_BEFORE.search(text[max(0, m.start() - 6):m.start()]):
            continue
        start = max(text.rfind(".", 0, m.start()), text.rfind("。", 0, m.start())) + 1
        end = min([i for i in (text.find(".", m.end()), text.find("。", m.end())) if i >= 0] or [len(text)])
        return text[start:end + 1].strip()[:90]
    return ""

PROMPT = """아래는 인터넷 표현 '{term}' 이 들어간 문장들이다. 사전의 뜻: {definition}
문장마다 세 가지를 붙여라.
on_topic: 그 문장이 '{term}' 을 **위 뜻의 유행어로** 쓰는가. 글자만 같은 딴 이야기(정책 이름·사람 이름·다른 뜻의 낱말)면 false.
polarity: 그 문장에서 '{term}' 이 쓰인 느낌 — positive(좋게·재미있게) | neutral | negative(비꼼·조롱·불쾌)
risk: 그 문장이 드러내는 위험 — hate(혐오·차별) | mockery(특정 대상 조롱) | gender(성별 갈등) | politics(정치) | sexual(선정성) | none
문장 번호(i)를 그대로 달아라. 판단이 어려우면 neutral, none.

문장:
{items}"""


def _usage(con: Connection, term) -> list[Evidence]:
    """분류할 쓰임 문장 — 표제어가 실제로 든 것만. 검색이 끌어온 딴 글이 최근 PER_TERM 칸을 차지해 진짜 문장이 밀려났다(2026-09-29)."""
    evs = [Evidence.model_validate_json(j) for (j,) in
           con.execute("SELECT json FROM evidences WHERE term_id=?", (term.term_id,)).fetchall()]
    evs = [e for e in evs if e.kind in USAGE_KINDS and not e.source_domain.startswith("naver") and (e.excerpt or e.title)
           and evidence_mentions(e, term.canonical, term.aliases)]
    return sorted(evs, key=lambda e: e.observed_at, reverse=True)[:PER_TERM]


def classify(con: Connection, term) -> int:
    """아직 분류하지 않은 근거 문장을 분류한다. 로컬 모델이 없으면 0."""
    if not local_ok():
        return 0
    done = ds.evidence_labels(con, term.term_id)
    todo = [e for e in _usage(con, term) if e.evidence_id not in done]
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


def sensitive_genres(con: Connection, term_id: str) -> list[str]:
    """위키 밈 분류(wiki_catalog) 가운데 민감한 소재의 것 — 나무위키 '인터넷 밈/정치 및 사회' 등. 분류 이름에서만 읽는다."""
    import json

    from .catalog import meta

    out: set[str] = set()
    for (cats,) in con.execute("SELECT categories_json FROM wiki_catalog WHERE term_id=?", (term_id,)).fetchall():
        out |= set(meta(json.loads(cats or "[]"))["genres"]) & SENSITIVE_GENRES
    return sorted(out)


def judge(con: Connection, term) -> tuple[str | None, list[str]]:
    """(수준, 이유들). 이유는 걸린 기사·쇼츠 문장을 인용하고, 커뮤니티 글은 건수로만 적는다."""
    labels = ds.evidence_labels(con, term.term_id)
    evs = {e.evidence_id: e for e in _usage(con, term)}
    labeled = [(evs[k], p, r) for k, (p, r) in labels.items() if k in evs and p != "offtopic"]
    offtopic = sum(1 for k, (p, _) in labels.items() if k in evs and p == "offtopic")
    risky = [(e, r) for e, _, r in labeled if r != "none"]
    negative = [e for e, p, _ in labeled if p == "negative"]

    def quote(e: Evidence) -> str:
        return f"“{(e.excerpt or e.title).strip()[:90]}” ({e.source_domain})"

    def risky_examples(n: int) -> list[str]:
        """위험 근거의 예 — 인용할 수 있는 것은 n건까지 인용, 커뮤니티 글은 건수 한 줄."""
        posts = [(e, r) for e, r in risky if not _quotable(e)]
        return [quote(e) for e, _ in risky if _quotable(e)][:n] + ([_posts_line(posts)] if posts else [])

    if unsafe(term.canonical):
        return "avoid", ["표제어 자체가 욕설·성적 표현이다."]
    origin = _bad_origin(con, term)
    if origin:
        return "avoid", [f"영상 해석이 지적한 기원: {origin[:120]}"]
    # 한 곳(블루스카이 등)에 몰린 위험 문장은 그 커뮤니티의 말투일 수 있다 — 출처가 둘 이상일 때만 '피함'.
    # 위험 문장이 쓰임의 절반을 넘을 때만 — 懶人包(요약 정리)·自嘲가 성폭행·정치 기사 제목에 들어 있다는 것만으로
    # '쓰지 말 것'이 됐다(실데이터 10-05, 11건 중 3건·6건 중 3건). 그런 말은 아래에서 위험 근거를 인용한 '주의'가 된다.
    if len(risky) >= AVOID_RISKY and len({e.source_domain for e, _ in risky}) >= 2 and len(risky) * 2 > len(labeled):
        return "avoid", [f"위험 유형이 붙은 근거 {len(risky)}건"] + risky_examples(2)
    m = ds.current_meaning(con, term.term_id)
    warned = nuance_warning(f"{m.nuance} {m.origin}" if m else "")
    reasons = [f"사전 뜻풀이에 적힌 주의점: “{warned}”"] if warned else []
    genres = sensitive_genres(con, term.term_id)
    if genres:
        reasons.append(f"위키 분류가 {'·'.join(genres)} 소재의 밈이라고 적었다 — 브랜드가 쓰기 조심스럽다.")
    topic = _SENSITIVE.search(f"{m.definition} {m.origin} {m.nuance}" if m else "")
    if topic and not warned:
        reasons.append(f"뜻풀이가 민감한 소재('{topic.group(0)}')를 다룬다.")
    if len(labeled) < MIN_LABELED:
        if reasons:                    # 근거 문장이 모자라도 사전이 이미 경고한 말은 주의
            return "caution", reasons
        extra = f" (글자만 같은 딴 이야기 {offtopic}건 제외)" if offtopic else ""
        return None, [f"그 뜻으로 쓰인 근거가 {len(labeled)}건뿐이라 판단을 보류한다{extra}."]
    if len(risky) >= CAUTION_RISKY:
        shown = [e for e, _ in risky if _quotable(e)]
        posts = [(e, r) for e, r in risky if not _quotable(e)]
        if shown:
            reasons.append(f"위험 유형이 붙은 근거 {len(risky)}건: " + quote(shown[0]))
        if posts:
            reasons.append(_posts_line(posts))
    ratio = len(negative) / len(labeled)
    if ratio >= CAUTION_NEGATIVE:
        shown_neg = [e for e in negative if _quotable(e)]
        if shown_neg:
            reasons.append(f"부정적으로 쓰인 근거가 {ratio:.0%} — 예: " + quote(shown_neg[0]))
        else:                          # 부정 문장이 모두 커뮤니티 글 — 그 글들 가운데 부정의 몫만 적는다
            posts = [e for e, _, _ in labeled if not _quotable(e)]
            reasons.append(f"커뮤니티 글의 {len(negative) / len(posts):.0%}가 부정적인 맥락")
    if reasons:
        return "caution", reasons
    return "none", [f"분류된 근거 {len(labeled)}건에 위험 신호가 없다."]


def apply(con: Connection, term, *, human: bool = False) -> None:
    """규칙으로 수준을 다시 매겨 저장한다. 사람의 결정(risk_human)이 있으면 그것이 실제 수준이고, 규칙의 판정(risk_rule_level)과
    이유는 따로 남긴다.
    human=True  검수 화면의 길 — 넘겨받은 용어의 사람의 결정을 그대로 저장한다.
    human=False 파이프라인 — 저장된 용어를 다시 읽어 판정하고 리스크 필드만 쓴다(옛 사본이 상태·사람의 결정을 덮지 않게)."""
    if not human:
        term = ds.get_term(con, term.term_id) or term
    level, reasons = judge(con, term)
    now = datetime.now(timezone.utc)
    if human:
        effective, why = (term.risk_human, ["검수자가 정한 수준"] + reasons) if term.risk_human else (level, reasons)
        term.risk_level, term.risk_reasons, term.risk_rule_level, term.risk_checked_at = effective, why, level, now
        ds.upsert_term(con, term, human=True)
    else:
        # 규칙의 판정만 넘긴다 — 실제 수준은 저장하는 순간의 사람의 결정으로 set_risk 가 정한다(판정하는 사이 검수자가 정한 것을 덮지 않게, 검토 3차)
        ds.set_risk(con, term.term_id, level, reasons, now)


def run(con: Connection) -> dict:
    with stage(con, "risk") as r:
        terms = ds.list_terms(con, ("verified",))
        # 분류할 문장이 남은 용어만, 남은 문장이 많은 것부터. 분류가 다 끝난 용어가 칸을 다 차지해 새 근거가 영영
        # 분류되지 않았다(2026-09-29 검토: 앞 30칸이 전부 남은 문장 0).
        pending = []
        for t in terms:
            done = ds.evidence_labels(con, t.term_id)
            left = sum(1 for e in _usage(con, t) if e.evidence_id not in done)
            if left:
                pending.append((left, t))
        pending.sort(key=lambda x: -x[0])
        labeled = 0
        for _, t in pending[:MAX_TERMS]:
            try:
                labeled += classify(con, t)
            except Exception as e:           # 한 용어의 형식 실패가 나머지를 막지 않는다
                r.note += f"{t.canonical}:{type(e).__name__} "
        for t in terms:
            fresh = ds.get_term(con, t.term_id)   # 분류하는 몇 분 사이 검수자가 바꾸거나 제외한 것을 옛 사본이 덮지 않게
            if fresh and fresh.status == "verified":
                apply(con, fresh)
        r.count = len(terms)
        r.detail = {"분류한 문장": labeled, "분류 대기 용어": max(0, len(pending) - MAX_TERMS)}
    return {"risk": r}
