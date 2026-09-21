"""3분 시연 — 하나의 명령으로 전체 루프를 보여준다.

팀 워크플로 문서가 요구하는 '3분 시연 경로'를 스크립트로 고정한 것이다.
매번 같은 순서, 같은 화면이 나오도록 해서 시연이 즉흥에 기대지 않게 한다.

    1. 지금 일정이 어떻게 보이는가        (의존관계 기준)
    2. 사람 용량과 회의 시간을 넣으면 어떻게 바뀌는가  ← 차별점
    3. 무엇을 옮기면 당겨지는가
    4. 보드와 코드를 맞대면 무엇이 보이나   ← 한쪽만으로는 안 보이는 것
    5. 회의 메모 사진을 넣으면            (Gemini 멀티모달)
    6. 무엇이 제안되는가 / 아직 반영 안 됨
    7. 승인해야 반영된다                  (--approve 없으면 여기서 멈춘다)

실행:
  python tools/demo.py                  읽기만 (아무것도 바꾸지 않는다)
  python tools/demo.py --approve        5단계 제안 중 첫 건을 실제 반영까지
  PMO_BACKEND=memory python tools/demo.py   계정 없이 로컬 보드로
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import time

from pmo_agent import approve as approve_mod  # noqa: E402
from pmo_agent import availability as avail_mod
from pmo_agent import capacity, ingest, schedule, signals, tools
from pmo_agent.env import samples_dir
from pmo_agent.llm import LLMError

NOTE = str(samples_dir() / "meeting-note.png")
W = 74


def step(n: int, title: str, why: str = "") -> None:
    print("\n" + "=" * W)
    print(f" {n}. {title}")
    if why:
        print(f"    {why}")
    print("=" * W)


def main(argv) -> int:
    do_approve = "--approve" in argv
    today = dt.date.today()
    t0 = time.time()

    board = tools.jira()
    print(
        f"보드: {getattr(board, 'site', '?')} / {getattr(board, 'project', '?')}"
        f"   ({type(board).__name__})"
    )
    tasks = tools._fetch()
    if not tasks:
        print("태스크가 없다. 먼저 시드를 만들어라:  python data/seed_jira.py --approve")
        return 1

    # ---- 1 ----
    step(1, "지금 일정", "의존관계(Blocks)만 본 계산 — 대부분의 PM 도구가 여기까지 한다")
    s = schedule.summary(tasks, today)
    print(f"  태스크 {s['total']}건 (완료 {s['done']})")
    print(
        f"  예측 완료일 {s['predicted_finish']}   임계경로 {len(s['critical_path'])}건"
        f"   지연 위험 {len(s['risks'])}건"
    )
    for r in s["risks"][:3]:
        print(f"    - {r['key']} {r['summary'][:24]:<24} {r['assignee']}  {r['reasons'][0]}")

    # ---- 2 ----
    step(
        2,
        "제약을 하나씩 더하면",
        "동시에 한 건 + 회의로 먹힌 시간. 어느 도구도 이 둘을 같이 보지 않는다",
    )
    availability = tools._availability()
    c = capacity.summary(tasks, today, availability=availability)
    b = c["bottleneck"]
    print(f"  의존관계만        {c['unconstrained_finish']}")
    if c["calendar_applied"]:
        print(f"  사람 용량 반영    {c['finish_without_meetings']}")
        print(
            f"  회의까지 반영     {c['capacity_finish']}   "
            f"(+{c['slip_vs_unconstrained']}영업일, 이 중 회의가 {c['meeting_slip_days']}일)"
        )
    else:
        print(f"  용량까지 반영     {c['capacity_finish']}   (+{c['slip_vs_unconstrained']}영업일)")
    if b:
        print(f"\n  병목: {b['assignee']} — 남은 {b['busy_days']}영업일, 가동률 {b['utilization']}")
        print(f"        이 사람이 비는 {b['free_at']}가 프로젝트의 하한선이다")
    if availability:
        print("\n  회의로 잃는 시간 (앞으로 10영업일):")
        for who in sorted({t.assignee for t in tasks.values() if t.assignee}):
            m = avail_mod.meeting_load(availability, who, today, 10)
            print(f"    - {who}  회의 {m['lost_hours']}시간 → 실가용 {m['available_days']}/10일")

    print("\n  선행은 끝났는데 담당자가 바빠서 기다리는 태스크:")
    for w in c["waiting_tasks"][:3]:
        print(
            f"    - {w['key']} {w['summary'][:24]:<24} {w['assignee']}  {w['waiting_days']}일 대기"
        )

    # ---- 3 ----
    step(3, "무엇을 옮기면 당겨지는가", "제안만 한다. 실제 이동은 사람이 정한다")
    rb = capacity.rebalance(tasks, today, max_moves=3, availability=availability)
    if rb["moves"]:
        print(
            f"  {len(rb['moves'])}건 이동 → {rb['before']} → {rb['after']} "
            f"({rb['gain_days']}영업일 단축)"
        )
        for m in rb["moves"]:
            print(
                f"    - {m['key']} {m['summary'][:24]:<24} {m['from']} → {m['to']}  "
                f"{m['gain_days']}일"
            )
    else:
        print("  옮겨서 당길 수 있는 태스크가 없다")

    # ---- 3.5 ----
    step(4, "보드와 코드를 맞대면", "한쪽만 봐서는 안 보이는 것 — 일정 계산과는 다른 종류의 신호")
    try:
        sig = signals.summary(tasks, tools.repo().snapshot(100), today)
        t = sig["team"]
        print(
            f"  저장소 {sig['repo']}  최근 {t['window_days']}일 커밋 {t['commits']}건, "
            f"집중도 {t['concentration']}, 열린 PR {t['open_prs']}건"
        )
        for n in t["notes"][:3]:
            print(f"    · {n}")
        if sig["note"]:
            print(f"    · {sig['note']}")
        for m in sig["mismatches"][:4]:
            print(f"    - {m['key']:<9} [{m['kind']}] {m['detail']}")
    except Exception as e:
        print(f"  (저장소를 읽지 못했다: {str(e)[:90]})")

    # ---- 4 ----
    step(5, "회의 메모 사진", "Gemini 멀티모달 — 모델은 '읽기'만 하고 판정은 코드가 한다")
    if not os.path.exists(NOTE):
        print("  샘플 메모가 없다. 먼저:  python tools/make_note.py")
        return 1
    print(f"  입력: {os.path.relpath(NOTE)}  ({os.path.getsize(NOTE) // 1024}KB)")
    try:
        r = ingest.ingest("", [NOTE], tasks=tasks, today=today)
    except LLMError as e:
        print(f"  모델 호출 실패: {str(e)[:160]}")
        return 1

    # ---- 5 ----
    step(6, "읽어낸 변경", "applied=false — 아직 아무것도 반영되지 않았다")
    for x in r["resolved"]:
        what = (
            f"마감 {x.get('duedate_was')} → {x['duedate']}"
            if x.get("duedate")
            else f"상태 → {x['status']}"
            if x.get("status")
            else "코멘트"
        )
        print(f"    {x['key']:<9} {x['summary'][:24]:<24} {what}  (확신 {x['confidence']})")
    for n in r["notes"]:
        print(f"    (메모)    {n}")
    for q in r["questions"]:
        print(f"    (질문)    {q}")
    if r["impact"]:
        i = r["impact"]
        print(
            f"\n  반영 시: 예상 완료 {i['predicted_finish_before']} → "
            f"{i['predicted_finish_after']}, "
            f"위험 {i['risks_before']}건 → {i['risks_after']}건"
        )

    # ---- 6 ----
    step(7, "승인", "쓰기는 사람이 고른 것만. 모델은 이 단계를 호출할 수 없다")
    print(approve_mod.render(r["proposals"], r["impact"]))
    items = approve_mod.appliable(r["proposals"])
    if not do_approve:
        print("\n  (읽기 전용 시연이다. 실제 반영까지 보려면 --approve 를 붙여라)")
    elif not items:
        print("\n  반영할 제안이 없다")
    else:
        print(f"\n  1번만 반영한다 → {approve_mod.describe(items[0])}")
        out = approve_mod.apply(r["proposals"], [0], source="demo")
        print(f"  반영 {out['applied']}건 / 실패 {out['failed']}건 — 기록: {approve_mod.LOG}")

    print(
        f"\n{'=' * W}\n  소요 {time.time() - t0:.1f}초. 숫자는 전부 schedule.py / capacity.py 가 "
        f"계산했다.\n{'=' * W}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
