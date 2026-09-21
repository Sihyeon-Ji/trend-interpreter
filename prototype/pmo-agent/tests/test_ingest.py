"""ingest.py 단위 테스트 — 가짜 Gemini 응답으로 API 키 없이 검증한다.

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import tempfile
import unittest

from pmo_agent import ingest  # noqa: E402
from pmo_agent.schedule import to_tasks  # noqa: E402

TODAY = dt.date(2026, 9, 21)


def tasks():
    return to_tasks(
        [
            {
                "key": "ECHO-1",
                "summary": "요구사항 정리",
                "status": "Done",
                "assignee": "김",
                "points": 3,
            },
            {
                "key": "ECHO-2",
                "summary": "스키마 설계",
                "status": "In Progress",
                "assignee": "이",
                "points": 4,
                "deps": ["ECHO-1"],
                "duedate": "2026-09-24",
            },
            {
                "key": "ECHO-3",
                "summary": "API 구현",
                "status": "To Do",
                "assignee": "박",
                "points": 5,
                "deps": ["ECHO-2"],
                "duedate": "2026-09-29",
            },
            {
                "key": "ECHO-4",
                "summary": "API 문서화",
                "status": "To Do",
                "assignee": "박",
                "points": 1,
            },
        ]
    )


def fake_response(payload):
    """Gemini generateContent 응답 모양으로 감싼다."""
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}]
    }


def caller_returning(payload):
    def _c(parts):
        _c.parts = parts
        return fake_response(payload)

    return _c


class TestAttach(unittest.TestCase):
    def test_확장자로_mime을_고른다(self):
        self.assertEqual(ingest.mime_of("a/b/note.PNG"), "image/png")
        self.assertEqual(ingest.mime_of("note.jpeg"), "image/jpeg")

    def test_모르는_형식은_거부한다(self):
        with self.assertRaises(ValueError):
            ingest.mime_of("note.txt")

    def test_이미지를_base64로_싣는다(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG fake bytes")
            path = f.name
        try:
            part = ingest.attach(path)
            self.assertEqual(part["inline_data"]["mime_type"], "image/png")
            self.assertEqual(base64.b64decode(part["inline_data"]["data"]), b"\x89PNG fake bytes")
        finally:
            os.unlink(path)

    def test_너무_크면_거부한다(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"0")
            path = f.name
        try:
            ingest.MAX_BYTES, keep = 0, ingest.MAX_BYTES
            with self.assertRaises(ValueError):
                ingest.attach(path)
        finally:
            ingest.MAX_BYTES = keep
            os.unlink(path)


class TestBuildParts(unittest.TestCase):
    def test_오늘과_실제_키를_같이_넣는다(self):
        head = ingest.build_parts("회의 메모", today=TODAY, keys=["ECHO-1", "ECHO-2"])[0]["text"]
        self.assertIn("2026-09-21", head)
        self.assertIn("ECHO-1", head)
        self.assertIn("회의 메모", head)

    def test_이미지가_파트로_붙는다(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"jpeg")
            path = f.name
        try:
            parts = ingest.build_parts("메모", [path], TODAY)
            self.assertEqual(len(parts), 2)
            self.assertIn("inline_data", parts[1])
        finally:
            os.unlink(path)


class TestParse(unittest.TestCase):
    def test_정상_JSON을_읽는다(self):
        r = ingest.parse(
            fake_response({"updates": [{"task": "ECHO-2"}], "notes": ["메모"], "questions": []})
        )
        self.assertEqual(r["updates"][0]["task"], "ECHO-2")
        self.assertEqual(r["notes"], ["메모"])

    def test_빈_응답은_질문으로_바꾼다(self):
        r = ingest.parse({"candidates": [{"content": {"parts": []}}]})
        self.assertEqual(r["updates"], [])
        self.assertTrue(r["questions"])

    def test_깨진_JSON도_죽지_않는다(self):
        r = ingest.parse({"candidates": [{"content": {"parts": [{"text": "{이건 JSON 아님"}]}}]})
        self.assertEqual(r["updates"], [])
        self.assertTrue(r["questions"])
        self.assertIn("raw", r)


class TestResolve(unittest.TestCase):
    def test_키가_그대로_맞으면_통과(self):
        self.assertEqual(ingest.resolve("ECHO-2", tasks())[0], "ECHO-2")

    def test_대소문자는_무시한다(self):
        self.assertEqual(ingest.resolve("echo-2", tasks())[0], "ECHO-2")

    def test_제목_부분일치도_찾는다(self):
        self.assertEqual(ingest.resolve("스키마", tasks())[0], "ECHO-2")

    def test_여러개에_걸리면_사람에게_넘긴다(self):
        key, why = ingest.resolve("API", tasks())  # ECHO-3, ECHO-4 둘 다 걸린다
        self.assertIsNone(key)
        self.assertIn("ECHO-3", why)
        self.assertIn("ECHO-4", why)

    def test_없는_태스크는_거부한다(self):
        self.assertIsNone(ingest.resolve("배포 자동화", tasks())[0])


class TestValidate(unittest.TestCase):
    def test_마감일_변경을_통과시킨다(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-3", "duedate": "2026-10-05", "confidence": 0.9}]},
            tasks(),
            TODAY,
        )
        self.assertEqual(v["resolved"][0]["key"], "ECHO-3")
        self.assertEqual(v["resolved"][0]["duedate"], "2026-10-05")
        self.assertEqual(v["resolved"][0]["duedate_was"], "2026-09-29")

    def test_없는_태스크는_질문으로_떨어진다(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-99", "duedate": "2026-10-05"}]}, tasks(), TODAY
        )
        self.assertEqual(v["resolved"], [])
        self.assertEqual(len(v["unresolved"]), 1)
        self.assertTrue(v["questions"])

    def test_ISO가_아닌_날짜는_거부한다(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-3", "duedate": "다음 주 화요일"}]}, tasks(), TODAY
        )
        self.assertEqual(v["resolved"], [])
        self.assertIn("해석할 수 없다", v["unresolved"][0]["reason"])

    def test_비상식적인_날짜는_거부한다(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-3", "duedate": "2099-01-01"}]}, tasks(), TODAY
        )
        self.assertEqual(v["resolved"], [])
        self.assertIn("비상식적", v["unresolved"][0]["reason"])

    def test_바꿀_내용이_없으면_거부한다(self):
        v = ingest.validate({"updates": [{"task": "ECHO-3", "confidence": 0.8}]}, tasks(), TODAY)
        self.assertEqual(v["resolved"], [])

    def test_상태와_메모도_실린다(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-2", "status": "Done", "note": "리뷰 끝"}]}, tasks(), TODAY
        )
        self.assertEqual(v["resolved"][0]["status"], "Done")
        self.assertEqual(v["resolved"][0]["note"], "리뷰 끝")

    def test_모델_질문을_보존한다(self):
        v = ingest.validate(
            {"updates": [], "questions": ["담당자가 누구인지 안 적혀 있음"]}, tasks(), TODAY
        )
        self.assertIn("담당자가 누구인지 안 적혀 있음", v["questions"])


class TestProposals(unittest.TestCase):
    def test_변경종류별로_propose툴에_매핑된다(self):
        v = ingest.validate(
            {
                "updates": [
                    {
                        "task": "ECHO-3",
                        "duedate": "2026-10-05",
                        "status": "In Progress",
                        "note": "지연",
                    }
                ]
            },
            tasks(),
            TODAY,
        )
        p = ingest.to_proposals(v)
        self.assertEqual(
            [x["tool"] for x in p],
            ["propose_field_update", "propose_transition", "propose_comment"],
        )
        self.assertEqual(p[0]["args"], {"key": "ECHO-3", "duedate": "2026-10-05"})

    def test_쓰기툴은_제안일뿐_실행되지_않는다(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-3", "duedate": "2026-10-05"}]}, tasks(), TODAY
        )
        self.assertTrue(
            all(x["tool"].startswith(("propose_", "note")) for x in ingest.to_proposals(v))
        )


class TestImpact(unittest.TestCase):
    def test_마감을_당기면_새_위험이_잡힌다(self):
        # ECHO-4 는 1일짜리라 오늘 기준 예상 완료가 9/22 — 마감을 9/21 로 당기면 그때부터 초과다
        v = ingest.validate(
            {"updates": [{"task": "ECHO-4", "duedate": "2026-09-21"}]}, tasks(), TODAY
        )
        i = ingest.impact(v["resolved"], tasks(), TODAY)
        self.assertIn("ECHO-4", [x["key"] for x in i["newly_at_risk"]])

    def test_완료처리하면_예측이_당겨진다(self):
        v = ingest.validate({"updates": [{"task": "ECHO-2", "status": "Done"}]}, tasks(), TODAY)
        i = ingest.impact(v["resolved"], tasks(), TODAY)
        self.assertLess(i["predicted_finish_after"], i["predicted_finish_before"])

    def test_원본_태스크를_건드리지_않는다(self):
        t = tasks()
        v = ingest.validate({"updates": [{"task": "ECHO-3", "duedate": "2026-10-05"}]}, t, TODAY)
        ingest.impact(v["resolved"], t, TODAY)
        self.assertEqual(t["ECHO-3"].duedate, dt.date(2026, 9, 29))


class TestIngest(unittest.TestCase):
    def test_전체_경로가_돌아간다(self):
        caller = caller_returning(
            {
                "updates": [
                    {
                        "task": "스키마",
                        "duedate": "2026-09-28",
                        "note": "DB 결정 지연",
                        "confidence": 0.8,
                    },
                    {"task": "ECHO-99", "duedate": "2026-10-01"},
                ],
                "notes": ["다음 주 월요일 정기 회의 취소"],
                "questions": [],
            }
        )
        r = ingest.ingest("회의 메모", tasks=tasks(), today=TODAY, caller=caller)
        self.assertEqual(r["resolved"][0]["key"], "ECHO-2")
        self.assertEqual(len(r["unresolved"]), 1)
        self.assertTrue(r["questions"])
        self.assertFalse(r["applied"])
        self.assertIsNotNone(r["impact"])
        json.dumps(r, ensure_ascii=False)

    def test_입력이_없으면_오류(self):
        self.assertIn(
            "error", ingest.ingest(tasks=tasks(), today=TODAY, caller=caller_returning({}))
        )

    def test_읽어낸게_없으면_영향도_없다(self):
        r = ingest.ingest(
            "메모", tasks=tasks(), today=TODAY, caller=caller_returning({"updates": []})
        )
        self.assertEqual(r["resolved"], [])
        self.assertIsNone(r["impact"])

    def test_모델에게_실제_키_목록을_준다(self):
        caller = caller_returning({"updates": []})
        ingest.ingest("메모", tasks=tasks(), today=TODAY, caller=caller)
        self.assertIn("ECHO-4", caller.parts[0]["text"])

    def test_키가_없으면_호출_자체가_막힌다(self):
        # 키를 읽는 주체는 llm.py 다. 여기를 비워야 실제 네트워크로 나가지 않는다 —
        # 단위 테스트는 어떤 경우에도 외부 API 를 호출하지 않아야 한다.
        from pmo_agent import llm

        keep, llm.env = llm.env, lambda k, d="": "" if k == "GEMINI_API_KEY" else d
        try:
            with self.assertRaises(llm.LLMError):
                ingest.call([{"text": "x"}])
        finally:
            llm.env = keep


if __name__ == "__main__":
    unittest.main(verbosity=2)
