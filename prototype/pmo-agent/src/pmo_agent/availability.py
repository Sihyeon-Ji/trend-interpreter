"""가용 시간 — 회의에 먹힌 시간을 빼고 실제로 일할 수 있는 양을 계산한다.

capacity.py 는 지금까지 "영업일 하루 = 온전히 하루 작업"이라고 가정했다.
현실은 회의·다른 프로젝트로 절반이 날아간다. 그 데이터는 보드에도 저장소에도 없고 캘린더에만 있다.

여기서 다루는 값은 하나다: **가용률** — 어떤 사람의 어떤 날, 프로젝트 작업에 쓸 수 있는 비율(0~1).

    회의 4시간 / 8시간 근무  →  가용률 0.5  →  하루짜리 태스크가 이틀 걸린다

이 모듈은 캘린더 API 를 모른다. {사람: {날짜: 회의시간}} 만 받는다 —
어댑터(MS Graph · 로컬)가 그 모양으로 맞춰 준다.
"""

from __future__ import annotations

import datetime as _dt

WORKDAY_HOURS = 8.0
MIN_FRACTION = 0.05  # 회의로 가득 찬 날도 완전히 0 으로 두지 않는다 (0 이면 일정이 무한히 밀린다)


def fraction_from_hours(meeting_hours: float, workday_hours: float = WORKDAY_HOURS) -> float:
    """회의 시간 → 그 날의 가용률. 근무시간을 넘겨도 0 밑으로는 내려가지 않는다."""
    if workday_hours <= 0:
        return 0.0
    free = (workday_hours - max(0.0, meeting_hours)) / workday_hours
    return max(MIN_FRACTION, min(1.0, free))


def from_busy_hours(busy: dict, workday_hours: float = WORKDAY_HOURS) -> dict:
    """{사람: {ISO날짜: 회의시간}} → {사람: {ISO날짜: 가용률}}."""
    return {
        who: {day: fraction_from_hours(hours, workday_hours) for day, hours in days.items()}
        for who, days in (busy or {}).items()
    }


def from_events(events, workday_hours: float = WORKDAY_HOURS) -> dict:
    """캘린더 이벤트 목록 → 가용률 표.

    이벤트 한 건: {"attendee": 이름, "date": "YYYY-MM-DD", "hours": 1.5}
    종일 일정은 hours 를 근무시간 전체로 넣으면 된다.
    같은 날 여러 건은 합산한다 — 겹치는 회의는 어댑터가 정리해서 넘긴다.
    """
    busy: dict[str, dict[str, float]] = {}
    for e in events or []:
        who = (e.get("attendee") or "").strip()
        day = (e.get("date") or "")[:10]
        if not who or not day:
            continue
        busy.setdefault(who, {})[day] = busy.setdefault(who, {}).get(day, 0.0) + float(
            e.get("hours") or 0.0
        )
    return from_busy_hours(busy, workday_hours)


def table(
    availability: dict | None,
    people,
    today: _dt.date,
    horizon: int,
    holidays=(),
) -> dict:
    """날짜 문자열 대신 '오늘부터 몇 번째 영업일'로 찾을 수 있게 펼친다.

    스케줄러는 영업일 오프셋으로 돌아가므로, 매번 날짜를 만들지 않도록 미리 풀어 둔다.
    캘린더에 없는 날은 1.0(온전히 가용)으로 본다 — 모르는 것을 '바쁘다'로 치지 않는다.
    """
    from pmo_agent import schedule

    days = [schedule.add_workdays(today, i, holidays).isoformat() for i in range(horizon + 1)]
    out: dict[str, list[float]] = {}
    for who in people:
        per_day = (availability or {}).get(who, {})
        out[who] = [float(per_day.get(d, 1.0)) for d in days]
    return out


def span_end(rates: list, start: float, work: float) -> float:
    """start(영업일 오프셋)에서 work(온전한 영업일 기준 작업량)를 소화하는 끝 지점.

    가용률이 낮은 날은 그만큼 오래 걸린다. 가용률 0.5 인 날이 이어지면 1일치 작업이 2일을 먹는다.
    """
    if work <= 1e-9:
        return start
    pos, remaining = start, work
    limit = len(rates)
    while remaining > 1e-9:
        day = int(pos)
        if day >= limit:  # 지평선을 넘으면 그 뒤는 온전히 가용한 것으로 본다
            return pos + remaining
        rate = rates[day]
        left_today = (1.0 - (pos - day)) * rate
        if rate > 0 and left_today >= remaining - 1e-9:
            return pos + remaining / rate
        remaining -= max(0.0, left_today)
        pos = day + 1
    return pos


def meeting_load(availability: dict | None, who: str, today: _dt.date, days: int = 10) -> dict:
    """앞으로 N영업일 동안 이 사람이 회의로 잃는 양. 리포트에서 근거로 쓴다."""
    from pmo_agent import schedule

    per_day = (availability or {}).get(who, {})
    lost = 0.0
    for i in range(days):
        d = schedule.add_workdays(today, i).isoformat()
        lost += 1.0 - float(per_day.get(d, 1.0))
    return {
        "assignee": who,
        "window_days": days,
        "lost_days": round(lost, 1),
        "lost_hours": round(lost * WORKDAY_HOURS, 1),
        "available_days": round(days - lost, 1),
    }
