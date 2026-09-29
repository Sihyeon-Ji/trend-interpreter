"""리스크 표본(scripts/risk_sample.py, Plan 03) — 층 나누기·필수 표현·일치율은 규칙이다. 모델 없이 임시 스키마로."""
import importlib.util
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from trend_agents.schemas import Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

_spec = importlib.util.spec_from_file_location("risk_sample", Path(__file__).resolve().parents[1] / "scripts" / "risk_sample.py")
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)
QUOTAS = {"avoid": 2, "caution": 4, "none": 2, "hold": 1}
REQUIRED = ("懶人包", "gaslighting", "brah", "FOMO", "없는말")


def test_risk_sample_is_stratified_keeps_required_terms_and_scores_agreement():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    levels = {"avoid": ["懶人包", "gaslighting", "거지근성"], "caution": ["brah", "FOMO", "viral video", "밈1", "밈2", "밈3"],
              "none": ["없음1", "없음2", "없음3", "없음4"], "hold": ["보류1", "보류2", "보류3"]}
    for level, names in levels.items():
        for name in names:
            ds.upsert_term(con, Term(term_id=f"t_{name}", canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now))
            ds.set_risk(con, f"t_{name}", None if level == "hold" else level, [f"{level} 이유"], now)
    ds.upsert_term(con, Term(term_id="t_new", canonical="판정전", lang="ko", status="verified", first_seen=now, last_seen=now))
    rows = rs.checked_terms(con)
    assert len(rows) == 16 and "t_new" not in {r["term_id"] for r in rows}      # 리스크 단계가 아직 보지 않은 말은 뽑지 않는다

    sample, missing = rs.draw(rows, QUOTAS, REQUIRED, seed=7)
    assert missing == ["없는말"]
    assert Counter(r["rule"] for r in sample) == QUOTAS                          # 층마다 정한 수 — 필수 표현도 제 층의 자리를 쓴다
    assert {"懶人包", "gaslighting", "brah", "FOMO"} <= {r["canonical"] for r in sample}
    assert rs.draw(rows, QUOTAS, REQUIRED, seed=7)[0] == sample                  # 같은 시드면 같은 표본
    assert "懶人包 ★" in rs.checklist(sample)

    def decide(name, level):                                                    # /admin/risk 의 결정(POST /review/{id}/risk)이 남기는 모양
        t = ds.get_term(con, f"t_{name}")
        t.risk_human, t.risk_decided_by, t.risk_decided_at = level, "reviewer", now
        ds.upsert_term(con, t, human=True)

    decide("懶人包", "caution")      # 규칙은 사용 자제 — 어긋남
    decide("gaslighting", "avoid")   # 같은 수준 — 일치
    decide("brah", "none")           # 규칙은 주의 — 어긋남
    decide("FOMO", None)             # '규칙대로' — 사람의 값은 지워지고 결정한 사람만 남는다: 일치
    res = rs.agreement(sample, {r["term_id"]: r for r in rs.checked_terms(con)})
    assert (res["reviewed"], res["agree"], res["total"]) == (4, 2, 9)
    assert res["by_level"]["avoid"] == [1, 2] and res["by_level"]["caution"] == [1, 2] and res["by_level"]["none"] == [0, 0]
    assert res["confusion"] == {"avoid->avoid": 1, "avoid->caution": 1, "caution->caution": 1, "caution->none": 1}
    assert sum(1 for r in res["rows"] if r["agree"] is None) == 5                # 나머지는 '검토 전'
    con.close()
