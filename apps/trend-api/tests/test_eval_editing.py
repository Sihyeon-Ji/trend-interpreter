"""편집 품질 지표(scripts/eval_editing.py, Plan 06 완료 기준 6) — 규칙만 본다. 모델 없이 임시 스키마로."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trend_agents.schemas import Evidence, MeaningDraft, MeaningText, MemeFit, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

_spec = importlib.util.spec_from_file_location("eval_editing", Path(__file__).resolve().parents[1] / "scripts" / "eval_editing.py")
ee = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ee)
E4B = "local:gemma4:e4b"


def _term(con, tid, name):
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now))


def _draft(definition):
    return MeaningDraft(definition=definition, origin="x", nuance="y", generations=["20s"], regions=["KR"], self_confidence=0.9)


def test_editing_metrics_follow_the_rules():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    _term(con, "t1", "자만추")
    seed = ds.add_meaning(con, "t1", _draft("자만추는 자연스러운 만남을 추구한다는 뜻"), "verified_auto", [])   # 조사 기록이 없는 판 = 사람이 쓴 것

    # 번역: 원래 뜻에 표제어가 있으면 번역문에도 그대로 있어야 한다. 옮겨 적으면(Jamanchu) 훼손이다
    rid = ds.run_start(con, "translate")
    ds.set_translation(con, "t1", "ko", MeaningText(definition="자만추는 자연스러운 만남 추구", origin="x", nuance="y"), E4B)
    ds.set_translation(con, "t1", "en", MeaningText(definition="Jamanchu means seeking natural encounters", origin="x", nuance="y"), E4B)
    ds.run_finish(con, rid, 2, "ok")
    _term(con, "t5", "실행밖")
    ds.set_translation(con, "t5", "ko", MeaningText(definition="실행 기록 밖에서 만든 번역", origin="x", nuance="y"), E4B)

    # 국가별 해석: 현지 밈은 인용한 근거의 문장에 있어야 하고, 보이는 출처(기사)인지 커뮤니티 글에만 있는지 나눈다
    ds.add_evidences(con, "t1", [
        Evidence(evidence_id="news", kind="news", url="https://news.example/a", title="日本でも自然な出会い「자만추」", source_domain="news.example",
                 observed_at=now, excerpt=""),
        Evidence(evidence_id="post", kind="community", url="https://bsky.app/p/1", title="자만추 밈 'ジャマンチュ' ㅋㅋ", source_domain="bsky.app",
                 observed_at=now, excerpt="")])
    ds.set_topic_note(con, "t1", "JP", json.dumps({
        "local_name": "자만추", "what_changed": {"ko": "일본에서는…", "en": "In Japan…"}, "self_confidence": 0.8,
        "local_memes": [{"label": "自然な出会い"}, {"label": "ジャマンチュ"}, {"label": "없는 밈"}, {"label": "자만추"}],
        "evidence_ids": ["news", "post", "gone"]}), E4B)
    ds.set_evidence_labels(con, "t1", [("news", "positive", "none"), ("post", "offtopic", "none")], E4B)
    ds.set_fit(con, "t1", seed.meaning_id, MemeFit(feelings=["joy"], uses=["reaction"], voice="wholesome"), E4B)

    # 뜻 초안: 조사 기록이 바로 뒤에 붙은 판이 모델의 초안이다
    _term(con, "t2", "느좋")
    rejected = ds.add_meaning(con, "t2", _draft("느낌이 좋다는 뜻의 줄임말"), "unverified", [])
    ds.log_research(con, "t2", "offline:" + E4B, "", [], "unverified", [])
    ds.set_verification(con, rejected.meaning_id, "rejected", "reviewer")               # 사람이 제외
    _term(con, "t3", "갓생")
    ds.add_meaning(con, "t3", _draft("부지런하고 생산적인 삶을 뜻하는 말"), "verified_auto", [])
    ds.log_research(con, "t3", "offline:" + E4B, "", [], "verified_auto", [])        # 게이트 통과, 사람은 보지 않음
    _term(con, "t4", "킹받네")
    ds.add_meaning(con, "t4", _draft("열받는다를 강조한 말"), "unverified", [])
    ds.queue_review(con, "t4", _draft("열받는다를 강조한 말"), ["출처 부족"], 1)
    ds.log_research(con, "t4", "offline:" + E4B, "", [], "unverified", [])           # 검수 대기
    _term(con, "t6", "오운완")                                                        # 다시 조사해 기계가 새 판을 썼다 — 옛 판은 이제 실려 있지 않다
    ds.add_meaning(con, "t6", _draft("오늘 운동 완료의 줄임말"), "verified_auto", [])
    ds.log_research(con, "t6", "offline:" + E4B, "", [], "verified_auto", [])
    ds.add_meaning(con, "t6", _draft("오늘 운동을 마쳤다는 줄임말"), "verified_auto", [])
    ds.log_research(con, "t6", "offline:" + E4B, "", [], "verified_auto", [])
    ds.upsert_term(con, Term(term_id="t7", canonical="킹정", lang="ko", status="needs_review", first_seen=now, last_seen=now))
    ds.add_meaning(con, "t7", _draft("정말 인정한다는 말"), "verified_auto", [])     # 게이트는 통과했지만 사전에 오르지 않은 말
    ds.log_research(con, "t7", "offline:" + E4B, "", [], "verified_auto", [])

    m = ee.measure(con)
    tr = m["translations"][E4B]
    assert (tr["rows"], tr["ko"], tr["en"], tr["lost"]) == (3, [1, 1], [0, 1], ["자만추 (en)"])
    assert tr["timed"] == 2 and tr["seconds"] >= 0                 # 실행 기록 밖에서 만든 것은 시간을 재지 않는다

    tn = m["topic_notes"][E4B]
    assert (tn["memes"], tn["visible"], tn["community_only"], tn["unanchored"], tn["echo"]) == (4, 2, 1, 1, 1)
    assert (tn["with_ids"], tn["ids"], tn["ids_found"], tn["name_kept"]) == (1, 3, 2, 1)

    assert (m["evidence_labels"][E4B]["anchored"], m["evidence_labels"][E4B]["offtopic"]) == (2, 1)
    assert m["term_fit"][E4B]["rows"] == 1

    d = m["drafts"]["offline:" + E4B]
    assert (d["drafts"], d["gate_passed"], d["decided"], d["corrected"], d["pending"]) == (6, 4, 1, 1, 1)
    assert d["published_unreviewed"] == 2                            # 지금 사전에 실린 판만: 갓생·오운완의 새 판(옛 판·오르지 않은 말은 빼고)
    assert d["decided_by:reviewer"] == 1 and set(m["drafts"]) == {"offline:" + E4B}   # 사람이 쓴 판(시드)은 초안으로 세지 않는다

    md = ee.table(m)
    assert "ko 1/1 (100%) · en 0/1 (0%)" in md and "보이는 근거 2 · 커뮤니티 글에만 1 · 없음 1 (표제어 되풀이 1)" in md
    assert "1/1 (100%) 제외·교체 (결정 reviewer 1)" in md
    rows = ee.judge_rows(con, per_model=5, seed=1)
    assert {r["산출물"] for r in rows} == {"번역", "국가별 해석"} and all(r["근거에 없는 주장(개수)"] == "" for r in rows)
    con.close()


def test_eval_reads_postgres_read_only(monkeypatch):
    """--sqlite 가 없으면 스키마를 맞추는 connect() 가 아니라 읽기 전용 연결로 붙는다."""
    from trend_agents.storage import db as pg

    monkeypatch.setattr(pg, "connect", lambda *a, **k: pytest.fail("스키마·마이그레이션을 맞추는 연결을 쓰면 안 된다"))
    monkeypatch.setattr(pg, "connect_read_only", lambda *a, **k: "read-only")
    assert ee._connect(None) == ("read-only", "DATABASE_URL")
