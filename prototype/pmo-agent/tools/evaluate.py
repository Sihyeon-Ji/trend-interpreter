"""평가 케이스 실행 — 세계가 심어 둔 것을 엔진이 찾아내는지, 그리고 없는 것을 지어내지 않는지.

두 종류를 본다:

  detect     세계에 일부러 심어 둔 상황을 찾아내는가 (성공 케이스)
  restraint  근거가 없을 때 침묵하는가, 승인 없이 쓰지 않는가 (실패·엣지 케이스)

두 번째가 더 중요하다. 못 찾는 것은 아쉬운 정도지만, 없는 것을 있다고 하거나
승인 없이 쓰는 것은 신뢰를 통째로 잃는다.

정답지는 하드코딩하지 않는다. 태스크 키는 날짜에 따라 달라지므로
`world.truths` 에서 그때그때 찾아 쓴다.

실행:
  python tools/evaluate.py          결과 표
  python tools/evaluate.py --json   기계가 읽을 형태
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

from pmo_agent import approve as approve_mod
from pmo_agent import availability as av
from pmo_agent import capacity, ingest, schedule, signals
from pmo_agent.seeds import world as world_mod

CASES = Path(__file__).resolve().parents[1] / "evaluation-cases" / "cases.jsonl"


def _setup(today: dt.date):
    world = world_mod.simulate(today)
    projected = world_mod.project(world)
    tasks = schedule.from_jira_issues(projected["board"]["issues"])
    avail = av.from_events(projected["calendar"]["events"])
    return world, projected, tasks, avail


def _truth(projected: dict, kind: str) -> dict | None:
    return next((t for t in projected["truths"] if t["kind"] == kind), None)


# ---------- 검출 ----------
def risk_contains_truth(ctx, case) -> tuple:
    truth = _truth(ctx["projected"], case["truth"])
    if not truth:
        return False, "정답지에 해당 항목이 없다"
    risks = {r["key"] for r in schedule.risks(ctx["tasks"], ctx["today"])}
    key = truth["key"]
    return key in risks, f"{key} {'포함' if key in risks else '누락'} (위험 {len(risks)}건)"


def signals_mismatch(ctx, case) -> tuple:
    truth = _truth(ctx["projected"], case["truth"])
    if not truth:
        return False, "정답지에 해당 항목이 없다"
    found = {(m["key"], m["kind"]) for m in ctx["signals"]["mismatches"]}
    hit = (truth["key"], case["truth"]) in found
    return hit, f"{truth['key']} / {case['truth']} {'검출' if hit else '미검출'}"


def meeting_top(ctx, case) -> tuple:
    truth = _truth(ctx["projected"], case["truth"])
    if not truth:
        return False, "정답지에 해당 항목이 없다"
    people = {t.assignee for t in ctx["tasks"].values() if t.assignee}
    loads = {p: av.meeting_load(ctx["avail"], p, ctx["today"], 10)["lost_hours"] for p in people}
    top = max(loads, key=lambda p: loads[p])
    return top == truth["assignee"], f"기대 {truth['assignee']} / 계산 {top} ({loads[top]}시간)"


# ---------- 절제 ----------
def silent_without_keys(ctx, _case) -> tuple:
    """커밋 메시지에 태스크 키가 없는 저장소 — 태스크 단위 경고를 내면 안 된다."""
    snapshot = {
        "repo": "x/y",
        "commits": [
            {**c, "message": "리팩터링", "sha": c["sha"]}
            for c in ctx["projected"]["repo"]["commits"][:10]
        ],
        "pulls": [],
        "branches": ["main"],
    }
    result = signals.summary(ctx["tasks"], snapshot, ctx["today"])
    quiet = not result["mismatches"] and bool(result["note"])
    return (
        quiet,
        f"불일치 {len(result['mismatches'])}건, 안내 {'있음' if result['note'] else '없음'}",
    )


def cycle_returns_error(ctx, _case) -> tuple:
    """순환 의존 — 예외로 죽지 않고 오류를 돌려줘야 한다."""
    tasks = schedule.to_tasks([{"key": "A", "deps": ["B"]}, {"key": "B", "deps": ["A"]}])
    try:
        capacity.levelled(tasks, ctx["today"])
        return False, "순환인데 계산이 통과했다"
    except schedule.CycleError as e:
        return True, f"CycleError 로 거부: {str(e)[:40]}"
    except Exception as e:  # 다른 예외로 죽으면 실패
        return False, f"예상 밖 예외: {type(e).__name__}"


def invented_key_unresolved(ctx, _case) -> tuple:
    """모델이 지어낸 키 — 반영하지 않고 질문으로 떨어뜨려야 한다."""
    extraction = {"updates": [{"task": "ECHO-9999", "duedate": "2026-12-01"}]}
    result = ingest.validate(extraction, ctx["tasks"], ctx["today"])
    ok = not result["resolved"] and result["unresolved"] and result["questions"]
    return bool(ok), f"반영 {len(result['resolved'])}건, 질문 {len(result['questions'])}건"


class _Recorder:
    """쓰기 호출을 받아 기록만 한다. 실제로 나가는 것이 있는지 보기 위한 스텁."""

    def __init__(self):
        self.calls: list = []

    def comment(self, key, text, approve=False):
        self.calls.append((key, approve))
        return {"ok": True}


def approval_required(ctx, _case) -> tuple:
    """승인 없이는 아무것도 나가면 안 된다.

    '고르지 않으면 반영 0건'과 '고르면 approve=True 로 나간다'를 각각 따로 본다 —
    한 스텁으로 둘 다 받으면 앞선 호출이 뒤 검사를 오염시킨다.
    """
    proposals = [{"tool": "propose_comment", "args": {"key": "ECHO-1", "text": "확인 요청"}}]
    skipped, chosen = _Recorder(), _Recorder()
    empty = approve_mod.apply(proposals, [], jira=skipped, source="eval")
    picked = approve_mod.apply(proposals, [0], jira=chosen, source="eval")
    ok = (
        empty["applied"] == 0
        and not skipped.calls  # 고르지 않았으면 호출 자체가 없어야 한다
        and picked["applied"] == 1
        and chosen.calls
        and chosen.calls[0][1] is True  # 고른 것만 approve=True 로 나간다
    )
    _ = ctx
    return bool(ok), (
        f"미선택 호출 {len(skipped.calls)}건 / 선택 반영 {picked['applied']}건"
        f" (approve={chosen.calls[0][1] if chosen.calls else '-'})"
    )


def calendar_absence_declared(ctx, _case) -> tuple:
    """캘린더가 없으면 회의를 반영했다고 말하면 안 된다."""
    result = capacity.summary(ctx["tasks"], ctx["today"], availability=None)
    ok = (
        result["calendar_applied"] is False
        and result["meeting_slip_days"] == 0
        and result["capacity_finish"] == result["finish_without_meetings"]
    )
    return (
        ok,
        f"calendar_applied={result['calendar_applied']}, 회의 {result['meeting_slip_days']}일",
    )


CHECKS = {
    "risk_contains_truth": risk_contains_truth,
    "signals_mismatch": signals_mismatch,
    "meeting_top": meeting_top,
    "silent_without_keys": silent_without_keys,
    "cycle_returns_error": cycle_returns_error,
    "invented_key_unresolved": invented_key_unresolved,
    "approval_required": approval_required,
    "calendar_absence_declared": calendar_absence_declared,
}


def load_cases(path: Path | None = None) -> list:
    text = (path or CASES).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def run(today: dt.date | None = None, path: Path | None = None) -> list:
    today = today or dt.date.today()
    # 평가는 실제 감사 로그를 건드리지 않는다 — 승인 기록은 진짜 반영만 남아야 한다
    keep_log = approve_mod.LOG
    approve_mod.LOG = str(Path(tempfile.mkdtemp(prefix="eval-")) / "approvals.jsonl")
    world, projected, tasks, avail = _setup(today)
    ctx = {
        "today": today,
        "world": world,
        "projected": projected,
        "tasks": tasks,
        "avail": avail,
        "signals": signals.summary(tasks, projected["repo"], today),
    }
    rows = []
    for case in load_cases(path):
        check = CHECKS.get(case["check"])
        if check is None:
            rows.append({**case, "passed": False, "detail": f"알 수 없는 검사: {case['check']}"})
            continue
        try:
            passed, detail = check(ctx, case)
        except Exception as e:  # 검사 자체가 터지는 것도 실패다
            passed, detail = False, f"{type(e).__name__}: {str(e)[:60]}"
        rows.append({**case, "passed": bool(passed), "detail": detail})
    approve_mod.LOG = keep_log
    return rows


def main(argv: list) -> int:
    rows = run()
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0 if all(r["passed"] for r in rows) else 1

    for group, label in (
        ("detect", "검출 — 심어 둔 것을 찾아내는가"),
        ("restraint", "절제 — 없는 것을 지어내지 않는가"),
    ):
        print(f"\n{label}")
        print("-" * 78)
        for row in [r for r in rows if r["group"] == group]:
            mark = "OK  " if row["passed"] else "FAIL"
            print(f"  {mark} {row['id']:<30} {row['detail']}")
    passed = sum(1 for r in rows if r["passed"])
    print(f"\n{'=' * 78}\n  {passed}/{len(rows)} 통과\n{'=' * 78}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
