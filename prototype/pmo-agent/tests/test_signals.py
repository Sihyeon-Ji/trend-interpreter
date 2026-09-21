"""보드-코드 대조 테스트 — 네트워크 없이 돈다.

가장 중요한 두 가지:
  1. 어긋남을 실제로 잡는가 (seed_repo 가 심어둔 것이 그대로 검출되는가)
  2. 근거가 없을 때 경고하지 않는가 (모르는 것을 '없다'고 말하지 않는가)

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import unittest

from pmo_agent import schedule, signals  # noqa: E402
from pmo_agent.adapters.memory_repo import MemoryRepo  # noqa: E402
from pmo_agent.seeds import board as seed  # noqa: E402
from pmo_agent.seeds import repo as seed_repo

TODAY = dt.date(2026, 9, 21)


def tasks():
    return schedule.to_tasks(
        [
            {
                "key": "ECHO-1",
                "summary": "요구사항",
                "status": "Done",
                "assignee": "갑",
                "points": 2,
            },
            {
                "key": "ECHO-2",
                "summary": "스키마",
                "status": "In Progress",
                "assignee": "을",
                "points": 3,
            },
            {"key": "ECHO-3", "summary": "API", "status": "To Do", "assignee": "갑", "points": 3},
            {
                "key": "ECHO-4",
                "summary": "문서",
                "status": "In Progress",
                "assignee": "을",
                "points": 1,
            },
        ]
    )


def commit(key, days_ago, author="갑", email=None, login=None, name=None):
    d = TODAY - dt.timedelta(days=days_ago)
    return {
        "sha": "abc1234",
        "date": d.isoformat(),
        "author": author,
        "login": login,
        "name": name or author,
        "email": email or f"{author}@t.test",
        "message": f"{key} 작업",
        "url": f"https://x/commit/{key}",
    }


def pull(number, key, state="open", updated_days=0, draft=False, reviewers=()):
    return {
        "number": number,
        "title": f"{key} 구현",
        "state": state,
        "draft": draft,
        "author": "을",
        "branch": f"feat/{key.lower()}",
        "created": (TODAY - dt.timedelta(days=updated_days + 2)).isoformat(),
        "updated": (TODAY - dt.timedelta(days=updated_days)).isoformat(),
        "merged": False,
        "reviewers": list(reviewers),
        "url": f"https://x/pull/{number}",
    }


class TestKeyExtraction(unittest.TestCase):
    def test_문장에서_키를_뽑는다(self):
        self.assertEqual(signals.keys_in("ECHO-12 스키마 수정"), {"ECHO-12"})
        self.assertEqual(signals.keys_in("fix ECHO-1 and ECHO-22"), {"ECHO-1", "ECHO-22"})

    def test_소문자도_잡는다(self):
        self.assertEqual(signals.keys_in("feat/echo-7 작업"), {"ECHO-7"})

    def test_키가_아닌_것은_무시한다(self):
        self.assertEqual(signals.keys_in("버전 1-2 업데이트"), set())
        self.assertEqual(signals.keys_in(""), set())


class TestLink(unittest.TestCase):
    def test_커밋_메시지로_연결한다(self):
        linked = signals.link(tasks(), [commit("ECHO-2", 1)], [])
        self.assertEqual(len(linked["ECHO-2"]["commits"]), 1)
        self.assertEqual(linked["ECHO-1"]["commits"], [])

    def test_PR_제목과_브랜치로_연결한다(self):
        linked = signals.link(tasks(), [], [pull(1, "ECHO-3")])
        self.assertEqual(len(linked["ECHO-3"]["pulls"]), 1)

    def test_보드에_없는_키는_버린다(self):
        linked = signals.link(tasks(), [commit("ECHO-99", 1)], [])
        self.assertNotIn("ECHO-99", linked)
        self.assertTrue(all(not v["commits"] for v in linked.values()))


class TestMismatches(unittest.TestCase):
    def find(self, ms, kind, key=None):
        return [m for m in ms if m["kind"] == kind and (key is None or m["key"] == key)]

    def test_완료인데_PR이_열려있다(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [], [pull(1, "ECHO-1")]), TODAY)
        self.assertTrue(self.find(ms, "done_with_open_pr", "ECHO-1"))

    def test_진행중인데_커밋이_오래됐다(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-2", 9)], []), TODAY)
        m = self.find(ms, "stalled", "ECHO-2")
        self.assertTrue(m)
        self.assertIn("9일 전", m[0]["detail"])

    def test_최근_커밋이면_멈춤이_아니다(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-2", 1)], []), TODAY)
        self.assertFalse(self.find(ms, "stalled"))

    def test_할일인데_커밋이_있다(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-3", 1)], []), TODAY)
        self.assertTrue(self.find(ms, "undeclared_progress", "ECHO-3"))

    def test_진행중인데_커밋이_아예_없다(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-2", 1)], []), TODAY)
        self.assertTrue(self.find(ms, "no_code_activity", "ECHO-4"))

    def test_PR이_리뷰를_기다린다(self):
        t = tasks()
        ms = signals.mismatches(
            t,
            signals.link(
                t, [commit("ECHO-2", 1)], [pull(7, "ECHO-2", updated_days=4, reviewers=["갑"])]
            ),
            TODAY,
        )
        m = self.find(ms, "review_waiting", "ECHO-2")
        self.assertTrue(m)
        self.assertIn("4일째", m[0]["detail"])
        self.assertIn("갑", m[0]["detail"])

    def test_초안_PR은_리뷰대기가_아니다(self):
        t = tasks()
        ms = signals.mismatches(
            t,
            signals.link(t, [commit("ECHO-2", 1)], [pull(8, "ECHO-2", updated_days=9, draft=True)]),
            TODAY,
        )
        self.assertFalse(self.find(ms, "review_waiting"))

    def test_근거_링크를_함께_준다(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [], [pull(1, "ECHO-1")]), TODAY)
        self.assertTrue(ms[0]["evidence"])

    def test_담당자와_상태를_함께_준다(self):
        t = tasks()
        ms = signals.mismatches(t, signals.link(t, [commit("ECHO-3", 1)], []), TODAY)
        m = self.find(ms, "undeclared_progress")[0]
        self.assertEqual(m["assignee"], "갑")
        self.assertEqual(m["status"], "To Do")


class TestIdentityMerge(unittest.TestCase):
    """실제 저장소에서 한 사람이 이름과 login 으로 갈려 집중도가 낮게 나온 적이 있다."""

    def test_같은_이메일이면_한_사람이다(self):
        cs = [
            commit("ECHO-1", 1, email="a@t.test", login=None, name="shji"),
            commit("ECHO-1", 2, email="a@t.test", login="Sihyeon-Ji", name="Sihyeon Ji"),
        ]
        m = signals.merge_identities(cs)
        self.assertEqual(len(m), 1)
        row = next(iter(m.values()))
        self.assertEqual(row["commits"], 2)
        self.assertEqual(row["author"], "Sihyeon-Ji")  # login 을 표시 이름으로
        self.assertIn("shji", row["aliases"])

    def test_이메일이_다르면_다른_사람이다(self):
        cs = [
            commit("ECHO-1", 1, email="a@t.test"),
            commit("ECHO-1", 1, email="b@t.test", author="을"),
        ]
        self.assertEqual(len(signals.merge_identities(cs)), 2)

    def test_병합_후_집중도가_올라간다(self):
        cs = [
            commit("ECHO-1", 1, email="a@t.test", name="shji"),
            commit("ECHO-1", 1, email="a@t.test", login="Sihyeon-Ji"),
            commit("ECHO-1", 1, email="b@t.test", author="을"),
        ]
        team = signals.team_activity({"commits": cs, "pulls": [], "branches": []}, TODAY)
        self.assertEqual(team["concentration"], 0.67)


class TestTeamActivity(unittest.TestCase):
    def test_한_사람에_몰리면_짚는다(self):
        cs = [commit("ECHO-1", 1) for _ in range(5)]
        t = signals.team_activity({"commits": cs, "pulls": [], "branches": []}, TODAY)
        self.assertEqual(t["concentration"], 1.0)
        self.assertTrue(any("한 사람" in n for n in t["notes"]))

    def test_PR이_없으면_리뷰절차_미가동을_짚는다(self):
        t = signals.team_activity(
            {"commits": [commit("ECHO-1", 1)], "pulls": [], "branches": []}, TODAY
        )
        self.assertTrue(any("PR 이 한 건도 없다" in n for n in t["notes"]))

    def test_커밋이_없으면_그것도_신호다(self):
        t = signals.team_activity({"commits": [], "pulls": [], "branches": []}, TODAY)
        self.assertTrue(any("커밋이 없다" in n for n in t["notes"]))

    def test_기간_밖_커밋은_세지_않는다(self):
        cs = [commit("ECHO-1", 30), commit("ECHO-2", 1)]
        self.assertEqual(
            signals.team_activity({"commits": cs, "pulls": [], "branches": []}, TODAY)["commits"], 1
        )


class TestEvidenceRequired(unittest.TestCase):
    """근거가 없을 때 경고하지 않는다 — 모르는 것을 '없다'고 말하면 전부 잡음이 된다."""

    def test_키_규칙을_안_쓰면_태스크_신호를_내지_않는다(self):
        snap = {
            "repo": "x/y",
            "commits": [
                {
                    "sha": "1",
                    "date": TODAY.isoformat(),
                    "author": "갑",
                    "login": None,
                    "name": "갑",
                    "email": "a@t",
                    "message": "그냥 커밋",
                    "url": "",
                }
            ],
            "pulls": [],
            "branches": ["main"],
        }
        s = signals.summary(tasks(), snap, TODAY)
        self.assertFalse(s["key_convention_in_use"])
        self.assertEqual(s["mismatches"], [])
        self.assertIn("연결할 근거가 없는", s["note"])

    def test_규칙을_쓰면_신호가_나온다(self):
        snap = {"repo": "x/y", "commits": [commit("ECHO-2", 9)], "pulls": [], "branches": []}
        s = signals.summary(tasks(), snap, TODAY)
        self.assertTrue(s["key_convention_in_use"])
        self.assertTrue(s["mismatches"])
        self.assertIsNone(s["note"])

    def test_저장소_신호는_규칙과_무관하게_나온다(self):
        snap = {"repo": "x/y", "commits": [], "pulls": [], "branches": []}
        self.assertTrue(signals.summary(tasks(), snap, TODAY)["team"]["notes"])


class TestMemoryRepo(unittest.TestCase):
    """GitHub 어댑터와 같은 모양이어야 signals 가 백엔드를 모른 채 돌아간다."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "repo.json")
        seed_repo.write(self.path, TODAY)
        self.repo = MemoryRepo(self.path)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_snapshot_모양이_같다(self):
        s = self.repo.snapshot()
        self.assertEqual(set(s), {"repo", "info", "commits", "pulls", "branches"})
        self.assertIn("default_branch", s["info"])

    def test_커밋은_최신순이다(self):
        ds = [c["date"] for c in self.repo.commits(10)]
        self.assertEqual(ds, sorted(ds, reverse=True))

    def test_상태로_PR을_거른다(self):
        self.assertTrue(all(p["state"] == "open" for p in self.repo.pulls("open")))

    def test_쓰기_메서드가_없다(self):
        for name in ("create_issue", "comment", "set_fields", "transition", "link", "push"):
            self.assertFalse(hasattr(self.repo, name), name)

    def test_파일이_없어도_깨지지_않는다(self):
        r = MemoryRepo(os.path.join(self.dir, "없음.json"))
        self.assertEqual(r.snapshot()["commits"], [])


