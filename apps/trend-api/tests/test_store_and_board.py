"""저장소 버전 관리와 보드 생성 — 네트워크·모델 없이 인메모리 SQLite 로."""
from datetime import date, datetime, timezone

from trend_agents.pipeline import board, candidates, track
from trend_agents.schemas import MeaningDraft, Term, TrendQuery
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def draft(defn, exp):
    return MeaningDraft(definition=defn, expansion=exp, origin="x", nuance="y", generations=["20s"], regions=["KR"], self_confidence=0.9)


def test_meaning_versions_close_previous():
    con = db.connect(":memory:")
    t = ds.upsert_term(con, Term(term_id="t1", canonical="자만추", status="verified"))
    m1 = ds.add_meaning(con, t.term_id, draft("뜻1", "자연스러운 만남 추구"), "verified_auto", [])
    same = ds.add_meaning(con, t.term_id, draft("뜻1", "자연스러운 만남 추구"), "verified_auto", [])
    assert same.meaning_id == m1.meaning_id  # 같은 뜻이면 새 버전 없음
    m2 = ds.add_meaning(con, t.term_id, draft("뜻2", "자연스러운 만남 추구"), "verified_auto", [])
    assert m2.version == 2
    hist = ds.list_meanings(con, t.term_id)
    assert hist[0].valid_to is not None and hist[1].valid_to is None  # 이전 버전은 닫히고 삭제되지 않는다
    assert ds.current_meaning(con, t.term_id).meaning_id == m2.meaning_id


def test_candidates_and_board_from_trend_queries():
    con = db.connect(":memory:")
    today = date.today()
    qs = [TrendQuery(term="삐에로 밈", region="KR", rank=1, source="bq_rising", date=today, percent_gain=9000, news_title="삐에로 밈 화제"),
          TrendQuery(term="토트넘 대 에버턴", region="KR", rank=2, source="bq_rising", date=today, percent_gain=5000),
          TrendQuery(term="La Peace", region="US", rank=1, source="rss_now", date=today, approx_traffic="500+")]
    assert ds.upsert_trend_queries(con, qs) == 3
    assert ds.upsert_trend_queries(con, qs) == 0  # 중복은 무시
    ds.save_classifications(con, [
        {"term": "삐에로 밈", "region": "KR", "category": "slang_meme", "kind": "slang_meme", "is_term_candidate": True, "lang": "ko"},
        {"term": "토트넘 대 에버턴", "region": "KR", "category": "sports_event", "kind": "sports", "is_term_candidate": False, "lang": "ko"},
        {"term": "La Peace", "region": "US", "category": "slang_meme", "kind": "slang_meme", "is_term_candidate": True, "lang": "en"},
    ], "test-model")
    assert ds.unclassified_queries(con) == []
    r = candidates.run(con)["candidates"]
    assert r.count == 2 and len(ds.candidates(con, "new")) == 2
    b = board.build(con)
    assert {i.region for i in b.items} == {"KR", "US"}
    kr = [i for i in b.items if i.region == "KR"]
    assert {i.category for i in kr} == {"slang_meme", "sports_event"}
    assert all(i.change == "new" for i in b.items) and all(i.rank == 1 for i in b.items)


def test_track_sets_weekly_and_lifecycle():
    con = db.connect(":memory:")
    ds.upsert_term(con, Term(term_id="t1", canonical="라부부", status="verified", first_seen=datetime(2026, 6, 1, tzinfo=timezone.utc)))
    for d in ("2026-09-08", "2026-09-09", "2026-09-10", "2026-09-12"):
        ds.upsert_trend_queries(con, [TrendQuery(term="라부부", region="KR", rank=1, source="bq_top", date=date.fromisoformat(d))])
    r = track.run(con)["track"]
    assert r.count == 1
    weekly = ds.get_weekly(con, "t1")
    assert sum(c for _, c in weekly) == 4
    assert ds.get_term(con, "t1").lifecycle in ("emerging", "rising", "peak", "steady", "declining")


