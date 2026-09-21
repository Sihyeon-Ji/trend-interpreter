"""The README is a claim, so it gets checked like one.

A project whose whole argument is "it does not say things it cannot show" cannot afford a
README that has drifted from the code. And it does drift: every one of these checks was
written after finding a real mismatch — an endpoint added and never documented, a test
count three releases old, a weight quoted from before it was tuned.

Only checkable claims are here. Prose is not testable and is not the point; a number, a
route, a filename or a flag is.

Run: pytest -q
"""

from __future__ import annotations

import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pmo_agent import api, linking, tools

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
CASES = ROOT / "evaluation-cases" / "cases.jsonl"


def case_lines() -> list:
    return [x for x in CASES.read_text(encoding="utf-8").splitlines() if x.strip()]


class TestNumbers:
    @pytest.mark.parametrize(
        ("name", "claimed"),
        [("W_AUTHOR", 0.30), ("W_WORDS", 0.35), ("W_PATH", 0.20), ("W_TIME", 0.15)],
    )
    def test_the_signal_weights_are_what_the_table_says(self, name, claimed):
        assert getattr(linking, name) == pytest.approx(claimed)

    def test_the_test_count_is_current(self):
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--collect-only", str(ROOT / "tests")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout
        collected = int(re.search(r"(\d+) tests collected", out).group(1))
        claimed = int(re.search(r"\*\*(\d+) tests", README).group(1))
        assert collected == claimed, f"README says {claimed}, pytest collects {collected}"

    def test_the_evaluation_case_count_is_current(self):
        claimed = int(re.search(r"the (\d+) evaluation cases", README).group(1))
        assert len(case_lines()) == claimed

    def test_the_detect_and_restraint_split_is_current(self):
        rows = case_lines()
        detect = sum(1 for x in rows if '"group": "detect"' in x)
        claimed = re.search(r"— (\d+) detect, \*\*(\d+) restraint\*\*", README)
        assert claimed, "the README no longer states the detect/restraint split"
        assert (detect, len(rows) - detect) == (int(claimed.group(1)), int(claimed.group(2)))


class TestInventory:
    def test_every_endpoint_is_documented(self):
        served = {r.path for r in api.app.routes if getattr(r, "path", "").startswith("/api/")}
        listed = set(re.findall(r"`(?:GET|POST) (/api/[a-z]+)`", README))
        assert served == listed, f"only served: {served - listed} | only listed: {listed - served}"

    def test_every_test_file_is_in_the_table(self):
        listed = set(re.findall(r"\| `(test_[a-z_]+\.py)`", README))
        actual = {p.name for p in (ROOT / "tests").glob("test_*.py")}
        assert actual == listed, f"only real: {actual - listed} | only listed: {listed - actual}"

    def test_every_documented_flag_is_read_somewhere(self):
        sources = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))
        for flag in re.findall(r"\| `([A-Z_]+)` \| `", README):
            assert f'"{flag}"' in sources, f"README documents {flag}, nothing reads it"

    def test_every_module_in_the_layout_exists(self):
        block = README.split("```", 2)[1] if "src/pmo_agent/" in README else ""
        for name in re.findall(r"^  ([a-z_]+\.py) ", block, re.MULTILINE):
            assert (ROOT / "src" / "pmo_agent" / name).exists(), f"layout lists missing {name}"


class TestPromises:
    """The claims that are the whole point, checked the way the README says they are."""

    def test_the_tool_layer_never_passes_approve_true(self):
        assert "approve=True" not in inspect.getsource(tools)

    def test_the_repository_adapters_have_no_write_methods(self):
        from pmo_agent.adapters.github import GitHub
        from pmo_agent.adapters.memory_repo import MemoryRepo

        forbidden = {"create", "update", "write", "post", "edit", "delete", "push", "commit"}
        for adapter in (GitHub, MemoryRepo):
            assert not forbidden & set(dir(adapter)), adapter.__name__

    def test_the_calendar_and_notes_adapters_have_no_write_methods(self):
        from pmo_agent.adapters.memory_calendar import MemoryCalendar
        from pmo_agent.adapters.memory_notes import MemoryNotes
        from pmo_agent.adapters.ms_calendar import MSCalendar
        from pmo_agent.adapters.notion import NotionNotes

        forbidden = {"create", "update", "write", "post", "edit", "delete", "append"}
        for adapter in (MemoryCalendar, MSCalendar, MemoryNotes, NotionNotes):
            assert not forbidden & set(dir(adapter)), adapter.__name__
