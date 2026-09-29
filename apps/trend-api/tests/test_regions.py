"""목표 지역 공급(Plan 04) — 광동어는 홍콩, 대만·홍콩 재기, 사전이 빈 지역의 조사 칸, 위키 씨앗, 다른 나라 판과 매체의 나라. 네트워크·모델 없이."""
import json
from datetime import datetime, timezone

from trend_agents.schemas import MeaningDraft, NewsItem, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

NOW = datetime.now(timezone.utc)


def _term(tid, name, lang, status="verified"):
    now = datetime.now(timezone.utc)
    return Term(term_id=tid, canonical=name, lang=lang, status=status, first_seen=now, last_seen=now)


def _verified(con, tid, name, lang, usage):
    """확인된 용어 — 조사가 정한 쓰는 나라(usage)와 함께."""
    ds.upsert_term(con, _term(tid, name, lang))
    ds.add_meaning(con, tid, MeaningDraft(definition="멋있어 보이려고 일부러 폼을 잡는 것", origin="x", nuance="y", generations=["20s"],
                                          regions=list(usage), self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, tid, [("20s", r, NOW.isoformat(), 1.0) for r in usage])


def _news(link, title, source, region="US", query=None, when=None):
    return NewsItem(title=title, link=link, source=source, published_at=when or NOW, region=region, query=query)


def _headlines(con, source, region, k):
    """그 판의 머리기사(키워드 없이 받은 뉴스) k 건 — 매체의 나라를 정하는 재료."""
    db.upsert_news(con, [_news(f"h-{source}-{region}-{i}", f"{source} headline {i}", source, region) for i in range(k)])


def _collect(con, monkeypatch, results: dict) -> None:
    """collect.run 을 네트워크 없이. 키워드 검색은 results[(판, 검색어)] 를 그 판의 결과로 돌려주고, 머리기사·트렌드·위키는 비운다."""
    from trend_agents.pipeline import collect

    monkeypatch.setattr(collect, "YOUTUBE_API_KEY", "")
    monkeypatch.setattr(collect.gt, "trending_now", lambda *a, **k: [])
    monkeypatch.setattr(collect.gt, "latest_refresh_date", lambda *a, **k: None)
    monkeypatch.setattr(collect.wikipedia_top, "top_articles", lambda *a, **k: [])
    monkeypatch.setattr(collect.news_rss, "fetch_news", lambda region, query=None, limit=30, **k:
                        [n.model_copy(update={"region": region, "query": query}) for n in results.get((region, query), [])])
    collect.run(con, mention_terms=30)


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
    monkeypatch.setattr(wiki_memes, "_members", lambda lang, cat, limit: [])     # 나라 분류를 받으러 나가지 않게
    got = {r["term"]: r["region"] for r in wiki_memes.known_memes(("zh",))}
    assert got == {"行得㗎啦": "HK", "傻眼貓咪": "TW"}


def test_chinese_mentions_are_taken_in_taiwan_and_hong_kong_each_time():
    """중국어 표제어는 대만판에 더해 홍콩판도 잰다 — 대만판만 재서 홍콩 키워드 검색이 0건이었다. 대만판은 매번(생애주기의 틀),
    번갈아 재면 홍콩을 잰 주의 대만 기사가 비었다. 광동어는 홍콩만, 다른 말은 그대로."""
    from trend_agents.pipeline.collect import mention_regions

    con = db.connect(":memory:")
    zh, yue, ko = _term("zh", "傻眼貓咪", "zh"), _term("yue", "行得㗎啦", "zh"), _term("ko", "럭키비키", "ko")
    seen = []
    for _ in range(3):
        got = mention_regions(zh, ds.mention_rotation(con).get("zh"))
        ds.mark_mention_sampled(con, "zh", got[-1])
        seen.append(got)
    assert seen == [["TW", "HK"]] * 3
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


def test_english_terms_are_also_counted_in_sg_my_ph_editions():
    """영어 표제어는 미국판에 더해 싱가포르·말레이시아·필리핀 영어판을 하나씩 돌아가며 잰다 — 미국 뉴스에서만 쟀다(US 195 · SG 2 · MY 3 · PH 2)."""
    from trend_agents.pipeline.collect import mention_regions

    con = db.connect(":memory:")
    en = _term("en", "aura farming", "en")
    seen = []
    for _ in range(4):
        got = mention_regions(en, ds.mention_rotation(con).get("en"))
        ds.mark_mention_sampled(con, "en", got[-1])
        seen.append(got)
    assert seen == [["US", "SG"], ["US", "MY"], ["US", "PH"], ["US", "SG"]]
    assert mention_regions(_term("ms", "LENGKET SEMUA", "ms"), None) == ["MY"]      # 말레이어는 말레이시아판 하나(근거가 되는 판)


def test_publisher_home_is_the_edition_that_carries_its_headlines():
    """매체의 나라는 최근 머리기사의 대부분(80% 이상, 10건 이상)이 나온 판 — 여러 판에 뜨는 BBC, 머리기사에 드문 매체는 나라가 없다.
    키워드 검색 결과는 재료가 아니다(우리가 어느 판에서 무엇을 찾았는지에 따라 달라진다)."""
    from trend_agents.pipeline import collect

    con = db.connect(":memory:")
    for source, region, k in (("CNA", "SG", 19), ("CNA", "MY", 1), ("BBC", "GB", 8), ("BBC", "US", 6), ("BBC", "SG", 6), ("Tiny", "SG", 3)):
        _headlines(con, source, region, k)
    db.upsert_news(con, [_news(f"q{i}", "So shiok", "Mothership", "SG", query="shiok") for i in range(12)])
    assert collect.source_homes(con) == {"CNA": "SG"}


def test_other_editions_give_evidence_only_from_their_own_outlets(monkeypatch):
    """표제어의 나라 밖 판(영어의 SG·MY·PH)에서 받은 기사는 그 판의 나라 매체가 낸 것만 근거(news)다. 다른 나라 매체가 그 판에 뜬 것
    (싱가포르판의 BBC·Bloomberg)은 mention_samples 에만 둔다 — news 에 넣었더니 같은 기사를 다른 말의 미국판 검색이나 다음 실행의 미국판에서
    받아도 주소가 같아 근거가 되지 못했다(검토 09-30). 조사가 그 나라에서 쓴다고 정한 말(싱글리시)은 그 판의 기사가 모두 근거다."""
    from trend_agents.pipeline.research import first_party_evidence

    con = db.connect(":memory:")
    _headlines(con, "CNA", "SG", 12)                                                   # CNA 는 싱가포르 매체
    _verified(con, "af", "aura farming", "en", ["US"])
    _verified(con, "sk", "skibidi", "en", ["US"])
    _verified(con, "sh", "shiok", "en", ["SG"])
    shared = _news("L", "Skibidi and aura farming take over", "BBC")
    results = {("US", "aura farming"): [_news("U1", "What is aura farming?", "CNN")],
               ("SG", "aura farming"): [shared, _news("C1", "Aura farming at the MRT", "CNA"), _news("L2", "Aura farming, explained", "Bloomberg")],
               ("US", "skibidi"): [shared],
               ("SG", "shiok"): [_news("M1", "So shiok lah", "Mothership")]}
    _collect(con, monkeypatch, results)
    assert dict(con.execute("SELECT link, region FROM news WHERE query IS NOT NULL").fetchall()) == {"U1": "US", "C1": "SG", "L": "US", "M1": "SG"}
    assert "L" in {e.url for e in first_party_evidence(con, "skibidi")}               # 싱가포르판이 먼저 받았어도 미국판의 근거
    assert {e.url for e in first_party_evidence(con, "aura farming")} == {"U1", "C1", "L"}
    assert {e.url for e in first_party_evidence(con, "shiok")} == {"M1"}
    samples = dict(con.execute("SELECT link, home FROM mention_samples WHERE term_id='af' AND region='SG'").fetchall())
    assert samples == {"L": None, "C1": "SG", "L2": None}                             # 매체의 나라를 함께 적는다

    results[("US", "aura farming")].append(_news("L2", "Aura farming, explained", "Bloomberg"))
    _collect(con, monkeypatch, results)                                                # 다음 실행: 지난번 싱가포르판에만 있던 기사를 미국판에서 받는다
    assert "L2" in {e.url for e in first_party_evidence(con, "aura farming")}


def test_other_editions_count_per_region_but_not_in_the_total_or_lifecycle():
    """다른 판에서 잰 기사(그 나라 매체의 근거든, mention_samples 의 지표든)는 나라별 수에만 센다. 전체 수·생애주기에 넣었더니 미국판에서
    [2]×11 로 '꾸준함' 인 말이 싱가포르판 기사 셋이 든 주에 '오르는 중' 이 됐다(검토 09-30 실측) — 오르는 중은 재검증이 3일마다라 칸도 가져갔다."""
    from datetime import date, time, timedelta

    from trend_agents.pipeline import track

    con = db.connect(":memory:")
    ds.upsert_term(con, Term(term_id="t", canonical="aura farming", lang="en", status="verified", first_seen=NOW - timedelta(days=200), last_seen=NOW))
    monday = date.today() - timedelta(days=date.today().weekday())
    at = lambda d: datetime.combine(d, time(12), tzinfo=timezone.utc)                      # noqa: E731
    db.upsert_news(con, [_news(f"us{w}-{i}", f"aura farming {w}-{i}", "CNN", "US", "aura farming", at(monday - timedelta(weeks=w) + timedelta(days=2)))
                         for w in range(1, 12) for i in range(2)])
    last_sunday = at(monday - timedelta(days=1))
    con.execute("INSERT OR REPLACE INTO mention_queries VALUES (?,?,?)", ("t", last_sunday.isoformat(), "SG"))   # 지난주 일요일까지 잼
    con.commit()
    track.run(con)
    assert ds.get_term(con, "t").lifecycle == "steady"

    saturday = last_sunday - timedelta(days=1)
    db.upsert_news(con, [_news(f"cna{i}", f"Aura farming at the MRT {i}", "CNA", "SG", "aura farming", saturday) for i in range(2)])   # 싱가포르 매체(근거)
    ds.add_mention_samples(con, "t", [_news("bbc", "Aura farming, explained", "BBC", "SG", "aura farming", saturday)], {})     # 다른 나라 매체(지표)
    track.run(con)
    week = (monday - timedelta(weeks=1)).isoformat()
    assert ds.get_term(con, "t").lifecycle == "steady"
    assert dict(ds.get_weekly(con, "t"))[week] == 2 and ds.get_weekly_region(con, "t")["SG"][week] == 3


def test_english_community_research_rotates_sg_my_ph_sites():
    """영어 표제어의 커뮤니티 조사는 싱가포르·말레이시아·필리핀 사이트를 돌아간다(각 목록에 reddit 이 있어 미국 몫도 그대로)."""
    from trend_agents.collectors.community import COMMUNITY_SITES
    from trend_agents.pipeline.research import community_region

    con = db.connect(":memory:")
    en = _term("en", "aura farming", "en")
    got = []
    for _ in range(4):
        got.append(community_region(con, en))
        ds.log_research(con, "en", "test", "", [], "unverified", [])
    assert got == ["SG", "MY", "PH", "SG"]
    assert all("reddit.com" in COMMUNITY_SITES[r] for r in ("SG", "MY", "PH"))


def test_term_joins_a_region_when_its_outlets_there_reach_n():
    """조사가 정하지 않은 목표 지역도 그 나라 매체 N 곳이 12주 안에 쓰면 그 지역 용어로 본다 — 더하기만 하고, 조사로 정한 '전 세계' 는 그대로
    둔다(판의 기사 수로 더했더니 미국에서만 쓴다던 영어 말이 '전 세계' 목록에서 빠졌다, 검토 09-30)."""
    from trend_agents.pipeline import dashboard

    n = dashboard.REGION_MIN_OUTLETS
    en = _term("en", "aura farming", "en")
    assert dashboard.term_regions(en, {"KR"}, {"SG": n, "MY": n - 1}) == ["KR", "SG"]
    assert dashboard.term_regions(en, {"US"}, {"PH": n}) == ["PH", "GLOBAL"]    # 미국에서만 쓰던 영어 말도 필리핀 매체 N 곳이면 필리핀에도
    assert dashboard.term_regions(en, {"US"}, {"PH": n - 1}) == ["GLOBAL"]
    cake = _term("cake", "The cake is a lie", "ja")                              # 나라 정보가 없는 로마자 표제어
    assert dashboard.term_regions(cake, set(), {"SG": n}) == ["SG", "GLOBAL"] and dashboard.term_regions(cake, set(), {}) == ["GLOBAL"]
    assert dashboard.term_regions(_term("zh", "傻眼貓咪", "zh"), set(), {"HK": n}) == ["TW", "HK"]
    assert dashboard.term_regions(_term("de", "Ehrenmann", "de"), {"DE"}, {"SG": n - 1}) == []


def test_regions_come_from_local_outlets_not_edition_hits():
    """판의 기사 수가 아니라 그 나라 매체 수로 센다 — 검토(09-30)가 재현한 잘못된 지역을 막는다. 홍콩판의 領便當 기사는 대만·태국 매체였고,
    싱가포르판의 'vibe' 는 BBC·Bloomberg·NYT 였다. 머리기사는 세지 않는다('草' 가 대만판 '草莓', 'vibe' 가 한국판 노래 'VIBE' 기사에 걸렸다).
    같은 매체의 다른 이름('Malay Mail'·'malaymail.com')은 한 곳이다."""
    from trend_agents.pipeline import dashboard

    con = db.connect(":memory:")
    for tid, name, lang, usage in (("lb", "領便當", "zh", ["TW"]), ("v", "vibe", "en", ["US"]), ("k", "草", "ja", ["JP"]), ("af", "aura farming", "en", ["US"])):
        _verified(con, tid, name, lang, usage)
    homes = {"LINE TODAY": "TH", "Yahoo新聞": "TW", "中天新聞網": "TW", "Malay Mail": "MY", "malaymail.com": "MY", "The Star": "MY"}

    def sample(tid, query, region, sources, title):
        ds.add_mention_samples(con, tid, [_news(f"{tid}{i}", f"{title} {i}", s, region, query) for i, s in enumerate(sources)], homes)

    def regions(tid):
        return dashboard.regions_for(con, ds.get_term(con, tid))

    sample("lb", "領便當", "HK", ["LINE TODAY", "LINE TODAY", "Yahoo新聞", "中天新聞網"], "角色領便當")
    sample("v", "vibe", "SG", ["BBC", "Bloomberg", "The New York Times", "Ars Technica"], "The vibe shift")
    sample("af", "aura farming", "MY", ["Malay Mail", "malaymail.com", "The Star"], "Aura farming")
    db.upsert_news(con, [_news(f"tw{i}", f"草莓季開跑 {i}", s, "TW") for i, s in enumerate(["自由時報", "UDN", "Yahoo新聞"])]
                   + [_news(f"kr{i}", f"태양 'VIBE' 차트 {i}", s, "KR") for i, s in enumerate(["연합뉴스", "뉴시스", "스포츠조선"])])
    assert (regions("lb"), regions("v"), regions("k")) == (["TW"], ["GLOBAL"], ["JP"])
    assert dashboard.local_outlets(con, "af") == {"MY": 2} and regions("af") == ["GLOBAL"]
    ds.add_mention_samples(con, "af", [_news("af9", "Aura farming at KLCC", "Free Malaysia Today", "MY", "aura farming")], {"Free Malaysia Today": "MY"})
    assert regions("af") == ["MY", "GLOBAL"]


def test_dashboard_and_dictionary_share_the_region_rule():
    """싱가포르 매체 N 곳이 쓴 말은 대시보드 싱가포르 목록에 들고(수치도 싱가포르판 기사), 사전 항목(API)의 지역도 같은 값이다.
    '전 세계' 목록에도 그대로 남는다."""
    from trend_agents.pipeline import dashboard, track, views

    con = db.connect(":memory:")
    _verified(con, "t1", "aura farming", "en", ["US"])
    track.run(con)
    dashboard.run(con)
    assert dashboard.card(con, "t1").regions == ["GLOBAL"] and views.term_record(con, ds.get_term(con, "t1")).regions == ["GLOBAL"]

    sg = ["The Straits Times", "CNA", "AsiaOne"]
    ds.add_mention_samples(con, "t1", [_news(f"sg{i}", f"Aura farming story {i}", s, "SG", "aura farming") for i, s in enumerate(sg)], dict.fromkeys(sg, "SG"))
    track.run(con)
    dashboard.run(con)
    board = dashboard.board(con, ["SG"])
    assert [c.term_id for c in board.rising + board.fading] == ["t1"] and (board.rising + board.fading)[0].mentions_4w == len(sg)
    assert dashboard.card(con, "t1").regions == ["SG", "GLOBAL"] == views.term_record(con, ds.get_term(con, "t1")).regions
    glob = dashboard.board(con, ["GLOBAL"])
    assert [c.term_id for c in glob.rising + glob.fading] == ["t1"]


def test_research_reserves_slots_for_under_covered_target_regions():
    """새 표제어 칸 가운데 몇 칸은 사전이 빈 목표 지역(HK·SG·MY·VN·PH·TH·ID) 후보에 먼저 — spot 후보는 출처 순서로 늘 맨 뒤라
    홍콩에서 네 번 본 行得㗎啦 가 09-28 부터 기다렸다. 그 지역에서 봤어도 그 지역 말이 아니면(인니 쇼츠의 힌디어) 칸을 받지 않는다."""
    from trend_agents.pipeline import research

    con = db.connect(":memory:")
    for k in range(12):
        ds.upsert_candidate(con, f"Wiki meme {k}", "en", "US", "wiki", note="kind=meme wiki=x")       # 위키 후보가 칸을 모두 채울 만큼
    for _ in range(4):
        ds.upsert_candidate(con, "行得㗎啦", "zh", "HK", "spot", note="kind=meme; spot")
        ds.upsert_candidate(con, "Kisme Jda Hoga", "hi", "ID", "spot", note="kind=meme; spot")
    for _ in range(2):
        ds.upsert_candidate(con, "หาแดก", "th", "TH", "spot", note="kind=meme; spot")
        ds.upsert_candidate(con, "WENG-WENG", "en", "PH", "spot", note="kind=meme; spot")
        ds.upsert_candidate(con, "Bro", "en", "ID", "spot", note="kind=meme; spot")               # 인니에서 본 영어 — 인니 말이 아니다
    ds.upsert_candidate(con, "TAM THÁI TỬ", "vi", "VN", "spot", note="kind=song; spot")            # 노래는 한 번만 봐도 승격
    region = {c.text: research.target_region(c) for c in ds.candidates(con, "new", 100)}
    assert (region["行得㗎啦"], region["หาแดก"], region["WENG-WENG"], region["TAM THÁI TỬ"]) == ("HK", "TH", "PH", "VN")
    assert region["Kisme Jda Hoga"] is region["Bro"] is region["Wiki meme 0"] is None

    got = [t.canonical for t in research.promote_candidates(con, 8)]
    assert len(got) == 8 and got[0] == "行得㗎啦" and set(got[:research.REGION_SLOTS]) == {"行得㗎啦", "หาแดก", "WENG-WENG"}   # 많이 본 순
    assert sum(g.startswith("Wiki meme") for g in got) == 8 - research.REGION_SLOTS                # 나머지 칸은 예전 순서(위키 먼저)
    assert "Kisme Jda Hoga" not in got and "Bro" not in got
    assert [t.canonical for t in research.promote_candidates(con, 8)][:1] == ["TAM THÁI TỬ"]      # 다음 실행에는 남은 지역 후보가 먼저


def test_wiki_seed_keeps_animal_memes_with_a_birth_year():
    """'태어난 해' 는 사람 문서의 표시라 버리지만, 동물 밈(태국 피그미하마 Moo Deng 'born 2024')까지 버렸다."""
    from trend_agents.collectors.wiki_memes import is_meme

    assert is_meme("Thai pygmy hippopotamus (born 2024)") and is_meme("Internet celebrity cat (2012–2019)")
    assert not is_meme("French pole vaulter (born 2003)") and not is_meme("American killer (born 1998)")
    assert not is_meme("Australian breakdancer (Born 1987)")                       # 예전처럼 대소문자는 가리지 않는다
    assert not is_meme("Japanese Thoroughbred racehorse (1996–2025)")        # 경주마는 따로 막는다
    assert not is_meme("미국의 유튜버, 방송인 (1990-2019)") and not is_meme("大韓民国の歌手 (1990-)")
    assert not is_meme("维基媒体消歧义页") and not is_meme("香港網絡論壇") and is_meme("香港流行語")       # 홍콩 분류의 동음이의·게시판 문서


def test_wiki_seeds_add_hong_kong_categories_and_target_country_english_memes(tmp_path, monkeypatch):
    """홍콩 분류(香港網絡迷因·香港網絡文化·香港俚語)를 더하고 그 문서는 홍콩으로 둔다 — 이미 받아 둔 캐시에도 새로 받는다.
    영어 밈은 설명이 목표 지역을 대면 그 나라로(Moo Deng → 태국, Pacu Jalur → 인도네시아), 북한은 한국이 아니다."""
    from trend_agents.collectors import wiki_memes

    cache = tmp_path / "wiki_memes.json"
    cache.write_text(json.dumps([
        {"title": "Moo Deng", "term": "Moo Deng", "lang": "en", "description": "Thai pygmy hippopotamus (born 2024)"},
        {"title": "Pacu Jalur", "term": "Pacu Jalur", "lang": "en", "description": "Traditional canoe racing in Sumatra, Indonesia"},
        {"title": "Chill Guy", "term": "Chill Guy", "lang": "en", "description": "2024 internet meme"},
        {"title": "Juche Gang", "term": "Juche Gang", "lang": "en", "description": "North Korean propaganda internet meme"},
        {"title": "傻眼貓咪", "term": "傻眼貓咪", "lang": "zh", "description": ""},
    ], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(wiki_memes, "CACHE", cache)
    asked: list[str] = []
    members = {"Category:香港網絡迷因": ["Obsession糖衣陷阱"], "Category:香港網絡文化": ["屈機", "港女 (潮語)", "香港網絡用語列表"],
               "Category:香港俚語": ["屈機", "師奶"]}
    monkeypatch.setattr(wiki_memes, "_members", lambda lang, cat, limit: asked.append(cat) or members[cat])
    monkeypatch.setattr(wiki_memes, "_simplified", lambda titles: set())
    monkeypatch.setattr(wiki_memes, "_descriptions", lambda lang, titles: {})

    got = {r["term"]: r["region"] for r in wiki_memes.known_memes(("en", "zh"))}
    assert asked == ["Category:香港網絡迷因", "Category:香港網絡文化", "Category:香港俚語"]     # 캐시에 없는 홍콩 분류만 받는다
    assert got == {"Moo Deng": "TH", "Pacu Jalur": "ID", "Chill Guy": "US", "Juche Gang": "US", "傻眼貓咪": "TW",
                   "Obsession糖衣陷阱": "HK", "屈機": "HK", "港女": "HK", "師奶": "HK"}
    asked.clear()
    assert {r["term"] for r in wiki_memes.known_memes(("zh",))} >= {"屈機", "傻眼貓咪"} and asked == []   # 다음에는 캐시에서
