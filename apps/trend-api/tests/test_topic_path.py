"""지도의 이동 경로 — 날짜를 대는 출처가 있는 나라끼리만 긋는다. 네트워크·모델 없이 인메모리 SQLite 로.

전에는 나라를 관심도(heat)로만 정렬하고 맨 앞 나라를 '처음 나온 곳'으로 그렸다. 그런데 조사 단계가 비중을 균등하게,
날짜를 모든 나라에 똑같이 넣어서 순서가 사실상 나라 코드의 알파벳순이었다. 이 테스트들은 그 순서가 경로로 둔갑하지 않게 막는다.
"""
from datetime import datetime, timezone

from trend_agents.pipeline import board
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

FIRST = datetime(2025, 9, 14, tzinfo=timezone.utc)  # 관측을 시작한 날처럼, 모든 나라에 똑같이 찍힌 날짜


def verified_term(con, regions):
    """조사 단계가 실제로 남기는 모양 그대로: 모든 나라에 같은 날짜, 같은 비중."""
    t = ds.upsert_term(con, Term(term_id="t_tung", canonical="Tung Tung Tung Sahur", status="verified", first_seen=FIRST))
    draft = MeaningDraft(definition="라마단 새벽 식사를 깨우는 북소리에서 나온 캐릭터 밈", expansion="", origin="x", nuance="y",
                         generations=["10s"], regions=regions, self_confidence=0.9)
    ds.add_meaning(con, t.term_id, draft, "verified_auto", [])
    share = round(1 / len(regions), 3)
    ds.set_usage(con, t.term_id, [("10s", r, FIRST.isoformat(), share) for r in regions])
    return t


def topic_of(con):
    (topic,) = board.build(con).topics
    return topic


def test_no_dated_source_means_no_origin():
    con = db.connect(":memory:")
    verified_term(con, ["KR", "JP", "ID"])
    variants = topic_of(con).variants
    # 날짜를 대는 출처가 하나도 없다 → 어느 나라도 경로의 점이 아니다
    assert [v.dated for v in variants] == [False, False, False]
    # 알파벳 첫 나라(ID)가 출발점이라고 주장할 근거가 없다는 것이 핵심. 순서는 남지만 dated 가 없으니 프런트가 선을 긋지 않는다
    assert all(v.since_source is None for v in variants)


def test_path_follows_dated_first_appearance():
    con = db.connect(":memory:")
    t = verified_term(con, ["KR", "JP", "ID"])
    ds.set_timeline(con, t.term_id, [
        {"region": "JP", "first_date": "2025-04-10", "source_ko": "위키백과 일본어판 · 문서 생성", "source_en": "Japanese Wikipedia · article created"},
        {"region": "ID", "first_date": "2025-02-28", "source_ko": "위키백과 인도네시아어판 · 문서 생성", "source_en": "Indonesian Wikipedia · article created"},
    ])
    variants = topic_of(con).variants
    # 날짜가 확인된 나라가 날짜순으로 앞에, 확인 안 된 나라는 뒤에
    assert [(v.region, v.dated) for v in variants] == [("ID", True), ("JP", True), ("KR", False)]
    assert variants[0].since == "2025-02-28"
    assert variants[0].since_source.en == "Indonesian Wikipedia · article created"


def test_undated_region_keeps_reference_date_but_not_a_source():
    con = db.connect(":memory:")
    t = verified_term(con, ["KR", "ID"])
    ds.set_timeline(con, t.term_id, [{"region": "ID", "first_date": "2025-02-28", "source_ko": "a", "source_en": "a"}])
    kr = next(v for v in topic_of(con).variants if v.region == "KR")
    assert kr.dated is False and kr.since_source is None
    assert kr.since == FIRST.date().isoformat()  # 참고용 날짜는 남되 순서를 정하는 데 쓰이지 않는다


def test_timeline_region_counts_even_without_usage():
    con = db.connect(":memory:")
    t = verified_term(con, ["ID"])  # 사용 지역 하나 — 원래는 주제가 되지 않는다
    ds.set_timeline(con, t.term_id, [{"region": "BR", "first_date": "2025-05-05", "source_ko": "a", "source_en": "a"}])
    regions = {v.region for v in topic_of(con).variants}
    assert regions == {"ID", "BR"}
