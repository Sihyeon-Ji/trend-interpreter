"""주간 리포트 테스트 — 숫자가 schedule.py 와 어긋나지 않는지, 문장이 데이터와 맞는지.

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import unittest

from pmo_agent import report, schedule  # noqa: E402
from pmo_agent.seeds import board as seed  # noqa: E402

TODAY = dt.date(2026, 9, 21)  # 월요일


def tasks():
    return schedule.to_tasks(
        [
            {
                "key": "ECHO-1",
                "summary": "요구사항 정리",
                "status": "Done",
                "assignee": "한서준",
                "points": 3,
            },
            {
                "key": "ECHO-2",
                "summary": "스키마 설계",
                "status": "In Progress",
                "assignee": "민아름",
                "points": 4,
                "deps": ["ECHO-1"],
                "duedate": "2026-09-23",
            },
            {
                "key": "ECHO-3",
                "summary": "API 구현",
                "status": "To Do",
                "assignee": "한서준",
                "points": 5,
                "deps": ["ECHO-2"],
                "duedate": "2026-09-18",
            },  # 이미 지남
            {
                "key": "ECHO-4",
                "summary": "문서화",
                "status": "To Do",
                "assignee": "민아름",
                "points": 1,
                "duedate": "2026-10-30",
            },
        ]
    )


class TestPieces(unittest.TestCase):
    def test_담당자별로_남은_작업을_모은다(self):
        w = {r["assignee"]: r for r in report.workload(tasks())}
        self.assertNotIn("한서준", [r for r in w if w[r]["count"] == 0])
        self.assertEqual(w["민아름"]["count"], 2)  # ECHO-2, ECHO-4
        self.assertEqual(w["한서준"]["count"], 1)  # ECHO-1 은 완료라 빠진다

    def test_완료된_태스크는_부하에서_빠진다(self):
        self.assertEqual(sum(r["count"] for r in report.workload(tasks())), 3)

    def test_이번주_마감만_고른다(self):
        keys = [t.key for t in report.due_soon(tasks(), TODAY)]
        self.assertIn("ECHO-2", keys)  # 9/23
        self.assertNotIn("ECHO-4", keys)  # 10/30 은 한참 뒤
        self.assertNotIn("ECHO-3", keys)  # 이미 지난 건 여기 말고 '마감 경과'

    def test_약속한_완료일은_가장_늦은_마감일이다(self):
        self.assertEqual(report.committed_finish(tasks()), dt.date(2026, 10, 30))

    def test_마감일이_하나도_없으면_약속일도_없다(self):
        self.assertIsNone(report.committed_finish(schedule.to_tasks([{"key": "A"}])))

    def test_마감이_지난_것을_따로_모은다(self):
        self.assertEqual([t.key for t in report.overdue(tasks(), TODAY)], ["ECHO-3"])

    def test_질문은_담당자와_키를_포함한다(self):
        r = schedule.risks(tasks(), TODAY)[0]
        q = report.question_for(r)
        self.assertIn(r["key"], q)
        self.assertIn(r["assignee"], q)
        self.assertTrue(q.endswith("?"))

    def test_차단관계가_질문에_들어간다(self):
        r = next(x for x in schedule.risks(tasks(), TODAY) if x["key"] == "ECHO-2")
        self.assertIn("ECHO-3", report.question_for(r))


class TestApprovalLog(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "approvals.jsonl")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, rows):
        with open(self.path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def test_기간_안의_성공만_센다(self):
        self.write(
            [
                {
                    "at": "2026-09-19T10:00:00",
                    "ok": True,
                    "tool": "propose_comment",
                    "args": {"key": "A"},
                },
                {
                    "at": "2026-09-01T10:00:00",
                    "ok": True,
                    "tool": "propose_comment",
                    "args": {"key": "B"},
                },
                {
                    "at": "2026-09-19T11:00:00",
                    "ok": False,
                    "tool": "propose_comment",
                    "args": {"key": "C"},
                },
            ]
        )
        keys = [r["args"]["key"] for r in report.recent_approvals(dt.date(2026, 9, 14), self.path)]
        self.assertEqual(keys, ["A"])

    def test_로그가_없어도_깨지지_않는다(self):
        self.assertEqual(report.recent_approvals(TODAY, os.path.join(self.dir, "없음.jsonl")), [])

    def test_깨진_줄은_건너뛴다(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{이건 JSON 아님}\n")
            f.write(
                json.dumps({"at": "2026-09-19T10:00:00", "ok": True, "tool": "x", "args": {}})
                + "\n"
            )
        self.assertEqual(len(report.recent_approvals(dt.date(2026, 9, 14), self.path)), 1)


class TestWeekly(unittest.TestCase):
    def setUp(self):
        self.md = report.weekly(tasks(), TODAY)

    def test_모든_섹션이_있다(self):
        for h in (
            "# ECHO 주간 리포트",
            "## 한눈에",
            "## 지연 위험",
            "## 임계경로",
            "## 이번 주 마감 예정",
            "## 담당자별 남은 작업",
            "## 확인 필요",
            "## 최근 반영 내역",
        ):
            self.assertIn(h, self.md)

    def test_약속일과_예측일을_나란히_보여준다(self):
        self.assertIn("| 약속한 완료일 | 2026-10-30 |", self.md)
        self.assertIn(schedule.forecast(tasks(), TODAY)["project_finish"].isoformat(), self.md)

    def test_숫자가_schedule과_일치한다(self):
        t = tasks()
        f = schedule.forecast(t, TODAY)
        self.assertIn(f["project_finish"].isoformat(), self.md)
        self.assertIn(f"{len(schedule.risks(t, TODAY))}건", self.md)

    def test_진행률을_센다(self):
        self.assertIn("1/4건 완료 (25%)", self.md)

    def test_마감경과_섹션은_해당될때만_나온다(self):
        self.assertIn("## 마감 경과", self.md)
        clean = schedule.to_tasks([{"key": "A", "status": "Done", "points": 1}])
        self.assertNotIn("## 마감 경과", report.weekly(clean, TODAY))

    def test_위험이_없으면_없다고_적는다(self):
        clean = schedule.to_tasks([{"key": "A", "status": "Done", "points": 1}])
        md = report.weekly(clean, TODAY)
        self.assertIn("## 지연 위험\n\n없습니다.", md)

    def test_계산_출처와_한계를_밝힌다(self):
        self.assertIn("schedule.py", self.md)
        self.assertIn("영업일", self.md)
        self.assertIn("capacity.py", self.md)
        self.assertIn("동시 1건을 가정", self.md)

    def test_완료목록을_주면_섹션이_생긴다(self):
        t = tasks()
        md = report.weekly(t, TODAY, done_recent=[t["ECHO-1"]])
        self.assertIn("## 이번 주에 끝난 일", md)
        self.assertIn("ECHO-1", md.split("## 이번 주에 끝난 일")[1].split("##")[0])

    def test_완료목록이_비면_없다고_적는다(self):
        md = report.weekly(tasks(), TODAY, done_recent=[])
        self.assertIn("## 이번 주에 끝난 일\n\n없습니다.", md)

    def test_완료목록을_안_주면_섹션을_빼먹는다(self):
        self.assertNotIn("## 이번 주에 끝난 일", report.weekly(tasks(), TODAY))

    def test_프로젝트명을_바꿀_수_있다(self):
        self.assertIn("# DEMO 주간 리포트", report.weekly(tasks(), TODAY, project="DEMO"))

    def test_빈_보드도_리포트가_나온다(self):
        md = report.weekly({}, TODAY)
        self.assertIn("0/0건 완료", md)
        self.assertIn("## 한눈에", md)


class TestSeedReport(unittest.TestCase):
    def test_시드_40건으로_리포트가_나온다(self):
        t = schedule.from_jira_issues(seed.build(TODAY))
        md = report.weekly(t, TODAY)
        self.assertIn("40건", md)
        self.assertGreater(len(md.splitlines()), 40)

    def test_위험_표는_상위_N건만_싣는다(self):
        t = schedule.from_jira_issues(seed.build(TODAY))
        rows = [line for line in report.weekly(t, TODAY).splitlines() if line.startswith("| ECHO-")]
        self.assertLessEqual(len([r for r in rows if "일 |" in r]), 40)


class TestSave(unittest.TestCase):
    def test_날짜가_파일명에_들어간다(self):
        d = tempfile.mkdtemp()
        try:
            p = report.save("# 테스트", TODAY, d)
            self.assertTrue(p.endswith("weekly-2026-09-21.md"))
            with open(p, encoding="utf-8") as f:
                self.assertEqual(f.read(), "# 테스트")
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
