"""콘텐츠 조사 에이전트의 규칙 — 네트워크·모델 없이. 모델 응답과 웹 문서는 가짜로 넣는다."""
from __future__ import annotations

import json

from trend_agents.pipeline import content_agent as C
from trend_agents.pipeline import web_tools as W
from trend_agents.storage import store as db

NAMU = "https://namu.wiki/w/오징어 게임/흥행 및 파급력"
KYM = "https://knowyourmeme.com/memes/ive-played-these-games-before"
CHUNK = ('본편 3화에서 성기훈이 "나는 이 게임을 해 봤어요!"라고 외치나 반박당하는 장면이 밈이 되었다. '
         '또한 해외에서도 "I\'ve Played These Games Before!"를 밈으로 사용하고 있다. 펩시가 자사 로고를 새긴 달고나 이미지를 올렸다.')


def fake_chat(items):
    def chat(prompt, schema):
        return schema.model_validate({"items": items})
    return chat


def test_extract_keeps_only_names_and_sentences_in_the_chunk():
    page = {"url": NAMU, "text": CHUNK}
    got = C._extract(page, "Squid Game", {"ko": "오징어 게임"}, fake_chat([
        {"name": "나는 이 게임을 해 봤어요!", "region": "GLOBAL", "kind": "대사", "sentence": "본편 3화에서 성기훈이"},
        {"name": "I've Played These Games Before!", "region": "GLOBAL", "kind": "대사", "sentence": "지어낸 문장"},
        {"name": "깐부", "region": "KR", "kind": "유행어"},                                  # 조각에 없다 → 지어낸 것
        {"name": "달고나", "region": "GLOBAL", "kind": "일회성"},                            # 기업이 한 번 따라 한 것
        {"name": "오징어 게임", "region": "KR", "kind": "패러디"},                            # 작품 이름 자체
        {"name": "오징어 게임 패러디 영상", "region": "KR", "kind": "패러디"},                  # 뭉뚱그린 말(조각에 없기도)
    ]))
    by = {g["name"]: g for g in got}
    assert set(by) == {"나는 이 게임을 해 봤어요!", "I've Played These Games Before!"}
    assert by["나는 이 게임을 해 봤어요!"]["region"] == "KR"                                # 한글 이름은 한국 이름
    assert by["I've Played These Games Before!"]["region"] == "GLOBAL"
    assert by["I've Played These Games Before!"]["sentence"] == ""                          # 조각에 없는 근거 문장은 버린다
    assert all(g["evidence_url"] == NAMU for g in got)


def test_extract_local_wikipedia_names_get_that_country():
    page = {"url": "https://id.wikipedia.org/wiki/Squid_Game", "text": 'termasuk game "Lampu merah, Lampu Hijau" pertama'}
    got = C._extract(page, "Squid Game", {}, fake_chat([{"name": "Lampu merah, Lampu Hijau", "region": "GLOBAL", "kind": "챌린지"}]))
    assert got[0]["region"] == "ID"


def _seed(monkeypatch):
    con = db.connect(":memory:")
    pages = {NAMU: "깐부 이야기. " + "가" * 400 + CHUNK + " 오징어 게임", KYM: "Part of a series on Squid Game. I've Played These Games Before! refers to a scene"}
    monkeypatch.setattr(W, "page_text", lambda url: pages.get(W.canon(url), ""))
    monkeypatch.setattr(W, "in_series", lambda url, name: "Part of a series on " + name in pages.get(W.canon(url), ""))
    found = [
        {"name": "나는 이 게임을 해 봤어요!", "region": "KR", "description": "고인물 비유", "quote": "", "evidence_url": NAMU, "same_as": "", "sentence": "s"},
        {"name": "I've Played These Games Before!", "region": "GLOBAL", "description": "영어권", "quote": "", "evidence_url": KYM, "same_as": "", "sentence": ""},
        {"name": "깐부", "region": "KR", "description": "", "quote": "", "evidence_url": NAMU, "same_as": "", "sentence": ""},
        {"name": "도시락", "region": "KR", "description": "", "quote": "", "evidence_url": NAMU, "same_as": "", "sentence": ""},   # 근거 문서에 이름 없음
        {"name": "하... 씨발, 기훈이 형!", "region": "KR", "description": "", "quote": "", "evidence_url": NAMU, "same_as": "", "sentence": ""},
    ]
    pages[NAMU] += " 하... 씨발, 기훈이 형!"
    con.execute("INSERT INTO content_index VALUES ('squid-game','Squid Game',?, 'r1', 'now')", (json.dumps({"ko": "오징어 게임", "ja": "イカゲーム"}, ensure_ascii=False),))
    C.verify(con, "r1", "squid-game", "Squid Game", {"ko": "오징어 게임"}, found)
    C.pair(con, "r1", "squid-game", "Squid Game", found, fake_chat([
        {"a": "[KR] 나는 이 게임을 해 봤어요!", "b": "[GLOBAL] I've Played These Games Before!", "reason": "3화 대사"},
        {"a": "깐부", "b": "I've Played These Games Before!", "reason": "엉뚱한 짝"},
    ]))
    return con


