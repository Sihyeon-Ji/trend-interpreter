"""문서 대조(Plan 12) — Know Your Meme 수집기, 조사 단계의 참고 문서 찾기, 전수조사 결과 가져오기, '문서 대조' 단계. 네트워크·모델 없이.
검수 큐의 제안 종류(고칠 안·위키끼리 다름·사전에서 뺄지)의 결정은 tests/test_review_kinds.py."""
import importlib.util
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from trend_agents.collectors import knowyourmeme
from trend_agents.pipeline import crosscheck
from trend_agents.schemas import CrosscheckJudgement, Evidence, MeaningDraft, MeaningFix, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

NOW = datetime.now(timezone.utc)
KYM_URL = "https://knowyourmeme.com/memes/aura-farming"
WIKI_URL = "https://en.wikipedia.org/wiki/Aura_farming"


def ev(kind, domain, title, excerpt="", url=None, when=None):
    return Evidence(evidence_id=ds.new_id("e", f"{url or domain}|{title}"), kind=kind, url=url or f"https://{domain}/x", title=title,
                    source_domain=domain, observed_at=when or NOW, excerpt=excerpt)


def draft(definition="멋있어 보이려고 일부러 폼을 잡는 행동", origin="게임 팬덤의 농담", nuance="놀리는 말로도 쓴다"):
    return MeaningDraft(definition=definition, origin=origin, nuance=nuance, generations=["10s"], regions=["US"], self_confidence=0.8)


def listed(con, tid, name, lang="en", verification="verified_auto", aliases=(), **kw):
    """확인된(공개) 항목 하나."""
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", aliases=list(aliases), first_seen=NOW, last_seen=NOW))
    return ds.add_meaning(con, tid, draft(**kw), verification, [])


@pytest.fixture(autouse=True)
def _kym_off(monkeypatch):
    """기본은 꺼짐으로 시험한다 — 이 서버의 .env 가 켜 두어도(2026-09-30 트윈) 시험 결과가 달라지지 않게. 켜는 시험은 직접 켠다."""
    from trend_agents import config

    monkeypatch.setattr(config, "KNOWYOURMEME_ENABLED", False)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """이 파일의 시험은 네트워크를 쓰지 않는다 — 가로채지 않은 수집기 호출이 있으면 바로 실패한다."""
    import httpx

    def blocked(*a, **k):
        raise AssertionError(f"시험에서 네트워크 호출: {a[:2]}")

    for name in ("get", "post", "request"):
        monkeypatch.setattr(httpx, name, blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)


# ---------- Know Your Meme 수집기 ----------
# 이용 약관 때문에 기본은 꺼져 있다(KNOWYOURMEME_ENABLED). 켜도 문서 주소와 제목만 남기고, 받은 글은 그 자리에서 확인에만 쓴다.

# 실제 문서의 틀(제목 h1.entry-title, 'About' 절 다음에 'Origin' 절)만 흉내 낸 예시 — 글은 시험용으로 지어냈다
KYM_PAGE = """<!DOCTYPE html><html><head><title>
Aura Farming | Know Your Meme
</title><meta property='og:title' content='Aura Farming | Know Your Meme' /></head><body>
<h1>Know Your Meme</h1>
<h1 class='content-title entry-title'>
Aura Farming
</h1>
<section class='bodycopy'>
<table class="navigation"><tr><td><a href="#about">About</a> • <a href="#origin">Origin</a></td></tr></table>
<h2 id="about">About</h2>
<p>This page is a test. <strong>Aura Farming</strong> is a made-up test sentence about acting "cool" on purpose to collect
"<a href="https://knowyourmeme.com/memes/aura-slang" class="internal-link">aura</a>" points.<sup class="footnote"><a href="#fn1">[1]</a></sup>
Another sentence without the name.</p>
<script>var s = "Aura Farming inside a script";</script>
<h2 id="origin">Origin</h2>
<p>Aura Farming began in a long origin paragraph that must never be stored.</p>
</section></body></html>"""
NOT_FOUND = "<html><head><title>Page Not Found (404) - Know Your Meme</title></head><body><h1>fail</h1></body></html>"


@pytest.fixture
def kym(monkeypatch, tmp_path):
    """Know Your Meme 을 켜고 요청을 가로챈다: pages = {slug: (상태, html)}. 요청한 주소를 calls 에 남긴다."""
    from trend_agents import config

    calls: list[str] = []
    pages: dict[str, tuple[int, str]] = {}

    def fake_get(path, timeout=15.0):
        calls.append(path)
        status, text = pages.get(path.removeprefix("/memes/"), (404, NOT_FOUND))
        return SimpleNamespace(status_code=status, text=text, url=knowyourmeme.BASE + path)

    monkeypatch.setattr(config, "KNOWYOURMEME_ENABLED", True)
    monkeypatch.setattr(knowyourmeme, "CACHE", tmp_path / "kym.json")
    monkeypatch.setattr(knowyourmeme, "_get", fake_get)
    return SimpleNamespace(calls=calls, pages=pages)


def test_kym_is_off_by_default_and_then_sends_no_request(kym, monkeypatch):
    from trend_agents import config

    kym.pages["aura-farming"] = (200, KYM_PAGE)
    monkeypatch.setattr(config, "KNOWYOURMEME_ENABLED", False)
    assert not knowyourmeme.enabled()
    assert knowyourmeme.lookup("aura farming", ["aura farm"]) == [] and kym.calls == []
    assert not knowyourmeme.CACHE.exists()


