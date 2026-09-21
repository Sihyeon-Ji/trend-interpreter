"""가상 캘린더 — world.py 시뮬레이션에서 '시간이 간 곳'만 투영한다.

다른 두 도구와 결정적으로 다른 점: **과거와 미래를 둘 다 담는다.**

  과거 회의 → "그 2주간 왜 진도가 안 나갔나"에 답한다
  미래 회의 → "앞으로 얼마나 쓸 수 있나"를 계산한다 (capacity.py 의 입력)

읽기 전용 데이터다 — 남의 일정을 만들거나 고치지 않는다.

실행:
  python -m pmo_agent.seeds.calendar            data/calendar_state.json 생성
  python -m pmo_agent.seeds.calendar --print    저장하지 않고 요약만
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import availability as av
from pmo_agent.adapters.memory_calendar import STORE
from pmo_agent.seeds import world as world_mod

HORIZON = world_mod.FWD_DAYS


def build(today: dt.date | None = None, seed_value: int = 20260922) -> dict:
    return world_mod.to_calendar(world_mod.simulate(today, seed_value))


def write(path: str | None = None, today: dt.date | None = None) -> dict:
    data = build(today)
    target = path or STORE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    return {"path": target, "events": len(data["events"]), "planted": len(data["planted"])}


def describe(data: dict, today: dt.date) -> dict:
    avail = av.from_events(data["events"])
    people = sorted({e["attendee"] for e in data["events"]})
    past = [e for e in data["events"] if e["date"] < today.isoformat()]
    return {
        "이벤트": len(data["events"]),
        "과거/미래": f"{len(past)} / {len(data['events']) - len(past)}",
        "기간": f"미래 {data['horizon_days']}영업일",
        "회의 부담": [av.meeting_load(avail, p, today, 10) for p in people],
    }


if __name__ == "__main__":
    today = dt.date.today()
    data = build(today)
    print(json.dumps(describe(data, today), ensure_ascii=False, indent=1))
    if "--print" not in sys.argv:
        result = write(today=today)
        print(f"\n저장: {result['path']}  (이벤트 {result['events']}건)")
        print("사용: CALENDAR_BACKEND=memory 로 두면 capacity 가 이 캘린더를 본다.")
