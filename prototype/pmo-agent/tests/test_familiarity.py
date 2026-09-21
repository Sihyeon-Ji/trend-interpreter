"""Handover plausibility tests — no network.

The rebalance search is arithmetic on who is free. Left alone it will propose that the
person who has only ever written documentation take over the data migration, and quote a
finish date that is perfectly correct about a move nobody would make.

What is checked here is mostly the *refusals*: when there is no evidence, the check has to
get out of the way rather than block everything. Evidence about people is the easiest kind
to be wrong about, and the cost of being wrong is telling a team who is not capable.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt

import pytest

from pmo_agent import capacity, familiarity, schedule

TODAY = dt.date(2026, 9, 21)


def commit(who, *paths, sha="a1", day="2026-09-15"):
    return {
        "sha": sha,
        "date": day,
        "author": who,
        "login": who,
        "name": who,
        "email": f"{who}@t.test",
        "message": "feat: work",
        "branch": "feat/x",
        "files": list(paths),
    }


def linked_with(**by_key):
    return {key: {"commits": commits, "pulls": [], "links": []} for key, commits in by_key.items()}


class TestArea:
    @pytest.mark.parametrize(
        ("path", "area"),
        [
            ("apps/api/src/builder_cup/auth.py", "apps/api"),
            ("apps/web/src/list-view.tsx", "apps/web"),
            ("docs/api-spec.md", "docs"),
            ("tests/test_search.py", "tests"),
            ("README.md", ""),
            ("", ""),
        ],
    )
    def test_the_area_is_the_directory_not_the_file(self, path, area):
        assert familiarity.area_of(path) == area

    def test_a_backslash_path_is_read_the_same_way(self):
        assert familiarity.area_of(r"apps\api\src\auth.py") == "apps/api"


class TestHistory:
    def test_it_counts_where_each_person_has_committed(self):
        history = familiarity.by_person(
            {},
            [
                commit("Ada", "apps/api/src/a.py", sha="a"),
                commit("Ada", "apps/api/src/b.py", sha="b"),
                commit("Bo", "docs/plan.md", sha="c"),
            ],
        )
        assert history["Ada"]["apps/api"] == 2
        assert history["Bo"]["docs"] == 1

    def test_a_task_takes_the_area_its_own_commits_agree_on(self):
        linked = linked_with(
            T1=[
                commit("Ada", "apps/api/src/a.py", sha="a"),
                commit("Ada", "apps/api/src/b.py", sha="b"),
                commit("Ada", "docs/x.md", sha="c"),
            ]
        )
        assert familiarity.task_areas(linked)["T1"] == "apps/api"


class TestChecker:
    def setup_method(self):
        self.commits = [
            commit("Ada", "apps/api/src/a.py", sha="a"),
            commit("Ada", "apps/api/src/b.py", sha="b"),
            commit("Bo", "docs/one.md", sha="c"),
            commit("Bo", "docs/two.md", sha="d"),
        ]
        self.linked = linked_with(T1=[self.commits[0], self.commits[1]])
        self.tasks = schedule.to_tasks([{"key": "T1", "summary": "API work", "assignee": "Ada"}])

    def test_someone_with_history_in_the_area_can_take_it(self):
        check = familiarity.checker(self.linked, self.commits)
        assert check(self.tasks["T1"], "Ada")

    def test_someone_with_no_history_in_the_area_cannot(self):
        check = familiarity.checker(self.linked, self.commits)
        assert not check(self.tasks["T1"], "Bo")

    def test_one_commit_is_a_drive_by_not_a_speciality(self):
        commits = [*self.commits, commit("Cal", "apps/api/src/c.py", sha="e")]
        check = familiarity.checker(self.linked, commits)
        task = self.tasks["T1"]
        assert not check(task, "Cal")
        assert familiarity.checker(self.linked, commits, min_commits=1)(task, "Cal")

    def test_a_task_with_no_known_area_is_open_to_anyone(self):
        # Absence of evidence is not evidence of incapacity
        check = familiarity.checker(self.linked, self.commits)
        stranger = schedule.to_tasks([{"key": "T9", "summary": "Unknown", "assignee": "Ada"}])
        assert check(stranger["T9"], "Bo")

    def test_with_no_history_at_all_there_is_no_checker(self):
        # Returning None rather than a permissive function lets the caller say "not vetted"
        assert familiarity.checker({}, []) is None
        assert familiarity.checker(linked_with(T1=[]), []) is None

    def test_commits_with_no_paths_produce_no_judgement(self):
        # A repository read without REPO_FILES has no paths, so it cannot judge anyone
        bare = [commit("Ada", sha="a"), commit("Bo", sha="b")]
        assert familiarity.checker(linked_with(T1=bare), bare) is None


class TestRebalance:
    def test_an_implausible_handover_is_not_proposed(self):
        tasks = schedule.to_tasks(
            [
                {"key": "T1", "summary": "API work", "assignee": "Ada", "points": 10},
                {"key": "T2", "summary": "More API", "assignee": "Ada", "points": 5},
                {"key": "T3", "summary": "Docs", "assignee": "Bo", "points": 1},
            ]
        )
        commits = [
            commit("Ada", "apps/api/src/a.py", sha="a"),
            commit("Ada", "apps/api/src/b.py", sha="b"),
            commit("Bo", "docs/one.md", sha="c"),
            commit("Bo", "docs/two.md", sha="d"),
        ]
        linked = linked_with(T1=commits[:2], T2=commits[:2], T3=commits[2:])
        check = familiarity.checker(linked, commits)

        free = capacity.rebalance(tasks, TODAY, max_moves=2)
        vetted = capacity.rebalance(tasks, TODAY, max_moves=2, can_take=check)

        assert free["moves"], "the unguarded search should want to move something"
        assert all(m["to"] != "Bo" for m in vetted["moves"]), vetted["moves"]

    def test_without_a_checker_the_search_is_unchanged(self):
        tasks = schedule.to_tasks(
            [{"key": f"T{i}", "summary": f"task {i}", "assignee": "Ada", "points": 5} for i in "12"]
            + [{"key": "Z", "summary": "Z", "assignee": "Bo", "points": 1}]
        )
        assert capacity.rebalance(tasks, TODAY, can_take=None) == capacity.rebalance(tasks, TODAY)
