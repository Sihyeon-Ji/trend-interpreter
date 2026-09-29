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
                                              why_now_en="Monsoon forecast.", trigger="event", self_confidence=0.8))
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
    assert spike["region"] == "TW" and spike["reason"]["ko"].startswith("북동")
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
        ds.set_usage(con, tid, [("20s", "KR", now.isoformat(), 1.0)])
    assert [r.term.term_id for r in views.country_page(con, "KR").terms] == ["v"]
