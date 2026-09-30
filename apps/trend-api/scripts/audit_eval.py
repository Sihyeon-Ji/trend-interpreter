"""사전 감사관 채점 (2026-09-30). 정답이 있는 문제로 감사관(로컬 Gemma 또는 Gemini)이 '고칠 것'·'괜찮음' 을 맞히는지 잰다.

정답지:
- 전수조사(data/work/crosscheck/audit.json, 1차·2차·반박 검사를 거친 판정) — '고칠 것' 은 고치기 **전** 판(이력에 남은 옛 판), '그대로' 는 지금 판
- 09-30 일괄 등재 표본 — 틀렸던 옛 판(v1)과 고친 뒤 좋았던 판
  uv run scripts/audit_eval.py --model local --n 20
결과: data/eval/audit-<model>-<시각>.json (커밋하지 않음)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.pipeline import audit  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

BAD_V1 = ["ライラック", "热爱105°C的你", "DJ NANMO WAKARAN", "Campfire song song", "Fuck Tha Police"]
GOOD_NOW = ["Scuba Dance", "Big Iron"]


def cases(con, n: int) -> list[tuple[str, object, str, str]]:
    """[(term_id, meaning, 정답, 출처)]"""
    rows = json.load(open("data/work/crosscheck/audit.json"))
    random.seed(11)
    fixes = [r for r in rows if r["verdict"] == "fix"]
    keeps = [r for r in rows if r["verdict"] == "keep"]
    out = []
    for r in random.sample(fixes, min(n, len(fixes))):
        ms = sorted(ds.list_meanings(con, r["term_id"]), key=lambda m: m.version)
        old = next((a for a, b in zip(ms, ms[1:]) if b.created_by == "twkim"), None)   # 전수조사 승인으로 닫힌 판
        if old:
            out.append((r["term_id"], old, "fix", "전수조사 고칠 것(옛 판)"))
    for r in random.sample(keeps, min(n, len(keeps))):
        m = ds.current_meaning(con, r["term_id"])
        if m:
            out.append((r["term_id"], m, "ok", "전수조사 그대로"))
    for name in BAD_V1:
        t = ds.find_term(con, name)
        ms = sorted(ds.list_meanings(con, t.term_id), key=lambda m: m.version) if t else []
        if ms:
            out.append((t.term_id, ms[0], "fix", "09-30 표본 옛 판"))
    for name in GOOD_NOW:
        t = ds.find_term(con, name)
        if t:
            out.append((t.term_id, ds.current_meaning(con, t.term_id), "ok", "09-30 표본 좋은 판"))
    return out


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--model", default="local", help="local · gemini · gemini:<모델 ID>")
    a.add_argument("--n", type=int, default=20)
    a.add_argument("--prompt", default="checklist", choices=["checklist", "simple"])
    a.add_argument("--votes", type=int, default=1, help="체크리스트를 여러 번 묻고 과반(온도 0.5)")
    a.add_argument("--tag", default="", help="결과 파일 이름에 붙일 표시(모델 크기 등)")
    args = a.parse_args()
    con = db.connect()
    results = []
    for tid, m, truth, src in cases(con, args.n):
        t = ds.get_term(con, tid)
        docs = audit.documents(t, ds.list_evidences(con, tid))
        if not docs:
            results.append({"term": t.canonical, "truth": truth, "source": src, "got": "no_doc"})
            continue
        t0 = time.time()
        try:
            if args.votes > 1:
                v, why, tally = audit.check_voted(con, t, m, docs, model=args.model, votes=args.votes)
                strict, check, used = v, {"votes": tally}, args.model
            elif args.prompt == "simple":
                v, reason, used = audit.check_simple(con, t, m, docs, model=args.model)
                why, strict, check = [reason], v, None
            else:
                c, used = audit.check(con, t, m, docs, model=args.model)
                v, why = audit.verdict(c)
                strict, check = ("fix" if (v == "fix" or c.matches_doc == "partly") else "ok"), c.model_dump()
        except Exception as e:
            results.append({"term": t.canonical, "truth": truth, "source": src, "got": f"error {type(e).__name__}"})
            continue
        results.append({"term": t.canonical, "truth": truth, "source": src, "got": v, "got_strict": strict, "why": why,
                        "check": check, "model": used, "sec": round(time.time() - t0, 1)})
        print(f"{'O' if v == truth else 'X'} {truth:>3}→{v:<3} {t.canonical[:24]:<24} {src} | {'; '.join(why)[:70]}", flush=True)
    judged = [r for r in results if r["got"] in ("ok", "fix")]

    def score(key: str) -> dict:
        tp = sum(1 for r in judged if r["truth"] == "fix" and r[key] == "fix")
        fp = sum(1 for r in judged if r["truth"] == "ok" and r[key] == "fix")
        fn = sum(1 for r in judged if r["truth"] == "fix" and r[key] == "ok")
        acc = sum(1 for r in judged if r["truth"] == r[key]) / max(1, len(judged))
        return {"accuracy": round(acc, 3), "fix_precision": round(tp / max(1, tp + fp), 3), "fix_recall": round(tp / max(1, tp + fn), 3), "n": len(judged)}

    summary = {"model": args.model, "prompt": args.prompt, "votes": args.votes, "tag": args.tag, "cases": len(results), "judged": len(judged), "default": score("got"), "partly_as_fix": score("got_strict"),
               "no_doc_or_error": len(results) - len(judged)}
    print(json.dumps(summary, ensure_ascii=False))
    out = Path("data/eval") / f"audit-{args.model.replace(':', '_')}{('-' + args.tag) if args.tag else ''}-{args.prompt}{('-v' + str(args.votes)) if args.votes > 1 else ''}-{datetime.now():%Y%m%d-%H%M}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
