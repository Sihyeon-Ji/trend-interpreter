"""리스크 판정 표본 20개 — 검수자 체크리스트와 일치율 (Plan 03 완료 기준 '표본 20개를 사람이 검토한 일치율'). 모델을 부르지 않는다.

  uv run scripts/risk_sample.py draw --sqlite <DB 사본>   # 층을 나눠 뽑아 docs/plans/03-term-risk-sample.csv 에 쓴다(파일이 있으면 --force 없이는 쓰지 않는다)
  uv run scripts/risk_sample.py agree                     # 그 파일에 검수자가 적은 수준을 뽑을 때의 규칙 수준과 견준다 — DB 를 보지 않는다
  (draw 는 --sqlite 가 없으면 DATABASE_URL 의 PostgreSQL 에 읽기 전용으로 붙는다 — 스키마·마이그레이션을 건드리지 않는다)

뽑는 법: 확인된(verified) 말 가운데 리스크 단계가 판정한 것(risk_checked_at 있음)을 규칙의 수준(risk_rule_level)으로 나눠
사용 자제 5 · 주의 7 · 없음 5 · 판단 보류 3. 1차 검토에서 어긋났거나 논의된 말(REQUIRED)은 제 층에 꼭 넣고(어긋난 넷을 모두 넣어
규칙이 위험을 놓친 쪽도 다시 본다), 나머지는 시드로 고정해 뽑는다. 말의 목록은 파이프라인이 돌 때마다 바뀌어 같은 시드로도 같은 표본이
다시 나오지 않는다 — 그래서 뽑은 표본(term_id)을 저장소에 커밋하고, 검수자도 그 파일에 수준을 적는다.
일치: 검수자가 '검수자가 정한 수준' 칸에 적은 수준이 뽑을 때의 규칙 수준(검수자가 본 체크리스트의 값)과 같은가. 빈칸은 '검토 전'.
검수자는 측정을 위해 운영 관리 화면(/admin/risk)의 수준을 고르지 않는다. 고르면 사람의 값(risk_human)으로 고정되어 뒤에 근거가 바뀌어도
규칙을 따르지 않고, 고르는 즉시 카드·추천에 나간다.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SAMPLE = Path(__file__).resolve().parents[3] / "docs" / "plans" / "03-term-risk-sample.csv"
QUOTAS = {"avoid": 5, "caution": 7, "none": 5, "hold": 3}
# Plan 03 1차 검토(개발자 16/20)에서 어긋난 넷(viral video·pov·brah 는 문장 분위기로 '주의', Tralalero Tralala 는 원본 음성의
# 신성모독을 놓쳐 '없음' — 규칙이 위험을 놓친 쪽의 유일한 예)과 검토 중 논의된 말 — 표본마다 다시 본다
REQUIRED = ("懶人包", "gaslighting", "brah", "viral video", "FOMO", "pov", "Tralalero Tralala")
LEVEL_KO = {"avoid": "사용 자제", "caution": "주의", "none": "없음", "hold": "판단 보류"}
COLUMNS = ("번호", "term_id", "표현", "필수", "규칙 수준", "규칙의 이유(첫 줄)", "검수자가 정한 수준", "검수자", "메모")


def checked_terms(con) -> list[dict]:
    """리스크 단계가 판정한 확인된 말. rule 은 규칙의 수준(없으면 판단 보류 'hold')."""
    out = []
    # 순서는 파이썬에서 — SQL 정렬은 DB 마다 문자 정렬 규칙이 달라 같은 시드로도 다른 표본이 나온다
    for tid, canon, j in sorted(con.execute("SELECT term_id, canonical, json FROM terms WHERE status='verified'").fetchall()):
        t = json.loads(j)
        if not t.get("risk_checked_at"):
            continue
        out.append({"term_id": tid, "canonical": canon, "rule": t.get("risk_rule_level") or "hold",
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


def save(path: Path, sample: list[dict]) -> None:
    """검수자가 채울 표본 파일. 검수자 칸은 비워 둔다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for i, r in enumerate(sample, 1):
            w.writerow([i, r["term_id"], r["canonical"], "★" if r["required"] else "", LEVEL_KO.get(r["rule"], r["rule"]),
                        r["reasons"][0] if r["reasons"] else "", "", "", ""])