def test_kym_keeps_only_the_page_address_and_title(kym):
    kym.pages["aura-farming"] = (200, KYM_PAGE)
    [e] = knowyourmeme.lookup("aura farming", ["aura farm", "아우라 파밍"])
    assert e.kind == "wiki" and e.source_domain == "knowyourmeme.com" and e.url == KYM_URL
    assert e.title == "Know Your Meme: Aura Farming" and e.excerpt == ""                        # 문서의 글은 남기지 않는다
    assert kym.calls == ["/memes/aura-farming"]                                                 # 문서 주소만 — 검색(/search)은 쓰지 않는다
    cached = knowyourmeme.CACHE.read_text(encoding="utf-8")
    assert "made-up test sentence" not in cached and "origin paragraph" not in cached           # 캐시에도 찾았나·주소·제목뿐
    assert set(json.loads(cached)["aura farming|aura farm|아우라 파밍"]) == {"at", "ok", "url", "title"}
    from trend_agents.verification import anchor_hit, reference_doc

    assert reference_doc(e) and anchor_hit("aura farming", e)                                  # 제목으로 참고 문서가 된다


def test_kym_needs_the_name_in_both_the_title_and_the_about_section(kym):
    kym.pages["delulu"] = (200, KYM_PAGE.replace("Aura Farming", "Delulu", 2))                 # 제목만 같고 'About' 은 딴 말
    assert knowyourmeme.lookup("delulu") == []
    kym.pages["brainrot"] = (200, KYM_PAGE.replace('<h1 class=\'content-title entry-title\'>\nAura Farming', "<h1 class='content-title entry-title'>\nItalian Brainrot"))
    assert knowyourmeme.covers(kym.pages["brainrot"][1], "aura farming") is False              # 'About' 에만 있고 제목은 상위 문서
    assert knowyourmeme.title_of(KYM_PAGE) == "Aura Farming" and '"aura" points.' in knowyourmeme.about_of(KYM_PAGE)
    assert "[1]" not in knowyourmeme.about_of(KYM_PAGE) and "script" not in knowyourmeme.about_of(KYM_PAGE)


def test_kym_tries_canonical_then_latin_aliases_at_most_three_times_and_caches(kym):
    assert knowyourmeme.lookup("推し活", ["오시카츠"]) == [] and kym.calls == []        # 로마자 표기가 없으면 열지 않는다
    assert knowyourmeme.lookup("推し活", ["오시카츠", "Oshi Katsu", "Oshikatsu!", "oshi-katsu", "Oshi Katsu 2", "fourth one"]) == []
    assert kym.calls == ["/memes/oshi-katsu", "/memes/oshikatsu", "/memes/oshi-katsu-2"]   # 같은 주소는 한 번, 최대 세 번
    kym.calls.clear()
    kym.pages["aint-nobody-got-time-for-that"] = (200, KYM_PAGE.replace("Aura Farming", "Ain't Nobody Got Time for That"))
    [e] = knowyourmeme.lookup("Ain't Nobody Got Time for That")
    assert kym.calls == ["/memes/aint-nobody-got-time-for-that"] and e.title == "Know Your Meme: Ain't Nobody Got Time for That"
    assert knowyourmeme.lookup("Ain't Nobody Got Time for That") == [e] and len(kym.calls) == 1   # 하루 캐시
    assert knowyourmeme.slug("Pokémon Go") == "pokemon-go" and knowyourmeme.slug("6-7") == "6-7" and knowyourmeme.slug("아우라") == ""


def test_kym_page_not_found_is_nothing_and_network_failures_are_not_cached(kym, monkeypatch):
    assert knowyourmeme.lookup("zzqx meme") == []                                        # 404 'Page Not Found'
    kym.pages["soft-404"] = (200, NOT_FOUND)
    assert knowyourmeme.lookup("soft 404") == []
    down = []
    monkeypatch.setattr(knowyourmeme, "_get", lambda path, timeout=15.0: down.append(path))    # 네트워크 실패(None)
    assert knowyourmeme.lookup("aura farming") is None                                      # '없음' 이 아니라 '닿지 못함'
    kym.pages["busy"] = (429, "")
    monkeypatch.setattr(knowyourmeme, "_get", lambda path, timeout=15.0: SimpleNamespace(status_code=429, text="", url=knowyourmeme.BASE + path))
    assert knowyourmeme.lookup("busy") is None
    assert "aura farming" not in json.loads(knowyourmeme.CACHE.read_text(encoding="utf-8"))   # 실패는 캐시하지 않는다 — 다음에 다시 본다


def test_kym_waits_between_requests(monkeypatch):
    waits = []
    monkeypatch.setattr(knowyourmeme.time, "sleep", waits.append)
    monkeypatch.setattr(knowyourmeme.httpx, "get", lambda url, **k: SimpleNamespace(status_code=404, text="", url=url, headers=k["headers"]))
    monkeypatch.setattr(knowyourmeme, "_last", time.time())
    r = knowyourmeme._get("/memes/x")
    assert knowyourmeme.MIN_GAP_S >= 2 and waits and waits[0] > 1.5
    assert r.url == "https://knowyourmeme.com/memes/x" and "trend-agents" in r.headers["User-Agent"]


