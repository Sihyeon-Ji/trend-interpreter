"""자원 제약 스케줄링 — 사람이 동시에 여러 건을 못 한다는 사실을 일정에 반영한다.

schedule.py 의 forecast() 는 의존관계만 본다. 그래서 한 사람이 8건을 동시에 진행한다고 가정하고,
'총 38영업일치를 들고 있는 사람'이 있어도 프로젝트가 22일 만에 끝난다고 답한다.
이 모듈은 담당자별 처리 용량(기본 1건 동시)을 넣어 '실제로 가능한' 완료일을 낸다.

방식: 직렬 일정 생성(serial SGS). 선행이 모두 끝난 태스크 중 여유(slack)가 적은 것부터
      담당자가 비는 시점에 붙인다. 표준 휴리스틱이고, 전부 결정론적이라 같은 입력이면 같은 답이
      나온다.

이 모듈도 Jira 를 모른다. schedule.Task 만 받는다.
"""

from __future__ import annotations

import datetime as _dt

from pmo_agent import availability as avail_mod
from pmo_agent import schedule

DEFAULT_CAPACITY = 1  # 한 사람이 동시에 잡는 태스크 수
UNASSIGNED = "(미배정)"


def _caps(tasks: dict, capacity) -> dict:
    """담당자 → 동시 처리 가능 건수."""
    people = {t.assignee or UNASSIGNED for t in tasks.values()}
    if isinstance(capacity, int):
        return {p: max(1, capacity) for p in people}
    out = {p: DEFAULT_CAPACITY for p in people}
    out.update({k: max(1, v) for k, v in (capacity or {}).items() if k in people})
    return out


def levelled(
    tasks: dict, today: _dt.date, capacity=None, holidays=(), availability: dict | None = None
) -> dict:
    """자원 제약을 넣은 완료 예측.

    반환: project_finish(실현 가능 완료일), unconstrained_finish(기존 예측), tasks, resources,
    bottleneck.
    tasks[key].waiting_days = 선행은 끝났는데 담당자가 바빠서 기다린 영업일 — 순수한 용량 손실이다.

    availability 를 주면 회의로 먹힌 시간을 반영한다 ({사람: {ISO날짜: 가용률}}).
    가용률 0.5 인 날이 이어지면 1일치 작업이 이틀을 먹는다. 주지 않으면 전원 1.0 으로 본다.
    """
    order = schedule.topo_order(tasks)  # 순환이면 여기서 CycleError
    caps = _caps(tasks, capacity)
    cpm = schedule.cpm(tasks, today, holidays)["tasks"]
    # 담당자마다 '슬롯' 몇 개, 슬롯마다 이미 잡힌 구간 목록. 새 태스크는 빈 구간에 끼워 넣는다.
    # (단순히 마지막 종료시각 뒤에 붙이면, 늦게 시작하는 태스크가 슬롯을 선점해 앞쪽이 통째로 빈다.)
    slots: dict[str, list[list[tuple[float, float]]]] = {
        p: [[] for _ in range(n)] for p, n in caps.items()
    }
    finish: dict[str, float] = {}
    rows: dict[str, dict] = {}
    busy = {p: 0.0 for p in caps}
    pending = set(order)

    # 가용률 표를 영업일 오프셋으로 펼쳐 둔다. 지평선은 전체 작업량 + 여유.
    horizon = int(sum(t.remaining for t in tasks.values()) * 2) + 60
    rates = avail_mod.table(availability, set(caps), today, horizon, holidays)

    def place(intervals: list, ready: float, work: float, who: str) -> tuple[float, float]:
        """ready 이후로, work 만큼이 통째로 들어가는 가장 이른 (시작, 끝).

        끝 지점은 가용률에 따라 달라진다 — 회의가 많은 구간에 걸치면 그만큼 뒤로 밀린다.
        그래서 '시작을 정하고 끝을 계산 → 겹치면 시작을 옮긴다'를 반복한다.
        """
        t = ready
        for _ in range(len(intervals) + 2):
            end = avail_mod.span_end(rates[who], t, work)
            clash = next(
                (iv for iv in sorted(intervals) if iv[0] < end - 1e-9 and iv[1] > t + 1e-9), None
            )
            if clash is None:
                return t, end
            t = clash[1]
        return t, avail_mod.span_end(rates[who], t, work)

    def priority(k):  # 여유 적은 순 → 마감 빠른 순 → 키 순
        t = tasks[k]
        return (cpm[k]["slack_days"], t.duedate or _dt.date.max, k)

    while pending:
        eligible = [k for k in pending if all(d in finish for d in tasks[k].deps)]
        if not eligible:  # topo_order 가 통과했으면 일어나지 않는다
            raise schedule.CycleError("일정을 진행할 수 없다: " + ", ".join(sorted(pending)))
        k = min(eligible, key=priority)
        pending.discard(k)
        t = tasks[k]
        who = t.assignee or UNASSIGNED
        dep_ready = max([finish[d] for d in t.deps], default=0.0)
        if t.remaining <= 0:  # 완료된 태스크는 사람을 쓰지 않는다
            start = end = dep_ready
        else:
            fits = [(*place(iv, dep_ready, t.remaining, who), i) for i, iv in enumerate(slots[who])]
            start, end, slot = min(fits)
            slots[who][slot].append((start, end))
            busy[who] += t.remaining
        finish[k] = end
        rows[k] = {
            "key": k,
            "summary": t.summary,
            "assignee": t.assignee,
            "status": t.status,
            "remaining_days": round(t.remaining, 2),
            "start": schedule.add_workdays(today, start, holidays),
            "finish": schedule.add_workdays(today, finish[k], holidays),
            "waiting_days": round(max(0.0, start - dep_ready), 2),
            "duedate": t.duedate,
            "late": bool(
                t.duedate and schedule.add_workdays(today, finish[k], holidays) > t.duedate
            ),
        }

    total = max(finish.values(), default=0.0)
    plain = schedule.forecast(tasks, today, holidays)
    resources = sorted(
        (
            {
                "assignee": p,
                "capacity": caps[p],
                "busy_days": round(busy[p], 1),
                "lost_to_meetings": (
                    avail_mod.meeting_load(availability, p, today)["lost_days"]
                    if availability
                    else 0.0
                ),
                "free_at": schedule.add_workdays(
                    today, max([e for iv in slots[p] for _, e in iv] or [0.0]), holidays
                ),
                "utilization": round(busy[p] / total, 2) if total else 0.0,
            }
            for p in caps
            if busy[p] > 0
        ),
        key=lambda r: -r["busy_days"],
    )
    return {
        "project_finish": schedule.add_workdays(today, total, holidays),
        "unconstrained_finish": plain["project_finish"],
        "slip_vs_unconstrained": schedule.workdays_between(
            plain["project_finish"], schedule.add_workdays(today, total, holidays), holidays
        ),
        "duration_days": int(round(total)),
        "tasks": rows,
        "resources": resources,
        "bottleneck": resources[0] if resources else None,
        "waiting_total": round(sum(r["waiting_days"] for r in rows.values()), 1),
    }


