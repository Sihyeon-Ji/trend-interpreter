"""급증 원인 조사. 검색어가 갑자기 뜨면 '왜 지금인가'를 여러 곳에서 찾아 지식그래프에 넣고, 급증이 이어지면 다시 조사해 갱신한다.

감지  : Google Trends 급상승(상승률) · 지금 뜨는 검색어(검색량) · 위키 조회 급증(전일 대비)
조사  : 뉴스 검색(RSS) · 위키백과 검색/요약/조회 곡선 · YouTube 최근 영상 검색 · (가능하면) Google Search grounding · 이미 모은 1차 근거
서술  : Gemini 가 근거만 보고 why_now·계기·관련 인물을 구조화. 인물 이름은 근거 원문에 실재해야 남긴다(앵커).
저장  : trend_explanations + edges(검색어 → TRIGGERED_BY → 인물, 검색어 → ABOUT → 위키 문서). 보드 설명이 이걸 쓴다.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from ..collectors import community, naver_search, news_rss, wikipedia_search, youtube
from ..config import REGIONS_FOCUS, YOUTUBE_API_KEY
from ..schemas import Evidence, ExplanationDraft, TrendExplanation
from ..storage import dictionary_store as ds
from ..storage import store as db
from google.genai import errors

from .gemini import BudgetExhausted, budget_left, local_ok, structured
from .match import mentions
from .research import first_party_evidence
from .runs import stage
from ..storage.db import Connection

MIN_GAIN = 1000          # bq_rising percent_gain
MIN_TRAFFIC = 2000       # rss_now approx_traffic
WIKI_JUMP = 2.0          # 전일 대비 조회 배수
REINVESTIGATE_DAYS = 2   # 급증이 이어지면 이 간격으로 다시 조사
SKIP_KINDS = {"sports"}  # 경기는 그 자체가 이유라 조사하지 않는다
YOUTUBE_PER_RUN = 3      # search.list 100 unit

PROMPT = """아래 근거만 보고, '{term}'({region}) 검색이 {date} 무렵 갑자기 늘어난 이유를 설명하라.
- why_now: 한국어 1~2문장. '누가(인플루언서·연예인·브랜드·방송) 무엇을 해서' 또는 '어떤 사건·출시·행사 때문에' 처럼 구체적으로. 근거에 이유가 없으면 "근거 부족: 이유 확인되지 않음".
- why_now_en: 같은 내용을 영어로.
- trigger: influencer | release | event | controversy | meme | promotion | holiday | sports | unknown
- actors: 근거 원문에 그대로 나오는 이름만. 추측 금지.
- first_signal: 근거에서 확인되는 가장 이른 날짜(YYYY-MM-DD), 없으면 null.
- self_confidence: 근거가 이유를 직접 말하면 0.8 이상, 간접이면 0.5, 없으면 0.2 이하.

