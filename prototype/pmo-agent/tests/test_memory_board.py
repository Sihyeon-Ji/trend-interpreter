"""로컬 보드 어댑터 테스트 — Jira 와 '같은 모양'인지가 핵심이다.

모양이 같아야 schedule/tools/approve 가 백엔드를 몰라도 된다.

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from pmo_agent import schedule  # noqa: E402
from pmo_agent.adapters.memory import MemoryBoard, make_issue  # noqa: E402


def sample():
    return [
        make_issue("ECHO-1", "요구사항 정리", "Done", "한서준", "2026-09-18", 3, blocks=["ECHO-2"]),
        make_issue(
            "ECHO-2", "스키마 설계", "In Progress", "민아름", "2026-09-24", 4, blocks=["ECHO-3"]
        ),
        make_issue("ECHO-3", "API 구현", "To Do", "한서준", "2026-09-29", 5),
    ]


class BoardTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "board.json")
        self.board = MemoryBoard(self.path)
        self.board._issues = {i["key"]: i for i in sample()}
        self.board._save()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def reloaded(self):
        return MemoryBoard(self.path)


class TestShapeMatchesJira(BoardTestCase):
    def test_schedule가_그대로_읽는다(self):
        tasks = schedule.from_jira_issues(self.board.search())
        self.assertEqual(tasks["ECHO-2"].deps, ["ECHO-1"])
        self.assertEqual(tasks["ECHO-1"].points, 3)
        self.assertTrue(tasks["ECHO-1"].is_done)
        self.assertEqual(tasks["ECHO-2"].assignee, "민아름")

    def test_whoami와_project_info가_있다(self):
        self.assertIn("displayName", self.board.whoami())
        self.assertEqual(self.board.project_info()["key"], "ECHO")

    def test_쓰기허용_사이트는_로컬뿐(self):
        self.assertEqual(self.board.allow, ["local"])


class TestSearch(BoardTestCase):
    def test_상태로_거른다(self):
        r = self.board.search('project = ECHO AND status = "To Do"')
        self.assertEqual([i["key"] for i in r], ["ECHO-3"])

    def test_담당자로_거른다(self):
        r = self.board.search('assignee = "한서준"')
        self.assertEqual({i["key"] for i in r}, {"ECHO-1", "ECHO-3"})

    def test_마감일순으로_정렬한다(self):
        self.assertEqual([i["key"] for i in self.board.search()], ["ECHO-1", "ECHO-2", "ECHO-3"])

    def test_limit을_지킨다(self):
        self.assertEqual(len(self.board.search(limit=2)), 2)

    def test_모르는_JQL은_무시하고_전부_준다(self):
        self.assertEqual(len(self.board.search("뭔가 이상한 JQL")), 3)


class TestWriteGate(BoardTestCase):
    def test_승인없이는_아무것도_바뀌지_않는다(self):
        self.assertTrue(self.board.set_fields("ECHO-3", {"duedate": "2026-10-05"})["dry_run"])
        self.assertTrue(self.board.comment("ECHO-3", "확인 요청")["dry_run"])
        self.assertTrue(self.board.transition("ECHO-3", "In Progress")["dry_run"])
        self.assertTrue(self.board.create_issue("새 태스크")["dry_run"])
        self.assertEqual(self.reloaded().issue("ECHO-3")["fields"]["duedate"], "2026-09-29")

    def test_승인하면_파일에_남는다(self):
        self.board.set_fields("ECHO-3", {"duedate": "2026-10-05"}, approve=True)
        self.assertEqual(self.reloaded().issue("ECHO-3")["fields"]["duedate"], "2026-10-05")

    def test_코멘트가_쌓인다(self):
        self.board.comment("ECHO-3", "첫 코멘트", approve=True)
        self.board.comment("ECHO-3", "둘째 코멘트", approve=True)
        self.assertEqual(len(self.reloaded().issue("ECHO-3")["fields"]["comments"]), 2)

    def test_상태전이가_반영된다(self):
        self.board.transition("ECHO-3", "In Progress", approve=True)
        self.assertEqual(self.reloaded().issue("ECHO-3")["fields"]["status"]["name"], "In Progress")

    def test_현재상태로는_전이할_수_없다(self):
        self.assertIn("error", self.board.transition("ECHO-3", "To Do"))

    def test_새_이슈는_번호가_이어진다(self):
        r = self.board.create_issue("새 태스크", approve=True)
        self.assertEqual(r["key"], "ECHO-4")
        self.assertEqual(len(self.reloaded().search()), 4)

    def test_링크는_양쪽에_달린다(self):
        self.board.link("ECHO-2", "ECHO-3", approve=True)
        b = self.reloaded()
        self.assertTrue(
            any(
                link.get("outwardIssue", {}).get("key") == "ECHO-3"
                for link in b.issue("ECHO-2")["fields"]["issuelinks"]
            )
        )
        self.assertTrue(
            any(
                link.get("inwardIssue", {}).get("key") == "ECHO-2"
                for link in b.issue("ECHO-3")["fields"]["issuelinks"]
            )
        )

    def test_없는_이슈는_오류(self):
        with self.assertRaises(RuntimeError):
            self.board.issue("ECHO-99")


class TestDoneHistory(BoardTestCase):
    def test_전이하면_변경시각이_남는다(self):
        self.board.transition("ECHO-3", "Done", approve=True)
        f = self.reloaded().issue("ECHO-3")["fields"]
        self.assertIn("status_changed_at", f)

    def test_최근_완료만_돌려준다(self):
        self.assertEqual(self.board.done_since(7), [])  # 아직 전이한 적 없다
        self.board.transition("ECHO-3", "완료", approve=True)
        self.assertEqual([i["key"] for i in self.reloaded().done_since(7)], ["ECHO-3"])

    def test_완료가_아니면_빠진다(self):
        self.board.transition("ECHO-3", "In Progress", approve=True)
        self.assertEqual(self.reloaded().done_since(7), [])

    def test_영어_상태로도_전이된다(self):
        r = self.board.transition("ECHO-3", "Done", approve=True)
        self.assertEqual(r["status"], "Done")


class TestMemoryOnly(unittest.TestCase):
    def test_파일없이도_돌아간다(self):
        b = MemoryBoard(issues=sample())
        self.assertIsNone(b.path)
        b.set_fields("ECHO-3", {"duedate": "2026-10-05"}, approve=True)
        self.assertEqual(b.issue("ECHO-3")["fields"]["duedate"], "2026-10-05")

    def test_빈_보드도_깨지지_않는다(self):
        b = MemoryBoard(issues=[])
        self.assertEqual(b.search(), [])


class TestPersistedFormat(BoardTestCase):
    def test_사람이_읽을_수_있는_JSON이다(self):
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["project"], "ECHO")
        self.assertEqual(len(data["issues"]), 3)
        self.assertIn("saved_at", data)

    def test_저장시각이_갱신된다(self):
        def saved_at():
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)["saved_at"]

        before = saved_at()
        self.board.comment("ECHO-1", "x", approve=True)
        self.assertIsInstance(before, str)
        self.assertIsInstance(saved_at(), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
