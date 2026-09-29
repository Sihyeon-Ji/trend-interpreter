"""결정론 규칙 테스트: 생애주기 판정 + 검증 게이트. 인프라·키 불필요."""
from datetime import datetime, timezone

from trend_agents.lifecycle import recheck_interval_days, stage
from trend_agents.schemas import Evidence, Meaning, MeaningDraft
from trend_agents.verification import gate

print("== lifecycle (주간 언급수, 오래된→최근) ==")
cases = {
    "emerging":  ([0, 0, 3, 9], 1),
    "rising":    ([2, 4, 6, 15], 8),
    "peak":      ([5, 20, 40, 38], 10),
    "declining": ([40, 30, 15, 8], 12),
    "dormant":   ([30, 10, 0, 0, 0, 0], 20),
    "steady":    ([10, 12, 11, 10], 30),
}
ok = True
for expect, (counts, weeks) in cases.items():
    got = stage(counts, weeks)
    ok &= got == expect
    print(f"  {counts!s:28} weeks={weeks:2d} -> {got:9s} (재검증 {recheck_interval_days(got)}일) {'OK' if got == expect else 'FAIL expected ' + expect}")

print("\n== verification gate ==")
now = datetime.now(timezone.utc)
draft = MeaningDraft(definition="자연스러운 만남을 추구한다는 뜻", expansion="자연스러운 만남 추구", origin="2010년대 후반 온라인 커뮤니티", nuance="소개팅·앱 대비 자연스러운 연애를 선호", generations=["20s", "30s"], regions=["KR"], self_confidence=0.85)
ev = [
    Evidence(evidence_id="e1", kind="short", url="https://www.youtube.com/watch?v=x", source_domain="youtube.com", observed_at=now, excerpt="자만추 vs 인만추"),
    Evidence(evidence_id="e2", kind="news", url="https://n.news.naver.com/a", source_domain="news.naver.com", observed_at=now, excerpt="자만추(자연스러운 만남 추구)"),
    Evidence(evidence_id="e5", kind="wiki", url="https://namu.wiki/w/자만추", source_domain="namu.wiki", observed_at=now, excerpt="자만추는 자연스러운 만남 추구의 줄임말이다"),
]
v, why = gate("자만추", draft, ev, None);            print(f"  2출처+1차근거+앵커+문서 -> {v:13s} {why}")
v, why = gate("자만추", draft, ev[:2], None);        print(f"  참고 문서 없음        -> {v:13s} {why}")
v, why = gate("자만추", draft, ev[:1], None);        print(f"  1출처                -> {v:13s} {why}")
web = [Evidence(evidence_id="e3", kind="web", url="https://a.com", source_domain="a.com", observed_at=now), Evidence(evidence_id="e4", kind="web", url="https://b.com", source_domain="b.com", observed_at=now)]
v, why = gate("자만추", draft, web, None);           print(f"  웹검색만 2출처(앵커X) -> {v:13s} {why}")
cur = Meaning(**draft.model_dump(), meaning_id="m1", term_id="t1", version=1, confidence=0.9, verification="verified_human", valid_from=now)
drift = draft.model_copy(update={"expansion": "자기 만족 추구"})
v, why = gate("자만추", drift, ev, cur);             print(f"  현행 뜻과 충돌(drift) -> {v:13s} {why}")
noanchor = [e.model_copy(update={"excerpt": "MZ 연애 트렌드 정리"}) for e in ev]
v, why = gate("자만추", draft, noanchor, None);       print(f"  출처2 but 용어 미등장 -> {v:13s} {why}")
print("\nALL OK" if ok else "\nLIFECYCLE FAIL")