근거:
{notes}"""



def news_domain(n) -> str:
    """Google News RSS 는 링크가 전부 news.google.com 이라 발행사(source)를 출처로 삼는다."""
    host = urlparse(n.link).netloc.removeprefix("www.")
    if "news.google." in host and getattr(n, "source", ""):
        return n.source.strip().lower().replace(" ", "")
    return host

def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _traffic(s: str | None) -> int:
    m = re.search(r"\d[\d,]*", s or "")
    return int(m.group(0).replace(",", "")) if m else 0


def detect(con: Connection, limit: int = 8) -> list[dict]:
    """오늘 급증한 (term, region) 후보. 집중 국가·상승률 순. 경기는 제외."""
    cls = {r[0]: r for r in con.execute("SELECT key, kind, lang FROM trend_class").fetchall()}
    latest = {}
    for region, d in con.execute("SELECT region, MAX(date) FROM trend_queries GROUP BY region").fetchall():
        latest[region] = d
    out: dict[tuple[str, str], dict] = {}
    for term, region, source, d, gain, traffic in con.execute("SELECT term, region, source, date, percent_gain, approx_traffic FROM trend_queries").fetchall():
        if d != latest.get(region):
            continue
        score = (gain or 0) if source == "bq_rising" else _traffic(traffic) if source == "rss_now" else 0
        if (source == "bq_rising" and (gain or 0) < MIN_GAIN) or (source == "rss_now" and _traffic(traffic) < MIN_TRAFFIC) or source == "bq_top":
            continue
        c = cls.get(f"{_norm(term)}|{region}")
        if c and c[1] in SKIP_KINDS:
            continue
        k = (term, region)
        cand = {"term": term, "region": region, "date": d, "score": score, "kind": c[1] if c else "unclassified", "lang": (c[2] if c else None) or wikipedia_search.lang_for(region), "why": source}
        if k not in out or out[k]["score"] < score:
            out[k] = cand
    # 위키 조회 급증 (전일 대비)
    days = [r[0] for r in con.execute("SELECT DISTINCT date FROM wiki_top ORDER BY date DESC LIMIT 2").fetchall()]
    if len(days) == 2:
        prev = {(l, a): v for l, a, v in con.execute("SELECT lang, article, views FROM wiki_top WHERE date=?", (days[1],)).fetchall()}
        for lang, article, views in con.execute("SELECT lang, article, views FROM wiki_top WHERE date=?", (days[0],)).fetchall():
            pv = prev.get((lang, article))
            if pv and views >= pv * WIKI_JUMP:
                region = {v: k for k, v in wikipedia_search.REGION_LANG.items()}.get(lang, "US")
                out.setdefault((article, region), {"term": article, "region": region, "date": days[0], "score": views, "kind": "wiki", "lang": lang, "why": "wiki_jump"})
    ranked = sorted(out.values(), key=lambda x: (x["region"] not in REGIONS_FOCUS, -x["score"]))
    return ranked[:limit]


def gather(con: Connection, term: str, region: str, lang: str, use_youtube: bool) -> tuple[list[Evidence], list[str]]:
    """여러 곳에서 근거를 모은다. 발췌는 원문 그대로."""
    now = datetime.now(timezone.utc)
    evs: list[Evidence] = []
    notes: list[str] = []
    news_region = region if region in news_rss.LOCALES else "US"
    try:
        for n in news_rss.fetch_news(news_region, query=term, limit=15):
            evs.append(Evidence(evidence_id=ds.new_id("e", n.link), kind="news", url=n.link, title=n.title[:200], source_domain=news_domain(n),
                                observed_at=n.published_at or now, excerpt=n.title))
        db.upsert_news(con, news_rss.fetch_news(news_region, query=term, limit=15))
    except Exception as e:
        notes.append(f"news search failed: {type(e).__name__}")
    try:
        for title in wikipedia_search.search(lang, term, limit=2):
            sm = wikipedia_search.summary(lang, title)
            if not sm or not sm["extract"]:
                continue
            pv = wikipedia_search.pageviews(lang, title)
            curve = " ".join(f"{d[4:6]}/{d[6:8]}:{v}" for d, v in pv[-7:])
            evs.append(Evidence(evidence_id=ds.new_id("e", sm["url"] or title), kind="web", url=sm["url"] or f"https://{lang}.wikipedia.org/wiki/{title}", title=f"Wikipedia: {sm['title']}",
                                source_domain=f"{lang}.wikipedia.org", observed_at=now, excerpt=sm["extract"][:300] + (f" | 최근 7일 조회 {curve}" if curve else "")))
            ds.add_edge(con, "query", f"{_norm(term)}|{region}", "ABOUT", "wiki", f"{lang}:{sm['title']}")
    except Exception as e:
        notes.append(f"wiki failed: {type(e).__name__}")
    if use_youtube and YOUTUBE_API_KEY:
        try:
            vids = youtube.search_shorts(term, region, hours=96, max_results=10)
            db.upsert_videos(con, vids)
            for v in vids[:6]:
                evs.append(Evidence(evidence_id=ds.new_id("e", v.url), kind="short", url=v.url, title=v.title[:200], source_domain="youtube.com", observed_at=v.published_at,
                                    excerpt=f"{v.channel} · 조회 {v.view_count:,} · {v.title}"[:240]))
        except Exception as e:
            notes.append(f"youtube failed: {type(e).__name__}")
    # 커뮤니티: 구글에 색인된 더쿠·디시·에펨·레딧 글, (키 있으면) Reddit·Bluesky, 찾은 영상의 상위 댓글
    vids = [(e.url.split("v=")[-1].split("&")[0].split("/")[-1], e.url, e.title) for e in evs if e.kind == "short"][:2]
    c_evs, c_notes = community.gather(term, region, vids)
    evs += c_evs
    notes += c_notes
    if region == "KR" and naver_search.available():  # 표시 전용 — 모델·게이트에는 넣지 않는다
        n_evs, n_notes = naver_search.gather(term)
        evs += n_evs
        notes += n_notes
    evs += [e for e in first_party_evidence(con, term) if e.evidence_id not in {x.evidence_id for x in evs}]
    return evs, notes


def explain(con: Connection, term: str, region: str, d: str, evs: list[Evidence]) -> TrendExplanation:
    # 네이버 검색 결과는 화면 표시 전용(약관), 커뮤니티·SNS 글은 건수만(ADR 0003) — 급증 이유는 기사·영상·문서로 쓴다
    model_evs, posts = community.for_prompt(naver_search.for_model(evs))
    lines = [f"- [{e.kind}] {e.source_domain} ({e.observed_at.date()}): {e.title}" + (f" — {e.excerpt}" if e.excerpt and e.excerpt != e.title else "") for e in model_evs[:30]] + ([posts] if posts else [])
    parsed, model = structured(con, PROMPT.format(term=term, region=region, date=d, notes="\n".join(lines) or "- (근거 없음)"), ExplanationDraft, temperature=0.2)
    draft = parsed if isinstance(parsed, ExplanationDraft) else ExplanationDraft.model_validate(parsed)
    corpus = _norm(" ".join(e.title + " " + e.excerpt for e in model_evs))
    anchored = [a for a in draft.actors if _norm(a.name) and _norm(a.name) in corpus]  # 근거에 없는 이름은 버린다
    dropped = len(draft.actors) - len(anchored)
    conf = draft.self_confidence * (0.7 if dropped and not anchored else 1.0)
    if not evs:
        conf = min(conf, 0.2)
    return TrendExplanation(**{**draft.model_dump(), "actors": anchored, "self_confidence": round(conf, 2)}, term=term, region=region, date=date.fromisoformat(d),
                            evidence_ids=[e.evidence_id for e in evs[:30]], model=model)


def run(con: Connection, max_spikes: int = 6) -> dict:
    with stage(con, "spikes") as r:
        spikes = detect(con, limit=max_spikes * 2)
        yt_used = 0
        for sp in spikes:
            if r.count >= max_spikes:
                break
            prev = ds.get_explanation(con, sp["term"], sp["region"])
            if prev and (datetime.now(timezone.utc) - prev[1]).days < REINVESTIGATE_DAYS:
                continue  # 아직 신선하다
            if budget_left(con) < 1 and not local_ok():  # 로컬 Gemma 가 켜져 있으면 예산과 무관
                r.note = "Gemini 예산 부족"
                break
            evs, notes = gather(con, sp["term"], sp["region"], sp["lang"], use_youtube=yt_used < YOUTUBE_PER_RUN)
            yt_used += 1
            qid = f"{_norm(sp['term'])}|{sp['region']}"
            ds.add_evidences(con, f"q|{qid}", evs[:30])  # 화면의 '왜 지금 뜨나' 카드가 근거를 보여 준다
            for e in evs[:30]:  # 모델이 막혀도 모은 근거는 그래프에 남긴다 — 다음 실행은 서술만 하면 된다
                ds.add_edge(con, "query", qid, "EVIDENCED_BY", "evidence", e.evidence_id)
            t = ds.find_term(con, sp["term"])
            if t:  # 검색어가 사전 용어와 같아도 점수·날짜 기사는 옮기지 않는다
                ds.add_evidences(con, t.term_id, [e for e in evs if mentions(f"{e.title} {e.excerpt}", t.canonical, t.aliases)])
                ds.add_edge(con, "query", qid, "IS_TERM", "term", t.term_id)
            try:
                x = explain(con, sp["term"], sp["region"], sp["date"], evs)
            except BudgetExhausted as e:
                r.note = str(e)
                break
            except errors.APIError as e:
                if e.code in (429, 503):
                    r.note = f"Gemini {e.code}: 서술은 다음 실행으로 (근거 {len(evs)}건은 저장됨)"
                    r.detail[sp["term"]] = f"evidence_only ev={len(evs)}"
                    break
                raise
            except Exception as e:  # 로컬 모델 형식 실패 등 — 이 급증만 건너뛴다 (근거·엣지는 이미 저장됨)
                r.note += f"{sp['term']}:{type(e).__name__} "
                r.detail[sp["term"]] = f"error ev={len(evs)}"
                continue
            ds.save_explanation(con, x)
            for a in x.actors:
                ds.add_edge(con, "query", qid, "TRIGGERED_BY", "actor", a.name)
            r.count += 1
            r.detail[sp["term"]] = f"{x.trigger} {x.self_confidence} {[a.name for a in x.actors][:3]} ev={len(evs)}"
        r.detail["detected"] = len(spikes)
    return {"spikes": r}