def test_crosscheck_looks_in_know_your_meme_only_when_enabled(monkeypatch):
    from trend_agents import config

    en = Term(term_id="t", canonical="aura farming", lang="en")
    ja = Term(term_id="t", canonical="推し活", lang="ja", aliases=["오시카츠"])
    assert crosscheck.sources(en) == ["wiki:en"] and crosscheck.sources(ja) == ["wiki:ja", "namu"]   # 기본(꺼짐)
    monkeypatch.setattr(config, "KNOWYOURMEME_ENABLED", True)
    assert crosscheck.sources(en) == ["kym", "wiki:en"] and crosscheck.sources(ja) == ["wiki:ja", "kym", "namu"]
    assert crosscheck.sources(Term(term_id="t", canonical="galau", lang="id")) == ["wiki:id", "wiki:en", "kym"]
    assert crosscheck.sources(Term(term_id="t", canonical="럭키비키", lang="ko")) == ["namu", "wiki:ko"]


def test_import_excerpts_are_confirmed_on_the_page_and_kym_keeps_only_address_and_title(monkeypatch):
    """전수조사 파일의 발췌는 그 문서에 실제로 있어야 근거가 된다 — 나무위키·위키백과는 그 자리에서 읽어 확인한다(본문은 두지 않는다)."""
    from trend_agents import config
    from trend_agents.collectors import namuwiki, wikipedia_search

    t = Term(term_id="t", canonical="aura farming", lang="en")
    filler = "word " * 60
    long = f"A very long sentence where {filler}and finally aura farming shows up {filler}"
    pages = {"Aura farming": f"Intro. {long} More text."}
    monkeypatch.setattr(wikipedia_search, "article_text", lambda lang, title, timeout=15.0, strict=False: pages.get(title, ""))
    e, why = crosscheck.confirmed_evidence(t, WIKI_URL, "Aura farming", long)
    assert why == "" and e.source_domain == "wikipedia.org" and len(e.excerpt) <= 200 and "aura farming" in e.excerpt and e.excerpt.startswith("…")
    assert crosscheck.confirmed_evidence(t, WIKI_URL, "x", "aura farming is a line that is not on the page")[1] == "문서에 그 발췌가 없음"
    assert crosscheck.confirmed_evidence(t, "https://www.reddit.com/r/x/1", "x", "aura farming")[1] == "참고 문서의 문서 주소가 아님"
    assert crosscheck.confirmed_evidence(t, "https://en.wikipedia.org/", "x", "aura farming")[1] == "참고 문서의 문서 주소가 아님"
    assert crosscheck.confirmed_evidence(t, "https://en.wikipedia.org/wiki/X", "X", "nothing here")[1] == "발췌에 표제어가 없음"
    assert crosscheck.confirmed_evidence(t, "https://dic.pixiv.net/a/aura", "x", "aura farming")[1] == "확인할 수집기가 없는 문서"
    ko = Term(term_id="k", canonical="럭키비키", lang="ko")
    monkeypatch.setattr(namuwiki, "page_text", lambda title: "… 럭키비키는 장원영의 말에서 나온 밈이다. …" if title == "럭키비키" else None)
    e, why = crosscheck.confirmed_evidence(ko, "https://namu.wiki/w/럭키비키", "럭키비키", "럭키비키는  장원영의 말에서 나온 밈이다.")
    assert why == "" and e.url == "https://namu.wiki/w/%EB%9F%AD%ED%82%A4%EB%B9%84%ED%82%A4" and e.title.startswith("나무위키: 럭키비키")
    assert crosscheck.confirmed_evidence(ko, "https://namu.wiki/w/다른문서", "x", "럭키비키는 장원영의 말에서 나온 밈이다.")[1] == "문서에 닿지 못함"
    assert crosscheck.confirmed_evidence(t, KYM_URL, "Aura Farming", "Aura Farming is acting cool.")[1] == "Know Your Meme 은 꺼져 있음(KNOWYOURMEME_ENABLED)"
    monkeypatch.setattr(config, "KNOWYOURMEME_ENABLED", True)
    monkeypatch.setattr(knowyourmeme, "from_url", lambda url, term, aliases=(): [ev("wiki", "knowyourmeme.com", "Know Your Meme: Aura Farming", url=url)])
    e, _ = crosscheck.confirmed_evidence(t, KYM_URL, "Aura Farming", "Aura Farming is acting cool.")
    assert e.url == KYM_URL and e.title == "Know Your Meme: Aura Farming" and e.excerpt == ""                   # 켜져 있어도 주소·제목만


# ---------- 조사 단계가 Know Your Meme 을 찾는다 (켜져 있을 때만) ----------

