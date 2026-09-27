"""Spanner Graph 에뮬레이터 실측: DDL(PROPERTY GRAPH) → 삽입 → GQL MATCH.

사전: docker run -d -p 9010:9010 -p 9020:9020 gcr.io/cloud-spanner-emulator/emulator
"""
import os
import time
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SPANNER_EMULATOR_HOST", "localhost:9010")
from trend_agents.schemas import Evidence, Meaning, Segment, Term  # noqa: E402
from trend_agents.storage import spanner_graph as g  # noqa: E402

t0 = time.time()
db = g.connect(project="trend-local")
print(f"connected + DDL applied ({len(g.DDL)} statements) in {time.time()-t0:.1f}s")

now = datetime.now(timezone.utc)
g.upsert_term(db, Term(term_id="t_jamanchu", canonical="자만추", status="verified", lifecycle="steady", first_seen=now - timedelta(days=400), last_seen=now))
g.upsert_term(db, Term(term_id="t_jamanchu_v", canonical="자만추하다", status="verified"))
g.link_variant(db, "t_jamanchu_v", "t_jamanchu")

ev = [
    Evidence(evidence_id="e_short1", kind="short", url="https://www.youtube.com/watch?v=abc", title="자만추 vs 인만추", source_domain="youtube.com", observed_at=now),
    Evidence(evidence_id="e_news1", kind="news", url="https://n.news.naver.com/xyz", title="MZ 연애 키워드 '자만추'", source_domain="news.naver.com", observed_at=now),
]
m1 = Meaning(meaning_id="m_jamanchu_1", term_id="t_jamanchu", version=1, definition="자연스러운 만남을 추구한다는 뜻", expansion="자연스러운 만남 추구",
             origin="2010년대 후반 온라인 커뮤니티", nuance="소개팅·앱 대비 자연스러운 연애 선호", generations=["20s", "30s"], regions=["KR"],
             self_confidence=0.85, confidence=0.85, verification="verified_auto", valid_from=now - timedelta(days=30), citations=["https://namu.wiki/w/자만추"])
g.add_meaning(db, m1, ev)
# 의미 변화 시나리오: v2 를 넣으면 v1 의 valid_to 가 닫혀야 한다
m2 = m1.model_copy(update={"meaning_id": "m_jamanchu_2", "version": 2, "nuance": "최근엔 '자연스럽게 만나기 어렵다'는 자조적 맥락으로도 쓰임", "valid_from": now})
g.add_meaning(db, m2, ev)

g.mark_used_by(db, "t_jamanchu", Segment(segment_id="KR-20s", generation="20s", region="KR"), now - timedelta(days=300), 0.6)
g.mark_used_by(db, "t_jamanchu", Segment(segment_id="KR-30s", generation="30s", region="KR"), now - timedelta(days=200), 0.3)
g.mark_used_by(db, "t_jamanchu", Segment(segment_id="KR-40s", generation="40s", region="KR"), now - timedelta(days=40), 0.1)

print("\n[GQL] lookup_verified('자만추')  — 현행(valid_to IS NULL) 버전만 나와야 함")
for r in g.lookup_verified(db, "자만추"):
    print("  ", r)
print("\n[GQL] spread_path('자만추') — 세대 간 확산 순서")
for r in g.spread_path(db, "자만추"):
    print("  ", r)
print("\n[GQL] resolve_variant('자만추하다') ->", g.resolve_variant(db, "자만추하다"))
with db.snapshot() as s:
    rows = list(s.execute_sql("SELECT version, valid_to IS NULL AS open FROM Meaning WHERE term_id='t_jamanchu' ORDER BY version"))
print("\n[SQL] Meaning versions (version, open):", rows)
