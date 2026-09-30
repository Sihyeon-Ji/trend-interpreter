"""4단계 리서치 + 검증. 후보를 용어로 올리고 Gemini(Search grounding)로 조사한 뒤, 근거를 '원문'으로 모아 게이트에 넣는다.
통과 → verified_auto 뜻(버전). 실패 → unverified 뜻 + 검수 큐. 판정은 verification.gate 가 한다."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx

from google.genai import errors

from ..config import ENGLISH_EDITIONS, GEMINI_FALLBACK_MODEL, GEMINI_MODEL, home_region, region_cycle
from ..interpreters.gemini_research import research_term
from ..lifecycle import recheck_interval_days
from ..schemas import Evidence, MeaningDraft, ShortsInterpretation, ShortsVideo, Term
from ..storage import dictionary_store as ds
from ..collectors.naver_search import for_model
from ..verification import anchor_hit, gate, normalize_url, reference_doc
from .gemini import BudgetExhausted, budget_left, local_ok, structured
from .match import mentions, same_term
from .runs import stage
from ..storage.db import Connection

MIN_CANDIDATE_COUNT = 2  # 소스 두 번 이상 등장했거나 쇼츠에서 나온 후보만
DICT_KINDS = {"slang": "slang", "slang_meme": "slang", "meme": "meme", "dance": "meme", "challenge": "meme", "song": "song"}  # kind → 사전 분류
STRONG_KINDS = {"slang", "slang_meme", "song", "challenge"}  # 한 번만 보여도 승격. '밈' 이름은 두 번째 등장을 기다린다
# 목표 지역 가운데 사전이 빈 곳(09-29 대시보드: HK 2 · SG 0 · MY 0 · VN 0 · PH 1 · TH 2 · ID 3). 새 표제어 칸 가운데 REGION_SLOTS 칸은
# 이 지역 후보에 출처와 상관없이 많이 본 순으로 먼저 준다 — spot 후보는 출처 순서로 늘 맨 뒤라 홍콩에서 네 번 본 行得㗎啦 가 09-28 부터 기다렸다.
UNDER_COVERED = ("HK", "SG", "MY", "VN", "PH", "TH", "ID")
REGION_SLOTS = 3
MAX_WEB_FETCH = 6
MAX_HOPS = 6      # 그라운딩 주소는 구글의 넘겨주기 주소다 — 넘겨주기를 한 칸씩 따라가며 어디로 가는지 본다
UA = "Mozilla/5.0 (compatible; trend-agents/0.1)"


def _norm(s: str) -> str:
    return "".join(s.split()).lower()



def news_domain(n) -> str:
    """Google News RSS 는 링크가 전부 news.google.com 이라 발행사(source)를 출처로 삼는다."""
    host = urlparse(n.link).netloc.removeprefix("www.")
    if "news.google." in host and getattr(n, "source", ""):
        return n.source.strip().lower().replace(" ", "")
    return host

def _excerpt(text: str, term: str, width: int = 240) -> str:
    """용어가 실제로 들어 있는 문장 하나. 없으면 빈 문자열(앵커 실패 → 게이트가 제외한다)."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"\s+", " ", t)
    for sent in re.split(r"(?<=[.!?。])\s+|\n", t):
        if mentions(sent, term):
            return sent.strip()[:width]
    return ""


def _kym_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "knowyourmeme.com" or host.endswith(".knowyourmeme.com")


def web_evidence(term: str, urls: list[str], aliases: list[str] | tuple[str, ...] = ()) -> list[Evidence]:
    """모델이 든 웹 주소의 제목과 용어가 든 문장. 넘겨주기는 한 칸씩 따라가며, Know Your Meme 으로 가면 여기서 받지 않는다 —
    이용 약관 때문에 꺼져 있으면(KNOWYOURMEME_ENABLED) 버리고, 켜져 있으면 수집기(knowyourmeme.from_url: /memes/ 문서만, 2초 간격,
    정직한 User-Agent, 주소와 제목만)로 넘긴다. 그라운딩 주소는 구글의 넘겨주기라 처음 주소만 보고는 어디로 가는지 모른다."""
    from ..collectors import knowyourmeme

    out: list[Evidence] = []
    with httpx.Client(follow_redirects=False, timeout=8.0, headers={"User-Agent": UA}) as c:
        for u in urls[:MAX_WEB_FETCH]:
            try:
                r, final = None, u
                for _ in range(MAX_HOPS):
                    if _kym_host(final):
                        break
                    r = c.get(final)
                    if not r.is_redirect:
                        break
                    final, r = urljoin(final, r.headers.get("location", "")), None
                if _kym_host(final):
                    if knowyourmeme.enabled():
                        out += knowyourmeme.from_url(final, term, aliases) or []
                    continue
                if r is None:              # 넘겨주기가 끝나지 않았다
                    continue
                final = str(r.url)
                body = r.text[:400_000]
            except Exception:
                continue
            title = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.S | re.I)
            domain = urlparse(final).netloc.removeprefix("www.")
            out.append(Evidence(evidence_id=ds.new_id("e", final), kind="web", url=final, title=html.unescape(title.group(1)).strip()[:200] if title else "",
                                source_domain=domain, observed_at=datetime.now(timezone.utc), excerpt=_excerpt(body, term)))
    return out