def load(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def level(text: str | None) -> str | None:
    """칸의 값('사용 자제' 또는 'avoid') → 수준. 빈칸은 None, 모르는 값은 ValueError."""
    s = (text or "").strip()
    if not s:
        return None
    for code, ko in LEVEL_KO.items():
        if s.casefold() == code or s.replace(" ", "") == ko.replace(" ", ""):
            return code
    raise ValueError(s)


def agreement(rows: list[dict]) -> dict:
    """표본 파일의 줄마다 검수자가 적은 수준을 뽑을 때의 규칙 수준(검수자가 본 값)과 견준다. rows: load() 의 줄."""
    out, confusion = [], Counter()
    for r in rows:
        try:
            rule, human = level(r["규칙 수준"]), level(r["검수자가 정한 수준"])
        except ValueError as e:
            raise ValueError(f"{r['번호']}번 {r['표현']}: '{e}' 은 수준이 아닙니다 — {'·'.join(LEVEL_KO.values())} 가운데 하나로 적으세요") from None
        out.append({"canonical": r["표현"], "rule": rule, "human": human, "by": (r.get("검수자") or "").strip(),
                    "agree": None if human is None else human == rule})
        if human is not None:
            confusion[(rule, human)] += 1
    done = [r for r in out if r["agree"] is not None]
    by_level = {lv: [sum(1 for r in done if r["rule"] == lv and r["agree"]), sum(1 for r in done if r["rule"] == lv)] for lv in QUOTAS}
    return {"rows": out, "reviewed": len(done), "agree": sum(1 for r in done if r["agree"]), "total": len(out),
            "by_level": by_level, "confusion": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())}}


def checklist(sample: list[dict]) -> str:
    """Plan 03 에 붙일 목록. 검수자는 이 표가 아니라 표본 파일에 적는다."""
    lines = ["| # | 표현 | 규칙 수준 | 규칙의 이유(첫 줄) |", "| ---: | --- | --- | --- |"]
    for i, r in enumerate(sample, 1):
        why = (r["reasons"][0] if r["reasons"] else "").replace("|", "/")[:80]
        lines.append(f"| {i} | {r['canonical']}{' ★' if r['required'] else ''} | {LEVEL_KO.get(r['rule'], r['rule'])} | {why} |")
    return "\n".join(lines)


def _connect(path: str | None):
    if path:
        p = Path(path)
        if not p.exists():
            raise SystemExit(f"DB 사본이 없습니다: {p}")
        return sqlite3.connect(f"file:{p}?mode=ro", uri=True), p.name
    from trend_agents.storage import db

    return db.connect_read_only(), "DATABASE_URL"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=("draw", "agree"))
    ap.add_argument("--sqlite", help="draw: 원작자 서버 DB 사본(.db). 읽기 전용으로 연다. 없으면 DATABASE_URL 의 PostgreSQL(읽기 전용)")
    ap.add_argument("--sample", default=str(SAMPLE), help="표본 파일(저장소에 커밋한다)")
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--force", action="store_true", help="draw: 있는 표본 파일을 덮어쓴다(검수자가 적은 수준도 지워진다)")
    a = ap.parse_args()
    path = Path(a.sample)
    if a.action == "draw":
        if path.exists() and not a.force:
            # 다시 뽑으면 다른 20개가 되어, 검토가 시작된 뒤라면 검수자가 적은 수준이 엉뚱한 말에 붙는다
            raise SystemExit(f"표본 파일이 이미 있습니다: {path} — 검토 중인 표본을 바꾸지 않도록 다시 뽑지 않습니다. 새로 뽑으려면 --force")
        con, source = _connect(a.sqlite)
        sample, missing = draw(checked_terms(con), seed=a.seed)
        save(path, sample)
        print(checklist(sample))
        counts = Counter(r["rule"] for r in sample)
        print(f"\n{len(sample)}개 ({' · '.join(f'{LEVEL_KO[k]} {counts.get(k, 0)}' for k in QUOTAS)}) · {source} · 시드 {a.seed} → {path}")
        if missing:
            print(f"확인된 말 가운데 리스크 판정이 없어 넣지 못한 필수 표현: {', '.join(missing)}")
        return
    if not path.exists():
        raise SystemExit(f"표본 파일이 없습니다: {path} — 먼저 draw 를 실행하세요")
    try:
        res = agreement(load(path))
    except ValueError as e:
        raise SystemExit(str(e)) from None
    print("| 표현 | 규칙 수준(뽑을 때) | 검수자가 정한 수준 | 일치 |\n| --- | --- | --- | --- |")
    for r in res["rows"]:
        human = LEVEL_KO[r["human"]] + (f" ({r['by']})" if r["by"] else "") if r["human"] else "검토 전"
        print(f"| {r['canonical']} | {LEVEL_KO[r['rule']]} | {human} | {'—' if r['agree'] is None else '예' if r['agree'] else '아니오'} |")
    per = " · ".join(f"{LEVEL_KO[k]} {a_}/{n}" for k, (a_, n) in res["by_level"].items() if n)
    print(f"\n일치 {res['agree']}/{res['reviewed']} (표본 {res['total']}개 중 {res['reviewed']}개 검토){' — ' + per if per else ''}")
    if res["confusion"]:
        print("규칙 → 검수자: " + ", ".join(f"{k} {v}" for k, v in res["confusion"].items()))


if __name__ == "__main__":
    main()