def test_spike_detection_ranks_focus_regions_and_skips_sports():
    from trend_agents.pipeline import spikes

    con = db.connect(":memory:")
    today = date.today()
    ds.upsert_trend_queries(con, [
        TrendQuery(term="만두", region="KR", rank=1, source="bq_rising", date=today, percent_gain=4800),
        TrendQuery(term="토트넘 대 에버턴", region="KR", rank=2, source="bq_rising", date=today, percent_gain=9000),
        TrendQuery(term="lego", region="DE", rank=1, source="rss_now", date=today, approx_traffic="5000+"),
        TrendQuery(term="tiny", region="US", rank=3, source="rss_now", date=today, approx_traffic="200+"),
    ])
    ds.save_classifications(con, [
        {"term": "만두", "region": "KR", "category": "food", "kind": "food", "is_term_candidate": False, "lang": "ko"},
        {"term": "토트넘 대 에버턴", "region": "KR", "category": "sports_event", "kind": "sports", "is_term_candidate": False, "lang": "ko"},
    ], "t")
    got = spikes.detect(con)
    assert [s["term"] for s in got] == ["만두", "lego"]  # 경기 제외, 검색량 미달 제외, 집중 국가 우선


def test_board_adds_korean_shopping_items():
    from trend_agents.pipeline import board

    con = db.connect(":memory:")
    weeks = [f"2026-{m:02d}-{d:02d}" for m, d in ((6, 1), (6, 8), (6, 15), (6, 22), (7, 6), (7, 13))]
    ds.upsert_shopping(con, "패션의류", "all", [{"period": w, "ratio": r} for w, r in zip(weeks, (50, 52, 55, 60, 70, 90))])
    ds.upsert_shopping(con, "패션의류", "20", [{"period": w, "ratio": r} for w, r in zip(weeks, (30, 30, 31, 33, 40, 61))])
    ds.upsert_shopping(con, "패션의류", "40", [{"period": w, "ratio": r} for w, r in zip(weeks, (20, 21, 20, 22, 25, 30))])
    items = board.shopping_items(con)
    assert len(items) == 1 and items[0].region == "KR" and items[0].category == "fashion_beauty"
    assert items[0].change == "up" and "20대" in items[0].note.ko


def test_promotion_needs_a_dictionary_kind():
    from trend_agents.pipeline.research import promote_candidates

    con = db.connect(":memory:")
    ds.upsert_candidate(con, "brics", "en", "IN", "trend")  # 분류 kind 없음 → 사전 대상 아님
    ds.upsert_candidate(con, "brics", "en", "US", "trend")
    ds.upsert_candidate(con, "aura farming", "en", "US", "trend", note="kind=slang_meme")
    ds.upsert_candidate(con, "Tung Sahur", "en", "ID", "shorts", note="kind=meme; ...")  # 밈 이름은 두 번째 등장을 기다린다
    got = {t.canonical: t for t in promote_candidates(con, 10)}
    assert set(got) == {"aura farming"} and got["aura farming"].category == "slang"
    assert {c.text for c in ds.candidates(con, "rejected")} == {"brics"}
    assert {c.text for c in ds.candidates(con, "new")} == {"Tung Sahur"}


def test_wiki_candidate_promotes_on_first_sight():
    """위키에서 온 후보는 1회만 보여도 조사 대상이 된다 (백과사전 문서 자체가 강한 신호)."""
    from trend_agents.pipeline.research import promote_candidates

    con = db.connect(":memory:")
    ds.upsert_candidate(con, "Bombardiro Crocodilo", "en", "US", "wiki", note="kind=meme wiki=Bombardiro Crocodilo")
    ds.upsert_candidate(con, "어쩌다 한 번 본 말", "ko", "KR", "trend", note="kind=meme")

    got = [t.canonical for t in promote_candidates(con, 10)]
    assert "Bombardiro Crocodilo" in got
    assert "어쩌다 한 번 본 말" not in got   # trend 출처는 여전히 2회 필요


def test_new_meaning_version_clears_stale_translations():
    """뜻이 바뀌면 예전 언어판은 지운다 — 안 지우면 화면에 옛 뜻이 남는다."""
    from datetime import datetime, timezone

    from trend_agents.schemas import MeaningDraft, MeaningText, Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = Term(term_id="t1", canonical="테스트말", lang="ko", status="researching", category="slang",
             first_seen=now, last_seen=now)
    ds.upsert_term(con, t)

    def draft(d: str) -> MeaningDraft:
        return MeaningDraft(definition=d, origin="unknown", nuance="없음", generations=["20s"], regions=["KR"],
                            self_confidence=0.9)

    ds.add_meaning(con, "t1", draft("처음 뜻"), "verified_auto", [])
    ds.set_translation(con, "t1", "ko", MeaningText(definition="처음 뜻", origin="unknown", nuance="없음"), "test")
    assert ds.get_translation(con, "t1", "ko") is not None

    ds.add_meaning(con, "t1", draft("고쳐 쓴 뜻"), "verified_auto", [])
    assert ds.get_translation(con, "t1", "ko") is None   # 옛 언어판은 사라진다


