"""감사관 파인튜닝 데이터 (2026-09-30, 사용자 결정: 전수조사 판정을 학습 정답으로). 시험 문제(audit_eval 의 표제어)는 학습에서 뺀다.
한 줄: {"term_id", "split": train|test, "messages": [{"role":"user"}, {"role":"assistant"}], "label": fix|ok}
참고 문서 글은 학습 파일에만 들어간다(학습 서버 ~/gemma-research/data, 커밋하지 않음).
  uv run scripts/audit_dataset.py > data/work/audit_sft.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_eval import cases  # noqa: E402
from trend_agents.pipeline import audit, crosscheck  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

PROMPT = audit.SIMPLE_PROMPT


def prompt(t, m, docs) -> str:
    lines = "\n\n".join(f"{i}. [{crosscheck.wiki_name(e.url)}] {e.title}\n{x}" for i, (e, x) in enumerate(docs, 1))
    return PROMPT.format(term=t.canonical, definition=m.definition or "(없음)", origin=m.origin or "(없음)", nuance=m.nuance or "(없음)", docs=lines)


def main() -> None:
    con = db.connect()
    test = {tid: (m, truth) for tid, m, truth, _ in cases(con, 20)}
    rows = json.load(open("data/work/crosscheck/audit.json"))
    out = []

    def emit(tid, m, label, reason, split):
        t = ds.get_term(con, tid)
        docs = audit.documents(t, ds.list_evidences(con, tid)) if t and m else []
        if not docs:
            return
        answer = json.dumps({"verdict": label, "reason": reason}, ensure_ascii=False)
        out.append({"term_id": tid, "split": split, "label": label,
                    "messages": [{"role": "user", "content": prompt(t, m, docs)}, {"role": "assistant", "content": answer}]})

    for r in rows:
        tid = r["term_id"]
        if tid in test:
            continue
        ms = sorted(ds.list_meanings(con, tid), key=lambda m: m.version)
        why = " ".join(p for p in r["problems"][:2])[:300]
        if r["verdict"] == "fix":
            old = next((a for a, b in zip(ms, ms[1:]) if b.created_by == "twkim"), None)
            new = next((b for a, b in zip(ms, ms[1:]) if b.created_by == "twkim"), None)
            emit(tid, old or (ms[-1] if ms else None), "fix", why, "train")
            if new:
                emit(tid, new, "ok", "뜻·유래가 문서와 맞고 밈으로 어떻게 쓰이는지 적었다.", "train")
        elif r["verdict"] == "not_a_meme":
            emit(tid, ms[-1] if ms else None, "fix", "문서는 이 말을 밈·유행어로 다루지 않는다. " + why, "train")
        elif r["verdict"] == "keep":
            emit(tid, ms[-1] if ms else None, "ok", "뜻·유래가 문서와 맞고 밈으로 어떻게 쓰이는지 적었다.", "train")
    if "--augment" in sys.argv:
        # 정답이 확실한 틀린 예(2026-09-30 3차): 멀쩡한 뜻을 (1) 다른 표제어의 뜻으로 바꿔치기, (2) 유래를 사이트 이름으로.
        # 일괄 등재의 옛 판을 모두 '고칠 것' 으로 넣으면 표본 10개 중 3개가 멀쩡해 정답의 30% 가 틀린다 — 그래서 만든 예만 쓴다.
        import random

        rnd = random.Random(5)
        oks = [x for x in out if x["split"] == "train" and x["label"] == "ok"]
        pool = [(x["term_id"], ds.current_meaning(con, x["term_id"])) for x in oks]
        extra = []
        for x in oks:
            t = ds.get_term(con, x["term_id"])
            m = ds.current_meaning(con, x["term_id"])
            docs = audit.documents(t, ds.list_evidences(con, x["term_id"]))
            if not (t and m and docs):
                continue
            other = rnd.choice([pm for tid, pm in pool if tid != x["term_id"] and pm])
            swapped = m.model_copy(update={"definition": other.definition, "origin": other.origin, "nuance": other.nuance})
            extra.append({"term_id": x["term_id"], "split": "train", "label": "fix", "messages": [
                {"role": "user", "content": prompt(t, swapped, docs)},
                {"role": "assistant", "content": json.dumps({"verdict": "fix", "reason": "문서와 다른 대상을 설명한다."}, ensure_ascii=False)}]})
            if rnd.random() < 0.5:
                site = m.model_copy(update={"origin": rnd.choice(["wikipedia.org", "namu.wiki", "knowyourmeme.com"])})
                extra.append({"term_id": x["term_id"], "split": "train", "label": "fix", "messages": [
                    {"role": "user", "content": prompt(t, site, docs)},
                    {"role": "assistant", "content": json.dumps({"verdict": "fix", "reason": "유래에 사이트 이름만 적었다."}, ensure_ascii=False)}]})
        out += extra
    for tid, (m, truth) in test.items():
        emit(tid, m, truth, "", "test")
    for x in out:
        print(json.dumps(x, ensure_ascii=False))
    from collections import Counter
    print(Counter((x["split"], x["label"]) for x in out), file=sys.stderr)


if __name__ == "__main__":
    main()
