"""검수 대기(needs_review) 항목을 지금 게이트로 다시 판정한다 — 모델을 부르지 않고 저장된 뜻·근거만 본다(2026-09-30 등재 기준 변경).
통과한 것은 저장된 뜻을 verified_auto 로 올리고 표제어를 verified 로, 조사 결과(new) 검수 줄은 게이트가 닫는다. 사람이 결정한 것은 건드리지 않는다.
  uv run scripts/regate.py            # 미리보기
  uv run scripts/regate.py --apply
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.collectors.naver_search import for_model  # noqa: E402
from trend_agents.schemas import MeaningDraft  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402
from trend_agents.verification import gate  # noqa: E402


def main() -> None:
    apply = "--apply" in sys.argv
    con = db.connect()
    catalog = {r[0] for r in con.execute("SELECT DISTINCT term_id FROM wiki_catalog").fetchall()}
    passed, why = [], Counter()
    for t in ds.list_terms(con, ("needs_review",)):
        m = ds.current_meaning(con, t.term_id)
        q = ds.pending_review(con, t.term_id)
        if not m or m.verification != "unverified" or (q and q["kind"] != "new"):
            continue
        d = MeaningDraft.model_validate(m.model_dump(include=set(MeaningDraft.model_fields)))
        v, reasons = gate(t.canonical, d, for_model(ds.list_evidences(con, t.term_id)), None, aliases=t.aliases, catalogued=t.term_id in catalog)
        if v != "verified_auto":
            why.update(r[:40] for r in reasons)
            continue
        passed.append(t)
        if apply:
            ds.set_verification(con, m.meaning_id, "verified_auto", "gate")
            t.status = "verified"
            ds.upsert_term(con, t)
            if q:
                ds.decide_review(con, t.term_id, "auto_verified", "gate", kind="new")
    print(("올림 " if apply else "올릴 것 ") + str(len(passed)), Counter(t.lang for t in passed).most_common(8))
    print("  예:", ", ".join(t.canonical for t in passed[:30]))
    print("남은 까닭:", why.most_common(6))


if __name__ == "__main__":
    main()