def blocked_by_people(result: dict, top: int = 5) -> list:
    """의존성이 아니라 '담당자가 바빠서' 기다리는 태스크 — 자원 제약의 직접 증거."""
    rows = [r for r in result["tasks"].values() if r["waiting_days"] > 0]
    return sorted(rows, key=lambda r: -r["waiting_days"])[:top]


def _copy(tasks: dict) -> dict:
    return {k: schedule.Task(**dict(t.__dict__)) for k, t in tasks.items()}


def rebalance(
    tasks: dict,
    today: _dt.date,
    capacity=None,
    max_moves: int = 3,
    holidays=(),
    availability: dict | None = None,
) -> dict:
    """병목 담당자의 태스크를 다른 사람에게 옮겨 완료일을 당길 수 있는지 탐색한다.

    탐욕적으로 한 건씩, 가장 많이 당겨지는 이동을 고른다. 제안일 뿐 반영하지 않는다.
    완료된 태스크와 이미 시작한 태스크(progress>0)는 옮기지 않는다 — 현실적으로 인계가 어렵다.
    """
    base = levelled(tasks, today, capacity, holidays, availability)
    cur, moves = _copy(tasks), []
    best = base
    people = sorted({t.assignee for t in tasks.values() if t.assignee})
    for _ in range(max_moves):
        b = best.get("bottleneck")
        if not b or len(people) < 2:
            break
        movable = [
            k
            for k, t in cur.items()
            if t.assignee == b["assignee"] and not t.is_done and t.progress <= 0
        ]
        found = None
        for k in movable:
            for other in people:
                if other == b["assignee"]:
                    continue
                trial = _copy(cur)
                trial[k].assignee = other
                r = levelled(trial, today, capacity, holidays, availability)
                gain = schedule.workdays_between(
                    r["project_finish"], best["project_finish"], holidays
                )
                if gain > 0 and (found is None or gain > found["gain_days"]):
                    found = {
                        "key": k,
                        "summary": cur[k].summary,
                        "from": b["assignee"],
                        "to": other,
                        "gain_days": gain,
                        "new_finish": r["project_finish"],
                        "_tasks": trial,
                        "_res": r,
                    }
        if not found:
            break
        cur, best = found.pop("_tasks"), found.pop("_res")
        moves.append(found)
    return {
        "before": base["project_finish"],
        "after": best["project_finish"],
        "gain_days": schedule.workdays_between(
            best["project_finish"], base["project_finish"], holidays
        ),
        "moves": moves,
        "resources_before": base["resources"],
        "resources_after": best["resources"],
    }


def summary(
    tasks: dict, today: _dt.date, capacity=None, holidays=(), availability: dict | None = None
) -> dict:
    """리포트·툴에서 그대로 쓸 수 있는 한 덩어리 (날짜는 ISO 문자열).

    캘린더를 주면 세 값이 나란히 나온다 — 각 제약이 며칠씩 더하는지 보이게 하기 위해서다:
      의존관계만  <  사람 용량까지  <  회의까지
    """
    r = levelled(tasks, today, capacity, holidays, availability)
    # 회의를 빼면 얼마였는지도 같이 낸다. 그래야 '회의 때문에 며칠'이 분리된다.
    no_cal = levelled(tasks, today, capacity, holidays, None) if availability else r
    meeting_slip = schedule.workdays_between(
        no_cal["project_finish"], r["project_finish"], holidays
    )
    return schedule.iso(
        {
            "today": today,
            "unconstrained_finish": r["unconstrained_finish"],
            "capacity_finish": r["project_finish"],
            "finish_without_meetings": no_cal["project_finish"],
            "meeting_slip_days": meeting_slip,
            "calendar_applied": bool(availability),
            "slip_vs_unconstrained": r["slip_vs_unconstrained"],
            "waiting_total_days": r["waiting_total"],
            "bottleneck": r["bottleneck"],
            "resources": r["resources"],
            "waiting_tasks": blocked_by_people(r),
        }
    )
