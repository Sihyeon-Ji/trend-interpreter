"""The local meeting-notes adapter — the fourth tool, and the only one that holds words.

The board holds status, the repository holds what was done, the calendar holds where the
time went. None of them can say *what was decided*. A note can, and only a note does:

    "External IdP spec change: the identity provider changed its token format, forcing a
     redesign. Authentication cannot move until we agree the new shape."

It is prose. There is no ticket key in it, no structure, and whoever was in the room wrote
it. Tying it to a task is the same inference problem as tying a commit to one, which is why
linking.py does both — see cause.py.

Read-only, like the repository and the calendar. There are no write methods here: an agent
has no business editing what someone wrote down in a meeting.

A real deployment would put Notion, Confluence or Google Docs behind this same shape.
"""

from __future__ import annotations

import datetime as _dt
import json
import os

from pmo_agent.env import data_dir

DEFAULT = "notes_state.json"


class MemoryNotes:
    """An adapter that treats one file as the notes archive."""

    def __init__(self, path: str | None = None, source: str = "echo-team/notes", data=None):
        self.path = path or str(data_dir() / DEFAULT)
        self.source = source
        self._data = data

    def _load(self) -> dict:
        if self._data is not None:
            return self._data
        if not os.path.exists(self.path):
            return {"source": self.source, "notes": []}
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle)

    # ---------- reads ----------
    def whoami(self) -> str:
        return self._load().get("source", self.source)

    def notes(self, days: int = 30, author: str = "", start=None) -> list:
        """Notes in the `days` days from `start` (today by default).

        Explaining a stall means looking backwards, so callers pass an earlier `start` —
        the same window the calendar adapter takes, for the same reason.
        """
        first = start or _dt.date.today()
        if isinstance(first, str):
            first = _dt.date.fromisoformat(first[:10])
        last = first + _dt.timedelta(days=int(days))
        rows = [
            n
            for n in self._load().get("notes", [])
            if n.get("date") and first.isoformat() <= n["date"][:10] < last.isoformat()
        ]
        if author:
            rows = [n for n in rows if n.get("author") == author]
        rows.sort(key=lambda n: (n.get("date", ""), n.get("author", "")))
        return rows


def load(path: str | None = None) -> MemoryNotes:
    return MemoryNotes(path)
