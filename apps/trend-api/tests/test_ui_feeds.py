"""'최근 변화'(/updates)와 나라 화면(/countries) — 화면 개편 2차(feeds) 검토에서 고친 규칙."""
from datetime import date, datetime, timezone

from trend_agents.schemas import MeaningDraft, Term, TrendExplanation
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _draft(definition: str) -> MeaningDraft:
    return MeaningDraft(definition=definition, origin="x", nuance="y", generations=["20s"], regions=["KR"], self_confidence=0.9)


def _seed():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name in (("a", "럭키비키"), ("b", "원영적 사고"), ("c", "자만추")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.add_meaning(con, "a", _draft("처음 뜻"), "verified_auto", [])
    ds.add_meaning(con, "a", _draft("바뀐 뜻"), "verified_auto", [])       # 같은 날 확인 → 뜻 바뀜: 한 행만
    ds.add_meaning(con, "b", _draft("뜻"), "verified_auto", [])
    ds.add_meaning(con, "c", _draft("제안"), "unverified", [])               # 확인 전 제안은 작업 기록
    for i in range(3):
        con.execute("INSERT INTO research_log VALUES (?,?,?,?,?,?,?)", ("b", now.isoformat(), "m", "", "[]", "verified_auto", "[]"))
    con.commit()
    ds.save_explanation(con, TrendExplanation(term="東北季風", region="TW", date=date.today(), why_now="북동 계절풍 예보로 검색이 늘었습니다.",
                                              why_now_en="Monsoon forecast.", why_now_ja="北東季節風の予報で検索が増えた。", trigger="event", self_confidence=0.8))
    ds.save_explanation(con, TrendExplanation(term="銀行", region="JP", date=date.today(), why_now="", why_now_en="", trigger="unknown",
                                              self_confidence=0.2))
    return con


def test_user_feed_keeps_only_user_kinds_one_row_per_term_per_day():
    con = _seed()
    feed = ds.update_feed(con, hours=1)
    kinds = [(r["kind"], r["label"]) for r in feed["items"]]
    assert {k for k, _ in kinds} <= set(ds.USER_UPDATE_KINDS)
    assert [lab for _, lab in kinds].count("럭키비키") == 1 and ("meaning_changed", "럭키비키") in kinds
    assert ("verified", "원영적 사고") in kinds and not any(lab == "자만추" for _, lab in kinds)
    changed = next(r for r in feed["items"] if r["kind"] == "meaning_changed")
    assert changed["previous"] == "처음 뜻"
    spike = next(r for r in feed["items"] if r["label"] == "東北季風")
    assert spike["region"] == "TW" and spike["reason"]["ko"].startswith("북동") and spike["reason"]["ja"].startswith("北東")
    assert next(r for r in feed["items"] if r["label"] == "銀行")["reason"] is None   # 원인 미확인은 이유를 지어내지 않는다
    assert feed["counts"] == {"verified": 1, "meaning_changed": 1, "spike": 2} and feed["total"] == 4


def test_counts_are_totals_before_the_limit_and_internal_kinds_stay_reachable():
    con = _seed()
    feed = ds.update_feed(con, hours=1, limit=1)
    assert len(feed["items"]) == 1 and feed["total"] == 4 and sum(feed["counts"].values()) == 4
    # 관리 화면용: 작업 기록은 그대로(하루 한 행으로 줄이지 않는다)
    work = ds.update_feed(con, hours=1, kinds=ds.UPDATE_KINDS)
    assert work["counts"]["recheck"] == 3 and work["counts"]["candidate_meaning"] == 1 and work["counts"]["new_term"] == 3
    # 기존 호출(kinds 없이)은 모든 종류 그대로
    assert {r["kind"] for r in ds.recent_updates(con, hours=1)} >= {"new_term", "recheck", "candidate_meaning"}


def test_updates_api_defaults_to_user_kinds(monkeypatch):
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    monkeypatch.setattr(api, "_con", _seed())
    c = TestClient(api.app)
    body = c.get("/updates?hours=48").json()
    assert set(body) == {"items", "counts", "total"} and set(body["counts"]) == set(ds.USER_UPDATE_KINDS)
    assert "recheck" in c.get("/updates?kinds=all").json()["counts"]
    assert set(c.get("/updates?kinds=spike,bogus").json()["counts"]) == {"spike"}


def test_country_page_lists_confirmed_terms_only():
    from trend_agents.pipeline import views

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, status in (("v", "verified"), ("n", "needs_review")):
        ds.upsert_term(con, Term(term_id=tid, canonical=tid * 3, lang="ko", status=status, first_seen=now, last_seen=now))
        from trend_agents.schemas import MeaningDraft

        ds.add_meaning(con, tid, MeaningDraft(definition="confirmed or proposed definition", origin="origin", nuance="nuance",
                                             generations=["20s"], regions=["KR"], self_confidence=0.9),
                       "verified_auto" if status == "verified" else "unverified", [])
        ds.set_usage(con, tid, [("20s", "KR", now.isoformat(), 1.0)])
    assert [r.term.term_id for r in views.country_page(con, "KR").terms] == ["v"]
    assert views.country_page(con, "KR", brief=True).terms == []      # 웹 나라 화면은 용어 목록을 받지 않는다(13MB 였다)


def test_japanese_spike_reason_is_kept_only_when_written_in_japanese():
    """급증 이유 일본어판(10-14): 가나가 있고 한글은 검색어·한국어 이유·인물 이름에 있는 것만. 아니면 비워 화면이 영어판을 쓴다."""
    from trend_agents.pipeline.spikes import ja_or_empty

    assert ja_or_empty("오살힘がファンの間で広まった。", "오살힘", "팬들이 쓴다", []) == "오살힘がファンの間で広まった。"
    assert ja_or_empty("ビ디오が話題になった", "x", "영상이 화제", []) == ""
    assert ja_or_empty("Fans use it", "x", "팬들이 쓴다", []) == ""


def test_user_feed_drops_terms_no_longer_in_the_dictionary():
    """실렸다가 검수로 내려간 말은 이용자 피드에 없다 — 링크가 404 였다(フェムテック, 10-14)."""
    con = _seed()
    t = ds.get_term(con, "b")
    t.status = "needs_review"
    ds.upsert_term(con, t, human=True)
    labels = [r["label"] for r in ds.update_feed(con, hours=1)["items"]]
    assert "원영적 사고" not in labels and "럭키비키" in labels


def test_public_entry_skips_evidence_notes_and_blanks_note_only_origin():
    """뜻 대신 근거 메모인 자동 확인 뜻은 싣지 않고, '근거 없음' 뿐인 유래는 공개 화면에서 비운다(10-14 점검)."""
    from trend_agents.pipeline import views
    from trend_agents.verification import is_public_entry, note_only

    con = _seed()
    ds.add_meaning(con, "b", _draft("근거에 밈 사용법에 대한 구체적인 설명이 없음."), "verified_auto", [])
    assert not is_public_entry(ds.get_term(con, "b"), ds.current_meaning(con, "b"))
    ds.add_meaning(con, "b", _draft("근거에 밈 사용법에 대한 구체적인 설명이 없음."), "verified_human", [])
    assert is_public_entry(ds.get_term(con, "b"), ds.current_meaning(con, "b"))         # 사람이 확인한 뜻은 그대로

    assert note_only("근거에 명시되지 않음") and note_only("unknown") and not note_only("2020년 방송에서 유래했다. 정확한 시기는 알 수 없다.")
    d = _draft("좋은 일로 끝난다고 여기는 태도.")
    d.origin = "근거 없음"
    ds.add_meaning(con, "a", d, "verified_auto", [])
    rec = views.term_record(con, ds.get_term(con, "a"), public=True)
    assert rec.meanings[-1].origin == "" and views.term_record(con, ds.get_term(con, "a")).meanings[-1].origin == "근거 없음"


def test_rechecking_an_auto_verified_meaning_keeps_it_unless_it_is_weak():
    """재조사가 같은 뜻을 말만 바꿔 새 판을 만들며 번역을 지웠다(권루트 19판, 10-14) — 지금 뜻이 약할 때만 바꾼다."""
    from trend_agents.pipeline.research import settled

    con = _seed()
    cur = ds.add_meaning(con, "b", _draft("특정 분야에 진심을 다해 임하는 것을 이르는 유행어."), "verified_auto", [])
    assert settled(con, "b", cur, _draft("어떤 일에 진지하게 몰두하는 태도를 이르는 말."), "verified_auto")
    assert not settled(con, "b", cur, _draft("다른 뜻"), "needs_review")
    ds.add_meaning(con, "b", _draft("근거에 밈 사용법에 대한 구체적인 설명이 없음."), "verified_auto", [])
    assert not settled(con, "b", ds.current_meaning(con, "b"), _draft("어떤 일에 몰두하는 태도를 이르는 말."), "verified_auto")


def test_slurs_inside_hashtags_and_names_are_unsafe():
    from trend_agents.pipeline.match import unsafe

    assert unsafe("#NiggerNavy") and unsafe("Noah Knigga")
    assert not unsafe("niggardly") and not unsafe("snigger") and not unsafe("Nigeria")