def test_verify_and_pair_are_rule_checked(monkeypatch):
    con = _seed(monkeypatch)
    v = dict(con.execute("SELECT name, verified FROM content_findings").fetchall())
    assert v["나는 이 게임을 해 봤어요!"] == 1 and v["I've Played These Games Before!"] == 1 and v["도시락"] == 0
    pairs = {(a, b): ok for a, b, ok in con.execute("SELECT a, b, verified FROM content_pairs")}
    assert pairs[("나는 이 게임을 해 봤어요!", "I've Played These Games Before!")] == 1     # 나무위키 문장이 영어 이름을 말한다
    assert pairs[("깐부", "I've Played These Games Before!")] == 0          # 같은 문서에 있어도 멀리 떨어져 있으면 짝 확인이 아니다


def test_view_groups_same_meme_across_countries_and_hides_profanity(monkeypatch):
    con = _seed(monkeypatch)
    v = C.view(con, "squid-game")
    first = v["memes"][0]
    assert [x["region"] for x in first["variants"]] == ["KR", "GLOBAL"] and first["same_scene"] == "3화 대사"
    names = [x["name"] for m in v["memes"] for x in m["variants"]]
    assert "도시락" not in names and "깐부" in names   # 확인 안 된 것은 빠지고, 짝이 없는 것은 혼자 한 줄
    assert not any("씨발" in n for n in names)      # 욕설 대사는 둘러보기에 내지 않는다
    assert C.find_content(con, "イカゲーム") == ("squid-game", "Squid Game") and C.find_content(con, "더 글로리") is None
    assert C.contents(con)[0]["memes"] == 3


def test_web_tools_whitelist_and_canon():
    assert W.allowed("https://namu.wiki/w/깐부") and W.allowed("https://th.wikipedia.org/wiki/x") and W.allowed(KYM)
    assert not W.allowed("https://gall.dcinside.com/board/view") and not W.allowed("https://namu.wiki/history/x")
    assert W.canon("https://namu.wiki/w/%EA%B9%90%EB%B6%80") == "https://namu.wiki/w/깐부"
    assert "error" in W.open_page("https://www.reddit.com/r/memes")


def test_pair_on_one_page_is_only_a_proposal(monkeypatch):
    con = db.connect(":memory:")
    page = "태국에 Thai the glory 가 많다. 문동은의 대사를 인용하는 것이 학폭 비판이 됐다. 더 글로리"
    monkeypatch.setattr(W, "page_text", lambda url: page)
    found = [{"name": "Thai the glory", "region": "TH", "description": "", "quote": "", "evidence_url": NAMU, "same_as": "", "sentence": ""},
             {"name": "문동은의 대사", "region": "KR", "description": "", "quote": "", "evidence_url": NAMU, "same_as": "", "sentence": ""}]
    C.pair(con, "r", "the-glory", "The Glory", found, fake_chat([{"a": "Thai the glory", "b": "문동은의 대사", "reason": "학폭 폭로"}]))
    assert con.execute("SELECT verified FROM content_pairs").fetchone()[0] == 0     # 같은 문서에 나란히 적힌 두 밈


def test_quote_list_lines_need_a_meme_cue_nearby():
    text = ("6. 명대사 [편집]\n" + "가" * 300 + '"사과하지 마. 사과받자." ' + "나" * 300
            + ' "멋지다 연진아!" 이 대사는 방영 뒤 밈으로 널리 쓰였다.')
    page = {"url": "https://namu.wiki/w/박연진", "text": text}
    items = [{"name": "사과하지 마. 사과받자.", "region": "KR", "kind": "대사"}, {"name": "멋지다 연진아!", "region": "KR", "kind": "대사"}]
    got = C._extract(page, "The Glory", {"ko": "더 글로리"}, fake_chat(items), quotes=True)
    assert [g["name"] for g in got] == ["멋지다 연진아!"]
    assert len(C._extract(page, "The Glory", {"ko": "더 글로리"}, fake_chat(items))) == 2     # 밈 절이면 그대로


def test_suggestions_need_a_redirect_or_a_cue(monkeypatch):
    """Gemini 가 낸 후보는 나무위키가 그 말을 작품 문서로 넘겨줄 때(또는 연 문서 곁에 밈이라는 말이 있을 때)만 받는다."""
    from types import SimpleNamespace

    from trend_agents.pipeline import gemini

    con = db.connect(":memory:")
    cands = C.Suggestions(items=[C.Meme(name="멋지다 연진아!", region="KR"), C.Meme(name="Bravo Yeon-jin!", region="TH"),
                                 C.Meme(name="나 지금 너무 신나", region="KR")])
    monkeypatch.setattr(gemini, "configured", lambda: True)
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: (SimpleNamespace(parsed=cands), "gemini-test"))
    pages = {"https://namu.wiki/w/멋지다 연진아": ("더 글로리", "1. 개요 김은숙 작가의 드라마"), "https://namu.wiki/w/더 글로리": ("더 글로리", "본문")}
    monkeypatch.setattr(W, "open_page", lambda u, *a: {"title": pages[W.canon(u)][0]} if W.canon(u) in pages else {"error": "없음"})
    monkeypatch.setattr(W, "page_text", lambda u: pages.get(W.canon(u), ("", ""))[1])
    monkeypatch.setattr(W, "page_title", lambda u: pages.get(W.canon(u), ("", ""))[0])
    got = C.suggest(con, "The Glory", {"ko": "더 글로리"}, [], ["https://namu.wiki/w/더 글로리"])
    assert [(g["name"], g["evidence_url"]) for g in got] == [("멋지다 연진아!", "https://namu.wiki/w/멋지다 연진아")]