def first_party_evidence(con: Connection, term: str, aliases: list[str] = ()) -> list[Evidence]:
    key = _norm(term)
    out: list[Evidence] = []
    for (j,) in con.execute("SELECT json FROM news").fetchall():
        from ..schemas import NewsItem

        n = NewsItem.model_validate_json(j)
        if mentions(n.title, term, aliases):
            out.append(Evidence(evidence_id=ds.new_id("e", n.link), kind="news", url=n.link, title=n.title[:200], source_domain=news_domain(n),
                                observed_at=n.published_at or datetime.now(timezone.utc), excerpt=n.title))
    for j, vj in con.execute("SELECT i.json, v.json FROM interpretations i LEFT JOIN videos v ON v.video_id=i.video_id").fetchall():
        it = ShortsInterpretation.model_validate_json(j)
        hit = [m for m in it.memes if same_term(m.name, term, aliases)]  # 밈 이름은 표기 동일성으로 (숫자꼴 용어도 쇼츠 근거를 잃지 않게)
        if hit:
            v = ShortsVideo.model_validate_json(vj) if vj else None
            # 발췌는 해석 모델이 쓴 문장이라 앵커가 될 수 없다(derived). 제목은 실제 영상 제목일 때만 원문이므로, 영상 행이 없으면 비운다.
            out.append(Evidence(evidence_id=ds.new_id("e", it.url), kind="short", url=it.url, title=(v.title[:200] if v else ""), source_domain="youtube.com",
                                observed_at=v.published_at if v else datetime.now(timezone.utc), excerpt=((f"“{hit[0].quote}” — " if hit[0].quote else "") + f"{hit[0].name}: {hit[0].origin_hypothesis}")[:240], derived=True))
    for t, region, d, src in con.execute("SELECT term, region, MAX(date), source FROM trend_queries GROUP BY term, region, source").fetchall():
        if key == _norm(t):
            if src == "namu_rank":   # 나무위키 실시간 검색어는 Google Trends 가 아니다 — 출처를 바르게 적는다(한 사이트가 독립 출처 둘로 세지지 않게)
                url, title, domain = "https://namu.wiki/", f"나무위키 실시간 검색어: {t}", "namu.wiki"
            else:
                url, title, domain = f"https://trends.google.com/trending?geo={region}", f"Google Trends {region} {src}: {t}", "trends.google.com"
            out.append(Evidence(evidence_id=ds.new_id("e", f"{url}|{t}|{d}"), kind="datalab", url=url, title=title, source_domain=domain,
                                observed_at=datetime.fromisoformat(d).replace(tzinfo=timezone.utc), excerpt=t))
    return out


def _kind(c) -> str:
    m = re.search(r"kind=(\w+)", c.note)
    return m.group(1) if m else ""


def _ready(c) -> bool:
    """승격할 만큼 봤나. 두 번 이상 봤거나, 한 번으로 되는 종류(유행어·노래·챌린지)이거나 출처(위키·질문·나무위키)일 때.
    위키백과에 문서가 있다는 것은 편집자가 백과사전 항목으로 쓸 만큼 자리잡은 표현이라는 뜻이다 —
    트렌드 목록에서 두 번 본 것보다 강한 신호라서 한 번에 승격한다. verified 여부는 여전히 게이트가 정한다.
    사람이 직접 물어본 말(hunt)은 수요가 곧 근거다. 위키 문서가 있는 것과 같은 급으로 본다."""
    kind = _kind(c)
    return kind in DICT_KINDS and (c.count >= MIN_CANDIDATE_COUNT or kind in STRONG_KINDS or bool({"wiki", "hunt", "namu"} & set(c.sources)))


def target_region(c) -> str | None:
    """후보가 사전이 빈 목표 지역(UNDER_COVERED)의 말이면 그 나라. 표제어의 나라(글자·언어, 광동어는 홍콩)가 그 지역이거나,
    그 지역에서 봤고 그 지역이 그 언어를 쓰는 곳(중국어 → 홍콩, 영어 → 싱가포르·말레이시아·필리핀)일 때만 — 인도네시아·싱가포르
    쇼츠 제목에서 본 spot 후보는 대부분 힌디어였다(09-29). 본 곳만으로 정하면 그런 말이 칸을 가져간다."""
    home = home_region(c.text, c.lang)
    if home in UNDER_COVERED:
        return home
    uses = (*region_cycle(c.text, c.lang), *(ENGLISH_EDITIONS if c.lang == "en" else ()))
    return next((r for r in c.regions if r in UNDER_COVERED and r in uses), None)


