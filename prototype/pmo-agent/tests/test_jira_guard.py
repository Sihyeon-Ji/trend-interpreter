"""Jira 어댑터 안전 가드 테스트 — 네트워크 없이 검증한다.

이 가드가 하는 일은 하나다: 샌드박스가 아닌 사이트로는 쓰기 요청이 나가지 않게 막는 것.
그리고 .env 표기 흔들림(https:// 접두사, 끝 슬래시, 대문자) 때문에 가드가 오작동하지 않게 하는 것.

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import os
import unittest

from pmo_agent.adapters.jira import Jira, WriteBlocked, _host  # noqa: E402

SANDBOX = "demo.atlassian.net"
REAL = "cytur.atlassian.net"


def jira(site=SANDBOX, allow=SANDBOX + ",localhost"):
    os.environ["WRITE_ALLOWLIST"] = allow
    return Jira(site=site, email="a@b.c", token="t", project="ECHO")


class TestHostNormalize(unittest.TestCase):
    def test_프로토콜과_끝슬래시를_떼어낸다(self):
        for v in (
            "https://demo.atlassian.net",
            "http://demo.atlassian.net/",
            "demo.atlassian.net/",
            "  DEMO.atlassian.net  ",
        ):
            self.assertEqual(_host(v), SANDBOX, v)

    def test_빈값도_처리한다(self):
        self.assertEqual(_host(""), "")
        self.assertEqual(_host(None), "")


class TestAllowlist(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("WRITE_ALLOWLIST", None)

    def test_표기가_달라도_같은_사이트로_인정한다(self):
        # .env 에 https:// 를 붙여 적은 경우 — 예전에는 이것 때문에 쓰기가 전부 막혔다
        j = jira(site="https://demo.atlassian.net", allow="https://demo.atlassian.net/,localhost")
        self.assertEqual(j.site, SANDBOX)
        self.assertIn(SANDBOX, j.allow)

    def test_허용된_사이트는_쓰기가_통과한다(self):
        j = jira()
        self.assertIn(j.site, j.allow)

    def test_실서비스_도메인은_쓰기가_막힌다(self):
        j = jira(site=REAL, allow=SANDBOX)
        with self.assertRaises(WriteBlocked):
            j._call("POST", "/issue", {"x": 1}, write=True)

    def test_차단_메시지에_사이트와_허용목록이_들어간다(self):
        j = jira(site=REAL, allow=SANDBOX)
        try:
            j._call("PUT", "/issue/X", {}, write=True)
            self.fail("차단되지 않았다")
        except WriteBlocked as e:
            self.assertIn(REAL, str(e))
            self.assertIn(SANDBOX, str(e))

    def test_허용목록이_비면_localhost만_남는다(self):
        os.environ.pop("WRITE_ALLOWLIST", None)
        j = Jira(site=SANDBOX, email="a@b.c", token="t", project="ECHO")
        self.assertNotIn(SANDBOX, j.allow)


class TestWriteGateDefaults(unittest.TestCase):
    """쓰기 함수는 approve 없이는 네트워크에 나가지 않는다 (dry_run)."""

    def setUp(self):
        self.j = jira()

    def tearDown(self):
        os.environ.pop("WRITE_ALLOWLIST", None)

    def test_기본은_전부_dry_run이다(self):
        self.assertTrue(self.j.create_issue("x")["dry_run"])
        self.assertTrue(self.j.comment("ECHO-1", "x")["dry_run"])
        self.assertTrue(self.j.set_fields("ECHO-1", {"duedate": "2026-10-01"})["dry_run"])
        self.assertTrue(self.j.link("ECHO-1", "ECHO-2")["dry_run"])

    def test_dry_run은_무엇을_바꿀지_보여준다(self):
        self.assertEqual(
            self.j.set_fields("ECHO-1", {"duedate": "2026-10-01"})["would_set"],
            {"duedate": "2026-10-01"},
        )
        self.assertEqual(self.j.comment("ECHO-1", "확인 요청")["text"], "확인 요청")


class TestConfigErrors(unittest.TestCase):
    def test_설정이_비면_바로_알려준다(self):
        # env 를 비워 끼운다 — 실제 .env 가 있으면 생성자가 거기서 값을 주워 와 테스트가
        # 통과해버린다
        import pmo_agent.adapters.jira as J

        keep, J.env = J.env, lambda k, d="": d
        try:
            with self.assertRaises(RuntimeError) as e:
                Jira(site="", email="", token="", project="ECHO")
            self.assertIn("SETUP.md", str(e.exception))
        finally:
            J.env = keep


if __name__ == "__main__":
    unittest.main(verbosity=2)
