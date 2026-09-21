"""The local calendar adapter — a backend for running the availability maths without OAuth.

Same idea as the board (memory.py) and the repo (memory_repo.py).
It returns **the same shapes** as the MS Graph adapter, so availability.py and capacity.py
never need to know which one is connected.

Read-only — there is no path to create or delete anyone's events.
"""

from __future__ import annotations

import datetime as _dt
import json
import os

from pmo_agent.env import data_dir

STORE = str(data_dir() / "calendar_state.json")


class MemoryCalendar:
    """An adapter that treats one file as the calendar. Same method names and shapes as MS Graph."""

    def __init__(self, path: str | None = None, data=None):
        self.path: str | None = None if data is not None else (path or STORE)
        self.source = "local"
        self._data = data

    def _load(self) -> dict:
        if self._data is None:
            if self.path and os.path.exists(self.path):
                with open(self.path, encoding="utf-8") as handle:
                    self._data = json.load(handle)
            else:
                self._data = {"source": "local", "events": []}
        return self._data

    # ---------- reads ----------
    def whoami(self) -> str:
        return "local"

    def events(self, days: int = 20, attendee: str = "", start=None) -> list:
        """Events in the `days` calendar days from `start` (today by default).

        Pass an earlier `start` to look backwards — that is how cause.py finds out
        what a person was doing while a task sat still.
        """
        first = start or _dt.date.today()
        if isinstance(first, str):
            first = _dt.date.fromisoformat(first[:10])
        last = first + _dt.timedelta(days=int(days))
        rows = [
            e
            for e in self._load().get("events", [])
            if e.get("date") and first.isoformat() <= e["date"][:10] < last.isoformat()
        ]
        if attendee:
            rows = [e for e in rows if e.get("attendee") == attendee]
        rows.sort(key=lambda e: (e.get("date", ""), e.get("start", "")))
        return rows

    def busy_hours(self, days: int = 20) -> dict:
        """{person: {ISO date: meeting hours}} — the shape availability.from_busy_hours takes."""
        out: dict[str, dict[str, float]] = {}
        for e in self.events(days):
            who, day = e.get("attendee", ""), (e.get("date") or "")[:10]
            if not who or not day:
                continue
            out.setdefault(who, {})
            out[who][day] = out[who].get(day, 0.0) + float(e.get("hours") or 0.0)
        return out


def load(path: str | None = None) -> MemoryCalendar:
    return MemoryCalendar(path)