def _research_offline(monkeypatch, kym_lookup):
    from trend_agents.collectors import community, gdelt_context, namuwiki, naver_search, wiktionary
    from trend_agents.pipeline import research

    monkeypatch.setattr(research, "budget_left", lambda con: 0)
    monkeypatch.setattr(research, "structured", lambda *a, **k: (draft(), "local:test"))
    monkeypatch.setattr(research, "first_party_evidence", lambda con, term, *a, **k: [ev("news", "news.example", f"{term} 유행", f"요즘 {term} 가 유행이다")])
    monkeypatch.setattr(research, "_wikipedia_evidence", lambda *a, **k: [])
    monkeypatch.setattr(research, "attach_media", lambda *a, **k: 0)
    monkeypatch.setattr(wiktionary, "lookup", lambda *a, **k: [])
    monkeypatch.setattr(gdelt_context, "sentences", lambda *a, **k: [])
    monkeypatch.setattr(naver_search, "gather", lambda *a, **k: ([], []))
    monkeypatch.setattr(community, "gather", lambda *a, **k: ([], []))
    monkeypatch.setattr(namuwiki, "lookup", lambda name: [])
    monkeypatch.setattr(knowyourmeme, "lookup", kym_lookup)
    con = db.connect(":memory:")
    for tid, name, lang, aliases in (("t_en", "aura farming", "en", []), ("t_ko", "럭키비키", "ko", []), ("t_ko2", "아우라 파밍", "ko", ["aura farming"])):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, aliases=aliases, status="researching", first_seen=NOW, last_seen=NOW))
    return research, con


def test_research_uses_know_your_meme_for_english_memes_when_enabled(monkeypatch):
    from trend_agents import config
    from trend_agents.verification import NO_REFERENCE

    calls = []

    def fake_kym(term, aliases=()):
        calls.append((term, tuple(aliases)))
        return [ev("wiki", "knowyourmeme.com", "Know Your Meme: Aura Farming", url=KYM_URL)] if term == "aura farming" else []

    monkeypatch.setattr(config, "KNOWYOURMEME_ENABLED", True)
    research, con = _research_offline(monkeypatch, fake_kym)
    assert research.research_one(con, ds.get_term(con, "t_en")) == ("verified_auto", [])        # 뉴스 + Know Your Meme 문서(주소·제목)
    assert KYM_URL in {e.url for e in ds.list_evidences(con, "t_en")}
    verdict, reasons = research.research_one(con, ds.get_term(con, "t_ko"))
    assert verdict == "unverified" and NO_REFERENCE in reasons
    assert all(term != "럭키비키" for term, _ in calls)                                     # 로마자 별칭이 없는 한국어 말은 열지 않는다
    research.research_one(con, ds.get_term(con, "t_ko2"))
    assert ("아우라 파밍", ("aura farming",)) in calls                                      # 로마자 별칭이 있으면 찾는다


def test_research_leaves_know_your_meme_alone_by_default_and_sends_the_meme_to_a_person(monkeypatch):
    from trend_agents.verification import NO_REFERENCE

    def never(*a, **k):
        raise AssertionError("꺼져 있으면 부르지 않는다")

    research, con = _research_offline(monkeypatch, never)
    verdict, reasons = research.research_one(con, ds.get_term(con, "t_en"))
    assert verdict == "unverified" and NO_REFERENCE in reasons                                    # 문서가 없으면 사람 검수(ADR 0003 예외 길)
    assert ds.get_term(con, "t_en").status == "needs_review" and ds.pending_review(con, "t_en")["kind"] == "new"


# ---------- 조사는 사람이 보는 제안을 덮지 않는다 ----------

def test_research_leaves_terms_with_a_pending_proposal_alone():
    """문서 대조의 제안을 사람이 보는 동안 조사가 지금 뜻을 바꾸거나 그 제안을 덮지 않는다. 조사가 닫는 것은 조사 결과(new) 줄뿐이다."""
    from trend_agents.pipeline import research

    con = db.connect(":memory:")
    m1 = listed(con, "t_af", "aura farming")
    ds.queue_review(con, "t_af", crosscheck.merged(m1, {"origin": "새 유래"}), ["문서 대조: 고칠 것"], 1, kind="correction")
    con.execute("INSERT INTO research_log VALUES (?,?,?,?,?,?,?)", ("t_af", (NOW - timedelta(days=400)).isoformat(), "x", "", "[]", "verified_auto", "[]"))
    con.commit()
    assert research.due_for_recheck(con, 10) == []
    assert research.research_one(con, ds.get_term(con, "t_af")) == ("under_review", [])
    assert ds.current_meaning(con, "t_af").meaning_id == m1.meaning_id
    assert ds.gate_reasons(con, "t_af") == []                                                   # 게이트의 사유가 아니다
    ds.decide_review(con, "t_af", "auto_verified", "gate", kind="new")
    assert ds.pending_review(con, "t_af")["kind"] == "correction"


# ---------- 전수조사 결과 가져오기 ----------