def test_old_single_sighting_spot_candidates_expire():
    """spot 에서 한 번만 보고 오래 묵은 후보는 만료된다 — 대기열이 끝없이 자라지 않게. 다른 출처는 건드리지 않는다."""
    from datetime import datetime, timedelta, timezone

    con = db.connect(":memory:")
    old = ds.upsert_candidate(con, "한번본말", "ko", "KR", "spot", note="kind=meme")
    keep = ds.upsert_candidate(con, "위키에서온말", "ko", "KR", "wiki", note="kind=meme")
    for c in (old, keep):
        c.last_seen = datetime.now(timezone.utc) - timedelta(days=30)
        con.execute("UPDATE candidates SET json=? WHERE candidate_id=?", (c.model_dump_json(), c.candidate_id))
    con.commit()
    assert ds.expire_candidates(con) == 1
    left = {c.text for c in ds.candidates(con, "new", 10)}
    assert left == {"위키에서온말"}


def test_expired_candidate_is_readable_and_revives_on_new_sighting():
    """만료된 후보도 다시 읽혀야 하고(스키마), 다시 나오면 new 로 돌아온다 — 예전엔 upsert 가 검증 오류로 죽었다."""
    from datetime import datetime, timedelta, timezone

    con = db.connect(":memory:")
    c = ds.upsert_candidate(con, "한번본말", "ko", "KR", "spot", note="kind=meme")
    c.last_seen = datetime.now(timezone.utc) - timedelta(days=30)
    con.execute("UPDATE candidates SET json=? WHERE candidate_id=?", (c.model_dump_json(), c.candidate_id))
    con.commit()
    assert ds.expire_candidates(con) == 1
    assert [x.text for x in ds.candidates(con, "expired", 10)] == ["한번본말"]
    again = ds.upsert_candidate(con, "한번본말", "ko", "KR", "spot", note="kind=meme")
    assert again.status == "new"


def test_research_does_not_override_human_approval(monkeypatch):
    """사람이 승인한 뜻은 자동 재조사가 덮거나 강등하지 않는다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import research
    from trend_agents.schemas import MeaningDraft, Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = Term(term_id="t1", canonical="사람확인말", lang="ko", status="verified", category="slang", first_seen=now, last_seen=now)
    ds.upsert_term(con, t)
    ds.add_meaning(con, "t1", MeaningDraft(definition="사람이 확인한 뜻입니다.", origin="unknown", nuance="없음",
                                           generations=["20s"], regions=["KR"], self_confidence=0.9), "verified_human", [])
    monkeypatch.setattr(research, "research_term", lambda *a, **k: (_ for _ in ()).throw(AssertionError("불리면 안 됨")))
    assert research.research_one(con, t) == ("verified_human", [])
    assert ds.current_meaning(con, "t1").verification == "verified_human"


def test_risk_rules_quote_evidence_and_ignore_single_noise(monkeypatch):
    """리스크 수준은 규칙이 정한다. 위험 근거 1건은 잡음, 3건이면 사용 자제, 근거가 모자라면 판단 보류."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import risk
    from trend_agents.schemas import Evidence, Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = Term(term_id="t1", canonical="테스트밈", lang="ko", status="verified", first_seen=now, last_seen=now)
    ds.upsert_term(con, t)
    evs = [Evidence(evidence_id=f"e{i}", kind="community", url=f"u{i}", title="t", source_domain="bsky.app",
                    observed_at=now, excerpt=f"@a.bsky.social · 0♥ — 테스트밈 문장 {i}") for i in range(6)]
    ds.add_evidences(con, "t1", evs)

    ds.set_evidence_labels(con, "t1", [("e0", "neutral", "politics")] + [(f"e{i}", "positive", "none") for i in range(1, 6)], "test")
    assert risk.judge(con, t)[0] == "none"                 # 위험 근거 1건은 잡음

    ds.set_evidence_labels(con, "t1", [(f"e{i}", "neutral", "hate") for i in range(3)], "test")
    level, reasons = risk.judge(con, t)
    assert level == "caution" and not any("@a.bsky" in r for r in reasons)   # 한 곳에 몰리면 주의까지, 머리말은 뗀다

    ds.add_evidences(con, "t1", [Evidence(evidence_id="n1", kind="news", url="n1", title="t", source_domain="news.example",
                                          observed_at=now, excerpt="테스트밈 기사")])
    ds.set_evidence_labels(con, "t1", [("n1", "negative", "hate")], "test")
    assert risk.judge(con, t)[0] == "avoid"                # 출처 둘 이상에서 3건 이상이면 사용 자제

    ds.set_evidence_labels(con, "t1", [(f"e{i}", "offtopic", "none") for i in range(6)] + [("n1", "offtopic", "none")], "test")
    level, reasons = risk.judge(con, t)
    assert level is None and "딴 이야기 7건" in reasons[0]   # 글자만 같은 딴 이야기는 판정에서 뺀다

    t2 = Term(term_id="t2", canonical="근거적은말", lang="ko", status="verified", first_seen=now, last_seen=now)
    assert risk.judge(con, t2)[0] is None                  # 근거가 모자라면 판단 보류


