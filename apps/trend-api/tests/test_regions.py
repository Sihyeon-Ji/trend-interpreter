"""목표 지역 공급(Plan 04) — 광동어는 홍콩, 대만·홍콩 번갈아 재기, 사전이 빈 지역의 조사 칸, 위키 씨앗, 영어판 지표. 네트워크·모델 없이."""
import json
from datetime import datetime, timezone

from trend_agents.schemas import Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _term(tid, name, lang, status="verified"):
    now = datetime.now(timezone.utc)
    return Term(term_id=tid, canonical=name, lang=lang, status=status, first_seen=now, last_seen=now)


def test_cantonese_headwords_belong_to_hong_kong():
    """광동어에만 쓰는 글자가 든 표제어, 광동어 코드(yue·yu)는 홍콩. 다른 중국어는 그대로 대만."""
    from trend_agents.config import home_region

    assert home_region("行得㗎啦", "zh") == "HK" and home_region("食咗飯未", "zh") == "HK"
    assert home_region("好正", "yue") == "HK" and home_region("好正", "yu") == "HK"
    assert home_region("傻眼貓咪", "zh") == "TW" and home_region("推し活", "ja") == "JP"
    assert home_region("aura farming", "en") is None


def test_cantonese_codes_share_one_candidate():
    """spot 이 같은 말을 zh·yu 로 따로 넣어 목격 수가 갈렸다(行得㗎啦, 09-28). 광동어 코드는 중국어 후보 하나로 모은다."""
    con = db.connect(":memory:")
    ds.upsert_candidate(con, "行得㗎啦", "zh", "HK", "spot", note="kind=meme; spot")
    ds.upsert_candidate(con, "行得㗎啦", "yu", "HK", "spot", note="kind=meme; spot")
    ds.upsert_candidate(con, "行得㗎啦", "yue", "HK", "spot", note="kind=meme; spot")
    assert [(c.text, c.lang, c.count) for c in ds.candidates(con, "new", 10)] == [("行得㗎啦", "zh", 3)]


def test_dashboard_puts_cantonese_headwords_in_hong_kong():
    """조사가 나라를 정하지 않은 중국어 표제어: 광동어 글자가 있으면 홍콩, 없으면 대만."""
    from trend_agents.pipeline.dashboard import term_regions

    assert term_regions(_term("hk", "行得㗎啦", "zh"), set()) == ["HK"]
    assert term_regions(_term("yue", "好正", "yue"), set()) == ["HK"]      # 예전 후보에 남은 광동어 코드
    assert term_regions(_term("tw", "傻眼貓咪", "zh"), set()) == ["TW"]


def test_wiki_seeds_send_cantonese_titles_to_hong_kong(tmp_path, monkeypatch):
    """중국어 위키 밈의 지역도 같은 규칙 — 광동어 제목은 홍콩, 그 밖에는 대만."""
    from trend_agents.collectors import wiki_memes

    cache = tmp_path / "wiki_memes.json"
    cache.write_text(json.dumps([{"title": "行得㗎啦", "term": "行得㗎啦", "lang": "zh", "description": ""},
                                 {"title": "傻眼貓咪", "term": "傻眼貓咪", "lang": "zh", "description": ""}], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(wiki_memes, "CACHE", cache)
    got = {r["term"]: r["region"] for r in wiki_memes.known_memes(("zh",))}
    assert got == {"行得㗎啦": "HK", "傻眼貓咪": "TW"}
