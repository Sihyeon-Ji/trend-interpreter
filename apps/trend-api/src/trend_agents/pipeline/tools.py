"""질문 응답 루프가 부르는 도구. 전부 저장된 데이터를 읽기만 한다 — 모델은 여기 없는 것을 말할 수 없다.

각 도구는 사람이 읽는 짧은 한국어 문자열을 돌려준다(모델이 그대로 근거로 쓴다). 무엇을 찾았는지는 Ctx 에 남겨,
답이 실제로 사전에 근거했는지 호출부가 확인하고 화면이 해당 표제어로 링크를 건다.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ..collectors.community import is_community_post
from ..lifecycle import recheck_interval_days  # noqa: F401  (생애주기 라벨과 같은 모듈을 쓴다는 표시)
from ..storage import dictionary_store as ds
from .match import keywords, loose_key, strip_particle, unsafe
from .views import shown_evidences
from ..storage.db import Connection

LIFECYCLE = {"emerging": "막 뜨는 중", "rising": "오르는 중", "peak": "절정", "steady": "꾸준함",
             "declining": "지는 중", "dormant": "잠잠함", "unknown": "판단 보류"}
GEN = {"10s": "10대", "20s": "20대", "30s": "30대", "40s": "40대", "50s+": "50대 이상", "all": "전 세대"}
REGION = {"KR": "한국", "JP": "일본", "US": "미국", "GB": "영국", "ID": "인도네시아", "TH": "태국", "VN": "베트남",
          "TW": "대만", "IN": "인도", "BR": "브라질", "DE": "독일", "FR": "프랑스", "MX": "멕시코", "PH": "필리핀"}
MAX_CHARS = 1200   # 도구 결과가 길면 모델이 앞부분만 보고 답한다 — 짧게 끊는다
MAX_CHARS_BY = {"search_index": 4200}   # 색인 문단은 여덟 개를 함께 봐야 답이 든 한 줄을 고른다


@dataclass
class Ctx:
    con: Connection
    term_ids: list[str] = field(default_factory=list)
    best: tuple[str, str] | None = None   # (표제어, 뜻) — 도구가 찾은 가장 가까운 항목
    _roman: dict[str, str] = field(default_factory=dict)   # 한글 표기 → 로마자 (같은 대화에서 한 번만 묻는다)
    cards: list[dict] = field(default_factory=list)        # 화면이 그리는 조각. 도구가 직접 채운다
    lang: str = "ko"                                       # 답하는 언어 — 목록을 고를 때 이 말 표제어를 앞에 둔다
    tried: list[str] = field(default_factory=list)         # 찾아봤지만 사전에 없던 말 — 실시간 찾아보기가 쓴다
    content: str = ""                                      # content_memes 가 찾은 작품 — 답이 됐으니 뜻으로 다시 훑지 않는다
    progress: Callable[[str, str], None] | None = None     # (단계, 사람이 읽는 말) — 화면에 흘려보낸다

    def seen(self, term_id: str) -> None:
        if term_id not in self.term_ids:
            self.term_ids.append(term_id)

    def say(self, step: str, label: str) -> None:
        """무엇을 하는 중인지 알린다. 오래 걸려도 보이면 기다릴 만하다."""
        if self.progress:
            try:
                self.progress(step, label)
            except Exception:
                pass

    def missed(self, q: str) -> None:
        """사전에서 못 찾은 **말** 을 적어 둔다. 루프가 끝나고 실시간으로 찾아볼 거리다.

        문장 전체는 적지 않는다 — 실시간 찾아보기가 "추구미 언제부터 쓰기 시작했어?" 를 통째로
        로마자로 바꿔 'Chugumi' 를 찾으러 간다(2026-09-16 평가에서 확인).
        """
        q = (q or "").strip()
        if len(q.split()) > 4 or len(q) > 40:
            return
        if q and q not in self.tried:
            self.tried.append(q)

    def card(self, d: dict) -> None:
        """도구가 찾은 것을 화면용으로 함께 내보낸다 — 글로만 답하면 목록·비율이 눈에 안 들어온다."""
        if len(self.cards) < 4 and d not in self.cards:
            self.cards.append(d)

    def offer(self, canonical: str, definition: str) -> None:
        if self.best is None:
            self.best = (canonical, definition)

    def romanized(self, q: str) -> str:
        """한글로 소리 나는 대로 적은 외래어 이름을 원어 표기로. 못 찾았을 때만 부른다.

        "트랄랄레로 트랄랄라" 와 "Tralalero Tralala" 는 글자가 하나도 겹치지 않아 느슨한 대조로도 이어지지
        않는다(2026-09-16 실측). 로마자 표기는 규칙으로 만들기 어려워 로컬 모델에 한 번 묻는다.
        """
        if not _HANGUL.search(q):
            return ""
        if q in self._roman:
            return self._roman[q]
        out = ""
        try:
            from ..interpreters import local_chat

            raw = local_chat.chat_text(ROMANIZE_PROMPT.format(q=q))
            out = re.sub(r"[^A-Za-z0-9' -]", " ", (raw or "").strip().splitlines()[0]).strip()[:60]
        except Exception:
            out = ""
        self._roman[q] = out
        return out


TOOL_LABEL = {"lookup_term": "사전에서 {0} 찾는 중", "search_terms": "사전에서 {0} 로 찾는 중",
              "why_trending": "{0} 가 왜 떴는지 보는 중", "country_trends": "{0} 트렌드 보는 중",
              "term_usage": "{0} 를 누가 쓰는지 보는 중", "list_terms": "조건에 맞는 표제어 모으는 중",
              "content_memes": "{0} 에서 나온 밈 보는 중", "read_web": "위키에서 {0} 문서 읽는 중",
              "search_index": "위키 문서 색인에서 {0} 찾는 중"}


def run_tool(ctx: Ctx, name: str, args: dict) -> str:
    fn = _TOOLS.get(name)
    if not fn:
        return f"그런 도구는 없습니다: {name}. 쓸 수 있는 도구: {', '.join(_TOOLS)}"
    what = _clean(str(next((v for v in args.values() if v), "")))[:30]
    ctx.say("tool", TOOL_LABEL.get(name, "사전 보는 중").format(f"'{what}'" if what else ""))
    try:
        return fn(ctx, args)[:MAX_CHARS_BY.get(name, MAX_CHARS)]
    except Exception as e:      # 도구 하나가 죽어도 루프는 계속 — 모델에 사실대로 알린다
        return f"도구 실행 중 오류({type(e).__name__}). 다른 방법으로 답해 주세요."


def _clean(s: str) -> str:
    return " ".join((s or "").split())


def _arg(args: dict, key: str) -> str:
    """도구 인자 한 개를 꺼내 다듬는다.

    작은 모델은 인자를 통째로 한 값에 밀어 넣는다 — category 로 "slang_meme', region='KR" 이 들어온다(09-16 실측).
    따옴표 뒤로는 버리고 첫 값만 쓴다."""
    v = _clean(str(args.get(key, "")))
    return re.split(r"['\"“”,;]", v)[0].strip()


_HANGUL = re.compile(r"[\uac00-\ud7a3]")
ROMANIZE_PROMPT = ("다음 한글은 외국어 이름을 소리 나는 대로 적은 것이다. 원래 표기(로마자)만 한 줄로 답하라. "
                   "설명·따옴표·다른 말 금지. 예: '퉁퉁퉁 사후르' -> Tung Tung Tung Sahur\n\n{q}")


def _fuzzy_find(con, q: str, cutoff: float = 0.82):
    """글자 하나 차이까지 맞춰 준다. 로마자 표기는 사람마다·모델마다 조금씩 다르게 적는다 —
    "Tralalarelo Tralalala" 로 적어도 "Tralalero Tralala" 를 찾아야 한다(2026-09-16 실측).
    정확·느슨 대조가 모두 빗나간 뒤에만 부른다."""
    key = re.sub(r"[^a-z0-9가-힣]", "", q.lower())
    if len(key) < 4:
        return None
    best, score = None, cutoff
    for t in _entries(con):
        for name in (t.canonical, *t.aliases):
            r = SequenceMatcher(None, key, re.sub(r"[^a-z0-9가-힣]", "", name.lower())).ratio()
            if r > score:
                best, score = t, r
    return best


def _romanized_find(ctx: "Ctx", q: str):
    """못 찾았을 때 로마자 표기로 한 번 더. 찾으면 사람이 친 한글 표기를 별칭으로 남겨 다음부터는 바로 찾게 한다."""
    roman = ctx.romanized(q)
    t = _fuzzy_find(ctx.con, q)                     # 로마자로 적은 별칭이 이미 있을 수도
    if not t and roman:
        t = _find(ctx.con, roman) or _fuzzy_find(ctx.con, roman)
    if t and q not in t.aliases:
        t.aliases = [*t.aliases, q][:12]
        ds.upsert_term(ctx.con, t)
    return t


def _status_codes(t) -> dict:
    """화면이 대시보드와 같은 말로 단계·쓸 때 조심을 붙이도록 코드를 함께 싣는다(이름은 화면 언어로 화면이 만든다).
    'lifecycle' 에 든 한국어 이름은 모델 근거와 예전 화면을 위해 그대로 둔다."""
    return {"lifecycle_code": t.lifecycle, "diffusion": t.diffusion, "risk_level": t.risk_level,
            "risk_checked_at": t.risk_checked_at.isoformat() if t.risk_checked_at else None, "lang": t.lang}


def _term_card(con, t, m) -> dict:
    # 출처 수는 사전 항목의 출처 표와 같은 수 — 화면이 '출처 n건 모두 보기' 로 그 표를 가리킨다(커뮤니티·SNS 글은 빠진다, ADR 0003)
    return {"type": "term", "term_id": t.term_id, "canonical": t.canonical,
            "definition": _clean(m.definition) if m else "", "origin": _clean(m.origin) if m else "",
            "status": t.status, "lifecycle": LIFECYCLE.get(t.lifecycle, t.lifecycle),
            "category": CATEGORY.get(t.category, t.category), **_status_codes(t),
            "evidence_count": len(shown_evidences(con, t)),
            "media": ds.get_media(con, t.term_id)}


def _list_card(con, title: str, rows: list) -> dict:
    items = []
    for t in rows[:12]:
        m = ds.current_meaning(con, t.term_id)
        items.append({"term_id": t.term_id, "canonical": t.canonical,
                      "definition": (_clean(m.definition)[:90] if m else ""),
                      "origin": (_clean(m.origin)[:120] if m and m.origin and m.origin != "unknown" else ""),
                      "lifecycle": LIFECYCLE.get(t.lifecycle, t.lifecycle), "status": t.status, **_status_codes(t)})
    return {"type": "list", "title": title, "items": items}


_UNUSABLE = re.compile(r"근거 부족|명확한 (사전적 )?(정의|의미)(는|가)? ?없")


def usable(con, t) -> bool:
    """사람에게 보여 줄 만한 뜻이 있는가. '근거 부족: 확인되지 않음' 을 카드로 내보내면
    아무 말도 안 한 것만 못하다(사용자 지적 09-16, '6-7')."""
    m = ds.current_meaning(con, t.term_id)
    d = (m.definition if m else "").strip()
    return len(d) >= 8 and not _UNUSABLE.search(d)


@contextmanager
def _dictionary(con, tables: tuple[str, ...] = ("meanings",)):
    """사람에게 보여 줄 만한 표제어 전부. 블록 안에서는 tables 를 한 번에 읽어 둔 값을 쓴다 — 사전 전체를 훑으며 표제어마다
    뜻·번역을 조회하면 Cloud SQL 에서 질문 하나가 90초를 넘겼다(staging 10-03)."""
    terms = ds.list_terms(con, ("verified", "needs_review"))
    with ds.batched(con, [t.term_id for t in terms], tables=tables):
        yield [t for t in terms if usable(con, t)]


def _entries(con) -> list:
    with _dictionary(con) as entries:
        return entries


def _find(con, q: str):
    """정확 → 조사 뗀 것 → 느슨(반복·된소리 무시) 순으로 찾는다.
    사람이 '퉁퉁퉁퉁퉁퉁싸후르가' 라고 쳐도 '퉁퉁퉁퉁 사후르' 를 찾아야 한다(2026-09-16 실측)."""
    cands = strip_particle(q)
    for cand in cands:
        t = ds.find_term(con, cand)
        # 뜻이 "근거 부족: 확인되지 않음" 인 표제어는 있어도 없는 것과 같다 — 그렇게 두어야
        # 실시간 찾아보기가 대신 답한다(사용자 지적 09-16, '6-7').
        if t and t.status in ("verified", "needs_review") and usable(con, t):
            return t
    keys = {loose_key(c) for c in cands if len(loose_key(c)) >= 2}
    if not keys:
        return None
    for t in _entries(con):
        if any(loose_key(x) in keys for x in (t.canonical, *t.aliases)):
            return t
    return None


def _same_family(con, q: str, limit: int = 5) -> list:
    """이름의 낱말 하나라도 겹치는 표제어들. "Espresso Assassino" 는 사전에 없지만
    "Cappuccino Assassino" 는 있다 — 같은 계열이라고 말해 줄 수 있어야 한다(사용자 지적 09-16)."""
    low = q.lower()
    toks = {w for w in re.split(r"[^A-Za-z0-9가-힣]+", low) if len(w) >= 5}
    words = set(re.split(r"[^A-Za-z0-9가-힣]+", low))
    out = []
    for t in _entries(con):
        names = [n.lower() for n in (t.canonical, *t.aliases)]
        # 질문 안에 표제어가 낱말째로 들어 있어도 같은 계열이다 — "스키비디 토일렛" 속 '스키비디'(skibidi 의 별칭)
        if any(w in " ".join(names) for w in toks) or any(len(n) >= 3 and n in words for n in names):
            out.append(t)
    return out[:limit]


def _by_meaning(con, text: str, limit: int = 5) -> list[tuple[int, object, object]]:
    """뜻·유래·뉘앙스에 걸리는 낱말 수로 점수를 매긴다 — 이름이 기억 안 날 때 설명으로 찾는 길."""
    ws = [w.lower() for w in keywords(text)]
    if not ws:
        return []
    out = []
    with _dictionary(con, ("meanings", "translations")) as entries:
        for t in entries:
            m = ds.current_meaning(con, t.term_id)
            tr = ds.get_translation(con, t.term_id, "ko")
            hay = " ".join(filter(None, [t.canonical, *t.aliases,
                                         (m.definition if m else ""), (m.origin if m else ""), (m.nuance if m else ""),
                                         (tr.definition if tr else "")])).lower()
            hits = sum(1 for w in ws if w in hay)
            # 낱말 하나가 우연히 걸린 것을 '가장 가까운 것' 이라고 내놓으면 틀린 답이 된다 —
            # "Italian brainrot" 에 skibidi 를 답하던 문제(2026-09-16 실측). 낱말이 둘 이상이면 둘 이상 맞아야 한다.
            if hits >= (1 if len(ws) == 1 else 2):
                out.append((hits, t, m))
    out.sort(key=lambda x: -x[0])
    return out[:limit]


def lookup_term(ctx: Ctx, args: dict) -> str:
    q = _clean(str(args.get("term", "")))
    if not q:
        return "term 인자가 비었습니다."
    t = _find(ctx.con, q) or _romanized_find(ctx, q)
    if not t:
        fam = _same_family(ctx.con, q) or _same_family(ctx.con, ctx.romanized(q))
        if fam:
            for t in fam:
                ctx.seen(t.term_id)
            ctx.card(_list_card(ctx.con, f"'{q}' 와 같은 계열", fam))
            fm = ds.current_meaning(ctx.con, fam[0].term_id)
            ctx.offer(fam[0].canonical, _clean(fm.definition) if fm else "")
            lines = "\n".join(f"- {t.canonical}: "
                              f"{_clean((ds.current_meaning(ctx.con, t.term_id) or fm).definition)[:70]}" for t in fam)
            ctx.missed(q)
            return (f"'{q}' 와 똑같은 표제어는 없습니다. 같은 계열로는 이런 것들이 있습니다:\n{lines}\n"
                    f"이 목록에 있는 이름만 말하라. 다른 이름을 지어내지 마라.")
        near = _by_meaning(ctx.con, q)
        if near:
            lines = "\n".join(f"- {x[1].canonical}: {_clean(x[2].definition)[:60] if x[2] else ''}" for x in near[:3])
            return f"'{q}' 와 정확히 같은 표제어는 없습니다. 비슷한 것:\n{lines}\n이 중 맞는 것이 있으면 그 이름으로 다시 찾아보세요."
        ctx.missed(q)
        return f"'{q}' 는 검증된 사전에 없습니다."
    ctx.seen(t.term_id)
    m = ds.current_meaning(ctx.con, t.term_id)
    ctx.card(_term_card(ctx.con, t, m))
    ctx.offer(t.canonical, _clean(m.definition) if m else "")   # 모델이 "없다" 고 해도 이걸 내보낸다
    if m:
        ctx.offer(t.canonical, _clean(m.definition))
    evs = shown_evidences(ctx.con, t)   # 사전 항목과 같은 근거 — 딴 글의 출처도, 커뮤니티·SNS 사이트 이름도 대지 않는다(ADR 0003)
    doms = sorted({e.source_domain for e in evs})[:4]
    if not m:
        return f"'{t.canonical}' 는 사전에 있지만 뜻이 아직 정리되지 않았습니다."
    state = "확인됨" if t.status == "verified" else "확인 중(사람 검수 대기)"
    lines = [f"표제어: {t.canonical} ({state}, {LIFECYCLE.get(t.lifecycle, t.lifecycle)})",
             f"뜻: {_clean(m.definition)}"]
    if m.expansion:
        lines.append(f"풀이: {_clean(m.expansion)}")
    if m.origin:
        lines.append(f"유래: {_clean(m.origin)}")
    if m.nuance:
        lines.append(f"뉘앙스: {_clean(m.nuance)}")
    lines.append(f"근거: {len(evs)}건 ({', '.join(doms) if doms else '없음'})")
    return "\n".join(lines)


def search_terms(ctx: Ctx, args: dict) -> str:
    """이름을 모를 때 쓴다. 통째로 들어 있으면 그것부터, 아니면 뜻·유래에 걸리는 낱말 수로 순위를 매긴다."""
    raw = _clean(str(args.get("query", "")))
    if not raw:
        return "query 인자가 비었습니다."
    hit = _find(ctx.con, raw) or _romanized_find(ctx, raw)   # 이름을 넘긴 것일 수도 있다
    if hit:
        ctx.seen(hit.term_id)
        return lookup_term(ctx, {"term": hit.canonical})
    q = raw.lower()
    exact = []
    with _dictionary(ctx.con) as entries:
        for t in entries:
            m = ds.current_meaning(ctx.con, t.term_id)
            hay = " ".join([t.canonical, *t.aliases, (m.definition if m else "")]).lower()
            if q in hay:
                exact.append((t, m))
            if len(exact) >= 8:
                break
    rows = [(t, m) for t, m in exact] or [(t, m) for _, t, m in _by_meaning(ctx.con, raw)]
    if not rows:
        ctx.missed(raw)
        fam = _same_family(ctx.con, raw) or _same_family(ctx.con, ctx.romanized(raw))
        if fam:
            for t in fam:
                ctx.seen(t.term_id)
            ctx.card(_list_card(ctx.con, f"'{raw}' 와 같은 계열", fam))
            fm = ds.current_meaning(ctx.con, fam[0].term_id)
            ctx.offer(fam[0].canonical, _clean(fm.definition) if fm else "")
            names = "\n".join(f"- {t.canonical}: {_clean((ds.current_meaning(ctx.con, t.term_id) or fm).definition)[:70]}"
                              for t in fam)
            return (f"'{raw}' 와 똑같은 표제어는 없습니다. 같은 계열로는 이런 것들이 있습니다:\n{names}\n"
                    f"이 목록에 있는 이름만 말하라. 다른 이름을 지어내지 마라.")
        # 없다고만 하면 모델이 있을 법한 이름을 지어낸다(2026-09-16 실측). 지어내지 말라고 못을 박는다.
        return (f"'{raw}' 로 찾은 표제어가 없습니다. 비슷한 표제어도 없습니다. "
                f"없는 표제어 이름을 지어내지 말고, 사전에 없다고만 답하라.")
    for t, _ in rows:
        ctx.seen(t.term_id)
    ctx.card(_term_card(ctx.con, rows[0][0], rows[0][1]))
    if len(rows) > 1:
        ctx.card(_list_card(ctx.con, f"'{raw}' 와 가까운 표제어", [t for t, _ in rows[1:]]))
    top, tm = rows[0]
    ctx.offer(top.canonical, _clean(tm.definition) if tm else "")
    head = f"가장 가까운 것: {top.canonical} — {_clean(tm.definition)[:110] if tm else '뜻 미정리'}"
    rest = "\n".join(f"- {t.canonical}: {_clean(m.definition)[:70] if m else '뜻 미정리'}" for t, m in rows[1:])
    return head + ("\n그 밖에:\n" + rest if rest else "")


def why_trending(ctx: Ctx, args: dict) -> str:
    term = _clean(str(args.get("term", "")))
    region = _clean(str(args.get("region", ""))).upper()[:2]
    if not term:
        return "term 인자가 비었습니다."
    got = ds.get_explanation(ctx.con, term, region) if region else None
    if not got:
        for (t, r), x in ds.explanations_by_region(ctx.con).items():
            if ds.norm(term) == t:
                got = (x, None)
                region = r
                break
    if not got:
        return f"'{term}' 의 급증 원인 조사 기록이 없습니다."
    x = got[0]
    actors = ", ".join(a.name for a in x.actors[:4]) or "없음"
    evs = [e for e in ds.list_evidences(ctx.con, f"q|{ds.norm(x.term)}|{x.region}") if not is_community_post(e)]   # 나라 화면의 근거 목록과 같은 규칙
    return (f"검색어: {x.term} ({REGION.get(x.region, x.region)}, {x.date})\n계기: {x.trigger}\n왜 지금: {_clean(x.why_now)}\n"
            f"관련 인물·주체: {actors}\n근거: {len(evs)}건")


def country_trends(ctx: Ctx, args: dict) -> str:
    region = _clean(str(args.get("region", ""))).upper()[:2]
    if not region:
        return "region 인자가 비었습니다 (ISO 2글자 국가코드)."
    cached = ds.cache_get(ctx.con, "board")
    if not cached:
        return "보드가 아직 만들어지지 않았습니다."
    import json

    items = [i for i in json.loads(cached[0]).get("items", []) if i.get("region") == region]
    if not items:
        return f"{REGION.get(region, region)} 자료가 아직 없습니다."
    # 네이버쇼핑 항목은 '분야 이름'(패션의류·식품…)이라 유행어가 아니다. 섞어서 내보내면 "한국 최신 밈" 질문에 엉뚱한 답이 나간다.
    shop = {"패션의류", "패션잡화", "화장품/미용", "식품", "디지털/가전"}
    search = [i for i in items if i.get("term") not in shop][:10]
    cats = [i.get("term") for i in items if i.get("term") in shop]
    name = REGION.get(region, region)
    out = []
    if search:
        out.append(f"{name} 에서 지금 많이 검색되는 것 (유행어가 아니라 검색어다):\n"
                   + "\n".join(f"- {i.get('term')} ({CATEGORY.get(i.get('category'), i.get('category'))})" for i in search))
    if cats:
        out.append(f"소비 분야 추세(쇼핑 분야 이름일 뿐 표현이 아니다): {', '.join(cats)}")
    out.append("이 나라의 '유행어·밈' 을 물었다면 list_terms 를 region 인자로 불러라 — 검증된 사전 표제어가 답이다.")
    return "\n".join(out)


def term_usage(ctx: Ctx, args: dict) -> str:
    q = _clean(str(args.get("term", "")))
    t = _find(ctx.con, q) if q else None
    if not t:
        return f"'{q}' 는 사전에 없습니다."
    ctx.seen(t.term_id)
    rows = ds.get_usage(ctx.con, t.term_id)
    measured = [r for r in rows if r["source"] == "datalab"]      # 세대 비중은 실측(네이버 데이터랩)만 — 모델 추정은 '추정' 으로만 말한다(Plan 15)
    weekly = ds.get_weekly(ctx.con, t.term_id, weeks=6)
    gens = ", ".join(GEN.get(g, g) for g in sorted({r["generation"] for r in measured}))
    if not gens:
        guess = ", ".join(GEN.get(g, g) for g in sorted({r["generation"] for r in rows} - {"all"}))
        gens = f"실측 자료 없음 (조사 때의 추정: {guess})" if guess else "자료 없음"
    regions = ", ".join(REGION.get(x, x) for x in sorted({r["region"] for r in rows})) or "자료 없음"
    trend = "자료 없음"
    if len(weekly) >= 2:
        trend = "오르는 중" if weekly[-1][1] > weekly[0][1] else ("지는 중" if weekly[-1][1] < weekly[0][1] else "비슷함")
    # 세대·나라 비중과 주별 언급은 글보다 막대·선이 빠르다 — 화면 조각으로도 내보낸다
    share: dict[str, float] = {}
    for r in measured:
        share[GEN.get(r["generation"], r["generation"])] = share.get(GEN.get(r["generation"], r["generation"]), 0.0) + float(r.get("share") or 0)
    total = sum(share.values()) or 1.0
    ctx.card({"type": "usage", "term": t.canonical, "term_id": t.term_id,
              "bars": [{"label": k, "ratio": round(v / total, 3)} for k, v in sorted(share.items(), key=lambda x: -x[1])[:6]],
              "regions": [REGION.get(x, x) for x in sorted({r["region"] for r in rows})][:8],
              "weekly": [{"week": w, "count": c} for w, c in weekly]})
    return f"표제어: {t.canonical}\n쓰는 세대: {gens}\n쓰는 나라: {regions}\n최근 6주 언급: {trend}"


CATEGORY = {"slang_meme": "유행어·밈", "song_challenge": "노래·챌린지", "fashion_beauty": "패션·뷰티",
            "food": "음식", "product": "제품", "people_content": "인물·콘텐츠", "sports_event": "스포츠·사건"}

# 사전에 실제로 붙는 분류는 slang·meme·song·other 뿐이다. 모델은 트렌드 쪽 이름(slang_meme)이나 한국어로 넘긴다 —
# 알아들을 수 있으면 맞춰 주고, 모르는 값이면 거르지 않는다. 빈 목록을 돌려주면 "사전에 없다"는 틀린 답이 나간다(09-16 실측).
_CAT_ALIAS = {"slang_meme": ("slang", "meme"), "유행어·밈": ("slang", "meme"), "유행어": ("slang",), "밈": ("meme",),
              "meme": ("meme",), "slang": ("slang",), "song_challenge": ("song",), "노래": ("song",), "song": ("song",),
              "other": ("other",)}


def _categories(cat: str) -> tuple[str, ...]:
    return _CAT_ALIAS.get(cat.lower().strip(), ())


def list_terms(ctx: Ctx, args: dict) -> str:
    """조건에 맞는 표제어 목록. '20대가 쓰는 말', '한국 유행어' 처럼 하나를 콕 집지 않고 둘러볼 때 쓴다.
    급상승 검색어(country_trends)와 다르다 — 이건 검증을 통과해 사전에 오른 표현들이다."""
    gen = _arg(args, "generation")
    region = _arg(args, "region").upper()[:2]
    cat = _arg(args, "category")
    want = _categories(cat)
    terms = ds.list_terms(ctx.con, ("verified",))
    # 표제어마다 사용층·주간 언급을 조회하면 Cloud SQL 에서 90초를 넘겼다(staging 10-03) — 두 표만 한 번에 읽는다
    with ds.batched(ctx.con, [t.term_id for t in terms], tables=("usage", "weekly")):
        rows = []
        for t in terms:
            if want and t.category not in want:
                continue
            if gen or region:
                use = ds.get_usage(ctx.con, t.term_id)
                if gen and not any(u["generation"] in (gen, "all") for u in use):
                    continue
                if region and not any(u["region"] == region for u in use):
                    continue
            rows.append(t)
        if not rows:
            what = " · ".join(filter(None, [GEN.get(gen, gen), REGION.get(region, region), CATEGORY.get(cat, cat)])) or "조건 없음"
            return f"{what} 에 해당하는 표제어가 사전에 없습니다. 조건을 빼고 list_terms 를 한 번 더 불러 보라."
        # 나라를 물었으면 그 나라 말로 된 표제어를 앞에 — "한국 밈" 에 영어판 문서 제목이 먼저 나오면 엉뚱하다.
        # 그다음은 실제로 쓰이는 걸 본 표현. 위키에서 막 받아 온 것들은 last_seen 이 전부 지금이라 그냥 두면 목록을 덮는다.
        # 나라를 물었으면 그 나라 말, 아니면 지금 답하는 말. 한국어로 물었는데 일본어 표제어가 먼저 나오면 엉뚱하다.
        lang_of = {"KR": "ko", "JP": "ja", "ID": "id", "US": "en", "GB": "en"}.get(region, "") or ctx.lang
        # '요즘' 은 실제 언급으로 잰다. last_seen 은 예전에 조사할 때마다 덮여서 '최근 조사한 순' 이 돼 있었다.
        rows = [t for t in rows if not unsafe(t.canonical) or t.risk_level == "none"]   # 검수자가 '문제 없음' 으로 푼 오탐은 보인다
        recent = {t.term_id: sum(c for _, c in ds.get_weekly(ctx.con, t.term_id, weeks=4)) for t in rows}
        rows.sort(key=lambda t: (1 if lang_of and t.lang == lang_of else 0, recent[t.term_id],
                                 1 if ds.get_usage(ctx.con, t.term_id) else 0), reverse=True)
        rows = rows[:12]
    for t in rows:
        ctx.seen(t.term_id)
    ctx.card(_list_card(ctx.con, " · ".join(filter(None, [GEN.get(gen, gen), REGION.get(region, region),
                                                          CATEGORY.get(cat, cat)])) or "사전에 오른 표현", rows))
    m0 = ds.current_meaning(ctx.con, rows[0].term_id)
    ctx.offer(rows[0].canonical, _clean(m0.definition) if m0 else "")
    head = f"사전에 {len(rows)}개 (최근 본 순):"
    body = []
    for t in rows:
        m = ds.current_meaning(ctx.con, t.term_id)
        body.append(f"- {t.canonical}: {_clean(m.definition)[:60] if m else '뜻 미정리'} ({LIFECYCLE.get(t.lifecycle, t.lifecycle)})")
    return head + "\n" + "\n".join(body)


def content_memes(ctx: Ctx, args: dict) -> str:
    """작품·콘텐츠 하나에서 나라마다 파생된 밈 — 콘텐츠 조사 에이전트가 위키·Know Your Meme 을 직접 읽고 규칙 확인을 거친 것."""
    from . import content_agent

    q = _arg(args, "content")
    hit = content_agent.find_content(ctx.con, q)
    if not hit:
        ctx.missed(q)
        return f"'{q}' 에서 파생된 밈은 아직 조사하지 않았습니다. read_web 으로 그 작품의 위키 문서를 직접 읽어 볼 수 있다."
    key, name = hit
    ctx.content = name
    found, pairs = content_agent.memes(ctx.con, key)
    region = _arg(args, "region").upper()[:2]
    rows = [f for f in found if not region or f["region"] in (region, "GLOBAL")]
    lines = [f"{name} 에서 나온 밈 {len(rows)}개 (나라별, 근거 문서 있음):"]
    for f in sorted(rows, key=lambda f: (f["region"] != (region or "KR"), f["region"]))[:15]:
        lines.append(f"- [{REGION.get(f['region'], '영어권' if f['region'] == 'GLOBAL' else f['region'])}] {f['name']}: {f['description'][:70]}")
    same = [p for p in pairs if p["verified"]]
    if same:
        lines.append("나라마다 이름이 다른 같은 밈: " + "; ".join(f"{p['a']}({p['a_region']}) = {p['b']}({p['b_region']})" for p in same[:6]))
    return "\n".join(lines)


def read_web(ctx: Ctx, args: dict) -> str:
    """사전에 없는 것을 물으면 허용한 위키(나무위키·위키백과·Know Your Meme)를 직접 열어 읽는다. 커뮤니티 글은 열지 않는다.
    읽은 것은 저장하지 않는다 — 답에는 '위키 문서에 따르면' 으로 출처를 밝힌다."""
    from . import web_tools as W

    title, site, lang = _arg(args, "title"), _arg(args, "site") or "namu", (_arg(args, "lang") or ctx.lang or "ko")[:2]
    if not title:
        return "title 이 필요하다"
    url = {"namu": f"https://namu.wiki/w/{title}", "wikipedia": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
           "kym": f"https://knowyourmeme.com/memes/{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}"}.get(site, "")
    if not url:
        return "site 는 namu·wikipedia·kym 가운데 하나"
    sec = _arg(args, "section")
    text = W.section_text(url, sec) if sec else ""
    page = W.open_page(url)
    if "error" in page and site == "wikipedia":
        hits = W.search("wikipedia", title, lang).get("results", [])
        if hits:
            url = hits[0]["url"]
            page = W.open_page(url)
    if "error" in page:
        return f"'{title}' 문서를 {site} 에서 찾지 못했습니다."
    ctx.card({"type": "web", "title": page["title"], "url": url})
    heads = ", ".join(page.get("headings", [])[:20])
    return f"[{page['title']}] {url}\n절: {heads}\n{(text or page['text'])[:900]}"


_INDEX = None


def search_index(ctx: Ctx, args: dict) -> str:
    """위키 본문 색인(나무위키·위키백과 여러 언어·PTT·홍콩·Trend A Word, 하루 두 번 갱신)에서 질문과 가까운 문단을 찾는다.
    사전에 없는 밈, 작품 문서 안에 묻힌 장면·대사, 다른 나라에서 부르는 이름을 찾을 때. 조각마다 문서 제목과 주소가 붙는다."""
    global _INDEX
    from . import doc_index

    q = _arg(args, "query")
    if not q:
        return "query 가 필요하다"
    if _INDEX is None:
        if not doc_index.INDEX_PATH.exists():
            return "색인이 아직 없습니다."
        _INDEX = doc_index.connect()
    found = doc_index.search(_INDEX, q, k=8)
    if not found:
        return f"색인에서 '{q}' 와 가까운 문단을 찾지 못했습니다."
    ctx.content = ctx.content or "index"
    for f in found[:2]:
        ctx.card({"type": "web", "title": f["title"], "url": f["url"]})
    lines = [f"[{i}] {f['title']}{' > ' + f['heading'] if f['heading'] else ''} ({f['url']})\n{f['text']}" for i, f in enumerate(found, 1)]
    return "위키 문서 색인에서 찾은 문단(이 안의 이름은 그대로 쓰고 문서 제목을 출처로):\n\n" + "\n\n".join(lines)


_TOOLS = {"lookup_term": lookup_term, "search_terms": search_terms, "why_trending": why_trending,
          "country_trends": country_trends, "term_usage": term_usage, "list_terms": list_terms,
          "content_memes": content_memes, "read_web": read_web, "search_index": search_index}
