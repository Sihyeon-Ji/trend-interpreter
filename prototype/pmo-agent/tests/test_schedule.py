"""schedule.py 단위 테스트 — 자격증명 없이 도는 순수 계산 검증 (SETUP.md 2-3).

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import datetime as dt
import json
import unittest

from pmo_agent.schedule import (  # noqa: E402
    CycleError,
    add_workdays,
    cpm,
    forecast,
    from_jira_issues,
    iso,
    propagate,
    risks,
    status_alike,
    summary,
    to_tasks,
    topo_order,
    workdays_between,
)

MON = dt.date(2026, 9, 21)  # 기준 월요일


def chain():
    """A(2) → B(3) → C(1) 일직선. 전부 임계경로."""
    return to_tasks(
        [
            {"key": "A", "points": 2},
            {"key": "B", "points": 3, "deps": ["A"]},
            {"key": "C", "points": 1, "deps": ["B"]},
        ]
    )


def diamond():
    """A(2) → B(5) → E(1),  A(2) → C(1) → E(1). B 쪽이 임계경로, C 는 여유 4일."""
    return to_tasks(
        [
            {"key": "A", "points": 2},
            {"key": "B", "points": 5, "deps": ["A"]},
            {"key": "C", "points": 1, "deps": ["A"]},
            {"key": "E", "points": 1, "deps": ["B", "C"]},
        ]
    )


class TestWorkdays(unittest.TestCase):
    def test_기준일이_월요일이다(self):
        self.assertEqual(MON.weekday(), 0)

    def test_주말을_건너뛴다(self):
        # 월요일 + 5영업일 = 다음 주 월요일
        self.assertEqual(add_workdays(MON, 5), MON + dt.timedelta(days=7))

    def test_0일은_제자리_주말이면_보정(self):
        self.assertEqual(add_workdays(MON, 0), MON)
        sat = MON + dt.timedelta(days=5)
        self.assertEqual(add_workdays(sat, 0), MON + dt.timedelta(days=7))

    def test_음수면_뒤로_간다(self):
        self.assertEqual(add_workdays(MON, -5), MON - dt.timedelta(days=7))
        self.assertEqual(add_workdays(MON, -1), MON - dt.timedelta(days=3))  # 금요일
        self.assertEqual(add_workdays(add_workdays(MON, -20), 20), MON)

    def test_영업일_차이는_주말을_빼고_센다(self):
        self.assertEqual(workdays_between(MON, MON + dt.timedelta(days=7)), 5)
        self.assertEqual(workdays_between(MON + dt.timedelta(days=7), MON), -5)

    def test_공휴일도_제외한다(self):
        wed = MON + dt.timedelta(days=2)
        self.assertEqual(add_workdays(MON, 2, holidays=[wed]), MON + dt.timedelta(days=3))


class TestCPM(unittest.TestCase):
    def test_일직선은_전부_임계경로(self):
        c = cpm(chain(), MON)
        self.assertEqual(c["duration_days"], 6)
        self.assertEqual(c["critical_path"], ["A", "B", "C"])
        self.assertEqual(c["finish"], add_workdays(MON, 6))
        self.assertTrue(all(r["slack_days"] == 0 for r in c["tasks"].values()))

    def test_짧은_가지에_여유가_생긴다(self):
        c = cpm(diamond(), MON)
        self.assertEqual(c["duration_days"], 8)  # A2 + B5 + E1
        self.assertEqual(c["critical_path"], ["A", "B", "E"])
        self.assertEqual(c["tasks"]["C"]["slack_days"], 4)
        self.assertFalse(c["tasks"]["C"]["critical"])

    def test_포인트가_없으면_기본_기간을_쓴다(self):
        c = cpm(to_tasks([{"key": "X"}]), MON)
        self.assertEqual(c["duration_days"], 2)

    def test_순환은_거부한다(self):
        t = to_tasks([{"key": "A", "deps": ["B"]}, {"key": "B", "deps": ["A"]}])
        with self.assertRaises(CycleError):
            topo_order(t)

    def test_존재하지_않는_선행은_버린다(self):
        t = to_tasks([{"key": "A", "deps": ["없는키", "A"]}])
        self.assertEqual(t["A"].deps, [])


class TestStatusAliases(unittest.TestCase):
    """Jira 사이트 언어에 따라 상태 이름이 한/영으로 갈린다. 모델은 영어로 답하는 경향이 있다."""

    def test_한글과_영어를_같은_뜻으로_본다(self):
        self.assertTrue(status_alike("Done", "완료"))
        self.assertTrue(status_alike("완료", "done"))
        self.assertTrue(status_alike("In Progress", "진행 중"))
        self.assertTrue(status_alike("To Do", "할 일"))

    def test_공백과_대소문자를_흡수한다(self):
        self.assertTrue(status_alike("진행중", "진행 중"))
        self.assertTrue(status_alike("IN PROGRESS", "in progress"))

    def test_다른_뜻은_구분한다(self):
        self.assertFalse(status_alike("Done", "진행 중"))
        self.assertFalse(status_alike("Blocked", "완료"))

    def test_빈값은_같지_않다(self):
        self.assertFalse(status_alike("", "완료"))


class TestForecast(unittest.TestCase):
    def test_완료된_태스크는_남은_기간이_0(self):
        t = chain()
        t["A"].status = "Done"
        f = forecast(t, MON)
        self.assertEqual(f["tasks"]["A"]["remaining_days"], 0)
        self.assertEqual(f["tasks"]["B"]["predicted_finish"], add_workdays(MON, 3))

    def test_진행률이_남은_기간을_줄인다(self):
        t = chain()
        t["A"].progress = 0.5
        self.assertEqual(forecast(t, MON)["tasks"]["A"]["remaining_days"], 1.0)

    def test_마감_초과를_일수와_함께_집어낸다(self):
        t = chain()
        t["C"].duedate = add_workdays(MON, 4)  # 실제 예상은 6영업일
        f = forecast(t, MON)["tasks"]["C"]
        self.assertTrue(f["late"])
        self.assertEqual(f["delay_days"], 2)

    def test_마감이_없으면_지연_판정을_하지_않는다(self):
        f = forecast(chain(), MON)["tasks"]["C"]
        self.assertFalse(f["late"])
        self.assertIsNone(f["delay_days"])


class TestPropagate(unittest.TestCase):
    def test_여유가_있으면_후행으로_번지지_않는다(self):
        p = propagate(diamond(), "C", 2, MON)  # C 의 여유는 4일
        self.assertIn("C", [r["key"] for r in p["affected"]])
        self.assertNotIn("E", [r["key"] for r in p["affected"]])
        self.assertEqual(p["project_finish_before"], p["project_finish_after"])

    def test_임계경로가_밀리면_프로젝트가_밀린다(self):
        p = propagate(diamond(), "B", 3, MON)
        moved = {r["key"]: r["slip_days"] for r in p["affected"]}
        self.assertEqual(moved["B"], 3)
        self.assertEqual(moved["E"], 3)
        self.assertEqual(workdays_between(p["project_finish_before"], p["project_finish_after"]), 3)

    def test_마감을_깨는지_표시한다(self):
        t = diamond()
        t["E"].duedate = add_workdays(MON, 8)
        p = propagate(t, "B", 3, MON)
        self.assertTrue(next(r for r in p["affected"] if r["key"] == "E")["breaks_duedate"])

    def test_원본_태스크를_건드리지_않는다(self):
        t = diamond()
        propagate(t, "B", 3, MON)
        self.assertEqual(t["B"].points, 5)

    def test_모르는_키는_오류를_돌려준다(self):
        self.assertIn("error", propagate(diamond(), "없음", 1, MON))


class TestRisks(unittest.TestCase):
    def test_완료된_태스크는_위험에서_빠진다(self):
        t = chain()
        t["A"].status = "완료"
        self.assertNotIn("A", [r["key"] for r in risks(t, MON)])

    def test_근거와_차단관계를_함께_준다(self):
        t = chain()
        t["B"].duedate = add_workdays(MON, 1)
        r = next(x for x in risks(t, MON) if x["key"] == "B")
        self.assertTrue(r["reasons"])
        self.assertEqual(r["blocks"], ["C"])
        self.assertTrue(r["critical"])

    def test_지연이_큰_순서로_정렬된다(self):
        t = chain()
        t["A"].duedate = add_workdays(MON, 1)  # 1일 초과
        t["C"].duedate = MON  # 6일 초과
        self.assertEqual([r["key"] for r in risks(t, MON)][0], "C")


class TestJiraMapping(unittest.TestCase):
    def test_blocks_링크_양방향을_선행관계로_바꾼다(self):
        issues = [
            {
                "key": "ECHO-1",
                "fields": {
                    "summary": "설계",
                    "status": {"name": "Done"},
                    "assignee": {"displayName": "최"},
                    "duedate": "2026-09-25",
                    "customfield_10016": 3,
                    "issuelinks": [{"type": {"name": "Blocks"}, "outwardIssue": {"key": "ECHO-2"}}],
                },
            },
            {
                "key": "ECHO-2",
                "fields": {
                    "summary": "구현",
                    "status": {"name": "To Do"},
                    "issuelinks": [{"type": {"name": "Blocks"}, "inwardIssue": {"key": "ECHO-1"}}],
                },
            },
        ]
        t = from_jira_issues(issues)
        self.assertEqual(t["ECHO-2"].deps, ["ECHO-1"])
        self.assertEqual(t["ECHO-1"].deps, [])
        self.assertTrue(t["ECHO-1"].is_done)
        self.assertEqual(t["ECHO-1"].duedate, dt.date(2026, 9, 25))
        self.assertEqual(t["ECHO-1"].points, 3)

    def test_blocks가_아닌_링크는_무시한다(self):
        issues = [
            {
                "key": "E-1",
                "fields": {
                    "issuelinks": [{"type": {"name": "Relates"}, "outwardIssue": {"key": "E-2"}}]
                },
            },
            {"key": "E-2", "fields": {}},
        ]
        self.assertEqual(from_jira_issues(issues)["E-2"].deps, [])

    def test_필드가_비어도_깨지지_않는다(self):
        t = from_jira_issues([{"key": "E-1", "fields": {}}])
        self.assertEqual(t["E-1"].summary, "")
        self.assertIsNone(t["E-1"].duedate)


class TestSummary(unittest.TestCase):
    def test_JSON으로_바로_직렬화된다(self):
        t = chain()
        t["C"].duedate = MON
        s = summary(t, MON)
        json.dumps(s, ensure_ascii=False)  # 예외 없으면 통과
        self.assertEqual(s["today"], MON.isoformat())
        self.assertEqual(s["critical_path"], ["A", "B", "C"])
        self.assertEqual(s["total"], 3)

    def test_계획과_예측의_차이를_일수로_준다(self):
        t = chain()
        t["A"].status = "Done"  # 2일치가 사라짐
        self.assertEqual(summary(t, MON)["slip_days"], -2)

    def test_iso는_원본을_바꾸지_않는다(self):
        o = {"d": MON, "xs": [MON]}
        self.assertEqual(iso(o)["d"], MON.isoformat())
        self.assertEqual(o["d"], MON)


if __name__ == "__main__":
    unittest.main(verbosity=2)