def promote_candidates(con: Connection, limit: int) -> list[Term]:
    """후보 → 용어(researching). 쇼츠에서 나온 것 또는 2회 이상 본 것. REGION_SLOTS 칸은 사전이 빈 목표 지역의 후보에 먼저 준다."""
    terms: list[Term] = []
    # 사람이 물어본 말·위키 문서가 있는 말을 먼저 조사한다. spot 출신이 앞을 막으면 좋은 후보가 대기열 뒤에 묻힌다.
    # 나무위키 분류는 오래된 한국어 말을 채워 넣는 것이라 지금 뜨는 신호(위키·쇼츠) 뒤에 두고, 한 번에 절반까지만 —
    # 앞에 두었더니 나무위키 'ㄱ' 항목 47개가 대만 위키 후보를 모두 막았다(2026-09-29 검토).
    first = {"hunt": 0, "wiki": 1, "shorts": 2, "namu": 3}
    namu_cap, namu_n = max(1, limit // 2), 0
    new = ds.candidates(con, "new", 400)          # 많이 본 순
    pool = sorted(new, key=lambda c: min((first.get(s, 9) for s in c.sources), default=9))
    # 사전이 빈 목표 지역의 후보는 출처와 상관없이 많이 본 순으로 REGION_SLOTS 개까지 맨 앞에 선다. 나머지 칸은 예전 순서
    reserved = [c for c in new if target_region(c) and _ready(c) and not ds.find_term(con, c.text)][:min(REGION_SLOTS, limit)]
    ahead = {c.candidate_id for c in reserved}
    for c in reserved + [c for c in pool if c.candidate_id not in ahead]:
        only_namu = set(c.sources) <= {"namu"}
        if only_namu and namu_n >= namu_cap:
            continue
        kind = _kind(c)
        if kind not in DICT_KINDS:  # 분류가 유행어·밈·노래·챌린지로 보지 않은 것은 사전에 넣지 않는다 (brics, aqi, iPhone Duo 같은 일반 검색어)
            ds.set_candidate_status(con, c.candidate_id, "rejected")
            continue
        if not _ready(c):
            continue
        if ds.find_term(con, c.text):
            ds.set_candidate_status(con, c.candidate_id, "promoted")
            continue
        alias = re.search(r"alias=(.+?)(?:\s+\w+=|$)", c.note)
        t = Term(term_id=ds.new_id("t", f"{_norm(c.text)}|{c.lang}"), canonical=c.text, lang=c.lang, status="researching", category=DICT_KINDS[kind],
                 aliases=[alias.group(1).strip()] if alias else [],
                 first_seen=c.first_seen, last_seen=c.last_seen)
        ds.upsert_term(con, t)
        ds.set_candidate_status(con, c.candidate_id, "promoted")
        terms.append(t)
        namu_n += only_namu
        if len(terms) >= limit:
            break
    return terms


def due_for_recheck(con: Connection, limit: int) -> list[Term]:
    """재검증 주기가 지난 것 — 아직 조사 기록이 없는 'researching' 용어, 사전에 오른 말(verified), 검수 대기 순으로, 같은 무리에서는 가장 오래전에
    조사한 것부터. 예전에는 조사 중 다음이 이름순이라 확인된 말이 검수 대기 수백 개 뒤로 밀려 2주 넘게 다시 보지 못했고, 그동안 '마지막으로
    쓰인 때' 가 늙어 꾸준한 밈이 '지는 중' 이 됐다(검토 3차)."""
    out: list[tuple] = []
    now = datetime.now(timezone.utc)
    order = {"researching": 0, "verified": 1}
    for t in ds.list_terms(con, ("researching", "verified", "needs_review")):
        cm = ds.current_meaning(con, t.term_id)
        if cm and cm.verification == "verified_human":
            continue
        if under_review(con, t.term_id):
            continue
        last = ds.last_researched(con, t.term_id)
        if last is None or (now - last).days >= recheck_interval_days(t.lifecycle):
            out.append((order.get(t.status, 2), last.isoformat() if last else "", t))
    out.sort(key=lambda x: (x[0], x[1]))
    return [t for _, _, t in out[:limit]]


OFFLINE_PROMPT = """아래는 우리가 직접 수집한 근거(뉴스 제목·쇼츠 해석·검색 트렌드·웹 발췌)다. 이것만 보고 '{term}' 의 뜻을 JSON(MeaningDraft)으로 구조화하라.
근거에 **없는 사실**은 만들지 마라. 다만 근거가 사전식 정의 문장을 주지 않는 것은 정상이다 — 무엇이 나오는지·어디서 시작했는지·
사람들이 어떻게 쓰는지가 근거에 적혀 있으면 그것을 모아 뜻을 네가 정리해 써라. 그게 이 일이다.
'근거 부족: 확인되지 않음' 은 근거에 이 표현에 관한 내용이 사실상 없을 때만 쓴다 (이름만 스쳐 지나가고 무엇인지 알 길이 없을 때).
그럴 때만 self_confidence 를 0.2 이하로 두라.
expansion 은 **줄임말을 푼 것만** 쓴다 (자만추 → "자연스러운 만남 추구"). 몇 낱말이면 되고, 줄임말이 아니면 null 이다.
뜻 설명을 여기 넣지 마라 — 그건 definition 자리다. generations 는 근거가 가리키는 세대, regions 는 ISO 국가코드.
is_expression: 유행어·밈·줄임말·챌린지·노래 후렴처럼 '요즘 생겨나 퍼진 표현'이면 true. 상품·기관·인물·정책·사건 이름, 그리고 전통 구호·종교 기도문·명절 인사·오래된 관용구는 false (예: 'Ganpati Bappa Morya' 는 가네샤 축제의 전통 구호라 false — 뜻은 설명할 수 있어도 유행어가 아니다).

근거:
{notes}"""


def _term_sentences(text: str, term: str, limit: int = 4) -> list[str]:
    """본문에서 용어가 실제로 나오는 문장들. 설명이 딸린 문장을 앞에 둔다
    (이름만 적힌 목록·소제목 "=== 이름 ===" 은 뒤로)."""
    from ..verification import anchor_hit

    rich, bare = [], []
    for sent in re.split(r"(?<=[.!?。])\s+|\n+", text):
        sent = sent.strip().strip("=").strip()
        if not (10 <= len(sent) <= 400):
            continue
        if not anchor_hit(term, Evidence(evidence_id="x", kind="wiki", url="https://wikipedia.org", title="",
                                         source_domain="wikipedia.org", observed_at=datetime.now(timezone.utc), excerpt=sent)):
            continue
        (rich if len(sent) >= len(term) + 30 else bare).append(sent)
        if len(rich) >= limit:
            break
    return (rich + bare)[:limit]


# 위키백과 본문에서 그 이름이 나온 문장들. 근거 발췌는 한 건만 쓰지만, 모델이 뜻을 쓸 때는 여러 문장이 있어야
# "근거 부족" 이라고만 답하지 않는다(2026-09-16 실측: 문장 하나로는 자기확신 0.20).
WIKI_CONTEXT: dict[str, list[str]] = {}


def _wikipedia_evidence(term: str, lang: str) -> list[Evidence]:
    """위키백과에 그 이름이 적힌 문장이 있으면 근거 한 건. 뜻은 여기서 베끼지 않는다 —
    게이트가 볼 '이 표현이 실재한다'는 증거다.

    개별 밈은 대개 독립 문서가 아니라 상위 문서로 넘어간다("Bombardiro Crocodilo" → "Italian brainrot").
    요약 앞 600자에는 이름이 없고 본문 중간 목록에 있어서, 본문을 받아 그 이름이 나오는 문장을 쓴다(실측 09-16).
    """
    out: list[Evidence] = []
    for lg in dict.fromkeys([lang, "en"]):
        e, sents = wikipedia_doc(term, lg)
        if e:
            WIKI_CONTEXT[term] = (WIKI_CONTEXT.get(term, []) + sents)[:6]
            out.append(e)
    return out


def wikipedia_doc(term: str, lg: str, *, strict: bool = False) -> tuple[Evidence | None, list[str]]:
    """위키백과 한 언어판에서 그 이름이 나온 문서 한 쪽(근거)과 그 문장들. 없으면 (None, []). 문서 대조(Plan 12)도 이것으로 찾는다.
    strict 면 닿지 못했을 때(429·5xx·네트워크) wikipedia_search.Unreachable 을 던진다 — '문서 없음' 과 가르려고."""
    from ..collectors import wikipedia_search

    try:
        sm = wikipedia_search.summary(lg, term, strict=strict)
        if not sm:
            titles = wikipedia_search.search(lg, term, limit=1)
            sm = wikipedia_search.summary(lg, titles[0], strict=strict) if titles else None
        if not sm:
            return None, []
        sents = _term_sentences(sm.get("extract") or "", term) or _term_sentences(
            wikipedia_search.article_text(lg, sm["title"], strict=strict), term)
    except Exception as e:
        if strict:
            raise wikipedia_search.Unreachable(f"{lg}: {type(e).__name__}") from e
        return None, []
    if not sents:                      # 그 문서에 이름이 없으면 근거가 아니다
        return None, []
    url = sm.get("url") or f"https://{lg}.wikipedia.org/wiki/{sm['title']}"
    return Evidence(evidence_id=ds.new_id("e", f"{url}|{term}"), kind="wiki", url=url,
                    title=sm["title"][:200], source_domain="wikipedia.org",
                    observed_at=datetime.now(timezone.utc), excerpt=sents[0][:240]), sents


_YT_ID = re.compile(r"(?:shorts/|watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,20})")


TITLE_HEAD = 15   # 제목 앞부분에 표현이 나와야 그 표현을 다루는 영상이다


def _pick_video(videos: list, term):
    """대표 영상 하나. 제목 **앞부분**에 표현이 나오는 것만 받는다.

    조회수 순 첫 번째를 그냥 쓰면 밈을 소재로만 쓴 영상이 걸린다 —
    "Italian brainrot" 에 "Can Starbucks Spell Italian Brainrot | Ep 7" 이 붙었다(사용자 지적 09-16).
    제목이 그 표현으로 시작할수록, 그리고 짧을수록 그 표현 자체를 다루는 영상이다.
    """
    words = term.canonical.lower().split()
    picks = []
    for v in videos:
        low = v.title.lower()
        if not (mentions(v.title, term.canonical, term.aliases) and all(w in low for w in words)):
            continue
        pos = low.find(term.canonical.lower())
        if pos < 0:                       # 별칭으로만 걸린 경우 — 첫 낱말 위치로 본다
            pos = min((low.find(w) for w in words if low.find(w) >= 0), default=99)
        if pos > TITLE_HEAD:              # 뒤쪽에 나오면 소재로만 쓴 영상이다
            continue
        picks.append((pos, len(v.title), v))
    picks.sort(key=lambda x: (x[0], x[1]))
    return picks[0][2] if picks else None


MEME_CUES = ("meme", "밈", "ミーム", "梗", "迷因", "explained", "해설", "解説", "원본", "original")


def video_is_about(con: Connection, term, title: str) -> bool:
    """대표 영상 후보의 제목이 그 밈을 가리키나 — 규칙으로만(09-30 실측: 로컬 Gemma e4b 는 제목만 보고는 느슨하면 'vibe'→노래 'VIBE' 를,
    엄격하면 'Surprised Pikachu Meme Explained' 까지 떨어뜨려 쓸 수 없었다). 받는 것은 둘:
    (1) 제목(앞부분에 표현이 있음은 _pick_video 가 봤다)에 밈 단서 낱말이 있다, (2) 해시태그·기호를 뺀 제목이 표현 그 자체다 —
    단 흔한 영어 한 낱말(vibe·rizz 처럼 노래·사람 이름과 겹치는 것)은 (2)로 받지 않는다. 틀린 영상보다 빈칸이 낫다."""
    low = title.lower()
    if any(c in low for c in MEME_CUES):
        return True
    bare = re.sub(r"#\S+", " ", title)
    bare = re.sub(r"[^\w\s]", " ", bare, flags=re.UNICODE)
    bare = re.sub(r"\s+", " ", bare).strip().lower()
    for name in (term.canonical, *term.aliases):
        n = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", name or "", flags=re.UNICODE)).strip().lower()
        if n and bare == n and not re.fullmatch(r"[a-z]+", n):
            return True
    return False


def collected_videos(con: Connection, term, limit: int = 200) -> list[ShortsVideo]:
    """모아 둔 쇼츠 가운데 표제어(또는 별칭)의 첫 낱말이 든 것, 조회수 순. 고르기는 _pick_video 가 한다."""
    heads = {n.lower().split()[0] for n in (term.canonical, *term.aliases) if n and n.split()}
    out: list[ShortsVideo] = []
    for h in heads:
        rows = con.execute("SELECT json FROM videos WHERE lower(json) LIKE ? ORDER BY view_count DESC LIMIT ?", (f"%{h}%", limit)).fetchall()
        for (j,) in rows:
            try:
                out.append(ShortsVideo.model_validate_json(j))
            except Exception:
                continue
    return out


def attach_media(con: Connection, term, evidences: list[Evidence], *, youtube: bool = False) -> int:
    """표제어의 대표 그림·영상을 붙인다. 파일은 받지 않고 주소만 둔다.

    그림은 위키미디어 공용의 자유 라이선스만 (영어판 공정이용 그림은 collectors 쪽에서 거른다).
    영상은 이미 근거로 가지고 있는 쇼츠 주소를 쓴다 — 화면에서는 유튜브 공식 플레이어로 끼워 넣는다.
    """
    from ..collectors import wikipedia_search

    added = 0
    # 쇼츠: 해석 기록에 이 표현이 나온 영상. 근거 주소는 도메인만 남은 것이 있어(초기 데이터) 영상 표를 직접 본다.
    for vid, ij in con.execute("SELECT video_id, json FROM interpretations").fetchall():
        if added >= 2:
            break
        try:
            it = ShortsInterpretation.model_validate_json(ij)
        except Exception:
            continue
        hit = next((m for m in it.memes if same_term(m.name, term.canonical, term.aliases)), None)
        if hit:
            ds.add_media(con, term.term_id, "video", f"https://www.youtube.com/watch?v={vid}",
                         page_url=f"https://www.youtube.com/watch?v={vid}", title=hit.name,
                         license="YouTube 임베드", attribution="youtube.com")
            added += 1
    for e in evidences:
        m = _YT_ID.search(e.url or "")
        if m and added < 2:
            ds.add_media(con, term.term_id, "video", f"https://www.youtube.com/watch?v={m.group(1)}",
                         page_url=e.url, title=e.title or "", license="YouTube 임베드", attribution=e.source_domain)
            added += 1
    # 이미 모아 둔 쇼츠(videos) 가운데 제목 앞부분에 그 표현이 있는 것 — 검색 한도를 쓰지 않는다(09-30: 사전 151개 중 12개만 그림·영상이 있었다)
    if not added:
        best = _pick_video(collected_videos(con, term), term)
        if best and video_is_about(con, term, best.title):
            ds.add_media(con, term.term_id, "video", f"https://www.youtube.com/watch?v={best.video_id}",
                         page_url=f"https://www.youtube.com/watch?v={best.video_id}", title=best.title,
                         license="YouTube 임베드", attribution="youtube.com")
            added += 1
    # 위키백과 밈 그림은 대부분 공정이용이라 못 쓴다(실측 09-16). 대신 유튜브에서 대표 영상을 찾는다 —
    # 검색은 100 unit 이라 하루 100회뿐이므로 부르는 쪽이 켤 때만 쓴다. 제목에 그 표현이 실제로 있는 영상만.
    if youtube and not added:
        try:
            from ..collectors import youtube as yt

            region = home_region(term.canonical, term.lang) or "US"
            best = _pick_video(yt.search_shorts(term.canonical, region, hours=24 * 365, max_results=10), term)
            if best and video_is_about(con, term, best.title):
                ds.add_media(con, term.term_id, "video", f"https://www.youtube.com/watch?v={best.video_id}",
                             page_url=f"https://www.youtube.com/watch?v={best.video_id}", title=best.title,
                             license="YouTube 임베드", attribution="youtube.com")
                added += 1
        except Exception:
            pass
    wiki = next((e for e in evidences if e.kind == "wiki"), None)
    if wiki:
        try:
            img = wikipedia_search.free_image(term.lang if wiki.url.startswith(f"https://{term.lang}.") else "en",
                                              wiki.title, term.canonical)
        except Exception:
            img = None
        if img and img.get("url"):
            ds.add_media(con, term.term_id, "image", img["url"], page_url=img.get("source_url", ""),
                         title=img.get("file", ""), license=img.get("license", ""), attribution=img.get("attribution", ""))
            added += 1
    return added


def offline_notes(evidences: list[Evidence], limit: int = 25) -> str:
    from ..collectors.community import for_prompt

    shown, posts = for_prompt(evidences)   # 커뮤니티·SNS 글은 건수만(ADR 0003)
    lines = [f"- [{e.kind}] {e.source_domain}: {e.title}" + (f" — {e.excerpt}" if e.excerpt and e.excerpt != e.title else "") for e in shown[:limit]]
    if posts:
        lines.append(posts)
    return "\n".join(lines) or "- (근거 없음)"


def under_review(con: Connection, term_id: str) -> bool:
    """문서 대조의 제안(고칠 안·위키끼리 다름·사전에서 뺄지)을 사람이 보고 있는가. 그 결정 전에는 조사가 지금 뜻을 바꾸지 않는다 —
    바꾸면 검수자가 본 뜻과 달라지고, 조사 결과(new) 줄이 그 제안을 덮는다(Plan 12). 판정은 ds.under_review 한 곳."""
    return ds.under_review(con, term_id)


MECHANICAL = ("표현이 아니라", "뜻이 비었", "모델 자기확신")
MODEL_ONLY = ("표현이 아니라", "모델 자기확신")   # 모델이 스스로 한 판단(is_expression·self_confidence)


def needs_human(reasons: list[str], documented: bool = False) -> bool:
    """사람이 볼 가치가 있는 보류인가. 뜻은 멀쩡한데 근거가 모자란 애매한 경우만 사람에게 보낸다.
    백과사전(나무위키·위키백과) 문서가 있는 말은 모델의 자기 판단만으로 닫지 않는다 — 나무위키 '분류:유행어' 에서 온
    말 12개 중 7개가 is_expression=false 하나로 닫혀 사람이 보지 못했다(2026-09-29 검토)."""
    if any("뜻이 비었" in r for r in reasons):        # 뜻이 빈 것은 규칙 판정 — 문서가 있어도 사람이 볼 것이 없다(검토 2차)
        return False
    if documented and any(m in r for r in reasons for m in MODEL_ONLY):
        return True
    return not any(m in r for r in reasons for m in MECHANICAL)


def community_region(con: Connection, term: Term) -> str:
    """커뮤니티를 뒤질 나라. 표제어의 나라(광동어는 홍콩)이고, 여러 나라가 같이 쓰는 말(중국어)은 조사할 때마다 번갈아 —
    중국어는 대만 사이트(PTT·Dcard)만 뒤져 홍콩(LIHKG·香港討論區) 글을 한 번도 보지 않았다(Plan 04). 영어는 싱가포르·말레이시아·필리핀
    포럼을 돌아간다(reddit 은 전처럼 미국판에서 따로, research_one). 커뮤니티 글은 전처럼 지표로만 쓴다(ADR 0003)."""
    cycle = region_cycle(term.canonical, term.lang) or (ENGLISH_EDITIONS if term.lang == "en" else ())
    return cycle[ds.research_count(con, term.term_id) % len(cycle)] if cycle else home_region(term.canonical, term.lang) or "US"


def research_one(con: Connection, term: Term, *, lean: bool = False) -> tuple[str, list[str]]:
    """1) Search grounding 조사(3.8 → 3.5). 2) 둘 다 할당량이면 우리가 모은 근거만으로 구조화(오프라인). 판정은 어느 길이든 게이트가 한다.
    lean: 위키 분류에서 가져온 말의 일괄 조사(Plan 16) — Gemini 검색·뉴스(GDELT, 16초 간격)·커뮤니티·네이버를 건너뛰고
    위키 문서·사전만 보고 로컬 모델로 뜻을 쓴다. 판정은 같은 게이트가 한다."""
    cur = ds.current_meaning(con, term.term_id)
    if cur and cur.verification == "verified_human":
        # 사람이 승인한 뜻은 자동 조사가 덮지 않는다. 게이트를 못 넘으면 사람 결정이 닫히고 강등되던 문제
        # (2026-09-28 검토: 6-7 등 4건). 바꾸려면 사람이 검수 화면에서 다시 결정한다.
        return "verified_human", []
    stored = ds.get_term(con, term.term_id)
    if (stored and stored.status == "retired") or (cur and cur.verification == "rejected"):
        return "rejected", []            # 단계가 대상을 고른 뒤 사람이 제외했다(검토 2차)
    if under_review(con, term.term_id):
        return "under_review", []        # 문서 대조의 제안을 사람이 보는 중 — 결정 뒤에 다시 조사한다
    entry_meaning = cur.meaning_id if cur else None
    method = GEMINI_MODEL
    urls: list[str] = []
    draft: MeaningDraft | None = None
    notes = ""
    # 무료 등급 할당량은 모델마다 따로다(하루 약 20회). 영상 해석(interpret)이 3.8 을 먼저 쓰므로 조사는 3.5 부터 —
    # 같은 모델을 두 단계가 서로 뺏으면 아침 첫 실행에서 둘 다 바닥난다(2026-09-28 실측: 11일간 조사 289건 전부 오프라인).
    for model in ((GEMINI_FALLBACK_MODEL, GEMINI_MODEL) if budget_left(con) >= 2 and not lean else ()):  # 예산 0 이면 grounding 시도 생략
        try:
            ds.gemini_spend(con, 2)  # research_term 은 호출 2회
            draft, urls, notes = research_term(term.canonical, model=model)
            method = model
            break
        except errors.APIError as e:
            if e.code not in (429, 503):
                raise
            if e.code == 429 and "RESOURCE_EXHAUSTED" in str(e) and model == GEMINI_MODEL:
                # 구글이 '오늘 할당량 끝' 이라고 했다. 남은 조사가 매번 실패하며 예산을 깎고 기다리지 않게 오늘 몫을 닫는다.
                ds.gemini_spend(con, max(0, budget_left(con)))
    first_party = first_party_evidence(con, term.canonical, term.aliases)
    try:
        from ..collectors import community, wiktionary

        # 일괄 등재가 그 말을 데려온 문서를 이미 붙였다(Plan 16) — 이름으로 다시 찾으면 괄호를 뗀 이름이 다른 문서로 간다
        # (09-30: 'ライラック'(노래)에 꽃 라일락 문서가 붙었다). 그런 말은 붙인 문서만 본다.
        if lean and term.canonical in WIKI_CONTEXT:
            raise StopIteration
        first_party += wiktionary.lookup(term.canonical, term.lang)  # 사전이 이미 아는 표현이면 뜻풀이가 앵커가 된다
        first_party += _wikipedia_evidence(term.canonical, term.lang)
        # 한국어 유행어는 나무위키가 사실상 표준 문서다(2026-09-28 실측 13/14). 짧은 발췌·링크·수정 시각만 쓴다.
        if term.lang == "ko" or any(re.search(r"[가-힣]", a) for a in term.aliases):
            from ..collectors import namuwiki

            for name in [term.canonical, *[a for a in term.aliases if re.search(r"[가-힣]", a)]][:2]:
                got = namuwiki.lookup(name)
                if got:
                    first_party += got
                    break
        # 한국어가 아닌 밈(영어·일본어 …)은 Know Your Meme 문서가 유래를 적는다 — 한국어 표제어도 로마자 별칭이 있으면 찾는다(Plan 12 §4).
        # Search grounding 이 없는 오프라인 조사가 위키백과·나무위키만 찾아 영어·일본어 밈이 문서가 있어도 검수 대기로 가던 것.
        # 이용 약관 때문에 기본은 꺼져 있다(KNOWYOURMEME_ENABLED) — 꺼져 있으면 부르지 않고, 그런 말은 사람 검수(ADR 0003 예외 길)로 간다.
        # 켜도 문서 주소와 제목만 근거로 둔다(collectors/knowyourmeme.py).
        from ..collectors import knowyourmeme

        if knowyourmeme.enabled() and (term.lang != "ko" or any(knowyourmeme.latin(a) for a in term.aliases)):
            first_party += knowyourmeme.lookup(term.canonical, term.aliases)
        if lean:
            raise StopIteration      # 일괄 조사는 문서·사전까지만 — 아래 뉴스·커뮤니티·네이버는 건너뛴다
        # 뉴스에서 실제로 쓰인 문장(GDELT Context, 최근 72시간). 이미 아는 말이 언론까지 번졌는지 보여 준다.
        from ..collectors import gdelt_context

        first_party += gdelt_context.sentences(term.canonical)

        region = community_region(con, term)
        if term.lang == "en":   # reddit 은 전처럼 미국판에서, SG·MY·PH 포럼은 따로 돌아가며 — 한 검색에 묶으면 reddit 몫이 줄었다(검토 09-30)
            first_party += community.gather(term.canonical, "US", forums=region)[0]
        else:
            first_party += community.gather(term.canonical, region)[0]
        if region == "KR":
            from ..collectors import naver_search

            first_party += naver_search.gather(term.canonical)[0]  # 표시 전용
    except Exception:
        pass
    if draft is None:  # 무료 등급: grounding 불가 → 오프라인 조사 (표시 전용 근거는 제외)
        notes = offline_notes(for_model(first_party))
        if WIKI_CONTEXT.get(term.canonical):
            notes += "\n\n위키 문서에서 이 표현이 나온 문장:\n" + "\n".join(
                f"- {x}" for x in WIKI_CONTEXT.pop(term.canonical))
        if lean:
            notes += ("\n\n이 표현은 위키의 '인터넷 밈·유행어' 분류에 든 것이다. definition 에는 대상(노래·작품·인물·물건)의 소개가 아니라 "
                      "**인터넷에서 밈으로 어떻게 쓰이는지**를 써라(어떤 장면·말투로, 무엇을 뜻하며 쓰나). 근거에 밈 쓰임이 없으면 "
                      "대상 소개 한 문장에 근거가 말하는 만큼만 덧붙여라. 제목을 번역만 해서 뜻이라 하지 마라. origin 은 어디서 언제 시작했는지이고, 사이트 이름을 쓰지 마라.")
        parsed, method = structured(con, OFFLINE_PROMPT.format(term=term.canonical, notes=notes), MeaningDraft)
        draft = parsed if isinstance(parsed, MeaningDraft) else MeaningDraft.model_validate(parsed)
        method = f"offline:{method}"
        urls = [e.url for e in first_party[:10]]
    # expansion 은 줄임말 풀이 자리다(자만추 → 자연스러운 만남 추구). 모델이 영어 정의 문장을 통째로 넣어
    # 화면 뜻 앞에 붙어 나왔다(사용자 지적 09-16). 풀이 길이를 넘어서면 뜻이지 풀이가 아니다.
    if draft.expansion and (len(draft.expansion) > 40 or len(draft.expansion.split()) > 8 or "." in draft.expansion[:-1]):
        draft.expansion = None
    if re.fullmatch(r"(https?://)?[\w.-]+\.(org|com|net|wiki|jp|kr|cn|tw)(/\S*)?", (draft.origin or "").strip()):
        draft.origin = "unknown"      # 유래 칸에 출처 사이트 이름만 쓴 것(09-30: 'wikipedia.org') — 유래가 아니다
    evidences = (web_evidence(term.canonical, urls, term.aliases) if not method.startswith("offline") else []) + first_party
    # 이미 저장된 참고 문서(일괄 등재가 미리 붙인 PTT鄉民百科·위키데이터 링크, 예전 조사가 찾은 문서)도 판정에 넣는다 —
    # 이번 조사가 다시 찾지 않은 문서가 빠져 문서가 있는 말이 떨어졌다(2026-09-30, '多蛙、空蛙').
    seen_urls = {normalize_url(e.url) for e in evidences}
    evidences += [e for e in ds.list_evidences(con, term.term_id) if reference_doc(e) and normalize_url(e.url) not in seen_urls]
    current = ds.current_meaning(con, term.term_id)
    if current and current.verification == "verified_human":
        # 조사하는 몇 분(그라운딩·GDELT 16초 간격·나무위키) 사이 검수자가 승인했다 — 그 결정을 덮지 않는다
        return "verified_human", []
    now_term = ds.get_term(con, term.term_id)
    if (now_term and now_term.status == "retired") or (current and current.verification == "rejected"):
        # 그 사이 검수자가 제외했다 — 새 판을 올리지 않는다(검토 2차: 승인만 지키고 제외는 덮었다)
        return "rejected", []
    if under_review(con, term.term_id):
        return "under_review", []        # 조사하는 사이 문서 대조가 제안을 올렸다 — 사람이 결정하기 전에는 덮지 않는다
    if (current.meaning_id if current else None) != entry_meaning:
        return "changed", []             # 조사하는 사이 뜻이 바뀌었다(사람이 고쳤거나 다른 단계가 먼저) — 덮지 않고 다음 주기에
    catalogued = con.execute("SELECT 1 FROM wiki_catalog WHERE term_id=? LIMIT 1", (term.term_id,)).fetchone() is not None   # 위키 밈 분류에 든 말(Plan 16)
    verification, reasons = gate(term.canonical, draft, for_model(evidences), current, aliases=term.aliases, catalogued=catalogued)
    # 용어가 원문에 없는 근거는 그 표제어의 근거가 아니다 — 인용으로 보여 주면 거짓말이 된다. 저장하지 않는다.
    # (표시 전용 네이버 결과는 게이트가 보지 않으므로 그대로 둔다.)
    display_only = {id(e) for e in evidences} - {id(e) for e in for_model(evidences)}
    keep = [e for e in evidences if id(e) in display_only or anchor_hit(term.canonical, e, term.aliases)]
    ds.add_evidences(con, term.term_id, keep)
    ds.add_meaning(con, term.term_id, draft, verification, urls)
    if verification == "verified_auto" and not ds.has_media(con, term.term_id):
        try:
            attach_media(con, term, keep)   # 사전에 오른 표제어에만 — 위키 호출을 아낀다
        except Exception:
            pass
    if verification == "verified_auto":
        term.status = "verified"
        if ds.gate_reasons(con, term.term_id):
            ds.decide_review(con, term.term_id, "auto_verified", "gate", kind="new")   # 조사 결과 줄만 — 문서 대조의 제안은 사람이 닫는다
    else:
        term.status = "needs_review"
        ds.queue_review(con, term.term_id, draft, reasons, len(evidences))
        # '문서가 있다' 는 나무위키 문서이거나, 제목에 표제어가 든 위키백과 문서일 때만 — 본문에 낱말이 스친 문서(소설 제목의 เผ่น)는 아니다
        documented = any(e.kind == "wiki" and (e.source_domain == "namu.wiki" or _norm(term.canonical) in _norm(e.title)) for e in keep)
        if not needs_human(reasons, documented=documented):
            # 게이트가 '표현이 아니다' 로 보았거나 뜻이 비었다 — 사람이 봐도 할 일이 없다. 사람 큐에서만 빼고
            # 표제어는 그대로 둔다(재조사 주기가 오면 다시 본다). 큐가 이런 것으로 500건 넘게 막혀 있었다(2026-09-28).
            ds.decide_review(con, term.term_id, "auto_rejected", "gate", kind="new")   # 방금 올린 조사 결과 줄만 — 문서 대조의 제안은 사람이 닫는다
    existing = ds.get_usage(con, term.term_id)
    if (draft.regions or draft.generations) and not any(u["region"] for u in existing):
        # 나라가 빈 줄만 있던 것(예전 조사가 '' 를 나라로 저장, 146개)은 새 조사로 고친다 — 처음 한 번만 쓰면 영영 못 고쳤다
        ds.clear_usage(con, term.term_id)
        rows = []
        # 나라를 비워 두면 표제어 언어의 나라로 (예전 기본값 'KR' 은 일본어 표제어도 한국에 넣었다)
        regions = draft.regions or [home_region(term.canonical, term.lang) or "GLOBAL"]
        gens = draft.generations or ["all"]   # 세대를 모르면(연대 '90s' 를 걸러 비면) '모든 세대' 로 — 나라가 저장되지 않던 것(검토 2차)
        share = 1.0 / max(1, len(gens) * len(regions))
        for g in gens:
            for r in regions:
                rows.append((g, r, (term.first_seen or datetime.now(timezone.utc)).isoformat(), round(share, 3)))
        ds.set_usage(con, term.term_id, rows)
    # last_seen 은 '밖에서 마지막으로 본 때' 다. 조사한 시각으로 덮으면 '최근 본 순' 목록이 '최근 조사한 순' 이 된다
    # (2026-09-28: 재조사한 오래된 밈 여섯 개가 '10대 유행어' 목록 맨 앞을 채웠다).
    ds.upsert_term(con, term)
    ds.log_research(con, term.term_id, method, notes, urls, verification, reasons)
    return verification, reasons


def run(con: Connection, max_new: int = 8, max_recheck: int = 4) -> dict:
    # 새 표제어는 한 번에 8개까지(예전 4). 조사 대기 131건이 하루 16건씩이면 8일 밀렸다(09-28). Gemini 는 하루 예산이 따로 막는다.
    with stage(con, "research") as r:
        seen: set[str] = set()
        targets = [t for t in promote_candidates(con, max_new) + due_for_recheck(con, max_recheck) if not (t.term_id in seen or seen.add(t.term_id))]
        verified = 0
        for t in targets:
            if budget_left(con) < 2 and not local_ok():
                r.note = "예산 부족"
                break
            try:
                v, reasons = research_one(con, t)
            except BudgetExhausted as e:
                r.note = str(e)
                break
            except Exception as e:  # 한 용어의 조사 실패(모델 형식·네트워크)가 나머지를 막지 않는다. researching 상태로 남아 다음 실행에 먼저 잡힌다
                r.note += f"{t.canonical}:{type(e).__name__} "
                r.detail[t.canonical] = f"error {type(e).__name__}"
                # 실패도 조사 기록으로 남겨 재조사 주기를 따르게 한다 — 기록이 없으면 '아직 조사 안 함' 으로 보여 매번 맨 앞에 다시 잡혔다
                ds.log_research(con, t.term_id, "error", f"{type(e).__name__}: {e}"[:500], [], "error", [])
                # researching 으로 두면 다음 실행에도 맨 앞에 잡혀 칸을 날린다(Frutiger Aero 18회 연속). 검수 대기로 뺀다.
                if t.status == "researching":
                    t.status = "needs_review"
                    ds.upsert_term(con, t)
                continue
            verified += v == "verified_auto"
            r.detail[t.canonical] = f"{v} {reasons[:2]}"
            r.count += 1
        r.detail["verified_auto"] = verified
        r.detail["media"] = backfill_media(con)
    return {"research": r}


MEDIA_PER_RUN = 8        # 실행마다 그림·영상을 찾아 줄 사전 항목 수
MEDIA_SEARCHES = 4       # 그중 유튜브 검색(100 unit)을 쓰는 수 — 하루 네 번 돌아 16회, 한도(하루 10,000)의 16%


def backfill_media(con: Connection, limit: int = MEDIA_PER_RUN, searches: int = MEDIA_SEARCHES) -> int:
    """그림·영상이 없는 확인된 항목에 붙인다(사람이 확인했거나 예전에 들어와 조사 때 못 붙인 것, 09-30: 151개 중 12개만 있었다).
    한 번 찾아 못 붙인 것은 media_tried 에 적어 두고 오래된 것부터 다시 본다."""
    tried = dict(con.execute("SELECT term_id, tried_at FROM media_tried").fetchall())
    todo = [t for t in ds.list_terms(con, ("verified",)) if not ds.has_media(con, t.term_id)]
    todo.sort(key=lambda t: tried.get(t.term_id, ""))
    added = 0
    for t in todo[:limit]:
        try:
            added += attach_media(con, t, ds.list_evidences(con, t.term_id), youtube=searches > 0) > 0
        except Exception:
            pass
        searches -= 1
        con.execute("INSERT OR REPLACE INTO media_tried VALUES (?, ?)", (t.term_id, datetime.now(timezone.utc).isoformat()))
        con.commit()                 # 한 개마다 — 끝에서 한 번만 하면 도는 내내 쓰기 잠금을 쥐어 다른 단계가 'database is locked' 로 죽었다(09-30)
    return added
