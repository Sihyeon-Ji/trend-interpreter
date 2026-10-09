"""저장소 버전 관리와 보드 생성 — 네트워크·모델 없이 인메모리 SQLite 로."""
from datetime import date, datetime, timedelta, timezone

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
    for ago in (5, 4, 3, 1):                     # 오늘 기준 — 날짜를 박아 두면 몇 주 뒤 '잠든 말'이 되어 실패했다(10-05)
        ds.upsert_trend_queries(con, [TrendQuery(term="라부부", region="KR", rank=1, source="bq_top", date=date.today() - timedelta(days=ago))])
    r = track.run(con)["track"]
    assert r.count == 1
    weekly = ds.get_weekly(con, "t1")
    assert sum(c for _, c in weekly) == 4
    assert ds.get_term(con, "t1").lifecycle in ("emerging", "rising", "peak", "steady", "declining")


def test_track_stores_diffusion_in_the_term_and_its_column():
    """확산 단계는 용어 JSON 과 terms.diffusion 열(마이그레이션 002 — 대시보드가 이 열로 거른다)에 같은 값으로 남는다 (Plan 02)."""
    from trend_agents.schemas import Evidence

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name in (("t1", "태동밈"), ("t2", "주류밈")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.add_evidences(con, "t1", [Evidence(evidence_id="c1", kind="community", url="https://theqoo.net/1", title="태동밈 써 봄",
                                          source_domain="theqoo.net", observed_at=now, excerpt="")])
    ds.add_evidences(con, "t2", [Evidence(evidence_id=f"n{i}", kind="news", url=f"https://news.example/{i}", title=f"주류밈 기사 {i}",
                                          source_domain="news.example", observed_at=now, excerpt="") for i in range(3)])
    assert track.run(con)["track"].count == 2
    for tid, want in (("t1", "underground"), ("t2", "mainstream")):   # 커뮤니티 글만 → 태동, 뉴스 3건 + 꾸준함 → 주류
        assert ds.get_term(con, tid).diffusion == want
        assert con.execute("SELECT diffusion FROM terms WHERE term_id=?", (tid,)).fetchone()[0] == want


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
    """리스크 수준은 규칙이 정한다. 위험 근거 1건은 잡음, 3건이면 사용 자제, 근거가 모자라면 판단 보류.
    이유는 기사·쇼츠 문장만 인용하고, 커뮤니티 글은 글도 사이트 이름도 옮기지 않고 건수로만 적는다(ADR 0003)."""
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
    assert (level, reasons) == ("caution", ["커뮤니티 글에서 혐오·차별 맥락으로 쓰인 경우 3건"])   # 한 곳에 몰리면 주의까지, 건수로만

    ds.add_evidences(con, "t1", [Evidence(evidence_id="n1", kind="news", url="n1", title="t", source_domain="news.example",
                                          observed_at=now, excerpt="테스트밈 기사")])
    ds.set_evidence_labels(con, "t1", [("n1", "negative", "hate")], "test")
    level, reasons = risk.judge(con, t)
    assert (level, reasons) == ("avoid", ["위험 유형이 붙은 근거 4건", "“테스트밈 기사” (news.example)",   # 출처 둘 이상에서 3건 이상이면 사용 자제
                                          "커뮤니티 글에서 혐오·차별 맥락으로 쓰인 경우 3건"])
    assert not any("bsky" in r or "테스트밈 문장" in r for r in reasons)

    # 위험 문장이 쓰임의 절반 이하 — 그 말이 위험한 기사 제목에 들어 있었을 뿐이다(懶人包, 10-05). 사용 자제가 아니라 주의
    ds.add_evidences(con, "t1", [Evidence(evidence_id=f"m{i}", kind="news", url=f"m{i}", title="t", source_domain="news.example",
                                          observed_at=now, excerpt=f"테스트밈 소식 {i}") for i in range(4)])
    ds.set_evidence_labels(con, "t1", [(f"m{i}", "neutral", "none") for i in range(4)], "test")
    level, reasons = risk.judge(con, t)                      # 11건 중 4건
    assert level == "caution" and reasons[0] == "위험 유형이 붙은 근거 4건: “테스트밈 기사” (news.example)"

    # 부정 비율: 부정 문장이 커뮤니티 글뿐이면 그 몫만, 기사가 있으면 기사를 인용한다
    neg = Term(term_id="t3", canonical="부정밈", lang="ko", status="verified", first_seen=now, last_seen=now)
    ds.upsert_term(con, neg)
    ds.add_evidences(con, "t3", [Evidence(evidence_id=f"p{i}", kind="community", url=f"p{i}", title="t", source_domain="theqoo.net",
                                          observed_at=now, excerpt=f"부정밈 글 {i}") for i in range(5)])
    ds.set_evidence_labels(con, "t3", [(f"p{i}", "negative" if i < 2 else "neutral", "none") for i in range(5)], "test")
    assert risk.judge(con, neg) == ("caution", ["커뮤니티 글의 40%가 부정적인 맥락"])
    ds.add_evidences(con, "t3", [Evidence(evidence_id="pn", kind="news", url="pn", title="t", source_domain="news.example",
                                          observed_at=now, excerpt="부정밈 논란 기사")])
    ds.set_evidence_labels(con, "t3", [("pn", "negative", "none")], "test")
    assert risk.judge(con, neg) == ("caution", ["부정적으로 쓰인 근거가 50% — 예: “부정밈 논란 기사” (news.example)"])

    ds.set_evidence_labels(con, "t1", [(f"e{i}", "offtopic", "none") for i in range(6)] + [("n1", "offtopic", "none")], "test")
    level, reasons = risk.judge(con, t)
    assert level is None and "딴 이야기 7건" in reasons[0]   # 글자만 같은 딴 이야기는 판정에서 뺀다

    t2 = Term(term_id="t2", canonical="근거적은말", lang="ko", status="verified", first_seen=now, last_seen=now)
    assert risk.judge(con, t2)[0] is None                  # 근거가 모자라면 판단 보류


def test_risk_avoids_profane_headwords_and_videos_with_a_bad_origin():
    """사용 자제 규칙 둘은 근거 문장 분류 없이도 선다(Plan 03 규칙표): 표제어 자체가 욕설·성적 표현, 영상 해석이 비하·혐오 기원을 지적(risk_flags).
    정치 같은 다른 깃발이나 다른 밈의 영상은 이 규칙에 걸리지 않는다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import risk
    from trend_agents.schemas import MemeRef, ShortsInterpretation, Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)

    def term(tid, name):
        t = Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now)
        ds.upsert_term(con, t)
        return t

    def video(vid, name, flags):
        return ShortsInterpretation(url=f"https://www.youtube.com/shorts/{vid}", language="ko", summary="s", why_viral="w", explain_for_outsider="e",
                                    memes=[MemeRef(name=name, kind="meme", origin_hypothesis="unknown", confidence=0.8)], target_generation=["10s"],
                                    risk_flags=flags)

    assert risk.judge(con, term("t1", "아헤가오")) == ("avoid", ["표제어 자체가 욕설·성적 표현이다."])
    db.save_interpretations(con, [video("v1", "원숭이 춤", ["비하 기원", "정치"]), video("v2", "정치밈", ["정치"]), video("v3", "다른밈", ["혐오 기원"])], "test")
    assert risk.judge(con, term("t2", "원숭이춤")) == ("avoid", ["영상 해석이 지적한 기원: 비하 기원"])   # 띄어쓰기만 다른 이름도 같은 밈
    assert risk.judge(con, term("t3", "정치밈"))[0] is None                                           # 정치 깃발만 — 근거가 없어 판단 보류


def test_human_risk_level_overrides_rules_until_cleared():
    """검수자가 정한 리스크 수준이 규칙보다 우선하고, 지우면 규칙 판정으로 돌아간다 (Plan 03 5번)."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import risk
    from trend_agents.schemas import Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = Term(term_id="t1", canonical="보통밈", lang="ko", status="verified", first_seen=now, last_seen=now)
    ds.upsert_term(con, t)

    stale = ds.get_term(con, "t1")                          # 파이프라인이 시작할 때 읽어 둔 사본

    t.risk_human = "avoid"                                  # 검수 화면(POST /review/{id}/risk)의 길
    risk.apply(con, t, human=True)
    got = ds.get_term(con, "t1")
    assert got.risk_level == "avoid" and got.risk_reasons[0] == "검수자가 정한 수준"
    assert got.risk_rule_level is None                      # 규칙의 판정은 따로 남는다(근거가 없으니 판단 보류)

    risk.apply(con, stale)                                  # 몇 분 뒤 파이프라인이 옛 사본으로 다시 매겨도 사람의 결정이 남는다
    assert ds.get_term(con, "t1").risk_level == "avoid" and ds.get_term(con, "t1").risk_human == "avoid"
    ds.upsert_term(con, stale)                              # 다른 단계(track 등)가 옛 사본을 통째로 저장해도
    assert ds.get_term(con, "t1").risk_human == "avoid"

    got.risk_human = None
    risk.apply(con, got, human=True)
    assert ds.get_term(con, "t1").risk_level is None      # 근거가 없으니 규칙은 판단 보류


def test_automation_never_unretires_a_term():
    """제외(retired)는 사람만 한다 — 옛 사본을 저장하는 자동 단계가 제외한 말을 되살리지 않는다."""
    from datetime import datetime, timezone

    from trend_agents.schemas import Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = Term(term_id="t1", canonical="내린말", lang="ko", status="verified", first_seen=now, last_seen=now)
    ds.upsert_term(con, t)
    stale = ds.get_term(con, "t1")
    t.status = "retired"
    ds.upsert_term(con, t, human=True)
    ds.upsert_term(con, stale)                               # 자동 단계의 옛 사본
    assert ds.get_term(con, "t1").status == "retired"
    stale.status = "verified"
    ds.upsert_term(con, stale, human=True)                   # 사람이 다시 승인하면 되살아난다
    assert ds.get_term(con, "t1").status == "verified"


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
    assert [c.term_id for c in b.rising] == ["kr"] and [c.term_id for c in b.fading] == ["jp"] and b.caution == []   # 사용 자제(bad)는 공개 목록에서 뺀다(10-09)
    assert b.rising[0].search[0].query == "럭키비키 뜻"
    assert b.counts["KR"] == 1 and b.counts["JP"] == 1 and b.counts["GLOBAL"] == 1 and "DE" not in b.counts

    g = dashboard.board(con, ["GLOBAL"])
    assert [c.term_id for c in g.rising] == ["us"] and g.rising[0].search == []   # 인도네시아 순위는 인도네시아를 고를 때만
    assert dashboard.board(con, ["ID", "GLOBAL"]).rising[0].search[0].region == "ID"
    assert dashboard.board(con, ["XX"]).regions == dashboard.REGIONS_FOCUS          # 모르는 지역은 무시하고 기본값

    ds.set_risk(con, "kr", "caution", ["위험 유형이 붙은 근거 3건"], now)   # 리스크 필드는 리스크 단계·검수자 길로만 바뀐다
    dashboard.refresh_card(con, "kr")                                               # 검수 결정이 다음 파이프라인을 기다리지 않는다
    assert {c.term_id for c in dashboard.board(con).caution} == {"kr"}
    assert dashboard.card(con, "de").regions == []                                # 사전 화면용으로는 지역 밖도 만든다


def test_board_survives_namuwiki_trending_rows():
    """나무위키 실시간 검색어(namu_rank)가 들어 있어도 보드가 만들어진다 — 출처표에 없어 보드 전체가 KeyError 로 멈췄다(2026-09-28)."""
    from trend_agents.pipeline import board

    con = db.connect(":memory:")
    ds.upsert_trend_queries(con, [TrendQuery(term="럭키비키", region="KR", rank=1, source="namu_rank", date=date.today()),
                                  TrendQuery(term="럭키비키", region="KR", rank=5, source="bq_top", date=date.today()),
                                  TrendQuery(term="오살힘", region="KR", rank=2, source="namu_rank", date=date.today())])
    for term in ("럭키비키", "오살힘"):
        con.execute("INSERT INTO trend_class VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"{term}|KR", term, "KR", "slang_meme", "slang", 1, "ko", date.today().isoformat(), "test"))
    con.commit()
    r = board.run(con)["board"]
    assert r.status == "ok" and r.count >= 1


def test_risk_rules_nuance_fading_and_selection(monkeypatch):
    """식상은 리스크가 아니고, 사전 뜻풀이의 주의점은 근거가 모자라도 주의다. 분류는 남은 문장이 있는 용어부터 한다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import risk
    from trend_agents.schemas import Evidence, Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)

    def term(tid, name, nuance, diffusion=None):
        t = Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now, diffusion=diffusion)
        ds.upsert_term(con, t)
        ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance=nuance, generations=["20s"], regions=["KR"],
                                              self_confidence=0.9), "verified_auto", [])
        return ds.get_term(con, tid)

    stale = term("old", "옛말", "친근하게 쓴다", diffusion="fading")
    ds.add_evidences(con, "old", [Evidence(evidence_id=f"o{i}", kind="community", url=f"u{i}", title="t", source_domain="theqoo.net",
                                           observed_at=now, excerpt=f"옛말 {i}") for i in range(5)])
    ds.set_evidence_labels(con, "old", [(f"o{i}", "neutral", "none") for i in range(5)], "test")
    assert risk.judge(con, stale)[0] == "none"                                  # 식상 하나로는 주의가 아니다
    rude = term("rude", "샤갈", "순화형이지만 뿌리는 욕설이다. 어른 앞에서는 욕으로 들린다")
    level, reasons = risk.judge(con, rude)
    assert level == "caution" and "욕설" in reasons[0]                          # 근거 0건이어도 사전이 이미 경고했다
    assert risk.judge(con, term("fine", "착한말", "비하하는 뜻은 없다. 자기 비하 농담으로도 쓴다"))[0] is None   # 부정·자조는 경고가 아니다

    # 분류할 문장이 남은 용어만 고른다 — 다 분류된 'old' 가 칸을 차지하지 않는다
    ds.add_evidences(con, "rude", [Evidence(evidence_id="r1", kind="community", url="r1", title="t", source_domain="theqoo.net",
                                            observed_at=now, excerpt="샤갈 진짜")])
    seen = []
    monkeypatch.setattr(risk, "classify", lambda con, t: seen.append(t.term_id) or 0)
    risk.run(con)
    assert seen == ["rude"]
    assert ds.get_term(con, "rude").risk_rule_level == "caution"


def test_track_counts_raw_sources_only_and_by_region():
    """주간 언급·마지막 본 때는 원본(뉴스·쇼츠·검색어)만. 조사 근거를 더하면 '최근 조사한 것' 이 '요즘 뜨는 것' 이 됐다(2026-09-29).
    원본은 나라별로도 센다 — 대시보드가 고른 지역의 수치만 보인다."""
    from datetime import datetime, timedelta, timezone

    from trend_agents.schemas import Evidence, NewsItem, Term

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    long_ago = now - timedelta(days=300)
    ds.upsert_term(con, Term(term_id="t1", canonical="럭키비키", lang="ko", status="verified", first_seen=long_ago, last_seen=long_ago))
    ds.add_evidences(con, "t1", [Evidence(evidence_id=f"e{i}", kind="community", url=f"c{i}", title="럭키비키", source_domain="theqoo.net",
                                          observed_at=now, excerpt="럭키비키") for i in range(9)])            # 오늘 조사한 근거 9건
    from trend_agents.storage import store
    store.upsert_news(con, [NewsItem(title="럭키비키 신드롬", link="n1", source="x", published_at=now, region="KR", query=None),
                            NewsItem(title="럭키비키 in Japan", link="n2", source="x", published_at=now, region="JP", query=None)])
    track.run(con)
    weekly = ds.get_weekly(con, "t1")
    assert weekly[-1][1] == 2                                                   # 원본 2건만 (근거 9건은 세지 않는다)
    by_region = ds.get_weekly_region(con, "t1")
    assert sum(by_region["KR"].values()) == 1 and sum(by_region["JP"].values()) == 1


def test_gate_closures_are_not_public_review_decisions():
    """게이트가 스스로 닫은 것은 공개 '오늘의 변화' 의 검수 결정이 아니다."""
    con = db.connect(":memory:")
    ds.queue_review(con, "t1", draft("뜻", None), ["표현이 아니라 상품"], 1)
    ds.decide_review(con, "t1", "auto_rejected", "gate")
    ds.queue_review(con, "t2", draft("뜻", None), ["근거 부족"], 1)
    ds.decide_review(con, "t2", "approve", "kim")
    for tid, name in (("t1", "안녕하세요"), ("t2", "럭키비키")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified"))
    reviewed = [u for u in ds.recent_updates(con, hours=1) if u["kind"] == "reviewed"]
    assert [u["term_id"] for u in reviewed] == ["t2"]


def test_track_does_not_trust_mentions_of_a_word_mostly_used_in_another_sense():
    """'Again'·'Robert' 처럼 흔한 낱말은 뉴스 제목·검색어 언급이 일반어로 부푼다. 근거 문장 분류에서 딴 이야기가 더 많으면
    언급의 모양 대신 그 뜻으로 쓰인 근거의 마지막 때로 본다(10-06, Plan 02). 딴 이야기가 적으면 지금처럼 언급으로 본다."""
    from trend_agents.schemas import Evidence

    today = date.today()
    con = db.connect(":memory:")
    for tid, word, on_topic in (("t1", "Again", False), ("t2", "Agane", True)):
        ds.upsert_term(con, Term(term_id=tid, canonical=word, lang="en", status="verified", first_seen=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        for ago in (20, 13, 6, 1):
            ds.upsert_trend_queries(con, [TrendQuery(term=word, region="US", rank=1, source="bq_top", date=today - timedelta(days=ago))])
        old = datetime.now(timezone.utc) - timedelta(days=120)
        evs = [Evidence(evidence_id=f"{tid}e{i}", kind="news", url=f"https://news.example.com/{tid}/{i}", title=f"{word} story {i}",
                        source_domain="news.example.com", observed_at=old if i == 0 else datetime.now(timezone.utc) - timedelta(days=i),
                        excerpt=f"{word} story {i}") for i in range(4)]
        ds.add_evidences(con, tid, evs)
        ds.set_evidence_labels(con, tid, [(f"{tid}e0", "positive", "none")] +
                               [(f"{tid}e{i}", "neutral" if on_topic else "offtopic", "none") for i in (1, 2, 3)], "local:gemma4:12b")
    # 딴 이야기가 더 많고 그 뜻의 근거가 셋 이상이며 1/3 이상: 그 뜻 근거 셋(120일 전) — 마지막 때로 '잠잠함'
    ds.upsert_term(con, Term(term_id="t3", canonical="Agian", lang="en", status="verified", first_seen=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    for ago in (20, 13, 6, 1):
        ds.upsert_trend_queries(con, [TrendQuery(term="Agian", region="US", rank=1, source="bq_top", date=today - timedelta(days=ago))])
    ds.add_evidences(con, "t3", [Evidence(evidence_id=f"t3e{i}", kind="news", url=f"https://news.example.com/t3/{i}", title=f"Agian story {i}",
                                          source_domain="news.example.com", observed_at=datetime.now(timezone.utc) - timedelta(days=120 if i < 3 else i),
                                          excerpt=f"Agian story {i}") for i in range(7)])
    ds.set_evidence_labels(con, "t3", [(f"t3e{i}", "neutral" if i < 3 else "offtopic", "none") for i in range(7)], "local:gemma4:12b")
    track.run(con)
    mixed, clean, older = ds.get_term(con, "t1"), ds.get_term(con, "t2"), ds.get_term(con, "t3")
    assert mixed.lifecycle == "unknown"                       # 그 뜻으로 쓰인 근거가 하나뿐 — 보류
    assert mixed.last_seen is None or (datetime.now(timezone.utc) - mixed.last_seen).days >= 119   # 일반어 제목은 '마지막으로 쓰인 때' 가 아니다
    assert clean.lifecycle in ("emerging", "rising", "peak", "steady")
    assert older.lifecycle == "dormant" and (datetime.now(timezone.utc) - older.last_seen).days >= 119
