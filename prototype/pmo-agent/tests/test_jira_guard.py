"""Jira adapter safety-guard tests — verified with no network.

The guard does one thing: stop a write request leaving for any site that is not the sandbox.
And it must not misfire on how .env is written (an https:// prefix, a trailing slash, capitals).

Run: python -m pytest tests/test_jira_guard.py -q
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
    def test_it_strips_the_protocol_and_the_trailing_slash(self):
        for v in (
            "https://demo.atlassian.net",
            "http://demo.atlassian.net/",
            "demo.atlassian.net/",
            "  DEMO.atlassian.net  ",
        ):
            self.assertEqual(_host(v), SANDBOX, v)

    def test_it_handles_an_empty_value(self):
        self.assertEqual(_host(""), "")
        self.assertEqual(_host(None), "")


class TestAllowlist(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("WRITE_ALLOWLIST", None)

    def test_a_different_spelling_is_still_the_same_site(self):
        # An https:// written into .env — this once blocked every write
        j = jira(site="https://demo.atlassian.net", allow="https://demo.atlassian.net/,localhost")
        self.assertEqual(j.site, SANDBOX)
        self.assertIn(SANDBOX, j.allow)

    def test_an_allowed_site_lets_writes_through(self):
        j = jira()
        self.assertIn(j.site, j.allow)

    def test_a_live_domain_is_blocked(self):
        j = jira(site=REAL, allow=SANDBOX)
        with self.assertRaises(WriteBlocked):
            j._call("POST", "/issue", {"x": 1}, write=True)

    def test_the_block_message_names_the_site_and_the_allowlist(self):
        j = jira(site=REAL, allow=SANDBOX)
        try:
            j._call("PUT", "/issue/X", {}, write=True)
            self.fail("it was not blocked")
        except WriteBlocked as e:
            self.assertIn(REAL, str(e))
            self.assertIn(SANDBOX, str(e))

    def test_an_empty_allowlist_leaves_only_localhost(self):
        os.environ.pop("WRITE_ALLOWLIST", None)
        j = Jira(site=SANDBOX, email="a@b.c", token="t", project="ECHO")
        self.assertNotIn(SANDBOX, j.allow)


class TestWriteGateDefaults(unittest.TestCase):
    """A write function never reaches the network without approve (dry_run)."""

    def setUp(self):
        self.j = jira()

    def tearDown(self):
        os.environ.pop("WRITE_ALLOWLIST", None)

    def test_everything_is_a_dry_run_by_default(self):
        self.assertTrue(self.j.create_issue("x")["dry_run"])
        self.assertTrue(self.j.comment("ECHO-1", "x")["dry_run"])
        self.assertTrue(self.j.set_fields("ECHO-1", {"duedate": "2026-10-01"})["dry_run"])
        self.assertTrue(self.j.link("ECHO-1", "ECHO-2")["dry_run"])

    def test_a_dry_run_shows_what_it_would_change(self):
        self.assertEqual(
            self.j.set_fields("ECHO-1", {"duedate": "2026-10-01"})["would_set"],
            {"duedate": "2026-10-01"},
        )
        self.assertEqual(self.j.comment("ECHO-1", "please confirm")["text"], "please confirm")


class TestConfigErrors(unittest.TestCase):
    def test_missing_settings_are_reported_at_once(self):
        # env is slotted in empty — with a real .env the constructor would pick values up
        # from there and the test would pass for the wrong reason
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