def test_human_risk_level_overrides_rules_until_cleared():
    """검수자가 정한 리스크 수준이 규칙보다 우선하고, 지우면 규칙 판정으로 돌아간다 (Plan 03 5번)."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import risk
    from trend_agents.schemas import Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = Term(term_id="t1", canonical="보통밈", lang="ko", status="verified", first_seen=now, last_seen=now)
    ds.upsert_term(con, t)

    t.risk_human = "avoid"
    risk.apply(con, t)
    got = ds.get_term(con, "t1")
    assert got.risk_level == "avoid" and got.risk_reasons[0] == "검수자가 정한 수준"

    risk.apply(con, got)                                   # 파이프라인이 다시 돌아도 유지된다
    assert ds.get_term(con, "t1").risk_level == "avoid"

    got.risk_human = None
    risk.apply(con, got)
    assert ds.get_term(con, "t1").risk_level is None      # 근거가 없으니 규칙은 판단 보류


def test_dashboard_regions_lists_and_search_follow_rules():
    """대시보드 지역·목록은 규칙이다 (Plan 04). 조사가 정한 나라 → 없으면 표제어 언어의 나라 → 목표 지역 밖 영어는 '전 세계'.
    사용 자제는 뜨는·식는 목록에 넣지 않고, 검색 순위는 고른 지역 것만 보인다."""
    from trend_agents.pipeline import dashboard

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)

    def term(tid, name, lang, lifecycle="steady", usage=(), **kw):
        t = Term(term_id=tid, canonical=name, lang=lang, status="verified", lifecycle=lifecycle, first_seen=now, last_seen=now, **kw)
        ds.upsert_term(con, t)
        ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance="y", generations=["20s"], regions=list(usage),
                                              self_confidence=0.9), "verified_auto", [])
        if usage:
            ds.set_usage(con, tid, [("20s", r, now.isoformat(), 1.0) for r in usage])

    term("kr", "럭키비키", "ko", "rising", ("KR",), diffusion="underground")
    term("jp", "推し活", "ja", "declining")                         # 나라 없음 → 일본어라 JP
    term("us", "aura farming", "en", usage=("US",))                 # 목표 지역 밖 영어 → 전 세계
    term("bad", "나쁜말", "ko", usage=("KR",), risk_level="avoid")
    term("de", "Ehrenmann", "de", usage=("DE",))                    # 목표 지역 밖 → 카드 없음
    ds.upsert_trend_queries(con, [TrendQuery(term="럭키비키 뜻", region="KR", rank=3, source="bq_top", date=date.today()),
                                  TrendQuery(term="aura farming kid", region="ID", rank=7, source="rss_now", date=date.today())])
    dashboard.run(con)

    b = dashboard.board(con)
    assert b.regions == dashboard.REGIONS_FOCUS
    assert [c.term_id for c in b.rising] == ["kr"] and [c.term_id for c in b.fading] == ["jp"] and [c.term_id for c in b.caution] == ["bad"]
    assert b.rising[0].search[0].query == "럭키비키 뜻"
    assert b.counts["KR"] == 2 and b.counts["JP"] == 1 and b.counts["GLOBAL"] == 1 and "DE" not in b.counts

    g = dashboard.board(con, ["GLOBAL"])
    assert [c.term_id for c in g.rising] == ["us"] and g.rising[0].search == []   # 인도네시아 순위는 인도네시아를 고를 때만
    assert dashboard.board(con, ["ID", "GLOBAL"]).rising[0].search[0].region == "ID"
    assert dashboard.board(con, ["XX"]).regions == dashboard.REGIONS_FOCUS          # 모르는 지역은 무시하고 기본값

    t = ds.get_term(con, "kr")
    t.risk_level = "avoid"
    ds.upsert_term(con, t)
    dashboard.refresh_card(con, "kr")                                             # 검수 결정이 다음 파이프라인을 기다리지 않는다
    assert {c.term_id for c in dashboard.board(con).caution} == {"bad", "kr"}
    assert dashboard.card(con, "de").regions == []                                # 사전 화면용으로는 지역 밖도 만든다
