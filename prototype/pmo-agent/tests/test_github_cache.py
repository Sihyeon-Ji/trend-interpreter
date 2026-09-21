"""The changed-file cache — no network, no gh, no real cache file.

`REPO_FILES=on` costs one API call per commit. Against the live repository that was 50
seconds for 64 commits, paid again on every run, and most of a demo's running time.

Caching it is not a guess about staleness. A git sha *is* the hash of the commit's
content, so the files a given sha touched cannot change and a hit is as good as a fetch,
for good. That makes the interesting tests the ones about what must **not** be cached: a
failed call yields an empty file list, and remembering it would turn one bad network
moment into a commit that permanently looks like it touched nothing.

Run: pytest -q
"""

from __future__ import annotations

import json

import pytest

from pmo_agent.adapters import github as mod
from pmo_agent.adapters.github import GitHub, GitHubError


@pytest.fixture(autouse=True)
def cache_in_tmp(tmp_path, monkeypatch):
    """Point the cache at a temporary directory — never at the developer's own."""
    monkeypatch.setattr(mod, "data_dir", lambda: tmp_path)
    return tmp_path


def commit(sha, day="2026-09-15"):
    return {"sha": sha, "date": day, "message": "feat: work", "name": "Ada", "files": []}


class Fake(GitHub):
    """A GitHub whose every network call is a dictionary, and which counts the calls."""

    def __init__(self, commits, files=None, fails=()):
        self.repo = "o/r"
        self._commits = commits
        self._files = files or {}
        self._fails = set(fails)
        self.asked: list = []

    def pulls(self, _state="all"):
        return []

    def commits(self, _limit=100, branch=""):
        return [dict(c) for c in self._commits]

    def branches(self):
        return ["main"]

    def repo_info(self):
        return {"name": "r"}

    def commit_files(self, sha):
        self.asked.append(sha)
        if sha in self._fails:
            raise GitHubError("502 from the API")
        return list(self._files.get(sha, []))


class TestItAsksOnceAndRemembers:
    def test_a_second_snapshot_asks_for_nothing(self):
        gh = Fake([commit("a1"), commit("b2")], {"a1": ["apps/api/x.py"], "b2": ["docs/y.md"]})
        first = gh.snapshot(10, with_files=True)
        assert sorted(gh.asked) == ["a1", "b2"]

        gh.asked.clear()
        second = gh.snapshot(10, with_files=True)
        assert gh.asked == [], "the second run went back to the network"
        assert [c["files"] for c in second["commits"]] == [c["files"] for c in first["commits"]]

    def test_only_the_new_commits_are_asked_for(self):
        gh = Fake([commit("a1")], {"a1": ["apps/api/x.py"], "c3": ["apps/web/z.tsx"]})
        gh.snapshot(10, with_files=True)

        gh._commits = [commit("c3", "2026-09-16"), commit("a1")]
        gh.asked.clear()
        got = gh.snapshot(10, with_files=True)
        assert gh.asked == ["c3"]
        assert {c["sha"]: c["files"] for c in got["commits"]} == {
            "a1": ["apps/api/x.py"],
            "c3": ["apps/web/z.tsx"],
        }

    def test_a_caller_editing_the_files_list_cannot_reach_the_cache(self):
        # Free today, because the cache is re-read from disk. Pinned anyway: the moment
        # anyone keeps it in memory, handing out the stored list itself would let a
        # caller's append rewrite history for every later run.
        gh = Fake([commit("a1")], {"a1": ["apps/api/x.py"]})
        got = gh.snapshot(10, with_files=True)
        got["commits"][0]["files"].append("nonsense.py")
        assert mod.cache_load()["o/r"]["a1"] == ["apps/api/x.py"]

    def test_without_the_flag_nothing_is_fetched_or_stored(self, cache_in_tmp):
        gh = Fake([commit("a1")], {"a1": ["apps/api/x.py"]})
        gh.snapshot(10, with_files=False)
        assert gh.asked == []
        assert not (cache_in_tmp / mod.CACHE_FILE).exists()


class TestWhatMustNotBeRemembered:
    def test_a_failed_call_is_not_cached(self):
        # Otherwise one bad network moment makes a commit look permanently empty
        gh = Fake([commit("a1")], {"a1": ["apps/api/x.py"]}, fails=["a1"])
        assert gh.snapshot(10, with_files=True)["commits"][0]["files"] == []

        gh._fails.clear()
        gh.asked.clear()
        got = gh.snapshot(10, with_files=True)
        assert gh.asked == ["a1"], "it remembered the failure"
        assert got["commits"][0]["files"] == ["apps/api/x.py"]

    def test_a_failure_does_not_lose_the_commits_that_worked(self):
        gh = Fake(
            [commit("a1"), commit("b2")],
            {"a1": ["apps/api/x.py"], "b2": ["docs/y.md"]},
            fails=["a1"],
        )
        got = gh.snapshot(10, with_files=True)
        assert {c["sha"]: c["files"] for c in got["commits"]} == {
            "a1": [],
            "b2": ["docs/y.md"],
        }

    def test_a_commit_that_genuinely_touched_nothing_is_cached(self):
        # An empty commit's empty list is a fact, unlike a failure's empty list
        gh = Fake([commit("a1")], {"a1": []})
        gh.snapshot(10, with_files=True)
        gh.asked.clear()
        gh.snapshot(10, with_files=True)
        assert gh.asked == []


class TestTheFileOnDisk:
    def test_two_repositories_do_not_share_entries(self, cache_in_tmp):
        one = Fake([commit("a1")], {"a1": ["apps/api/x.py"]})
        one.snapshot(10, with_files=True)
        two = Fake([commit("a1")], {"a1": ["totally/other.py"]})
        two.repo = "other/repo"
        assert two.snapshot(10, with_files=True)["commits"][0]["files"] == ["totally/other.py"]

        stored = json.loads((cache_in_tmp / mod.CACHE_FILE).read_text(encoding="utf-8"))
        assert set(stored) == {"o/r", "other/repo"}

    def test_a_corrupt_cache_is_ignored_rather_than_fatal(self, cache_in_tmp):
        (cache_in_tmp / mod.CACHE_FILE).write_text("{not json", encoding="utf-8")
        gh = Fake([commit("a1")], {"a1": ["apps/api/x.py"]})
        assert gh.snapshot(10, with_files=True)["commits"][0]["files"] == ["apps/api/x.py"]

    def test_a_cache_holding_something_other_than_a_map_is_ignored(self, cache_in_tmp):
        (cache_in_tmp / mod.CACHE_FILE).write_text("[1, 2, 3]", encoding="utf-8")
        assert mod.cache_load() == {}

    def test_it_is_trimmed_rather_than_growing_without_end(self, cache_in_tmp, monkeypatch):
        monkeypatch.setattr(mod, "CACHE_MAX", 3)
        mod.cache_save({"o/r": {f"s{i}": [] for i in range(10)}})
        kept = json.loads((cache_in_tmp / mod.CACHE_FILE).read_text(encoding="utf-8"))["o/r"]
        assert list(kept) == ["s7", "s8", "s9"], "it should keep the newest"

    def test_an_unwritable_cache_is_a_slow_run_not_a_failure(self, monkeypatch):
        def refuse(*_a, **_k):
            raise OSError("read-only filesystem")

        monkeypatch.setattr(mod, "_cache_path", refuse)
        gh = Fake([commit("a1")], {"a1": ["apps/api/x.py"]})
        assert gh.snapshot(10, with_files=True)["commits"][0]["files"] == ["apps/api/x.py"]
