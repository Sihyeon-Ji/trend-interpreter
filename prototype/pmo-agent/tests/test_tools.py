"""툴 레이어 단위 테스트 — 가짜 Jira 를 끼워 자격증명 없이 검증한다.

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import datetime as dt
import inspect
import json
import unittest

from pmo_agent import tools  # noqa: E402

TODAY = "2026-09-21"  # 월요일


def issue(key, summary="", status="To Do", assignee=None, duedate=None, points=None, blocks=()):
    """Jira search() 응답 한 건을 흉내낸다. blocks = 이 이슈가 차단하는 후행 키들."""
    return {
        "key": key,
        "fields": {
            "summary": summary or key,
            "status": {"name": status},
            "assignee": {"displayName": assignee} if assignee else None,
            "duedate": duedate,
            "customfield_10016": points,
            "issuelinks": [
                {"type": {"name": "Blocks"}, "outwardIssue": {"key": k}} for k in blocks
            ],
        },
    }


SAMPLE = [
    issue("ECHO-1", "요구사항 정리", "Done", "김", points=3, blocks=["ECHO-2"]),
    issue(
        "ECHO-2",
        "스키마 설계",
        "In Progress",
        "이",
        duedate="2026-09-24",
        points=4,
        blocks=["ECHO-3"],
    ),
    issue("ECHO-3", "API 구현", "To Do", "박", duedate="2026-09-29", points=5),
]


class FakeJira:
    """실제 Jira 대신 끼우는 스텁. 쓰기 호출은 실행하지 않고 인자만 기록한다."""

    project = "ECHO"

    def __init__(self, issues=None):
        self.issues = SAMPLE if issues is None else issues
        self.calls = []

    def search(self, jql=None, limit=100):
        self.calls.append(("search", jql, limit))
        return self.issues[:limit]

    def issue(self, key):
        self.calls.append(("issue", key))
        return next(i for i in self.issues if i["key"] == key)

    def comment(self, key, text, approve=False):
        self.calls.append(("comment", key, text, approve))
        return {"dry_run": not approve, "would_comment_on": key, "text": text}

    def set_fields(self, key, fields, approve=False):
        self.calls.append(("set_fields", key, fields, approve))
        return {"dry_run": not approve, "issue": key, "would_set": fields}

    def transition(self, key, to_name, approve=False):
        self.calls.append(("transition", key, to_name, approve))
        return {"dry_run": not approve, "issue": key, "would_transition_to": to_name}


class ToolTestCase(unittest.TestCase):
    """각 테스트마다 가짜 Jira 를 끼우고 끝나면 되돌린다."""

    issues = None

    def setUp(self):
        self.fake = FakeJira(self.issues)
        tools._j = self.fake

    def tearDown(self):
        tools._j = None


class TestDeclarations(ToolTestCase):
    def test_선언과_구현이_1대1로_맞는다(self):
        self.assertEqual({d["name"] for d in tools.DECLARATIONS}, set(tools.REGISTRY))

    def test_필수_파라미터가_실제_시그니처에_있다(self):
        for d in tools.DECLARATIONS:
            params = inspect.signature(tools.REGISTRY[d["name"]]).parameters
            for name in d["parameters"].get("properties", {}):
                self.assertIn(name, params, f"{d['name']} 선언에만 있는 인자: {name}")
            for name in d["parameters"].get("required", []):
                self.assertIn(name, params)

    def test_쓰기_툴은_propose_로만_노출된다(self):
        names = set(tools.REGISTRY)
        self.assertFalse({n for n in names if n.startswith(("create_", "update_", "delete_"))})
        self.assertEqual(
            {n for n in names if "propose" in n},
            {"propose_comment", "propose_field_update", "propose_transition"},
        )


class TestListTasks(ToolTestCase):
    def test_선행관계를_함께_준다(self):
        rows = {t["key"]: t for t in tools.list_tasks()["tasks"]}
        self.assertEqual(rows["ECHO-2"]["deps"], ["ECHO-1"])
        self.assertEqual(rows["ECHO-3"]["deps"], ["ECHO-2"])
        self.assertEqual(rows["ECHO-1"]["deps"], [])

    def test_필터가_JQL에_실린다(self):
        tools.list_tasks(status="In Progress", assignee="이")
        jql = self.fake.calls[0][1]
        self.assertIn('status = "In Progress"', jql)
        self.assertIn('assignee = "이"', jql)


class TestAnalyzeSchedule(ToolTestCase):
    def test_임계경로와_위험을_계산한다(self):
        r = tools.analyze_schedule(today=TODAY)
        self.assertEqual(r["critical_path"], ["ECHO-1", "ECHO-2", "ECHO-3"])
        self.assertEqual(r["done"], 1)
        self.assertEqual(r["total"], 3)
        self.assertTrue(r["risks"])

    def test_JSON으로_바로_나간다(self):
        json.dumps(tools.analyze_schedule(today=TODAY), ensure_ascii=False)

    def test_위험에_근거_문장이_붙는다(self):
        r = tools.analyze_schedule(today=TODAY)
        self.assertTrue(all(x["reasons"] for x in r["risks"]))

    def test_기준일을_비우면_오늘을_쓴다(self):
        self.assertEqual(tools.analyze_schedule()["today"], dt.date.today().isoformat())


class TestEmptyProject(ToolTestCase):
    issues = []

    def test_태스크가_없으면_오류를_돌려준다(self):
        self.assertIn("error", tools.analyze_schedule(today=TODAY))


class TestCycle(ToolTestCase):
    issues = [issue("A", blocks=["B"]), issue("B", blocks=["A"])]

    def test_순환은_예외가_아니라_오류로_돌려준다(self):
        r = tools.analyze_schedule(today=TODAY)
        self.assertIn("error", r)
        self.assertIn("hint", r)

    def test_시뮬레이션도_마찬가지다(self):
        self.assertIn("error", tools.simulate_delay("A", 2, today=TODAY))


class TestSimulateDelay(ToolTestCase):
    def test_후행과_프로젝트_완료일이_함께_밀린다(self):
        r = tools.simulate_delay("ECHO-2", 3, today=TODAY)
        moved = {x["key"]: x["slip_days"] for x in r["affected"]}
        self.assertEqual(moved["ECHO-2"], 3)
        self.assertEqual(moved["ECHO-3"], 3)
        self.assertNotEqual(r["project_finish_before"], r["project_finish_after"])

    def test_마감을_깨는_태스크를_표시한다(self):
        r = tools.simulate_delay("ECHO-2", 3, today=TODAY)
        self.assertTrue(next(x for x in r["affected"] if x["key"] == "ECHO-3")["breaks_duedate"])

    def test_날짜가_ISO_문자열로_나온다(self):
        r = tools.simulate_delay("ECHO-2", 1, today=TODAY)
        self.assertIsInstance(r["project_finish_after"], str)
        json.dumps(r, ensure_ascii=False)

    def test_모르는_키는_후보를_알려준다(self):
        r = tools.simulate_delay("없음", 1, today=TODAY)
        self.assertIn("error", r)
        self.assertIn("ECHO-1", r["available"])


class TestWriteGate(ToolTestCase):
    def test_코멘트는_승인없이_호출된다(self):
        r = tools.propose_comment("ECHO-2", "일정 확인 부탁드립니다")
        self.assertTrue(r["dry_run"])
        self.assertEqual(
            self.fake.calls[-1], ("comment", "ECHO-2", "일정 확인 부탁드립니다", False)
        )

    def test_필드변경도_승인없이_호출된다(self):
        r = tools.propose_field_update("ECHO-3", duedate="2026-10-02")
        self.assertTrue(r["dry_run"])
        self.assertIs(self.fake.calls[-1][-1], False)
        self.assertEqual(r["would_set"], {"duedate": "2026-10-02"})

    def test_상태전이도_승인없이_호출된다(self):
        self.assertTrue(tools.propose_transition("ECHO-3", "In Progress")["dry_run"])
        self.assertIs(self.fake.calls[-1][-1], False)

    def test_어떤_읽기툴도_쓰기를_부르지_않는다(self):
        tools.list_tasks()
        tools.analyze_schedule(today=TODAY)
        tools.simulate_delay("ECHO-2", 1, today=TODAY)
        self.assertEqual({c[0] for c in self.fake.calls}, {"search"})


class TestDispatch(ToolTestCase):
    def test_모르는_툴이름은_오류(self):
        self.assertIn("error", tools.dispatch("없는툴", {}))

    def test_예외를_삼켜서_오류로_바꾼다(self):
        self.assertIn(
            "error", tools.dispatch("simulate_delay", {"key": "ECHO-2", "days": "숫자아님"})
        )

    def test_인자없이_호출해도_죽지_않는다(self):
        self.assertIn("count", tools.dispatch("list_tasks", None))

    def test_정상_호출은_그대로_통과한다(self):
        self.assertEqual(tools.dispatch("analyze_schedule", {"today": TODAY})["total"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
