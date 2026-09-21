"""Shared test setup.

`tools` keeps its adapters and its last repository reading at module level, which is what
makes a demo read the repository once instead of three times. Across tests that same
memory is a way for one test's data to turn up in the next one's answer, so it is cleared
before each.
"""

from __future__ import annotations

import pytest

from pmo_agent import tools


@pytest.fixture(autouse=True)
def forget_the_last_reading():
    tools.forget_snapshot()
    yield
    tools.forget_snapshot()
