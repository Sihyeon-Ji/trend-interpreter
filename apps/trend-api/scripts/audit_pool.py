"""감사관 학습 정답을 매길 문제 묶음(2026-10-01). 학습(audit_sft*)·첫 시험·두 번째 시험에 쓴 표제어는 뺀다. 출처별로 고루.
  uv run scripts/audit_pool.py --n 220 --parts 4     # → data/work/audit_pool_<i>.jsonl
"""
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_dataset import prompt  # noqa: E402
from trend_agents.pipeline import audit  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 220
parts = int(sys.argv[sys.argv.index("--parts") + 1]) if "--parts" in sys.argv else 4
con = db.connect()
used = set()
for f in ("data/work/audit_sft_aug.jsonl", "data/work/audit_holdout.jsonl"):
    used |= {json.loads(x)["term_id"] for x in open(f, encoding="utf-8")}
share = {"namu": 0.45, "pttpedia": 0.15, "trendaword": 0.2, "wikidata": 0.15, "evchk": 0.05}
by = {}
for tid, src in con.execute("SELECT DISTINCT term_id, source FROM wiki_catalog").fetchall():
    if tid not in used:
        by.setdefault(src, []).append(tid)
rnd = random.Random(1001)
out = []
for src, frac in share.items():
    pool = by.get(src, []); rnd.shuffle(pool); want = int(n * frac); got = 0
    for tid in pool:
        if got >= want:
            break
        t = ds.get_term(con, tid); m = ds.current_meaning(con, tid) if t else None
        if not (t and m and t.status in ("verified", "needs_review")):
            continue
        docs = audit.documents(t, ds.list_evidences(con, tid))
        if not docs:
            continue
        out.append({"term_id": tid, "source": src, "canonical": t.canonical, "definition": m.definition, "origin": m.origin, "nuance": m.nuance,
                    "docs": [{"url": e.url, "title": e.title, "text": x[:1200]} for e, x in docs], "prompt": prompt(t, m, docs)})
        got += 1
rnd.shuffle(out)
for i in range(parts):
    with open(f"data/work/audit_pool_{i}.jsonl", "w", encoding="utf-8") as f:
        for x in out[i::parts]:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
print(len(out), {s: sum(1 for x in out if x["source"] == s) for s in share})
