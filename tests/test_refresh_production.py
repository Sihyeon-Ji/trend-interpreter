"""Plan 19 갱신 도구 – 새 snapshot DB 위에 운영 DB의 사람 결정과 사용자 자료를 덮어 얹는다."""
from datetime import datetime, timedelta, timezone

import pytest

from scripts import refresh_production as refresh
from trend_agents.schemas import Evidence, MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

NOW = datetime.now(timezone.utc)


def draft(definition):
    return MeaningDraft(definition=definition, origin="커뮤니티", nuance="가볍게", generations=["10s"], regions=["KR"], self_confidence=0.8)


def seed_term(con, tid, definition, verification="verified_auto"):
    ds.upsert_term(con, Term(term_id=tid, canonical=tid, lang="ko", status="verified", first_seen=NOW, last_seen=NOW))
    ds.add_meaning(con, tid, draft(definition), verification, [])
    con.commit()


def evidence(tid, n):
    return Evidence(evidence_id=f"{tid}-{n}", kind="news", url=f"https://news.example/{tid}/{n}", title=f"{tid} {n}",
                    source_domain="news.example", observed_at=NOW - timedelta(days=n), excerpt=f"{tid} 이 쓰였다")


@pytest.fixture
def dbs():
    """운영(source)과 새 snapshot(target). 둘 다 같은 자동 표제어를 갖고, 운영에만 사람의 결정이 있다."""
    source, target = db.connect(":memory:"), db.connect(":memory:")
    for con in (source, target):
        for tid in ("approved", "risky", "rejected", "untouched"):
            seed_term(con, tid, f"{tid} 자동 뜻")
    # 운영에서만 생긴 일
    m = ds.current_meaning(source, "approved")
    ds.set_verification(source, m.meaning_id, "verified_human", "ejchoi")
    ds.add_evidences(source, "approved", [evidence("approved", 1)])
    t = ds.get_term(source, "risky")
    t.risk_human, t.risk_decided_by, t.risk_decided_at = "avoid", "ejchoi", NOW
    ds.upsert_term(source, t, human=True)
    ds.queue_review(source, "rejected", draft("rejected 제안"), ["근거 부족"], 1)
    ds.decide_review(source, "rejected", "reject", "ejchoi")
    source.execute("INSERT INTO gemini_calls VALUES (?,?)", ("usd:2026-10", 1_234_567))
    source.execute("INSERT INTO reader_prefs VALUES (?,?,?)", ("reviewer", '{"gen": "20s"}', NOW.isoformat()))
    source.execute("INSERT INTO lookups VALUES (?,?,?,?,?,?)", ("k", "모르는 말", "ko", 2, NOW.isoformat(), NOW.isoformat()))
    source.commit()
    # 새 snapshot 은 수집 PC 의 자동 자료가 더 새롭다
    seed_term(target, "approved", "approved 수집 PC 의 새 자동 뜻")
    ds.add_evidences(target, "approved", [evidence("approved", 2)])
    seed_term(target, "untouched", "untouched 수집 PC 의 새 자동 뜻")
    seed_term(target, "brand-new", "새로 들어온 말")
    target.execute("INSERT INTO gemini_calls VALUES (?,?)", ("usd:2026-10", 5))
    target.commit()
    return source, target


def definitions(con, tid):
    return [m.definition for m in ds.list_meanings(con, tid)]


def test_human_terms_cover_every_kind_of_human_decision(dbs):
    source, _ = dbs
    assert refresh.human_terms(source) == {"approved", "risky", "rejected"}


def test_overlay_keeps_human_decisions_and_new_automatic_data(dbs):
    source, target = dbs
    report = refresh.overlay(source, target)

    assert report["human_terms"] == 3
    assert definitions(target, "approved") == definitions(source, "approved")       # 사람이 승인한 판이 이긴다
    assert ds.current_meaning(target, "approved").verification == "verified_human"
    assert ds.get_term(target, "risky").risk_human == "avoid"
    assert ds.review_history(target, "rejected")[0]["decision"] == "reject"
    assert {e.evidence_id for e in ds.list_evidences(target, "approved")} == {"approved-1", "approved-2"}   # 근거는 합친다
    assert definitions(target, "untouched")[-1] == "untouched 수집 PC 의 새 자동 뜻"   # 사람이 손대지 않은 말은 새 자료
    assert ds.get_term(target, "brand-new") is not None
    assert target.execute("SELECT count FROM gemini_calls WHERE day='usd:2026-10'").fetchone()[0] == 1_234_567
    assert target.execute("SELECT COUNT(*) FROM reader_prefs").fetchone()[0] == 1
    assert target.execute("SELECT COUNT(*) FROM lookups").fetchone()[0] == 1


def test_overlay_rejudges_the_risk_it_brings_back_from_production(dbs):
    """행을 통째로 옮기면 운영의 옛 자동 리스크도 따라온다 – 10-05 전환 직전 덮어 얹기로 106개가 09-30 판정으로 돌아갔다."""
    source, target = dbs
    old = NOW - timedelta(days=5)
    ds.set_risk(source, "approved", "avoid", ["옛 규칙"], old)          # 사람이 정하지 않은 자동 판정
    source.commit()
    report = refresh.overlay(source, target)

    approved = ds.get_term(target, "approved")
    assert approved.risk_checked_at > old and approved.risk_rule_level != "avoid"   # 근거 1·2건뿐 – 지금 규칙은 판단 보류
    assert ds.get_term(target, "risky").risk_level == "avoid"         # 사람의 결정은 그대로
    assert report["risk_rejudged"] == 3


def test_overlay_is_idempotent_and_compare_passes(dbs):
    source, target = dbs
    refresh.overlay(source, target)
    first = refresh.counts(target)
    refresh.overlay(source, target)
    assert refresh.counts(target) == first
    assert refresh.compare(source, target)["differences"] == []


def test_compare_reports_a_decision_made_after_the_overlay(dbs):
    source, target = dbs
    refresh.overlay(source, target)
    m = ds.current_meaning(source, "untouched")
    ds.set_verification(source, m.meaning_id, "verified_human", "ejchoi")
    source.commit()
    assert "verified_human" in refresh.compare(source, target)["differences"]
    refresh.overlay(source, target)
    assert refresh.compare(source, target)["differences"] == []


def test_recompute_fills_lifecycle_and_rule_risk_without_models(dbs):
    source, target = dbs
    refresh.overlay(source, target)
    assert ds.get_term(target, "approved").lifecycle == "unknown"
    result = refresh.recompute(target)
    approved = ds.get_term(target, "approved")
    assert approved.lifecycle == "steady"                 # 이틀 전 쓰임 근거
    assert approved.risk_checked_at is not None
    assert ds.get_term(target, "risky").risk_level == "avoid"   # 사람의 결정은 재계산이 덮지 않는다
    assert result["recomputed"]["risk"] == 5