def _audit(con):
    listed(con, "t_af", "aura farming")
    listed(con, "t_human", "delulu", verification="verified_human", definition="망상에 빠졌다는 뜻의 줄임말")
    listed(con, "t_sk", "skibidi")
    listed(con, "t_cookie", "viral Crumbl Labubu cookie")
    listed(con, "t_nodoc", "라을라", lang="ko")
    listed(con, "t_keep", "6-7")
    m = listed(con, "t_busy", "brat summer")
    ds.queue_review(con, "t_busy", MeaningDraft.model_validate(m.model_dump(include=set(MeaningDraft.model_fields))), ["사람이 보는 중"], 1)
    ds.upsert_term(con, Term(term_id="t_new", canonical="galau", lang="id", status="needs_review"))
    rows = [
        {"term_id": "t_af", "verdict": "fix", "problems": ["유래가 문서와 다름"], "sources": [WIKI_URL],
         "proposal": {"definition": "", "origin": "'aura' 속어에서 나와 2024년에 퍼졌다", "nuance": ""},
         "excerpt": {"url": WIKI_URL, "title": "Aura farming", "text": "Aura farming refers to acting cool on purpose to build aura."}},
        {"term_id": "t_human", "verdict": "fix", "problems": ["뜻이 모자람"], "sources": ["https://knowyourmeme.com/memes/delulu"],
         "proposal": {"definition": "망상(delusional)을 줄인 말로, 이뤄지기 어려운 기대를 품은 사람을 놀리거나 스스로 웃는 말", "origin": "", "nuance": ""},
         "excerpt": {"url": "https://www.reddit.com/r/x/1", "title": "delulu", "text": "delulu is everywhere"}},      # 참고 문서가 아님
        {"term_id": "t_sk", "verdict": "conflict", "problems": ["문서마다 뜻이 다름"], "sources": [],
         "alternatives": [{"wiki": "Know Your Meme", "url": "https://knowyourmeme.com/memes/skibidi-toilet", "summary": "뜻 없이 붙인다"},
                          {"wiki": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Skibidi_Toilet", "summary": "'이상하다' 는 뜻",
                           "proposal": {"definition": "주로 '이상하다' 는 뜻으로 붙이는 말"}}],
         "excerpt": {"url": "https://en.wikipedia.org/wiki/Skibidi_Toilet", "title": "Skibidi Toilet", "text": "A web series."}},  # 표제어 없음
        {"term_id": "t_cookie", "verdict": "not_a_meme", "problems": ["문서가 쿠키 상품을 다룬다"], "sources": ["https://en.wikipedia.org/wiki/Crumbl"]},
        {"term_id": "t_nodoc", "verdict": "no_doc", "problems": [], "sources": [],
         "excerpt": {"url": "https://namu.wiki/w/%EB%9D%BC%EC%9D%84%EB%9D%BC", "title": "라을라", "text": "라을라는 문서가 없다고 한 말이다"}},
        {"term_id": "t_keep", "verdict": "keep", "problems": [], "sources": ["https://en.wikipedia.org/wiki/6-7_(meme)"],
         "excerpt": {"url": "https://knowyourmeme.com/memes/6-7", "title": "6-7", "text": "6-7 is a meme shouted by students."}},   # Know Your Meme 은 꺼짐
        {"term_id": "t_busy", "verdict": "fix", "problems": ["유래가 다름"], "sources": ["https://en.wikipedia.org/wiki/Brat_summer"],
         "proposal": {"origin": "다른 유래"}},
        {"term_id": "t_new", "verdict": "not_a_meme", "problems": ["일반 낱말"], "sources": ["https://id.wikipedia.org/wiki/Galau"]},
        {"term_id": "t_gone", "verdict": "keep"},
    ]
    return [crosscheck.AuditRecord.model_validate(r) for r in rows]


def _state(con):
    return (con.execute("SELECT term_id, status FROM terms ORDER BY term_id").fetchall(),
            con.execute("SELECT meaning_id, verification, valid_to FROM meanings ORDER BY meaning_id").fetchall())


