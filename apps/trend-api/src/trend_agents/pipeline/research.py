"""4단계 리서치 + 검증. 후보를 용어로 올리고 Gemini(Search grounding)로 조사한 뒤, 근거를 '원문'으로 모아 게이트에 넣는다.
통과 → verified_auto 뜻(버전). 실패 → unverified 뜻 + 검수 큐. 판정은 verification.gate 가 한다."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from google.genai import errors

from ..config import GEMINI_FALLBACK_MODEL, GEMINI_MODEL
from ..interpreters.gemini_research import research_term
from ..lifecycle import recheck_interval_days
from ..schemas import Evidence, MeaningDraft, ShortsInterpretation, ShortsVideo, Term
from ..storage import dictionary_store as ds
from ..collectors.naver_search import for_model
from ..verification import anchor_hit, gate
from .gemini import BudgetExhausted, budget_left, local_ok, structured
from .match import mentions, same_term
from .runs import stage
from ..storage.db import Connection

MIN_CANDIDATE_COUNT = 2  # 소스 두 번 이상 등장했거나 쇼츠에서 나온 후보만
DICT_KINDS = {"slang": "slang", "slang_meme": "slang", "meme": "meme", "dance": "meme", "challenge": "meme", "song": "song"}  # kind → 사전 분류
STRONG_KINDS = {"slang", "slang_meme", "song", "challenge"}  # 한 번만 보여도 승격. '밈' 이름은 두 번째 등장을 기다린다
MAX_WEB_FETCH = 6
UA = "Mozilla/5.0 (compatible; trend-agents/0.1)"


# 표제어 언어 → 근거를 찾을 나라. 중국어는 목표 지역인 대만으로(본토 제외, ADR 0001).
LANG_REGION = {"ko": "KR", "ja": "JP", "id": "ID", "th": "TH", "vi": "VN", "zh": "TW", "tl": "PH", "fil": "PH", "ms": "MY"}

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


def web_evidence(term: str, urls: list[str]) -> list[Evidence]:
    out: list[Evidence] = []
    with httpx.Client(follow_redirects=True, timeout=8.0, headers={"User-Agent": UA}) as c:
        for u in urls[:MAX_WEB_FETCH]:
            try:
                r = c.get(u)
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
                                observed_at=v.published_at if v else datetime.now(timezone.utc), excerpt=f"{hit[0].name}: {hit[0].origin_hypothesis}"[:240], derived=True))
    for t, region, d, src in con.execute("SELECT term, region, MAX(date), source FROM trend_queries GROUP BY term, region, source").fetchall():
        if key == _norm(t):
            url = f"https://trends.google.com/trending?geo={region}"
            out.append(Evidence(evidence_id=ds.new_id("e", f"{url}|{t}|{d}"), kind="datalab", url=url, title=f"Google Trends {region} {src}: {t}", source_domain="trends.google.com",
                                observed_at=datetime.fromisoformat(d).replace(tzinfo=timezone.utc), excerpt=t))
    return out


def promote_candidates(con: Connection, limit: int) -> list[Term]:
    """후보 → 용어(researching). 쇼츠에서 나온 것 또는 2회 이상 본 것."""
    terms: list[Term] = []
    # 사람이 물어본 말·위키 문서가 있는 말을 먼저 조사한다. spot 출신이 앞을 막으면 좋은 후보가 대기열 뒤에 묻힌다.
    first = {"hunt": 0, "namu": 1, "wiki": 2, "shorts": 3}
    pool = sorted(ds.candidates(con, "new", 400), key=lambda c: min((first.get(s, 9) for s in c.sources), default=9))
    for c in pool:
        m = re.search(r"kind=(\w+)", c.note)
        kind = m.group(1) if m else ""
        if kind not in DICT_KINDS:  # 분류가 유행어·밈·노래·챌린지로 보지 않은 것은 사전에 넣지 않는다 (brics, aqi, iPhone Duo 같은 일반 검색어)
            ds.set_candidate_status(con, c.candidate_id, "rejected")
            continue
        # 위키백과에 문서가 있다는 것은 편집자가 백과사전 항목으로 쓸 만큼 자리잡은 표현이라는 뜻이다 —
        # 트렌드 목록에서 두 번 본 것보다 강한 신호라서 한 번에 승격한다. verified 여부는 여전히 게이트가 정한다.
        # 사람이 직접 물어본 말(hunt)은 수요가 곧 근거다. 위키 문서가 있는 것과 같은 급으로 본다.
        if c.count < MIN_CANDIDATE_COUNT and kind not in STRONG_KINDS and not ({"wiki", "hunt", "namu"} & set(c.sources)):
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
        if len(terms) >= limit:
            break
    return terms


def due_for_recheck(con: Connection, limit: int) -> list[Term]:
    """아직 조사 기록이 없는 'researching' 용어가 먼저, 그다음 재검증 주기가 지난 것."""
    out: list[Term] = []
    now = datetime.now(timezone.utc)
    for t in ds.list_terms(con, ("researching", "verified", "needs_review")):
        cm = ds.current_meaning(con, t.term_id)
        if cm and cm.verification == "verified_human":
            continue
        last = ds.last_researched(con, t.term_id)
        if last is None or (now - last).days >= recheck_interval_days(t.lifecycle):
            out.append(t)
    out.sort(key=lambda t: (t.status != "researching",))
    return out[:limit]


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
    from ..collectors import wikipedia_search

    out: list[Evidence] = []
    for lg in dict.fromkeys([lang, "en"]):
        try:
            sm = wikipedia_search.summary(lg, term)
            if not sm:
                titles = wikipedia_search.search(lg, term, limit=1)
                sm = wikipedia_search.summary(lg, titles[0]) if titles else None
            if not sm:
                continue
            sents = _term_sentences(sm.get("extract") or "", term) or _term_sentences(
                wikipedia_search.article_text(lg, sm["title"]), term)
        except Exception:
            continue
        if not sents:                  # 그 문서에 이름이 없으면 근거가 아니다
            continue
        excerpt = sents[0]
        WIKI_CONTEXT[term] = (WIKI_CONTEXT.get(term, []) + sents)[:6]
        url = sm.get("url") or f"https://{lg}.wikipedia.org/wiki/{sm['title']}"
        out.append(Evidence(evidence_id=ds.new_id("e", f"{url}|{term}"), kind="wiki", url=url,
                            title=sm["title"][:200], source_domain="wikipedia.org",
                            observed_at=datetime.now(timezone.utc), excerpt=excerpt[:240]))
    return out


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
    # 위키백과 밈 그림은 대부분 공정이용이라 못 쓴다(실측 09-16). 대신 유튜브에서 대표 영상을 찾는다 —
    # 검색은 100 unit 이라 하루 100회뿐이므로 부르는 쪽이 켤 때만 쓴다. 제목에 그 표현이 실제로 있는 영상만.
    if youtube and not added:
        try:
            from ..collectors import youtube as yt

            region = LANG_REGION.get(term.lang, "US")
            best = _pick_video(yt.search_shorts(term.canonical, region, hours=24 * 365, max_results=10), term)
            if best:
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
    lines = []
    for e in evidences[:limit]:
        lines.append(f"- [{e.kind}] {e.source_domain}: {e.title}" + (f" — {e.excerpt}" if e.excerpt and e.excerpt != e.title else ""))
    return "\n".join(lines) or "- (근거 없음)"


MECHANICAL = ("표현이 아니라", "뜻이 비었", "모델 자기확신")


def needs_human(reasons: list[str]) -> bool:
    """사람이 볼 가치가 있는 보류인가. 뜻은 멀쩡한데 근거가 모자란 애매한 경우만 사람에게 보낸다."""
    return not any(m in r for r in reasons for m in MECHANICAL)


def research_one(con: Connection, term: Term) -> tuple[str, list[str]]:
    """1) Search grounding 조사(3.8 → 3.5). 2) 둘 다 할당량이면 우리가 모은 근거만으로 구조화(오프라인). 판정은 어느 길이든 게이트가 한다."""
    cur = ds.current_meaning(con, term.term_id)
    if cur and cur.verification == "verified_human":
        # 사람이 승인한 뜻은 자동 조사가 덮지 않는다. 게이트를 못 넘으면 사람 결정이 닫히고 강등되던 문제
        # (2026-09-28 검토: 6-7 등 4건). 바꾸려면 사람이 검수 화면에서 다시 결정한다.
        return "verified_human", []
    method = GEMINI_MODEL
    urls: list[str] = []
    draft: MeaningDraft | None = None
    notes = ""
    # 무료 등급 할당량은 모델마다 따로다(하루 약 20회). 영상 해석(interpret)이 3.8 을 먼저 쓰므로 조사는 3.5 부터 —
    # 같은 모델을 두 단계가 서로 뺏으면 아침 첫 실행에서 둘 다 바닥난다(2026-09-28 실측: 11일간 조사 289건 전부 오프라인).
    for model in ((GEMINI_FALLBACK_MODEL, GEMINI_MODEL) if budget_left(con) >= 2 else ()):  # 예산 0 이면 grounding 시도 생략
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
        # 뉴스에서 실제로 쓰인 문장(GDELT Context, 최근 72시간). 이미 아는 말이 언론까지 번졌는지 보여 준다.
        from ..collectors import gdelt_context

        first_party += gdelt_context.sentences(term.canonical)

        region = LANG_REGION.get(term.lang, "US")
        first_party += community.gather(term.canonical, region)[0]
        if region == "KR":
            from ..collectors import naver_search

            first_party += naver_search.gather(term.canonical)[0]  # 표시 전용
    except Exception:
        pass
    if draft is None:  # 무료 등급: grounding 불가 → 오프라인 조사 (표시 전용 근거는 제외)
        notes = offline_notes(for_model(first_party))
        if WIKI_CONTEXT.get(term.canonical):
            notes += "\n\n위키백과 본문에서 이 표현이 나온 문장:\n" + "\n".join(
                f"- {x}" for x in WIKI_CONTEXT.pop(term.canonical))
        parsed, method = structured(con, OFFLINE_PROMPT.format(term=term.canonical, notes=notes), MeaningDraft)
        draft = parsed if isinstance(parsed, MeaningDraft) else MeaningDraft.model_validate(parsed)
        method = f"offline:{method}"
        urls = [e.url for e in first_party[:10]]
    # expansion 은 줄임말 풀이 자리다(자만추 → 자연스러운 만남 추구). 모델이 영어 정의 문장을 통째로 넣어
    # 화면 뜻 앞에 붙어 나왔다(사용자 지적 09-16). 풀이 길이를 넘어서면 뜻이지 풀이가 아니다.
    if draft.expansion and (len(draft.expansion) > 40 or len(draft.expansion.split()) > 8 or "." in draft.expansion[:-1]):
        draft.expansion = None
    evidences = (web_evidence(term.canonical, urls) if not method.startswith("offline") else []) + first_party
    current = ds.current_meaning(con, term.term_id)
    verification, reasons = gate(term.canonical, draft, for_model(evidences), current, aliases=term.aliases)
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
            ds.decide_review(con, term.term_id, "auto_verified", "gate")
    else:
        term.status = "needs_review"
        ds.queue_review(con, term.term_id, draft, reasons, len(evidences))
        if not needs_human(reasons):
            # 게이트가 '표현이 아니다' 로 보았거나 뜻이 비었다 — 사람이 봐도 할 일이 없다. 사람 큐에서만 빼고
            # 표제어는 그대로 둔다(재조사 주기가 오면 다시 본다). 큐가 이런 것으로 500건 넘게 막혀 있었다(2026-09-28).
            ds.decide_review(con, term.term_id, "auto_rejected", "gate")
    if (draft.regions or draft.generations) and not ds.get_usage(con, term.term_id):
        rows = []
        share = 1.0 / max(1, len(draft.generations) * max(1, len(draft.regions or ["KR"])))
        for g in draft.generations:
            for r in draft.regions or ["KR"]:
                rows.append((g, r, (term.first_seen or datetime.now(timezone.utc)).isoformat(), round(share, 3)))
        ds.set_usage(con, term.term_id, rows)
    # last_seen 은 '밖에서 마지막으로 본 때' 다. 조사한 시각으로 덮으면 '최근 본 순' 목록이 '최근 조사한 순' 이 된다
    # (2026-09-28: 재조사한 오래된 밈 여섯 개가 '10대 유행어' 목록 맨 앞을 채웠다).
    ds.upsert_term(con, term)
    ds.log_research(con, term.term_id, method, notes, urls, verification, reasons)
    return verification, reasons


def run(con: Connection, max_new: int = 4, max_recheck: int = 4) -> dict:
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
                # researching 으로 두면 다음 실행에도 맨 앞에 잡혀 칸을 날린다(Frutiger Aero 18회 연속). 검수 대기로 뺀다.
                if t.status == "researching":
                    t.status = "needs_review"
                    ds.upsert_term(con, t)
                continue
            verified += v == "verified_auto"
            r.detail[t.canonical] = f"{v} {reasons[:2]}"
            r.count += 1
        r.detail["verified_auto"] = verified
    return {"research": r}
