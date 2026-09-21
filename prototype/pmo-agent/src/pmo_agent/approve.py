"""승인 게이트 — 제안을 사람이 보고 고른 것만 실제로 반영한다.

이 파일이 프로젝트에서 유일하게 approve=True 를 넘기는 곳이다.
Gemini 는 여기를 호출할 수 없다 (DECLARATIONS/REGISTRY 에 올리지 않는다 — test_approve.py 가 이걸
검사한다).
사람이 CLI 에서 번호를 고르는 것만이 승인이다. '전부 승인'도 사용자가 직접 all 을 입력해야 한다.

반영한 것은 logs/approvals.jsonl 에 한 줄씩 남는다 — 무엇을, 언제, 어떤 결과로.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import tools
from pmo_agent.adapters.jira import Jira, WriteBlocked
from pmo_agent.env import logs_dir

LOG = str(logs_dir() / "approvals.jsonl")

# 제안 이름 → 실제 반영 함수. 여기 없는 제안은 반영 대상이 아니다(note 등).
APPLIERS = {
    "propose_field_update": lambda j, a: j.set_fields(
        a["key"], {k: v for k, v in a.items() if k != "key"}, approve=True
    ),
    "propose_transition": lambda j, a: j.transition(a["key"], a["to_status"], approve=True),
    "propose_comment": lambda j, a: j.comment(a["key"], a["text"], approve=True),
}


def describe(p: dict) -> str:
    """제안 한 건을 사람이 읽을 한 줄로."""
    tool, a = p.get("tool", "?"), p.get("args") or {}
    if tool == "propose_field_update":
        bits = ", ".join(f"{k}={v}" for k, v in a.items() if k != "key")
        return f"{a.get('key')}  필드 변경  {bits}"
    if tool == "propose_transition":
        return f"{a.get('key')}  상태 → {a.get('to_status')}"
    if tool == "propose_comment":
        return f'{a.get("key")}  코멘트  "{(a.get("text") or "")[:60]}"'
    if tool == "note":
        return f'(반영 안 함) 메모  "{(a.get("text") or "")[:60]}"'
    return f"{tool}  {json.dumps(a, ensure_ascii=False)[:70]}"


def render(proposals: list, impact: dict | None = None) -> str:
    """승인 화면. 반영 대상만 번호가 붙는다."""
    lines, n = [], 0
    for p in proposals:
        if p.get("tool") in APPLIERS:
            n += 1
            lines.append(f" [{n:>2}] {describe(p)}")
        else:
            lines.append(f"      {describe(p)}")
    if not lines:
        lines.append("      (제안 없음)")
    out = ["제안된 변경 — 아직 아무것도 반영되지 않았습니다", "-" * 62, *lines]
    if impact:
        out += [
            "-" * 62,
            f" 예상 완료일  {impact.get('predicted_finish_before')} → "
            f"{impact.get('predicted_finish_after')}",
            f" 위험 태스크  {impact.get('risks_before')}건 → {impact.get('risks_after')}건",
        ]
        for r in impact.get("newly_at_risk") or []:
            out.append(f"   신규 위험  {r['key']} {r.get('summary', '')}")
    return "\n".join(out)


def appliable(proposals: list) -> list:
    """번호가 붙는(= 실제 반영 가능한) 제안만 순서대로."""
    return [p for p in proposals if p.get("tool") in APPLIERS]


def select(answer: str, count: int) -> list:
    """사용자 입력 → 0-기반 인덱스 목록. 빈 입력·n·q 는 아무것도 고르지 않은 것으로 본다.
    'all' 만이 전체 승인이고, 그 외에는 번호를 직접 적어야 한다."""
    s = (answer or "").strip().lower()
    if s in ("", "n", "no", "q", "quit", "none", "아니오"):
        return []
    if s in ("a", "all", "전부"):
        return list(range(count))
    picked = []
    for chunk in s.replace(" ", ",").split(","):
        if not chunk:
            continue
        if "-" in chunk[1:]:  # 3-5 같은 범위
            a, _, b = chunk.partition("-")
            if a.isdigit() and b.isdigit():
                picked += list(range(int(a), int(b) + 1))
            continue
        if chunk.isdigit():
            picked.append(int(chunk))
    return sorted({i - 1 for i in picked if 1 <= i <= count})


def log(entry: dict) -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def apply(proposals: list, indices, jira: Jira | None = None, source: str = "") -> dict:
    """고른 제안만 실제로 반영한다. 한 건이 실패해도 나머지는 계속한다.

    쓰기 차단(WriteBlocked)은 잡아서 결과에 남긴다 — 실서비스 도메인에 쓰려 한 사고 기록이 필요하다.
    """
    items = appliable(proposals)
    j = jira or tools.jira()
    done, at = [], dt.datetime.now().isoformat(timespec="seconds")
    for i in sorted(set(indices)):
        if not 0 <= i < len(items):
            done.append({"index": i + 1, "ok": False, "error": "없는 번호"})
            continue
        p = items[i]
        rec = {"at": at, "source": source, "tool": p["tool"], "args": p.get("args") or {}}
        try:
            rec["result"] = APPLIERS[p["tool"]](j, p.get("args") or {})
            rec["ok"] = True
        except WriteBlocked as e:
            rec.update(ok=False, error=f"쓰기 차단: {e}", blocked=True)
        except Exception as e:
            rec.update(ok=False, error=str(e)[:300])
        log(rec)
        done.append(
            {
                "index": i + 1,
                "desc": describe(p),
                "ok": rec["ok"],
                **({"error": rec["error"]} if not rec["ok"] else {}),
            }
        )
    return {
        "applied": sum(1 for d in done if d["ok"]),
        "failed": sum(1 for d in done if not d["ok"]),
        "skipped": len(items) - len(done),
        "results": done,
    }


def gate(proposals: list, impact: dict | None = None, source: str = "", ask=input) -> dict:
    """대화형 승인. ask 를 바꿔 끼우면 테스트에서 비대화형으로 돌릴 수 있다."""
    items = appliable(proposals)
    print(render(proposals, impact))
    if not items:
        return {"applied": 0, "failed": 0, "skipped": 0, "results": []}
    print("-" * 62)
    print(" 반영할 번호를 입력하세요 (예: 1,3  또는 1-3). all = 전부, 엔터 = 아무것도 안 함")
    picked = select(ask(" > "), len(items))
    if not picked:
        print(" 아무것도 반영하지 않았습니다.")
        return {"applied": 0, "failed": 0, "skipped": len(items), "results": []}
    where = getattr(tools.jira(), "site", "?")  # jira 사이트 또는 'local'
    print(f"\n 다음을 실제로 반영합니다 (대상: {where}):")
    for i in picked:
        print("   -", describe(items[i]))
    if (ask(" 정말 반영할까요? (yes 입력) ") or "").strip().lower() not in ("yes", "y", "예"):
        print(" 취소했습니다. 반영된 것 없음.")
        return {"applied": 0, "failed": 0, "skipped": len(items), "results": []}
    out = apply(proposals, picked, source=source)
    print(f"\n 반영 {out['applied']}건 / 실패 {out['failed']}건 — 기록: {LOG}")
    for r in out["results"]:
        print(
            ("   OK  " if r["ok"] else "   실패 ")
            + r.get("desc", "")
            + ("" if r["ok"] else f"  ({r.get('error')})")
        )
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    blob = json.load(open(src, encoding="utf-8")) if src else json.load(sys.stdin)
    gate(blob.get("proposals") or [], blob.get("impact"), source=src or "stdin")
