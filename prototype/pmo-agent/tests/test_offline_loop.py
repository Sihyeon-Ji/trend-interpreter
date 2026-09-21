"""시드 + 전체 루프 통합 테스트 — API 키도 Jira 계정도 없이 돈다.

메모 → 추출(가짜 Gemini) → 검증 → 일정 영향 → 승인 → 로컬 보드 반영까지 한 번에 확인한다.
여기가 통과하면, 남은 미지수는 '진짜 Gemini 가 메모를 제대로 읽어내는가' 하나뿐이다.

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile
import unittest

from test_ingest import caller_returning  # noqa: E402

from pmo_agent import approve, ingest, schedule, tools  # noqa: E402
from pmo_agent.adapters.memory import MemoryBoard  # noqa: E402
from pmo_agent.seeds import board as seed  # noqa: E402

TODAY = dt.date(2026, 9, 21)


class TestSeed(unittest.TestCase):
    def test_태스크_40개_담당자_4명(self):
        issues = seed.build(TODAY)
        self.assertEqual(len(issues), 40)
        tasks = schedule.from_jira_issues(issues)
        self.assertEqual(len({t.assignee for t in tasks.values()}), 4)

    def test_같은_시드는_같은_보드를_만든다(self):
        self.assertEqual(seed.build(TODAY), seed.build(TODAY))

    def test_의존관계에_순환이_없다(self):
        schedule.topo_order(schedule.from_jira_issues(seed.build(TODAY)))  # 예외 안 나면 통과

    def test_끝난_것도_진행중인_것도_있다(self):
        # 로컬 보드도 실제 Jira 프로젝트와 같은 한국어 상태를 쓴다
        tasks = schedule.from_jira_issues(seed.build(TODAY))
        statuses = {t.status for t in tasks.values()}
        self.assertIn("완료", statuses)
        self.assertIn("진행 중", statuses)

    def test_지연된_태스크가_실제로_있다(self):
        tasks = schedule.from_jira_issues(seed.build(TODAY))
        self.assertTrue(schedule.risks(tasks, TODAY))

    def test_스토리포인트와_마감일이_다_붙어있다(self):
        tasks = schedule.from_jira_issues(seed.build(TODAY))
        self.assertTrue(all(t.points and t.duedate for t in tasks.values()))

    def test_실명이_섞이지_않았다(self):
        names = {t.assignee for t in schedule.from_jira_issues(seed.build(TODAY)).values()}
        self.assertEqual(names, set(seed.PEOPLE))

    def test_파일로_저장된다(self):
        d = tempfile.mkdtemp()
        try:
            r = seed.write(os.path.join(d, "b.json"), TODAY)
            self.assertEqual(r["count"], 40)
            self.assertEqual(len(MemoryBoard(r["path"]).search(limit=100)), 40)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestOfflineLoop(unittest.TestCase):
    """키 없이 도는 전체 루프."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        path = os.path.join(self.dir, "board.json")
        seed.write(path, TODAY)
        self.board = MemoryBoard(path)
        tools._j = self.board
        self.keep_log, approve.LOG = approve.LOG, os.path.join(self.dir, "approvals.jsonl")

    def tearDown(self):
        tools._j = None
        approve.LOG = self.keep_log
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_보드를_읽어_일정을_분석한다(self):
        r = tools.analyze_schedule(today=TODAY.isoformat())
        self.assertEqual(r["total"], 40)
        self.assertTrue(r["critical_path"])
        self.assertTrue(r["risks"])

    def test_지연_시뮬레이션이_돈다(self):
        key = tools.analyze_schedule(today=TODAY.isoformat())["critical_path"][0]
        r = tools.simulate_delay(key, 3, today=TODAY.isoformat())
        self.assertTrue(r["affected"])

    def test_메모에서_제안까지_간다(self):
        r = self._ingest_memo()
        self.assertTrue(r["resolved"])
        self.assertTrue(r["proposals"])
        self.assertFalse(r["applied"])

    def test_승인해야_보드가_바뀐다(self):
        r = self._ingest_memo()
        before = self.board.issue("ECHO-20")["fields"]["duedate"]
        approve.apply(r["proposals"], [], source="test")  # 아무것도 안 고름
        self.assertEqual(MemoryBoard(self.board.path).issue("ECHO-20")["fields"]["duedate"], before)
        approve.apply(r["proposals"], [0], source="test")  # 첫 제안만 승인
        self.assertEqual(
            MemoryBoard(self.board.path).issue("ECHO-20")["fields"]["duedate"], "2026-10-05"
        )

    def test_승인_기록이_남는다(self):
        r = self._ingest_memo()
        approve.apply(r["proposals"], [0], source="memo")
        with open(approve.LOG, encoding="utf-8") as f:
            self.assertIn("ECHO-20", f.read())

    def test_반영_뒤_일정이_다시_계산된다(self):
        r = self._ingest_memo()
        before = tools.analyze_schedule(today=TODAY.isoformat())["predicted_finish"]
        approve.apply(r["proposals"], [0], source="test")
        tools._j = MemoryBoard(self.board.path)  # 보드를 새로 읽는다
        self.assertIsInstance(
            tools.analyze_schedule(today=TODAY.isoformat())["predicted_finish"], str
        )
        self.assertIsInstance(before, str)

    def _ingest_memo(self):
        """ECHO-20 의 마감을 미루는 메모를 읽었다고 가정한다."""
        tasks = tools._fetch()
        caller = caller_returning(
            {
                "updates": [
                    {
                        "task": "ECHO-20",
                        "duedate": "2026-10-05",
                        "note": "외부 API 스펙 변경으로 지연",
                        "confidence": 0.9,
                    }
                ],
                "notes": ["다음 주 정기 회의 취소"],
                "questions": [],
            }
        )
        return ingest.ingest("회의 메모", tasks=tasks, today=TODAY, caller=caller)


class TestBackendSelection(unittest.TestCase):
    def test_환경변수로_로컬보드를_고른다(self):
        keep, tools._j = os.environ.get("PMO_BACKEND"), None
        os.environ["PMO_BACKEND"] = "memory"
        try:
            self.assertIsInstance(tools.jira(), MemoryBoard)
        finally:
            tools._j = None
            os.environ.pop("PMO_BACKEND", None)
            if keep:
                os.environ["PMO_BACKEND"] = keep


if __name__ == "__main__":
    unittest.main(verbosity=2)
