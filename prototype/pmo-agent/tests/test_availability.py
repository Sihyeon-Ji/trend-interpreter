"""가용 시간 테스트 — 회의가 일정에 실제로 반영되는지.

핵심 관심사 셋:
  1. 회의 시간이 가용률로 정확히 환산되는가
  2. 가용률이 낮으면 태스크가 그만큼 오래 걸리는가
  3. 캘린더가 없을 때 예전과 똑같이 동작하는가 (있는 기능을 깨지 않았는가)

실행: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile

import pytest

from pmo_agent import availability as av
from pmo_agent import capacity, schedule
from pmo_agent.adapters.memory_calendar import MemoryCalendar
from pmo_agent.seeds import calendar as cal_seed

TODAY = dt.date(2026, 9, 21)  # 월요일


def solo(n=2, points=5, who="갑"):
    return schedule.to_tasks(
        [
            {"key": f"T{i}", "summary": f"작업{i}", "assignee": who, "points": points}
            for i in range(1, n + 1)
        ]
    )


def busy(who, hours, days=20, today=TODAY):
    return {who: {schedule.add_workdays(today, i).isoformat(): hours for i in range(days)}}


class TestFraction:
    def test_회의가_없으면_온전히_가용하다(self):
        assert av.fraction_from_hours(0) == 1.0

    def test_절반을_회의에_쓰면_절반만_남는다(self):
        assert av.fraction_from_hours(4, 8) == 0.5

    def test_하루를_통째로_먹혀도_0으로_두지_않는다(self):
        # 0 이면 그 사람의 일정이 무한히 밀린다 — 최소값을 남긴다
        assert av.fraction_from_hours(8, 8) == av.MIN_FRACTION
        assert av.fraction_from_hours(99, 8) == av.MIN_FRACTION

    def test_음수_시간은_무시한다(self):
        assert av.fraction_from_hours(-3) == 1.0


class TestConversion:
    def test_회의시간_표를_가용률로_바꾼다(self):
        out = av.from_busy_hours({"갑": {"2026-09-21": 2.0}})
        assert out["갑"]["2026-09-21"] == 0.75

    def test_같은_날_여러_건은_합산한다(self):
        events = [
            {"attendee": "갑", "date": "2026-09-21", "hours": 1.0},
            {"attendee": "갑", "date": "2026-09-21", "hours": 3.0},
        ]
        assert av.from_events(events)["갑"]["2026-09-21"] == 0.5

    def test_사람이나_날짜가_비면_버린다(self):
        assert av.from_events([{"attendee": "", "date": "2026-09-21", "hours": 1}]) == {}
        assert av.from_events([{"attendee": "갑", "date": "", "hours": 1}]) == {}

    def test_빈_입력도_처리한다(self):
        assert av.from_events([]) == {}
        assert av.from_busy_hours(None) == {}


class TestSpan:
    def test_온전히_가용하면_작업량만큼_걸린다(self):
        assert av.span_end([1.0] * 10, 0.0, 3.0) == pytest.approx(3.0)

    def test_절반만_가용하면_두_배_걸린다(self):
        assert av.span_end([0.5] * 10, 0.0, 3.0) == pytest.approx(6.0)

    def test_하루만_바쁘면_그_날만큼_밀린다(self):
        rates = [1.0, 0.0, 1.0, 1.0, 1.0]
        assert av.span_end(rates, 0.0, 2.0) == pytest.approx(3.0)

    def test_작업량이_0이면_제자리(self):
        assert av.span_end([1.0] * 5, 2.0, 0.0) == 2.0

    def test_지평선을_넘으면_온전히_가용한_것으로_본다(self):
        # 표에 있는 2일은 0.5 씩 = 1.0 소화, 남은 4.0 은 온전히 가용 → 2 + 4 = 6
        assert av.span_end([0.5, 0.5], 0.0, 5.0) == pytest.approx(6.0)


class TestMeetingLoad:
    def test_잃은_시간을_일과_시간으로_준다(self):
        load = av.meeting_load(av.from_busy_hours(busy("갑", 4.0)), "갑", TODAY, 10)
        assert load["lost_days"] == 5.0
        assert load["lost_hours"] == 40.0
        assert load["available_days"] == 5.0

    def test_캘린더에_없는_사람은_온전히_가용하다(self):
        assert av.meeting_load({}, "을", TODAY, 10)["lost_days"] == 0.0


class TestSchedulerIntegration:
    def test_캘린더가_없으면_예전과_같다(self):
        tasks = solo(2, points=5)
        before = capacity.levelled(tasks, TODAY)
        after = capacity.levelled(tasks, TODAY, availability=None)
        assert before["project_finish"] == after["project_finish"]

    def test_회의가_많으면_완료일이_밀린다(self):
        tasks = solo(2, points=5)
        plain = capacity.levelled(tasks, TODAY)
        heavy = capacity.levelled(tasks, TODAY, availability=av.from_busy_hours(busy("갑", 4.0)))
        assert heavy["project_finish"] > plain["project_finish"]

    def test_절반_가용이면_기간이_두_배쯤_된다(self):
        tasks = solo(1, points=4)
        plain = schedule.workdays_between(TODAY, capacity.levelled(tasks, TODAY)["project_finish"])
        half = schedule.workdays_between(
            TODAY,
            capacity.levelled(tasks, TODAY, availability=av.from_busy_hours(busy("갑", 4.0)))[
                "project_finish"
            ],
        )
        assert half == plain * 2

    def test_다른_사람_회의는_영향이_없다(self):
        tasks = solo(2, points=5, who="갑")
        same = capacity.levelled(tasks, TODAY, availability=av.from_busy_hours(busy("을", 6.0)))
        assert same["project_finish"] == capacity.levelled(tasks, TODAY)["project_finish"]

    def test_회의로_잃은_양을_자원_정보에_싣는다(self):
        tasks = solo(2, points=5)
        r = capacity.levelled(tasks, TODAY, availability=av.from_busy_hours(busy("갑", 2.0)))
        assert r["resources"][0]["lost_to_meetings"] > 0

    def test_재배치도_가용률을_본다(self):
        tasks = schedule.to_tasks(
            [{"key": f"T{i}", "assignee": "갑", "points": 5} for i in range(1, 5)]
            + [{"key": "Z", "assignee": "을", "points": 1}]
        )
        r = capacity.rebalance(
            tasks, TODAY, max_moves=2, availability=av.from_busy_hours(busy("갑", 4.0))
        )
        assert r["gain_days"] > 0
        assert r["moves"][0]["from"] == "갑"


class TestMemoryCalendar:
    def setup_method(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "cal.json")
        cal_seed.write(self.path, TODAY)
        self.cal = MemoryCalendar(self.path)

    def teardown_method(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_이벤트를_날짜순으로_준다(self):
        days = [e["date"] for e in self.cal.events(20)]
        assert days == sorted(days)

    def test_사람으로_거른다(self):
        who = self.cal.events(20)[0]["attendee"]
        assert all(e["attendee"] == who for e in self.cal.events(20, attendee=who))

    def test_회의시간_표를_준다(self):
        table = self.cal.busy_hours(20)
        assert table
        assert all(isinstance(v, dict) for v in table.values())

    def test_쓰기_메서드가_없다(self):
        for name in ("create_event", "delete", "update", "set_fields"):
            assert not hasattr(self.cal, name), name

    def test_파일이_없어도_깨지지_않는다(self):
        assert MemoryCalendar(os.path.join(self.dir, "없음.json")).events() == []


class TestCalendarSeed:
    def test_같은_시드는_같은_캘린더를_만든다(self):
        assert cal_seed.build(TODAY) == cal_seed.build(TODAY)

    def test_병목_담당자에게_회의가_몰린다(self):
        data = cal_seed.build(TODAY)
        avail = av.from_events(data["events"])
        planted = next(p for p in data["planted"] if p["kind"] == "meeting_overload")
        loads = {
            p: av.meeting_load(avail, p, TODAY, 10)["lost_days"]
            for p in {e["attendee"] for e in data["events"]}
        }
        assert max(loads, key=lambda p: loads[p]) == planted["assignee"]

    def test_하루가_통째로_날아가는_날이_있다(self):
        data = cal_seed.build(TODAY)
        workshop = next(p for p in data["planted"] if p["kind"] == "workshop")
        that_day = [e for e in data["events"] if e["date"] == workshop["date"]]
        assert any(e["hours"] >= av.WORKDAY_HOURS for e in that_day)

    def test_가상_인물만_등장한다(self):
        tasks = schedule.from_jira_issues(
            __import__("pmo_agent.seeds.board", fromlist=["build"]).build(TODAY)
        )
        people = {t.assignee for t in tasks.values() if t.assignee}
        assert {e["attendee"] for e in cal_seed.build(TODAY)["events"]} <= people

    def test_JSON으로_직렬화된다(self):
        json.dumps(cal_seed.build(TODAY), ensure_ascii=False)