def test_import_reports_by_default_then_queues_once_and_never_touches_the_entries(monkeypatch):
    from trend_agents.collectors import wikipedia_search

    page = "Aura farming refers to acting cool on purpose to build aura. It spread in 2024."
    monkeypatch.setattr(wikipedia_search, "article_text", lambda lang, title, timeout=15.0, strict=False: page if title == "Aura farming" else "")
    con = db.connect(":memory:")
    records = _audit(con)
    before = _state(con)
    evidence_before = con.execute("SELECT COUNT(*) FROM evidences").fetchone()[0]

    rep = crosscheck.import_audit(con, records)                                              # 보고만
    assert dict(rep["counts"]) == {"fix": 3, "conflict": 1, "not_a_meme": 2, "no_doc": 1, "keep": 1}
    assert sorted((n, k) for n, k, _ in rep["would_queue"]) == [("aura farming", "correction"), ("delulu", "correction"),
                                                                ("skibidi", "conflict"), ("viral Crumbl Labubu cookie", "retire")]
    assert rep["no_doc"] == ["라을라"] and ("t_gone", "사전에 없는 항목") in rep["skipped"]
    assert [q["term_id"] for q in ds.review_queue(con)] == ["t_busy"] and ds.last_crosschecks(con) == {}
    assert _state(con) == before and con.execute("SELECT COUNT(*) FROM evidences").fetchone()[0] == evidence_before

    rep = crosscheck.import_audit(con, records, queue=True, store_evidence=True)
    assert sorted((n, k) for n, k, _ in rep["queued"]) == [("aura farming", "correction"), ("delulu", "correction"),
                                                           ("skibidi", "conflict"), ("viral Crumbl Labubu cookie", "retire")]
    kinds = {q["term_id"]: q["kind"] for q in ds.review_queue(con)}
    assert kinds == {"t_af": "correction", "t_human": "correction", "t_sk": "conflict", "t_cookie": "retire", "t_busy": "new"}
    assert _state(con) == before                                                             # 상태·뜻은 그대로 — 사람이 승인한 뜻도
    af = ds.pending_review(con, "t_af")
    assert af["draft"].origin.startswith("'aura'") and "문서 대조: 고칠 것" in af["reasons"] and f"참고 문서: {WIKI_URL}" in af["reasons"]
    sk = ds.pending_review(con, "t_sk")
    assert sk["draft"] is None and [d["proposal"] is None for d in sk["docs"]] == [True, False]
    skipped = dict(rep["skipped"])
    assert skipped["brat summer"] == "이미 검수 대기 중인 제안이 있음" and skipped["galau"] == "확인된 항목이 아님(needs_review)"
    assert skipped["t_gone"] == "사전에 없는 항목"
    assert [(n, u) for n, u in rep["evidence"]] == [("aura farming", WIKI_URL)]               # 참고 문서이고 표제어가 든 발췌만
    assert {u: why for _, u, why in rep["evidence_skipped"]} == {
        "https://www.reddit.com/r/x/1": "참고 문서의 문서 주소가 아님", "https://en.wikipedia.org/wiki/Skibidi_Toilet": "발췌에 표제어가 없음",
        "https://knowyourmeme.com/memes/6-7": "Know Your Meme 은 꺼져 있음(KNOWYOURMEME_ENABLED)"}
    [wiki_ev] = [e for e in ds.list_evidences(con, "t_af") if e.url == WIKI_URL]
    assert wiki_ev.kind == "wiki" and wiki_ev.source_domain == "wikipedia.org" and len(wiki_ev.excerpt) <= 200
    assert not any(e.source_domain == "namu.wiki" for e in ds.list_evidences(con, "t_nodoc"))   # 문서 없음은 아무것도 바꾸지 않는다
    logs = ds.last_crosschecks(con)
    assert {k: v["verdict"] for k, v in logs.items()} == {"t_af": "fix", "t_human": "fix", "t_sk": "conflict", "t_cookie": "not_a_meme", "t_keep": "keep"}

    log_rows = con.execute("SELECT COUNT(*) FROM crosscheck_log").fetchone()[0]
    evidence_rows = con.execute("SELECT COUNT(*) FROM evidences").fetchone()[0]
    queued_at = {q["term_id"]: q["queued_at"] for q in ds.review_queue(con)}
    again = crosscheck.import_audit(con, records, queue=True, store_evidence=True)            # 다시 돌려도 겹치지 않는다
    assert again["queued"] == [] and again["evidence"] == []
    assert {n for n, w in again["skipped"] if w == "이미 검수 대기 중인 제안이 있음"} >= {"aura farming", "delulu", "skibidi", "viral Crumbl Labubu cookie"}
    assert {q["term_id"]: q["queued_at"] for q in ds.review_queue(con)} == queued_at
    assert con.execute("SELECT COUNT(*) FROM crosscheck_log").fetchone()[0] == log_rows
    assert con.execute("SELECT COUNT(*) FROM evidences").fetchone()[0] == evidence_rows
    assert _state(con) == before


