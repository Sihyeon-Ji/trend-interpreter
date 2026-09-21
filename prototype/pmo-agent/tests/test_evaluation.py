"""평가 케이스가 테스트에서도 돈다 — 시연 전에 깨진 것을 알기 위해.

`tools/evaluate.py` 를 사람이 돌리는 것만으로는 회귀를 놓친다.
여기에 묶어 두면 계산을 고칠 때마다 정답지와 맞는지 자동으로 확인된다.

실행: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import evaluate  # noqa: E402

TODAY = dt.date(2026, 9, 21)  # 월요일


class TestCaseFile:
    def test_열_건이_있다(self):
        cases = evaluate.load_cases()
        assert len(cases) == 10

    def test_성공_다섯_실패_다섯(self):
        cases = evaluate.load_cases()
        assert sum(1 for c in cases if c["group"] == "detect") == 5
        assert sum(1 for c in cases if c["group"] == "restraint") == 5

    def test_모든_케이스에_검사가_등록돼_있다(self):
        for case in evaluate.load_cases():
            assert case["check"] in evaluate.CHECKS, case["id"]

    def test_아이디가_겹치지_않는다(self):
        ids = [c["id"] for c in evaluate.load_cases()]
        assert len(ids) == len(set(ids))

    def test_왜_심었는지_적혀_있다(self):
        # 근거 없는 케이스는 나중에 아무도 고치지 못한다
        for case in evaluate.load_cases():
            assert case.get("why"), case["id"]
            assert case.get("ask"), case["id"]

    def test_JSONL_한_줄씩_읽힌다(self):
        text = evaluate.CASES.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip():
                json.loads(line)


class TestRun:
    def test_전부_통과한다(self):
        rows = evaluate.run(TODAY)
        failed = [f"{r['id']}: {r['detail']}" for r in rows if not r["passed"]]
        assert not failed, "실패: " + " / ".join(failed)

    def test_결과에_근거가_담긴다(self):
        for row in evaluate.run(TODAY):
            assert row["detail"], row["id"]

    def test_오늘_날짜로도_통과한다(self):
        # 세계는 오늘을 기준으로 만들어진다 — 날짜가 바뀌어도 정답지와 계산이 맞아야 한다
        rows = evaluate.run()
        assert all(r["passed"] for r in rows), [r["id"] for r in rows if not r["passed"]]

    def test_실제_감사로그를_건드리지_않는다(self):
        from pmo_agent import approve as approve_mod

        before = approve_mod.LOG
        evaluate.run(TODAY)
        assert approve_mod.LOG == before
