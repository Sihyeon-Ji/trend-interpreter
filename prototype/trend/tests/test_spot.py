"""발굴(spot) 규칙과 해석 실패 기록 — 모델 없이."""
from trend_agents.pipeline.spot import keep
from trend_agents.schemas import SpottedTerm
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import sqlite_store as db


def sp(term, kind="slang", conf=0.9, lang="ko"):
    return SpottedTerm(i=0, term=term, lang=lang, kind=kind, confidence=conf)


def test_spot_keeps_only_anchored_expressions():
    line = "오늘 점메추 실패… 결국 #편의점 ㅠ 장원영 럭키비키"
    no_existing = lambda t: None  # noqa: E731
    assert keep(sp("점메추"), line, no_existing)
    assert not keep(sp("저메추"), line, no_existing)  # 줄에 없음 = 환각
    assert not keep(sp("#편의점"), line, no_existing)  # 태그
    assert not keep(sp("장원영", kind="none"), line, no_existing)
    assert not keep(sp("럭키비키", conf=0.3), line, no_existing)
    assert not keep(sp("럭키비키"), line, lambda t: object())  # 이미 사전에 있음


def test_lookup_misses_are_counted_and_consumed():
    con = db.connect(":memory:")
    ds.log_lookup_miss(con, "이거 완전 갓생이네", "ko")
    ds.log_lookup_miss(con, "이거 완전 갓생이네", "ko")
    ds.log_lookup_miss(con, "x" * 300, "ko")  # 너무 길면 기록하지 않음
    rows = ds.pending_lookups(con)
    assert len(rows) == 1 and con.execute("SELECT count FROM lookups").fetchone()[0] == 2
    ds.delete_lookups(con, [rows[0][0]])
    assert ds.pending_lookups(con) == []
