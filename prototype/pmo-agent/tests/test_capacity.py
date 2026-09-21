"""자원 제약 스케줄링 테스트.

검증 관심사는 둘이다:
  1) 한 사람이 동시에 여러 건을 하지 않는가 (구간이 겹치지 않는가)
  2) 사람이 놀고 있는데 일을 미루지 않는가 (빈 구간을 채우는가)

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import datetime as dt
import json
import unittest

from pmo_agent import capacity, schedule  # noqa: E402
from pmo_agent.seeds import board as seed  # noqa: E402

TODAY = dt.date(2026, 9, 21)  # 월요일


def solo(n=4, points=5, assignee="한서준"):
    """한 사람에게 독립 태스크 n건. 의존관계가 없으니 차이는 오로지 용량 때문이다."""
    return schedule.to_tasks(
        [
            {"key": f"T{i}", "summary": f"작업{i}", "assignee": assignee, "points": points}
            for i in range(1, n + 1)
        ]
    )


def two_people():
    """A(5) → B(5) 직렬, 그 옆에 C(5), D(5) 독립. C·D 는 같은 사람이라 직렬이 된다."""
    return schedule.to_tasks(
        [
            {"key": "A", "summary": "A", "assignee": "갑", "points": 5},
            {"key": "B", "summary": "B", "assignee": "갑", "points": 5, "deps": ["A"]},
            {"key": "C", "summary": "C", "assignee": "을", "points": 5},
            {"key": "D", "summary": "D", "assignee": "을", "points": 5},
        ]
    )


def intervals(result, who):
    rows = [r for r in result["tasks"].values() if r["assignee"] == who and r["remaining_days"] > 0]
    return sorted((r["start"], r["finish"]) for r in rows)


class TestCapacityConstraint(unittest.TestCase):
    def test_한_사람_작업은_겹치지_않는다(self):
        r = capacity.levelled(seed_tasks(), TODAY)
        for who in {t["assignee"] for t in r["tasks"].values() if t["assignee"]}:
            iv = intervals(r, who)
            for (s1, e1), (s2, e2) in zip(iv, iv[1:], strict=False):
                self.assertLessEqual(e1, s2, f"{who}: {s1}~{e1} 와 {s2}~{e2} 가 겹친다")

    def test_혼자_4건이면_직렬로_늘어난다(self):
        r = capacity.levelled(solo(4, points=5), TODAY)
        # 의존관계가 없으니 기존 예측은 5일, 용량 반영하면 20일
        self.assertEqual(schedule.workdays_between(TODAY, r["unconstrained_finish"]), 5)
        self.assertEqual(schedule.workdays_between(TODAY, r["project_finish"]), 20)
        self.assertEqual(r["slip_vs_unconstrained"], 15)

    def test_동시_처리_수를_올리면_당겨진다(self):
        r1 = capacity.levelled(solo(4), TODAY, capacity=1)
        r2 = capacity.levelled(solo(4), TODAY, capacity=2)
        r4 = capacity.levelled(solo(4), TODAY, capacity=4)
        self.assertGreater(r1["project_finish"], r2["project_finish"])
        self.assertEqual(r4["project_finish"], r4["unconstrained_finish"])

    def test_담당자별로_용량을_다르게_줄_수_있다(self):
        t = solo(4, assignee="갑")
        r = capacity.levelled(t, TODAY, capacity={"갑": 4})
        self.assertEqual(r["project_finish"], r["unconstrained_finish"])

    def test_사람이_다르면_병렬로_돈다(self):
        r = capacity.levelled(two_people(), TODAY)
        self.assertEqual(
            schedule.workdays_between(TODAY, r["project_finish"]), 10
        )  # 갑 A→B, 을 C→D

    def test_완료된_태스크는_사람을_쓰지_않는다(self):
        t = solo(4)
        for k in ("T1", "T2", "T3"):
            t[k].status = "Done"
        r = capacity.levelled(t, TODAY)
        self.assertEqual(schedule.workdays_between(TODAY, r["project_finish"]), 5)
        self.assertEqual(len(r["resources"]), 1)


class TestNoIdleWaste(unittest.TestCase):
    """늦게 시작하는 태스크가 슬롯을 선점해 앞쪽을 비워두면 안 된다."""

    def tasks(self):
        # X 는 긴 선행(P) 때문에 10일 뒤에야 시작 가능. Y 는 지금 당장 가능. 둘 다 '을' 담당.
        return schedule.to_tasks(
            [
                {"key": "P", "summary": "선행", "assignee": "갑", "points": 10},
                {"key": "X", "summary": "늦게 시작", "assignee": "을", "points": 3, "deps": ["P"]},
                {"key": "Y", "summary": "지금 가능", "assignee": "을", "points": 3},
            ]
        )

    def test_앞쪽_빈_시간을_버리지_않는다(self):
        r = capacity.levelled(self.tasks(), TODAY)
        y = r["tasks"]["Y"]
        self.assertEqual(y["start"], schedule.add_workdays(TODAY, 0))  # 바로 시작해야 한다
        self.assertEqual(y["waiting_days"], 0)

    def test_전체_완료일이_최소값이다(self):
        r = capacity.levelled(self.tasks(), TODAY)
        self.assertEqual(schedule.workdays_between(TODAY, r["project_finish"]), 13)  # P10 + X3


class TestWaiting(unittest.TestCase):
    def test_사람_때문에_기다린_일수를_센다(self):
        r = capacity.levelled(solo(2, points=5), TODAY)
        rows = {k: v for k, v in r["tasks"].items()}
        self.assertEqual(sorted(x["waiting_days"] for x in rows.values()), [0.0, 5.0])

    def test_대기_사유_목록을_준다(self):
        r = capacity.levelled(solo(3, points=5), TODAY)
        w = capacity.blocked_by_people(r)
        self.assertEqual(len(w), 2)
        self.assertGreater(w[0]["waiting_days"], w[1]["waiting_days"])

    def test_대기가_없으면_빈_목록(self):
        r = capacity.levelled(solo(1), TODAY)
        self.assertEqual(capacity.blocked_by_people(r), [])


class TestBottleneck(unittest.TestCase):
    def test_가장_많이_든_사람이_병목이다(self):
        t = schedule.to_tasks(
            [
                {"key": "A", "assignee": "갑", "points": 10},
                {"key": "B", "assignee": "을", "points": 2},
            ]
        )
        self.assertEqual(capacity.levelled(t, TODAY)["bottleneck"]["assignee"], "갑")

    def test_가동률은_0과_1_사이다(self):
        r = capacity.levelled(seed_tasks(), TODAY)
        for x in r["resources"]:
            self.assertTrue(0 < x["utilization"] <= 1.0, x)


class TestRebalance(unittest.TestCase):
    def test_한쪽에_몰린_일을_옮겨_당긴다(self):
        t = schedule.to_tasks(
            [
                {"key": f"T{i}", "summary": f"작업{i}", "assignee": "갑", "points": 5}
                for i in range(1, 5)
            ]
            + [{"key": "Z", "summary": "Z", "assignee": "을", "points": 1}]
        )
        r = capacity.rebalance(t, TODAY, max_moves=2)
        self.assertGreater(r["gain_days"], 0)
        self.assertTrue(r["moves"])
        self.assertEqual(r["moves"][0]["from"], "갑")

    def test_옮길_수_없으면_빈_제안(self):
        r = capacity.rebalance(solo(3), TODAY)  # 사람이 하나뿐
        self.assertEqual(r["moves"], [])
        self.assertEqual(r["before"], r["after"])

    def test_진행중인_태스크는_옮기지_않는다(self):
        t = schedule.to_tasks(
            [
                {
                    "key": "A",
                    "assignee": "갑",
                    "points": 10,
                    "status": "In Progress",
                    "progress": 0.5,
                },
                {"key": "B", "assignee": "갑", "points": 5},
                {"key": "C", "assignee": "을", "points": 1},
            ]
        )
        moved = {m["key"] for m in capacity.rebalance(t, TODAY)["moves"]}
        self.assertNotIn("A", moved)

    def test_완료된_태스크는_옮기지_않는다(self):
        t = schedule.to_tasks(
            [
                {"key": "A", "assignee": "갑", "points": 10, "status": "Done"},
                {"key": "B", "assignee": "갑", "points": 5},
                {"key": "C", "assignee": "을", "points": 1},
            ]
        )
        self.assertNotIn("A", {m["key"] for m in capacity.rebalance(t, TODAY)["moves"]})

    def test_원본을_건드리지_않는다(self):
        t = schedule.to_tasks(
            [{"key": f"T{i}", "assignee": "갑", "points": 5} for i in range(1, 5)]
            + [{"key": "Z", "assignee": "을", "points": 1}]
        )
        capacity.rebalance(t, TODAY)
        self.assertTrue(all(x.assignee == "갑" for k, x in t.items() if k != "Z"))


class TestSummary(unittest.TestCase):
    def test_JSON으로_바로_나간다(self):
        s = capacity.summary(seed_tasks(), TODAY)
        json.dumps(s, ensure_ascii=False)
        self.assertIsInstance(s["capacity_finish"], str)

    def test_두_예측을_나란히_준다(self):
        s = capacity.summary(seed_tasks(), TODAY)
        self.assertIn("unconstrained_finish", s)
        self.assertIn("capacity_finish", s)
        self.assertGreaterEqual(s["capacity_finish"], s["unconstrained_finish"])

    def test_순환이면_예외를_올린다(self):
        t = schedule.to_tasks([{"key": "A", "deps": ["B"]}, {"key": "B", "deps": ["A"]}])
        with self.assertRaises(schedule.CycleError):
            capacity.levelled(t, TODAY)

    def test_빈_보드도_깨지지_않는다(self):
        r = capacity.levelled({}, TODAY)
        self.assertIsNone(r["bottleneck"])
        self.assertEqual(r["resources"], [])


def seed_tasks():
    return schedule.from_jira_issues(seed.build(TODAY))


class TestOnSeed(unittest.TestCase):
    def test_시드에서_용량_반영이_더_늦다(self):
        r = capacity.levelled(seed_tasks(), TODAY)
        self.assertGreater(r["project_finish"], r["unconstrained_finish"])
        self.assertGreater(r["slip_vs_unconstrained"], 0)

    def test_재배치로_실제로_당겨진다(self):
        self.assertGreater(capacity.rebalance(seed_tasks(), TODAY, max_moves=2)["gain_days"], 0)

    def test_같은_입력이면_같은_답이_나온다(self):
        a = capacity.summary(seed_tasks(), TODAY)
        b = capacity.summary(seed_tasks(), TODAY)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
