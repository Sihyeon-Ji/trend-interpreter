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
