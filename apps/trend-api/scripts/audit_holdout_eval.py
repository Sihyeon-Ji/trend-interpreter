"""두 번째 시험 채점: 체크리스트형 감사관(로컬 Ollama 또는 Gemini)을 data/work/audit_holdout_labels.json 의 정답과 맞춘다."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.pipeline import audit  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

model = sys.argv[1] if len(sys.argv) > 1 else "local"
labels = json.load(open("data/work/audit_holdout_labels.json"))
con = db.connect()
res = []
for tid, truth in labels.items():
    if truth == "unsure":
        continue
    t = ds.get_term(con, tid); m = ds.current_meaning(con, tid)
    docs = audit.documents(t, ds.list_evidences(con, tid))
    try:
        c, _ = audit.check(con, t, m, docs, model=model)
        v, why = audit.verdict(c)
    except Exception as e:                 # 형식 실패도 결과다 — 틀린 것으로 센다
        v, why = "error", [type(e).__name__]
    res.append((truth, v, len(m.definition or "")))
    print(("O" if v == truth else "X"), truth, v, t.canonical[:20], "; ".join(why)[:60], flush=True)
tp = sum(a == "fix" and b == "fix" for a, b, _ in res); fp = sum(a == "ok" and b == "fix" for a, b, _ in res); fn = sum(a == "fix" and b == "ok" for a, b, _ in res)
print(json.dumps({"model": model, "n": len(res), "accuracy": round(sum(a == b for a, b, _ in res) / len(res), 3), "errors": sum(b == "error" for _, b, _ in res),
                  "fix_precision": round(tp / max(1, tp + fp), 3), "fix_recall": round(tp / max(1, tp + fn), 3)}))