def test_import_script_reads_the_file_and_judge_needs_a_local_model(monkeypatch, tmp_path, capsys):
    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps([{"term_id": "t_af", "verdict": "fix", "problems": ["유래가 다름"], "sources": [WIKI_URL],
                                  "proposal": {"origin": "'aura' 속어에서"}, "alternatives": [], "excerpt": None},
                                 {"term_id": "t_af", "verdict": "maybe"}]), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("crosscheck_dictionary", Path(__file__).resolve().parents[1] / "scripts" / "crosscheck_dictionary.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr(script.db, "connect", lambda *a, **k: con)

    monkeypatch.setattr("sys.argv", ["crosscheck_dictionary.py", "import", "--from", str(audit)])
    script.main()
    out = capsys.readouterr().out
    assert "고칠 것 1" in out and "올릴 제안 1건" in out and "형식 오류" in out and ds.review_queue(con) == []
    monkeypatch.setattr("sys.argv", ["crosscheck_dictionary.py", "import", "--from", str(audit), "--queue"])
    script.main()
    assert [q["kind"] for q in ds.review_queue(con)] == ["correction"]

    from trend_agents.pipeline import gemini

    monkeypatch.setattr(gemini, "local_ok", lambda: False)
    monkeypatch.setattr("sys.argv", ["crosscheck_dictionary.py", "judge"])
    with pytest.raises(SystemExit, match="로컬 모델"):
        script.main()


# ---------- '문서 대조' 단계 ----------

def _no_model(monkeypatch):
    """기본 개발 환경(MODEL_PROVIDER=mock, 로컬 모델 없음). 모델을 부르면 실패한다."""
    from trend_agents.interpreters import local_chat
    from trend_agents.pipeline import gemini, local_llm

    def boom(*a, **k):
        raise AssertionError("기본 환경에서는 모델을 부르지 않는다")

    monkeypatch.setattr(gemini, "USE_LOCAL_GEMMA", False)
    for mod, name in ((local_llm, "available"), (local_llm, "structured"), (local_chat, "_chat"), (gemini, "generate")):
        monkeypatch.setattr(mod, name, boom)


def test_stage_decides_no_doc_by_rule_and_calls_no_model_by_default(monkeypatch):
    from trend_agents.collectors import namuwiki

    _no_model(monkeypatch)
    monkeypatch.setattr(crosscheck, "gather", lambda term: ([], []))                          # 네트워크 없이
    monkeypatch.setattr(namuwiki, "lookup", lambda name: [])                                  # '문서가 고쳐졌나' 확인도
    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    ds.add_evidences(con, "t_af", [ev("wiki", "wikipedia.org", "Aura farming", "Aura farming is acting cool.", url=WIKI_URL)])
    listed(con, "t_nodoc", "라을라", lang="ko")
    ds.add_evidences(con, "t_nodoc", [ev("news", "news.example", "라을라 유행", "요즘 라을라 가 뜬다"),
                                      ev("community", "bsky.app", "라을라", "라을라 ㅋㅋ")])                    # 커뮤니티 글은 문서가 아니다
    before = _state(con)
    r = crosscheck.run(con)["crosscheck"]
    assert r.status == "ok" and r.count == 2 and "로컬 모델 없음" in r.note
    logs = ds.last_crosschecks(con)
    assert logs["t_nodoc"]["verdict"] == "no_doc" and logs["t_nodoc"]["model"] == "rule"         # 문서 없음은 규칙이 정한다
    assert logs["t_af"]["verdict"] == crosscheck.UNJUDGED and logs["t_af"]["urls"] == [WIKI_URL]
    assert _state(con) == before and ds.review_queue(con) == []                                # 상태·뜻은 그대로, 큐에도 없다
    assert crosscheck.run(con)["crosscheck"].count == 0                                        # 이미 본 것은 문서가 바뀌기 전에는 다시 보지 않는다
    assert [t.term_id for t in crosscheck.targets(con, 8, judging=True)] == ["t_af"]            # 로컬 모델이 생기면 판정하지 못한 것을 다시 본다
    con.execute("UPDATE crosscheck_log SET checked_at=? WHERE term_id='t_nodoc'", ((NOW - timedelta(days=crosscheck.RETRY_DAYS + 1)).isoformat(),))
    con.commit()
    assert [t.term_id for t in crosscheck.targets(con, 8)] == ["t_nodoc"]                        # 문서 없음은 며칠 뒤 다시 찾는다(일시 실패·새 문서)


def test_stage_waits_before_retrying_a_model_failure(monkeypatch):
    from trend_agents.pipeline import gemini

    monkeypatch.setattr(gemini, "local_ok", lambda: True)
    monkeypatch.setattr(crosscheck, "gather", lambda term: ([ev("wiki", "wikipedia.org", "Aura farming", "Aura farming is acting cool.", url=WIKI_URL)], []))

    def broken(*a, **k):
        raise ValueError("로컬 LLM 구조화 출력 실패")

    monkeypatch.setattr(crosscheck, "judge", broken)
    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    r = crosscheck.run(con)["crosscheck"]
    assert r.count == 0 and "aura farming:ValueError" in r.note and ds.review_queue(con) == []
    assert ds.last_crosschecks(con)["t_af"]["verdict"] == crosscheck.ERROR
    assert crosscheck.targets(con, 8, judging=True) == []                                        # 실행마다 같은 말이 칸을 차지하지 않는다
    con.execute("UPDATE crosscheck_log SET checked_at=?", ((NOW - timedelta(days=crosscheck.RETRY_DAYS + 1)).isoformat(),))
    con.commit()
    assert [t.term_id for t in crosscheck.targets(con, 8, judging=True)] == ["t_af"]


def test_stage_sends_model_proposals_to_the_queue_without_touching_the_entry(monkeypatch):
    from trend_agents.pipeline import gemini

    monkeypatch.setattr(gemini, "local_ok", lambda: True)
    found = {"aura farming": ev("wiki", "wikipedia.org", "Aura farming", "Aura farming is acting cool.", url=WIKI_URL),
             "viral Crumbl Labubu cookie": ev("wiki", "wikipedia.org", "Crumbl", "The viral Crumbl Labubu cookie was a limited product.",
                                              url="https://en.wikipedia.org/wiki/Crumbl"),
             "6-7": ev("wiki", "wikipedia.org", "6-7 (meme)", "6-7 is a meme shouted by students.", url="https://en.wikipedia.org/wiki/6-7")}
    verdicts = {"aura farming": CrosscheckJudgement(verdict="fix", reason="유래가 문서 1과 다름", proposal=MeaningFix(origin="'aura' 속어에서 나왔다")),
                "viral Crumbl Labubu cookie": CrosscheckJudgement(verdict="not_a_meme", reason="문서 1은 상품을 다룬다"),
                "6-7": CrosscheckJudgement(verdict="keep", reason="문서 1과 같다")}
    asked = []

    def fake_judge(term, meaning, docs):
        asked.append((term.canonical, [e.url for e in docs]))
        return verdicts[term.canonical], "local:test"

    monkeypatch.setattr(crosscheck, "gather", lambda term: ([found[term.canonical]], []))
    monkeypatch.setattr(crosscheck, "judge", fake_judge)
    con = db.connect(":memory:")
    listed(con, "t_af", "aura farming")
    listed(con, "t_cookie", "viral Crumbl Labubu cookie", verification="verified_human")
    listed(con, "t_keep", "6-7")
    before = _state(con)
    r = crosscheck.run(con)["crosscheck"]
    assert r.count == 3 and sorted(n for n, _ in asked) == ["6-7", "aura farming", "viral Crumbl Labubu cookie"]
    assert _state(con) == before                                                              # 모델의 제안은 상태·뜻을 바꾸지 않는다
    q = {x["term_id"]: x for x in ds.review_queue(con)}
    assert set(q) == {"t_af", "t_cookie"} and q["t_af"]["kind"] == "correction" and q["t_cookie"]["kind"] == "retire"
    assert q["t_af"]["draft"].origin == "'aura' 속어에서 나왔다" and q["t_af"]["reasons"][:2] == ["문서 대조: 고칠 것", "유래가 문서 1과 다름"]
    assert q["t_af"]["docs"][0]["url"] == WIKI_URL
    assert WIKI_URL in {e.url for e in ds.list_evidences(con, "t_af")}                       # 찾은 문서는 짧은 발췌·링크로 근거에
    assert {k: v["verdict"] for k, v in ds.last_crosschecks(con).items()} == {"t_af": "fix", "t_cookie": "not_a_meme", "t_keep": "keep"}


def test_stage_rechecks_only_when_a_reference_document_changed(monkeypatch):
    from trend_agents.collectors import namuwiki
    from trend_agents.pipeline import gemini

    monkeypatch.setattr(gemini, "local_ok", lambda: False)
    monkeypatch.setattr(crosscheck, "gather", lambda term: ([], []))
    namu_mod = {"when": NOW - timedelta(days=30)}
    namu_url = "https://namu.wiki/w/%EB%9F%AD%ED%82%A4%EB%B9%84%ED%82%A4"
    monkeypatch.setattr(namuwiki, "lookup", lambda name: [ev("wiki", "namu.wiki", f"나무위키: {name}", f"{name}는 긍정 밈이다", url=namu_url,
                                                              when=namu_mod["when"])])
    con = db.connect(":memory:")
    listed(con, "t_ko", "럭키비키", lang="ko")
    listed(con, "t_en", "aura farming")
    listed(con, "t_busy", "brat summer")
    ds.queue_review(con, "t_busy", None, ["문서 대조: 밈이 아님"], 1, kind="retire")
    assert {t.term_id for t in crosscheck.targets(con, 8)} == {"t_ko", "t_en"}               # 사람이 보고 있는 제안이 있는 말은 건너뛴다
    assert crosscheck.run(con, limit=1)["crosscheck"].count == 1                              # 실행마다 칸이 정해져 있다
    crosscheck.run(con)
    assert crosscheck.targets(con, 8) == []
    ds.add_evidences(con, "t_en", [ev("wiki", "wikipedia.org", "Aura farming", "Aura farming is acting cool.", url=WIKI_URL)])
    assert [t.term_id for t in crosscheck.targets(con, 8)] == ["t_en"]                        # 새 참고 문서 근거가 생겼다
    crosscheck.run(con)
    namu_mod["when"] = NOW + timedelta(minutes=5)                                             # 마지막 대조 뒤 나무위키 문서가 고쳐졌다
    assert [t.term_id for t in crosscheck.targets(con, 8)] == ["t_ko"]


def test_long_no_doc_asks_to_retire_only_auto_verified(monkeypatch):
    """자동 확인된 말이 NO_DOC_RETIRE_DAYS 넘게 이어서 '문서 없음' 이면 '뺄지' 제안만 올린다. 사람이 확인한 말·닿지 못함은 셈하지 않는다."""
    _no_model(monkeypatch)
    monkeypatch.setattr(crosscheck, "gather", lambda term: ([], []))
    con = db.connect(":memory:")
    listed(con, "t_auto", "라을라", lang="ko")
    listed(con, "t_human", "라을라2", lang="ko", verification="verified_human")
    old = (NOW - timedelta(days=crosscheck.NO_DOC_RETIRE_DAYS + 1)).isoformat()
    for tid in ("t_auto", "t_human"):
        con.execute("INSERT INTO crosscheck_log VALUES (?,?,'no_doc','[]','rule')", (tid, old))
        con.execute("INSERT INTO crosscheck_log VALUES (?,?,'unreachable','[]','')", (tid, (NOW - timedelta(days=3)).isoformat()))
    con.commit()
    auto, human = ds.get_term(con, "t_auto"), ds.get_term(con, "t_human")
    assert crosscheck.check(con, auto, judging=False)["queued"] == "queued"
    assert crosscheck.check(con, human, judging=False)["queued"] is None                      # 사람이 확인한 말은 묻지 않는다
    q = ds.pending_review(con, "t_auto")
    assert q["kind"] == "retire" and ds.get_term(con, "t_auto").status == "verified"           # 빼지는 않는다 — 사람이 정한다
    con.execute("INSERT INTO crosscheck_log VALUES ('t_fresh',?,'no_doc','[]','rule')", ((NOW - timedelta(days=2)).isoformat(),))
    listed(con, "t_fresh", "라을라3", lang="ko")
    con.execute("INSERT INTO crosscheck_log VALUES ('t_fresh',?,'keep','[]','local')", ((NOW - timedelta(days=30)).isoformat(),))
    con.commit()
    assert crosscheck.check(con, ds.get_term(con, "t_fresh"), judging=False)["queued"] is None  # 문서를 찾았던 뒤로는 이틀뿐
