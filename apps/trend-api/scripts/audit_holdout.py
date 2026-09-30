"""감사관 두 번째 시험(2026-09-30): 학습·첫 시험에 쓰지 않은 일괄 등재 항목에서 출처별로 고루 뽑는다.
정답은 모델 결과를 보기 전에 사람(개발 중 검토자)이 문서와 뜻을 대조해 매기고 data/work/audit_holdout_labels.json 에 둔다.
  uv run scripts/audit_holdout.py pick --n 30        # 문제 뽑기 → data/work/audit_holdout.jsonl (+ 검토용 요약 출력)
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_dataset import prompt  # noqa: E402
from trend_agents.pipeline import audit  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402


def main() -> None:
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 30
    con = db.connect()
    used = {json.loads(x)["term_id"] for x in open("data/work/audit_sft_aug.jsonl", encoding="utf-8")}
    rows = con.execute("SELECT term_id, source FROM wiki_catalog").fetchall()
    by: dict[str, list[str]] = {}
    for tid, src in rows:
        if tid not in used:
            by.setdefault(src, []).append(tid)
    rnd = random.Random(2026)
    picks = []
    per = {"namu": n // 3, "pttpedia": n // 5, "trendaword": n // 5, "wikidata": n // 10}
    for src, k in per.items():
        pool = list(dict.fromkeys(by.get(src, [])))
        rnd.shuffle(pool)
        got = 0
        for tid in pool:
            if got >= k:
                break
            t = ds.get_term(con, tid)
            m = ds.current_meaning(con, tid) if t else None
            if not (t and m and t.status in ("verified", "needs_review")):
                continue
            docs = audit.documents(t, ds.list_evidences(con, tid))
            if not docs:
                continue
            picks.append({"term_id": tid, "source": src, "canonical": t.canonical, "prompt": prompt(t, m, docs),
                          "definition": m.definition, "origin": m.origin, "docs": [(e.url, x[:700]) for e, x in docs]})
            got += 1
    with open("data/work/audit_holdout.jsonl", "w", encoding="utf-8") as f:
        for p in picks:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    for i, p in enumerate(picks):
        print(f"\n### {i} {p['canonical']} ({p['source']})\n뜻: {p['definition'][:220]}\n유래: {(p['origin'] or '')[:160]}")
        for u, x in p["docs"][:1]:
            print(f"문서 {u[:60]}: {x[:520]}")


if __name__ == "__main__":
    main()
