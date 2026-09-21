"""로컬 저장소 어댑터 — GitHub 계정 없이 코드 신호를 돌리기 위한 백엔드.

adapters/memory.py(보드)와 같은 발상이다. GitHub 어댑터와 **같은 모양**을 돌려주므로
agent/signals.py 는 어느 쪽에 붙어 있는지 알 필요가 없다.

실제 저장소와 다른 점은 하나뿐이다: 데이터가 JSON 파일에서 온다.
그래서 데모가 네트워크·계정·레이트리밋에 좌우되지 않고, 시연할 상황을 정확히 재현할 수 있다.

여기도 읽기 전용이다 — 쓰기 메서드가 없다.
"""

from __future__ import annotations

import json
import os

from pmo_agent.env import data_dir

STORE = str(data_dir() / "repo_state.json")


class MemoryRepo:
    """파일 한 개를 저장소로 쓰는 어댑터. GitHub 클래스와 메서드 이름·반환 모양이 같다."""

    def __init__(self, path: str | None = None, repo: str = "echo-team/echo-pmo-demo", data=None):
        self.path = None if data is not None else (path or STORE)
        self.repo = repo
        self._data = data

    def _load(self) -> dict:
        if self._data is None:
            if self.path and os.path.exists(self.path):
                with open(self.path, encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {
                    "repo": self.repo,
                    "info": {},
                    "commits": [],
                    "pulls": [],
                    "branches": [],
                }
        return self._data

    # ---------- 읽기 (GitHub 과 동일한 인터페이스) ----------
    def whoami(self) -> str:
        return "local"

    def repo_info(self) -> dict:
        d = self._load()
        info = dict(d.get("info") or {})
        info.setdefault("full_name", d.get("repo", self.repo))
        info.setdefault("default_branch", "develop")
        info.setdefault("private", True)
        return info

    def commits(self, limit: int = 100, branch: str = "") -> list:
        rows = self._load().get("commits", [])
        if branch:
            rows = [c for c in rows if c.get("branch", "") == branch]
        return sorted(rows, key=lambda c: c.get("date", ""), reverse=True)[:limit]

    def pulls(self, state: str = "all", limit: int = 50) -> list:
        rows = self._load().get("pulls", [])
        if state != "all":
            rows = [p for p in rows if p.get("state") == state]
        return rows[:limit]

    def reviews(self, number: int) -> list:
        for p in self._load().get("pulls", []):
            if p.get("number") == int(number):
                return p.get("reviews", [])
        return []

    def branches(self) -> list:
        return list(self._load().get("branches", []))

    def collaborators(self) -> list:
        return list(self._load().get("collaborators", []))

    def snapshot(self, commit_limit: int = 100) -> dict:
        return {
            "repo": self._load().get("repo", self.repo),
            "info": self.repo_info(),
            "commits": self.commits(commit_limit),
            "pulls": self.pulls("all"),
            "branches": self.branches(),
        }


def load(path: str | None = None) -> MemoryRepo:
    return MemoryRepo(path)
