"""밈으로 쓰인다는 것이 확인되지 않은 말은 둘러보는 목록에서 빼거나 뒤로 보낸다 — 규칙만, 모델 없이."""
import json
from datetime import datetime, timezone

from trend_agents.pipeline import dashboard
from trend_agents.pipeline.audit import NO_USAGE
from trend_agents.pipeline.views import KeywordCard, Tone
from trend_agents.schemas import MeaningDraft, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def test_unconfirmed_wiki_entries_leave_the_lists_but_stay_in_the_dictionary():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)

    def term(tid, name, *, catalog=True, checked=True, on=0, off=0, verification="verified_auto", lifecycle="steady"):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", lifecycle=lifecycle, first_seen=now, last_seen=now))
        m = ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                                  self_confidence=0.9), verification, [])
        ds.set_usage(con, tid, [("20s", "KR", now.isoformat(), 1.0)])
        if catalog:
            con.execute("INSERT INTO wiki_catalog VALUES (?,?,?,?,?)", (tid, "namu", name, '["인터넷 밈/한국"]', now.isoformat()))
        if checked:
            ds.set_risk(con, tid, "none" if on else None, ["규칙"], now)
        labels = [(f"{tid}-on{i}", "positive", "none") for i in range(on)] + [(f"{tid}-off{i}", "offtopic", "none") for i in range(off)]
        if labels:
            ds.set_evidence_labels(con, tid, labels, "local:test")
        return m

    term("lucky", "럭키비키", on=3)                                     # 그 뜻으로 쓰인 글이 있다
    term("tomato", "토마토")                                            # 위키 분류에서만, 점검 뒤에도 쓰인 글 0
    kim = term("kim", "김여정", on=2)                                   # 쓰인 글은 있어도 감사관이 '대상 소개뿐' 이라고 남긴 뜻
    con.execute("INSERT INTO audit_log VALUES (?,?,?,?,?,?,?)",
                ("kim", kim.meaning_id, now.isoformat(), "fix", json.dumps([NO_USAGE], ensure_ascii=False), "local:test", "flagged"))
    term("human", "오살힘", verification="verified_human")               # 사람이 확인한 뜻은 그대로
    term("pending", "갓생", checked=False, lifecycle="rising")         # 점검 전 — 빼지 않고 뒤로
    term("found", "느좋", catalog=False, checked=False)                # 위키 분류가 아닌 길(쓰임에서 발굴)로 들어온 말
    con.commit()
    dashboard.run(con)

    b = dashboard.board(con, ["KR"])
    ids = [c.term_id for c in b.rising]
    assert "tomato" not in ids and "kim" not in ids
    assert set(ids) == {"lucky", "human", "pending", "found"}
    assert ids[-1] == "pending"                                       # 막 퍼지는 말이라도 확인 전이면 확인된 말 뒤
    assert b.counts["KR"] == 4                                        # 지역 칩 건수도 목록과 같다
    assert dashboard.card(con, "tomato") is not None                  # 사전 화면·카피 검사는 그대로 찾는다


def test_mentions_mixed_with_other_stories_do_not_lead_the_list():
    def card(tid, mentions, mixed=False, confirmed=True):
        return KeywordCard(term_id=tid, canonical=tid, lang="ko", category="meme", gloss_ko="", gloss_en="", regions=["KR"],
                           lifecycle="steady", weekly=[], mentions_4w=mentions, search=[], tone=Tone(), evidences=[],
                           use_confirmed=confirmed, mentions_mixed=mixed)

    rising, _, _ = dashboard.split([card("dori", 30, mixed=True), card("lucky", 5), card("new", 50, confirmed=False)])
    assert [c.term_id for c in rising] == ["lucky", "dori", "new"]


def test_meme_use_counts_labels():
    con = db.connect(":memory:")
    t = Term(term_id="t", canonical="도리", lang="ko", status="verified")
    labels = {"a": ("offtopic", "none"), "b": ("offtopic", "none"), "c": ("neutral", "none")}
    held, confirmed, mixed = dashboard.meme_use(con, t, None, labels)
    assert (held, confirmed, mixed) == (False, True, True)            # 위키 분류가 아니면 빼지 않는다
