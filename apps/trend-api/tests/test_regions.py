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


def test_chinese_mentions_alternate_between_taiwan_and_hong_kong():
    """중국어 표제어는 대만·홍콩 뉴스판을 번갈아 잰다 — 대만판만 재서 홍콩 키워드 검색이 0건이었다. 광동어는 홍콩만, 다른 말은 그대로."""
    from trend_agents.pipeline.collect import mention_regions

    con = db.connect(":memory:")
    zh, yue, ko = _term("zh", "傻眼貓咪", "zh"), _term("yue", "行得㗎啦", "zh"), _term("ko", "럭키비키", "ko")
    seen = []
    for _ in range(3):
        [region] = mention_regions(zh, ds.mention_rotation(con).get("zh"))
        ds.mark_mention_sampled(con, "zh", region)
        seen.append(region)
    assert seen == ["TW", "HK", "TW"]
    assert mention_regions(yue, "HK") == ["HK"] and mention_regions(yue, None) == ["HK"]
    assert mention_regions(ko, None) == ["KR"] and mention_regions(_term("de", "Ehrenmann", "de"), None) == ["DE"]


def test_chinese_community_research_alternates_between_taiwan_and_hong_kong():
    """커뮤니티 조사도 조사할 때마다 대만·홍콩 사이트를 번갈아 뒤진다. 광동어는 홍콩, 한국어는 한국."""
    from trend_agents.pipeline.research import community_region

    con = db.connect(":memory:")
    zh = _term("zh", "傻眼貓咪", "zh")
    assert community_region(con, zh) == "TW"
    ds.log_research(con, "zh", "test", "", [], "unverified", [])
    assert community_region(con, zh) == "HK"
    ds.log_research(con, "zh", "test", "", [], "unverified", [])
    assert community_region(con, zh) == "TW"
    assert community_region(con, _term("yue", "行得㗎啦", "zh")) == "HK"
    assert community_region(con, _term("ko", "럭키비키", "ko")) == "KR"


def test_mention_rotation_column_upgrades_an_existing_table():
    """마이그레이션 013 은 이미 있는 두 칸짜리 mention_queries 에 나라 칸을 더한다(운영 DB). 예전 행은 차례가 없는 것으로 읽힌다."""
    con = db.connect(":memory:")
    con.executescript("DROP TABLE mention_queries; CREATE TABLE mention_queries (term_id TEXT PRIMARY KEY, last_at TEXT);"
                      "INSERT INTO mention_queries VALUES ('old', '2026-09-28T00:00:00+00:00'); DELETE FROM schema_migrations WHERE version=13;")
    from trend_agents.storage.db import apply_migrations

    assert apply_migrations(con) == ["013_mention_regions.sql"]
    assert ds.mention_rotation(con) == {} and set(ds.mention_sampled(con)) == {"old"}
    ds.mark_mention_sampled(con, "old", "HK")
    assert ds.mention_rotation(con) == {"old": "HK"}