class TestSeededRepo(unittest.TestCase):
    """심어둔 어긋남이 실제로 검출되는가 — 이 테스트가 시연의 사전 점검이다."""

    def setUp(self):
        self.data = seed_repo.build(TODAY)
        self.tasks = schedule.from_jira_issues(seed.build(TODAY))
        self.summary = signals.summary(self.tasks, {**self.data, "planted": None}, TODAY)

    def test_같은_시드는_같은_저장소를_만든다(self):
        self.assertEqual(seed_repo.build(TODAY), seed_repo.build(TODAY))

    def test_키_규칙이_돈다(self):
        self.assertTrue(self.summary["key_convention_in_use"])
        self.assertGreater(self.summary["linked_tasks"], 5)

    def test_심어둔_어긋남이_전부_검출된다(self):
        found = {(m["key"], m["kind"]) for m in self.summary["mismatches"]}
        for p in self.data["planted"]:
            self.assertIn((p["key"], p["kind"]), found, f"{p['key']} {p['kind']} 미검출")

    def test_네_종류가_모두_나온다(self):
        kinds = {m["kind"] for m in self.summary["mismatches"]}
        self.assertEqual(
            kinds & {"stalled", "done_with_open_pr", "undeclared_progress", "review_waiting"},
            {"stalled", "done_with_open_pr", "undeclared_progress", "review_waiting"},
        )

    def test_가상_인물만_등장한다(self):
        authors = {c["author"] for c in self.data["commits"]}
        self.assertEqual(authors, set(seed_repo.LOGIN.values()))

    def test_JSON으로_직렬화된다(self):
        json.dumps(self.summary, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
