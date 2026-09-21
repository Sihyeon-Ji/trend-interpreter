"""The local repository adapter — a backend for code signals without a GitHub account.

Same idea as adapters/memory.py (the board). It returns **the same shapes** as the GitHub
adapter, so signals.py never needs to know which one is connected.

There is exactly one difference from a real repository: the data comes from a JSON file.
That keeps the demo off the network, off accounts and off rate limits, and lets us reproduce
the exact situation we want to show.

Read-only here too — there are no write methods.
"""

from __future__ import annotations

import json
import os

from pmo_agent.env import data_dir

STORE = str(data_dir() / "repo_state.json")


class MemoryRepo:
    """An adapter that treats one file as the repository. Same methods and shapes as GitHub."""

    def __init__(self, path: str | None = None, repo: str = "echo-team/echo-app", data=None):
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

    # ---------- reads (the same interface as GitHub) ----------
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
        data = self._load()
        return {
            "repo": data.get("repo", self.repo),
            "info": self.repo_info(),
            "commits": self.commits(commit_limit),
            "pulls": self.pulls("all"),
            "branches": self.branches(),
            "people": data.get("people", {}),
        }


def load(path: str | None = None) -> MemoryRepo:
    return MemoryRepo(path)
