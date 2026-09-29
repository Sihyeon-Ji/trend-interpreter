"""나무위키 단계 — 한국어 유행어의 '업데이트되면 받아오기'.

1. 실시간 검색어 → trend_queries(source=namu_rank). 분류(classify)가 유행어인지 가른다.
2. 분류:유행어 · 분류:인터넷 밈 에 오른 말 중 사전에 없는 것 → 후보(source=namu, 한 번에 승격).
3. 이미 가진 한국어 표제어의 나무위키 문서가 **마지막 조사 뒤에 고쳐졌으면** 다시 조사한다.
   문서마다 기계가 읽는 최근 수정 시각이 있다(2026-09-28 실측, 절반이 최근 2주 안에 수정).

본문은 옮기지 않는다(CC BY-NC-SA 2.0 KR). 수집기는 collectors/namuwiki.py.
"""
from __future__ import annotations

import re
from ..storage.db import Connection
from datetime import date, timezone

from ..collectors import namuwiki
from ..schemas import TrendQuery
from ..storage import dictionary_store as ds
from .match import unsafe
from .runs import stage

CATEGORIES = ("유행어", "인터넷 밈")
MAX_NEW = 8       # 조사 단계가 실행마다 새로 세우는 수(research.run max_new)보다 많이 넣으면 대기열만 쌓인다(2026-09-29 검토)
MAX_RECHECK = 6


def run(con: Connection) -> dict:
    with stage(con, "namu") as r:
        today = date.today()
        rank = namuwiki.ranking()
        ds.upsert_trend_queries(con, [TrendQuery(term=t, region="KR", rank=i + 1, source="namu_rank", date=today)
                                      for i, t in enumerate(rank)])

        added = 0
        for cat in CATEGORIES:
            for name in namuwiki.category(cat):
                if added >= MAX_NEW:
                    break
                # 틀 문구('XX라면 …')·욕설·영어 노래 제목 같은 것이 분류에 섞여 있다(2026-09-28 검토). 이미 후보에
                # 있는 말은 다시 넣지 않는다 — 실행마다 넣으면 횟수가 부풀어 '두 번 등장' 규칙을 저절로 채운다.
                if (len(name) > 20 or "(" in name or "XX" in name or unsafe(name) or not re.search(r"[가-힣]", name)
                        or ds.find_term(con, name) or ds.has_candidate(con, name, "ko")):
                    continue
                ds.upsert_candidate(con, name, "ko", "KR", "namu", note=f"kind=slang namu={cat}")
                added += 1

        rechecked = []
        tried = 0
        from .gemini import BudgetExhausted, budget_left, local_ok
        from .research import research_one

        for t in ds.list_terms(con, ("verified",)):
            if len(rechecked) >= MAX_RECHECK or t.lang != "ko":
                continue
            cm = ds.current_meaning(con, t.term_id)
            if cm and cm.verification == "verified_human":   # 사람이 승인한 뜻은 다시 조사하지 않는다 — 칸만 차지했다
                continue
            # 비교는 마지막 '성공한' 조사와 — 실패 기록과 비교하면 문서가 고쳐진 것을 놓쳤다(검토 2차)
            last = ds.last_researched(con, t.term_id, ok_only=True)
            if not last:
                continue
            ev = namuwiki.lookup(t.canonical)          # 하루 캐시 — 문서를 매번 받지 않는다
            if ev and ev[0].observed_at > last.replace(tzinfo=last.tzinfo or timezone.utc):
                if budget_left(con) < 2 and not local_ok():   # research.run 과 같은 예산 확인
                    r.note += "예산 부족 "
                    break
                tried += 1
                try:
                    v, _ = research_one(con, t)
                    if v in ("verified_auto", "unverified"):   # 실제로 다시 조사한 것만 (사람의 결정·그 사이 바뀐 것은 건너뛴다)
                        rechecked.append(t.canonical)
                except BudgetExhausted:
                    break                               # 오늘 몫이 끝났다 — 기록하지 않고 다음 실행에 다시
                except Exception as e:
                    r.note += f"{t.canonical}:{type(e).__name__} "
                    # 형식 실패 같은 것은 기록해 다음 실행에 같은 용어가 칸을 차지하지 않게 한다. 일시적 네트워크 실패는 기록하지 않는다
                    if not isinstance(e, (OSError, TimeoutError)):
                        ds.log_research(con, t.term_id, "error", f"{type(e).__name__}: {e}"[:500], [], "error", [])
                if tried >= MAX_RECHECK:                # 실패도 칸을 센다
                    break
        r.count = len(rank) + added + len(rechecked)
        r.detail = {"실시간 검색어": rank[:10], "새 후보": added, "문서가 고쳐져 다시 조사": rechecked}
    return {"namu": r}
