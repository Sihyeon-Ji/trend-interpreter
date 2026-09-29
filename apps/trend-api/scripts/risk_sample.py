"""리스크 판정 표본 20개 — 검수자 체크리스트와 일치율 (Plan 03 완료 기준 '표본 20개를 사람이 검토한 일치율'). 모델을 부르지 않는다.

  uv run scripts/risk_sample.py draw --sqlite <DB 사본>    # 층을 나눠 뽑아 artifacts/eval/risk-sample.json 에 저장하고 체크리스트를 보인다
  uv run scripts/risk_sample.py agree --sqlite <DB 사본>   # 저장한 표본을 다시 읽어 검수자의 결정(/admin/risk)과 규칙 판정의 일치율
  (--sqlite 가 없으면 DATABASE_URL 의 PostgreSQL. 검수자는 운영 화면에서 정하므로 agree 는 운영 DB 나 그 사본으로 돌린다)

뽑는 법: 확인된(verified) 말 가운데 리스크 단계가 판정한 것(risk_checked_at 있음)을 규칙의 수준(risk_rule_level)으로 나눠
사용 자제 5 · 주의 7 · 없음 5 · 판단 보류 3. 1차 검토에서 어긋났거나 논의된 말(REQUIRED)은 제 층에 꼭 넣고(어긋난 넷을 모두 넣어
규칙이 위험을 놓친 쪽도 다시 본다), 나머지는 시드로 고정해 뽑는다.
일치: 검수자가 정한 수준이 규칙의 수준과 같은가. 검수자가 '규칙대로' 를 고르면 사람의 값은 지워지고 결정한 사람만 남으므로(risk_decided_by)
그것도 규칙에 동의한 것으로 센다. 결정이 없는 줄은 '검토 전'.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

OUT = Path(__file__).resolve().parents[3] / "artifacts" / "eval" / "risk-sample.json"
QUOTAS = {"avoid": 5, "caution": 7, "none": 5, "hold": 3}
# Plan 03 1차 검토(개발자 16/20)에서 어긋난 넷(viral video·pov·brah 는 문장 분위기로 '주의', Tralalero Tralala 는 원본 음성의
# 신성모독을 놓쳐 '없음' — 규칙이 위험을 놓친 쪽의 유일한 예)과 검토 중 논의된 말 — 표본마다 다시 본다
REQUIRED = ("懶人包", "gaslighting", "brah", "viral video", "FOMO", "pov", "Tralalero Tralala")
LEVEL_KO = {"avoid": "사용 자제", "caution": "주의", "none": "없음", "hold": "판단 보류"}


def checked_terms(con) -> list[dict]:
    """리스크 단계가 판정한 확인된 말. level 은 규칙의 수준(없으면 판단 보류 'hold')."""
    out = []
    # 순서는 파이썬에서 — SQL 정렬은 DB 마다 문자 정렬 규칙이 달라 같은 시드로도 다른 표본이 나온다
    for tid, canon, j in sorted(con.execute("SELECT term_id, canonical, json FROM terms WHERE status='verified'").fetchall()):
        t = json.loads(j)
        if not t.get("risk_checked_at"):
            continue
        out.append({"term_id": tid, "canonical": canon, "rule": t.get("risk_rule_level") or "hold", "human": t.get("risk_human"),
                    "decided_by": t.get("risk_decided_by"), "decided_at": t.get("risk_decided_at"),
                    "reasons": [r for r in t.get("risk_reasons") or [] if r != "검수자가 정한 수준"]})
    return out


def draw(rows: list[dict], quotas: dict[str, int] = QUOTAS, required: tuple[str, ...] = REQUIRED, seed: int = 20260929) -> tuple[list[dict], list[str]]:
    """(표본, 찾지 못한 필수 표현). 필수 표현은 규칙이 지금 매긴 층에 먼저 넣고, 층의 남은 자리를 시드로 뽑는다."""
    rng = random.Random(seed)
    wanted = {r.casefold() for r in required}
    picked = [r for r in rows if r["canonical"].casefold() in wanted]
    missing = [r for r in required if r.casefold() not in {p["canonical"].casefold() for p in picked}]
    sample = [dict(r, required=True) for r in picked]
    for level, n in quotas.items():
        have = sum(1 for r in sample if r["rule"] == level)
        pool = [r for r in rows if r["rule"] == level and r not in picked]
        sample += [dict(r, required=False) for r in rng.sample(pool, max(0, min(n - have, len(pool))))]
    order = list(quotas)
    sample.sort(key=lambda r: (order.index(r["rule"]) if r["rule"] in order else len(order), not r["required"], r["canonical"]))
    return sample, missing


def agreement(sample: list[dict], now: dict[str, dict]) -> dict:
    """표본마다 지금 저장된 결정을 규칙의 수준과 견준다. now: {term_id: checked_terms 의 줄}."""
    rows, confusion = [], Counter()
    for s in sample:
        cur = now.get(s["term_id"])
        rule = cur["rule"] if cur else s["rule"]
        decided = bool(cur and (cur["human"] or cur["decided_by"]))
        human = (cur["human"] or rule) if decided else None     # '규칙대로' 는 사람의 값을 지우고 결정한 사람만 남긴다
        rows.append({"term_id": s["term_id"], "canonical": s["canonical"], "rule_at_draw": s["rule"], "rule": rule, "human": human,
                     "by": cur["decided_by"] if cur else None, "agree": None if human is None else human == rule})
        if human is not None:
            confusion[(rule, human)] += 1
    done = [r for r in rows if r["agree"] is not None]
    by_level = {lv: [sum(1 for r in done if r["rule"] == lv and r["agree"]), sum(1 for r in done if r["rule"] == lv)] for lv in QUOTAS}
    return {"rows": rows, "reviewed": len(done), "agree": sum(1 for r in done if r["agree"]), "total": len(rows),
            "by_level": by_level, "confusion": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())}}


def checklist(sample: list[dict]) -> str:
    lines = ["| # | 표현 | 규칙 수준 | 규칙의 이유(첫 줄) | 검수자가 정한 수준 |", "| ---: | --- | --- | --- | --- |"]
    for i, r in enumerate(sample, 1):
        why = (r["reasons"][0] if r["reasons"] else "").replace("|", "/")[:80]
        lines.append(f"| {i} | {r['canonical']}{' ★' if r['required'] else ''} | {LEVEL_KO.get(r['rule'], r['rule'])} | {why} |  |")
    return "\n".join(lines)


def _connect(path: str | None):
    if path:
        p = Path(path)
        if not p.exists():
            raise SystemExit(f"DB 사본이 없습니다: {p}")
        return sqlite3.connect(f"file:{p}?mode=ro", uri=True), p.name
    from trend_agents.storage import store as db

    return db.connect(), "DATABASE_URL"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=("draw", "agree"))
    ap.add_argument("--sqlite", help="원작자 서버 DB 사본(.db). 읽기 전용으로 연다. 없으면 DATABASE_URL 의 PostgreSQL")
    ap.add_argument("--sample", default=str(OUT), help="표본 파일")
    ap.add_argument("--seed", type=int, default=20260929)
    a = ap.parse_args()
    con, source = _connect(a.sqlite)
    path = Path(a.sample)
    if a.action == "draw":
        sample, missing = draw(checked_terms(con), seed=a.seed)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"drawn_at": datetime.now(timezone.utc).isoformat(), "source": source, "seed": a.seed, "quotas": QUOTAS,
                                    "missing": missing, "terms": sample}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(checklist(sample))
        counts = Counter(r["rule"] for r in sample)
        print(f"\n{len(sample)}개 ({' · '.join(f'{LEVEL_KO[k]} {counts.get(k, 0)}' for k in QUOTAS)}) → {path}")
        if missing:
            print(f"확인된 말 가운데 리스크 판정이 없어 넣지 못한 필수 표현: {', '.join(missing)}")
        return
    if not path.exists():
        raise SystemExit(f"표본 파일이 없습니다: {path} — 먼저 draw 를 실행하세요")
    saved = json.loads(path.read_text(encoding="utf-8"))
    res = agreement(saved["terms"], {r["term_id"]: r for r in checked_terms(con)})
    print("| 표현 | 규칙 수준(뽑을 때 → 지금) | 검수자 | 일치 |\n| --- | --- | --- | --- |")
    for r in res["rows"]:
        rule = LEVEL_KO.get(r["rule"], r["rule"]) + ("" if r["rule"] == r["rule_at_draw"] else f" (뽑을 때 {LEVEL_KO.get(r['rule_at_draw'])})")
        human = f"{LEVEL_KO.get(r['human'], r['human'])} ({r['by'] or '?'})" if r["human"] else "검토 전"
        print(f"| {r['canonical']} | {rule} | {human} | {'—' if r['agree'] is None else '예' if r['agree'] else '아니오'} |")
    per = " · ".join(f"{LEVEL_KO[k]} {a_}/{n}" for k, (a_, n) in res["by_level"].items() if n)
    print(f"\n일치 {res['agree']}/{res['reviewed']} (표본 {res['total']}개 중 {res['reviewed']}개 검토){' — ' + per if per else ''}")
    if res["confusion"]:
        print("규칙 → 검수자: " + ", ".join(f"{k} {v}" for k, v in res["confusion"].items()))


if __name__ == "__main__":
    main()
