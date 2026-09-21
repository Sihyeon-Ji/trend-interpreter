"""승인 게이트 단위 테스트 — 가짜 Jira 로 실제 쓰기 없이 검증한다.

핵심 관심사는 하나다: 사람이 명시적으로 고른 것만 반영되는가.

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import contextlib
import inspect
import io
import json
import os
import tempfile
import unittest

from test_tools import FakeJira  # noqa: E402

from pmo_agent import approve, tools  # noqa: E402
from pmo_agent.adapters.jira import WriteBlocked  # noqa: E402

PROPOSALS = [
    {"tool": "propose_field_update", "args": {"key": "ECHO-2", "duedate": "2026-09-28"}},
    {"tool": "propose_comment", "args": {"key": "ECHO-2", "text": "DB 선택 지연으로 마감 연기"}},
    {"tool": "propose_transition", "args": {"key": "ECHO-3", "to_status": "In Progress"}},
    {"tool": "note", "args": {"text": "정기 회의 취소"}},
]


def answers(*seq):
    """input() 대신 끼울 함수 — 정해진 답을 순서대로 돌려준다."""
    it = iter(seq)
    return lambda _prompt="": next(it, "")


class GateTestCase(unittest.TestCase):
    """로그를 임시 파일로 돌리고 가짜 Jira 를 끼운다."""

    def setUp(self):
        self.fake = FakeJira()
        tools._j = self.fake
        self.dir = tempfile.mkdtemp()
        self.keep_log, approve.LOG = approve.LOG, os.path.join(self.dir, "approvals.jsonl")

    def tearDown(self):
        tools._j = None
        approve.LOG = self.keep_log

    def logged(self):
        if not os.path.exists(approve.LOG):
            return []
        with open(approve.LOG, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def run_gate(self, *inputs, proposals=None, impact=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = approve.gate(
                proposals if proposals is not None else PROPOSALS,
                impact,
                source="test",
                ask=answers(*inputs),
            )
        return out, buf.getvalue()


class TestModelCannotApprove(unittest.TestCase):
    """모델이 승인 경로에 손댈 수 없다는 것이 이 프로젝트의 핵심 안전장치다."""

    def test_툴_레이어에는_approve_True가_없다(self):
        self.assertNotIn("approve=True", inspect.getsource(tools))

    def test_승인함수는_Gemini에_노출되지_않는다(self):
        names = set(tools.REGISTRY) | {d["name"] for d in tools.DECLARATIONS}
        self.assertFalse(names & {"apply", "gate", "approve", "select"})

    def test_반영함수는_전부_approve_True로_부른다(self):
        for name, fn in approve.APPLIERS.items():
            self.assertIn("approve=True", inspect.getsource(fn), name)


class TestSelect(unittest.TestCase):
    def test_엔터는_아무것도_고르지_않는다(self):
        for s in ("", "  ", "n", "no", "q", "아니오"):
            self.assertEqual(approve.select(s, 3), [], s)

    def test_번호를_고른다(self):
        self.assertEqual(approve.select("1,3", 3), [0, 2])
        self.assertEqual(approve.select("2", 3), [1])

    def test_공백으로_구분해도_된다(self):
        self.assertEqual(approve.select("1 3", 3), [0, 2])

    def test_범위를_고른다(self):
        self.assertEqual(approve.select("1-3", 3), [0, 1, 2])

    def test_all만이_전체승인이다(self):
        self.assertEqual(approve.select("all", 3), [0, 1, 2])
        self.assertEqual(approve.select("전부", 2), [0, 1])
        self.assertEqual(approve.select("y", 3), [])  # yes 는 전체승인이 아니다

    def test_범위를_벗어난_번호는_버린다(self):
        self.assertEqual(approve.select("0,5,2", 3), [1])

    def test_쓰레기_입력은_아무것도_고르지_않는다(self):
        self.assertEqual(approve.select("어쩌고저쩌고", 3), [])

    def test_중복은_한_번만(self):
        self.assertEqual(approve.select("2,2,2", 3), [1])


class TestRender(GateTestCase):
    def test_반영대상에만_번호가_붙는다(self):
        s = approve.render(PROPOSALS)
        self.assertIn("[ 1]", s)
        self.assertIn("[ 3]", s)
        self.assertNotIn("[ 4]", s)  # note 는 번호 없음
        self.assertIn("반영 안 함", s)

    def test_아직_반영되지_않았음을_알린다(self):
        self.assertIn("아직 아무것도 반영되지 않았습니다", approve.render(PROPOSALS))

    def test_일정_영향을_같이_보여준다(self):
        s = approve.render(
            PROPOSALS,
            {
                "predicted_finish_before": "2026-10-02",
                "predicted_finish_after": "2026-10-07",
                "risks_before": 2,
                "risks_after": 3,
                "newly_at_risk": [{"key": "ECHO-5", "summary": "통합 테스트"}],
            },
        )
        self.assertIn("2026-10-02 → 2026-10-07", s)
        self.assertIn("ECHO-5", s)

    def test_제안이_없어도_깨지지_않는다(self):
        self.assertIn("제안 없음", approve.render([]))


class TestApply(GateTestCase):
    def test_고른_것만_approve_True로_나간다(self):
        out = approve.apply(PROPOSALS, [0], jira=self.fake, source="t")
        self.assertEqual(out["applied"], 1)
        self.assertEqual(
            self.fake.calls[-1], ("set_fields", "ECHO-2", {"duedate": "2026-09-28"}, True)
        )

    def test_고르지_않은_것은_건드리지_않는다(self):
        approve.apply(PROPOSALS, [0], jira=self.fake)
        self.assertEqual([c[0] for c in self.fake.calls], ["set_fields"])

    def test_note는_번호에서_빠져_반영되지_않는다(self):
        out = approve.apply(PROPOSALS, [0, 1, 2], jira=self.fake)
        self.assertEqual(out["applied"], 3)
        self.assertNotIn("note", [c[0] for c in self.fake.calls])

    def test_빈_선택은_아무것도_하지_않는다(self):
        out = approve.apply(PROPOSALS, [], jira=self.fake)
        self.assertEqual((out["applied"], self.fake.calls), (0, []))

    def test_없는_번호는_실패로_남는다(self):
        out = approve.apply(PROPOSALS, [99], jira=self.fake)
        self.assertEqual((out["applied"], out["failed"]), (0, 1))

    def test_한_건이_실패해도_나머지는_계속한다(self):
        def boom(*a, **k):
            raise RuntimeError("Jira 500")

        self.fake.set_fields = boom
        out = approve.apply(PROPOSALS, [0, 1], jira=self.fake)
        self.assertEqual((out["applied"], out["failed"]), (1, 1))

    def test_쓰기차단은_사고기록으로_남는다(self):
        def blocked(*a, **k):
            raise WriteBlocked("cytur.atlassian.net 는 WRITE_ALLOWLIST 에 없음")

        self.fake.set_fields = blocked
        out = approve.apply(PROPOSALS, [0], jira=self.fake, source="t")
        self.assertEqual(out["failed"], 1)
        rec = self.logged()[-1]
        self.assertTrue(rec["blocked"])
        self.assertIn("cytur", rec["error"])


class TestAuditLog(GateTestCase):
    def test_반영한_것이_한_줄씩_남는다(self):
        approve.apply(PROPOSALS, [0, 2], jira=self.fake, source="memo.json")
        rows = self.logged()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["source"] for r in rows}, {"memo.json"})
        self.assertTrue(all(r["ok"] and r["at"] for r in rows))

    def test_무엇을_바꿨는지_인자까지_남는다(self):
        approve.apply(PROPOSALS, [0], jira=self.fake)
        self.assertEqual(self.logged()[0]["args"], {"key": "ECHO-2", "duedate": "2026-09-28"})

    def test_반영하지_않으면_로그도_없다(self):
        approve.apply(PROPOSALS, [], jira=self.fake)
        self.assertEqual(self.logged(), [])


class TestGate(GateTestCase):
    def test_엔터만_치면_아무것도_반영되지_않는다(self):
        out, text = self.run_gate("")
        self.assertEqual(out["applied"], 0)
        self.assertEqual(self.fake.calls, [])
        self.assertIn("아무것도 반영하지 않았습니다", text)

    def test_번호를_골라도_최종확인이_필요하다(self):
        out, text = self.run_gate("1", "아니")
        self.assertEqual(out["applied"], 0)
        self.assertEqual(self.fake.calls, [])
        self.assertIn("취소했습니다", text)

    def test_yes까지_해야_반영된다(self):
        out, _ = self.run_gate("1", "yes")
        self.assertEqual(out["applied"], 1)
        self.assertEqual(self.fake.calls[-1][-1], True)

    def test_반영전에_무엇을_바꿀지_보여준다(self):
        _, text = self.run_gate("1", "no")
        self.assertIn("ECHO-2", text)
        self.assertIn("2026-09-28", text)

    def test_전체승인도_확인을_거친다(self):
        out, _ = self.run_gate("all", "yes")
        self.assertEqual(out["applied"], 3)

    def test_반영할_것이_없으면_묻지도_않는다(self):
        out, text = self.run_gate(proposals=[{"tool": "note", "args": {"text": "메모"}}])
        self.assertEqual(out["applied"], 0)
        self.assertNotIn("정말 반영할까요", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
