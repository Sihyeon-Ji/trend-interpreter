"""로컬 캘린더 어댑터 — OAuth 없이 가용 시간 계산을 돌리기 위한 백엔드.

보드(memory.py)·저장소(memory_repo.py)와 같은 발상이다.
MS Graph 어댑터와 **같은 모양**을 돌려주므로 availability.py 와 capacity.py 는
어느 쪽에 붙어 있는지 알 필요가 없다.

읽기 전용이다 — 남의 일정을 만들거나 지울 경로가 없다.
"""

from __future__ import annotations

import json
import os

from pmo_agent.env import data_dir

STORE = str(data_dir() / "calendar_state.json")


class MemoryCalendar:
    """파일 한 개를 캘린더로 쓰는 어댑터. MS Graph 어댑터와 메서드 이름·반환 모양이 같다."""

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

    # ---------- 읽기 ----------
    def whoami(self) -> str:
        return "local"

    def events(self, days: int = 20, attendee: str = "") -> list:
        """앞으로 days 영업일 안의 일정. attendee 를 주면 그 사람 것만."""
        rows = list(self._load().get("events", []))
        if attendee:
            rows = [e for e in rows if e.get("attendee") == attendee]
        rows.sort(key=lambda e: (e.get("date", ""), e.get("start", "")))
        return rows

    def busy_hours(self, days: int = 20) -> dict:
        """{사람: {ISO날짜: 회의시간}} — availability.from_busy_hours 가 받는 모양."""
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
