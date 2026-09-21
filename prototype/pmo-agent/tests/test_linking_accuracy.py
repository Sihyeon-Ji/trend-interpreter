"""The headline number, measured rather than remembered — no network.

The README opens with precision, recall and mean confidence for keyless linking. For a
project whose whole argument is "it does not say what it cannot show", that figure being
a remembered one from a run months ago is the worst possible place to drift. So it is
measured here, at several dates, and the README is held to what comes out.

The two numbers are not equally important and are not treated as such:

  precision has to be **exactly 1.00**. A wrong link puts somebody else's commit on a task
            and every number built on top inherits it silently. There is no acceptable
            rate of that, so the test admits none
  recall    has a floor, not a target. A commit the linker refuses to place is reported as
            unlinked and costs nothing but a little coverage — that is the restraint
            working, and tightening it further would be a fair trade

Measured across dates on purpose. One good day is a coincidence; the world regenerates
from `today`, so a rule that happens to suit this week shows up immediately.

Run: pytest -q
"""

from __future__ import annotations

import re
from pathlib import Path

import measure_links
import pytest

README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
DATES = 8
# The worst date measures 0.857, which *displays* as 0.86. Claiming 0.86 as a floor
# would be the rounding presented as a guarantee, so the floor stays at what is
# actually true. Nine people across three teams did lift it — fewer tasks per person
# means the author signal discriminates better — just not to 0.86.
RECALL_FLOOR = 0.85


@pytest.fixture(scope="module")
def rows():
    return measure_links.over_dates(DATES)


class TestAccuracy:
    def test_it_never_makes_a_wrong_link(self, rows):
        bad = [(r["date"], r["wrong_examples"]) for r in rows if r["wrong"]]
        assert not bad, bad

    def test_precision_is_exactly_one_at_every_date(self, rows):
        assert [r["precision"] for r in rows] == [1.0] * DATES

    def test_recall_holds_its_floor_at_every_date(self, rows):
        worst = min(r["recall"] for r in rows)
        assert worst >= RECALL_FLOOR, f"recall fell to {worst}"

    def test_there_is_something_to_measure(self, rows):
        # A world that stopped producing commits would pass everything above vacuously
        assert all(r["commits"] > 40 for r in rows), [r["commits"] for r in rows]

    def test_the_unlinked_are_refusals_not_losses(self, rows):
        # right + wrong + unlinked has to account for every commit that had an answer
        for r in rows:
            assert r["right"] + r["wrong"] + r["unlinked"] == r["commits"], r


class TestTheReadmeSaysWhatIsMeasured:
    def test_the_claimed_precision_is_the_measured_one(self, rows):
        claimed = re.search(r"\*\*precision ([\d.]+)\*\*", README)
        assert claimed, "the README no longer states a precision"
        assert float(claimed.group(1)) == rows[0]["precision"]

    def test_the_claimed_recall_floor_is_not_above_the_measured_one(self, rows):
        claimed = re.search(r"\*\*recall ([\d.]+)\*\* at worst", README)
        assert claimed, "the README no longer states a recall floor"
        assert float(claimed.group(1)) <= min(r["recall"] for r in rows)

    def test_the_claimed_date_count_is_the_measured_one(self, rows):
        claimed = re.search(r"measured at \*\*(\d+) dates\*\*", README)
        assert claimed, "the README no longer says how many dates were measured"
        assert int(claimed.group(1)) == len(rows)
