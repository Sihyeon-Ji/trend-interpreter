"""Model-assisted linking tests — no network, fake responses.

What matters here is not performance but **the boundary**:

  · does the model ever overwrite a link the rules settled
  · is an invented key outside the candidate set thrown away
  · is "I don't know" respected
  · do the rule-made links survive a model failure

Using the model costs precision (measured: 1.00 → 0.99). So every model-decided link is
marked `how="model"` and carries its confidence.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json

from pmo_agent import link_assist, linking, schedule

TODAY = dt.date(2026, 9, 21)


def tasks():
    return schedule.to_tasks(
        [
            {
                "key": "ECHO-1",
                "summary": "Authentication",
                "assignee": "Ada",
                "points": 3,
                "duedate": "2026-09-18",
            },
            {
                "key": "ECHO-2",
                "summary": "Search",
                "assignee": "Bo",
                "points": 3,
                "duedate": "2026-09-18",
            },
            {
                "key": "ECHO-3",
                "summary": "Notifications",
                "assignee": "Ada",
                "points": 2,
                "duedate": "2026-09-20",
            },
        ]
    )


def commit(sha, message, author="Ada", date="2026-09-17", files=()):
    return {
        "sha": sha,
        "date": date,
        "author": author,
        "login": author,
        "name": author,
        "email": f"{author}@t.test",
        "message": message,
        "branch": "feat/x",
        "files": list(files),
    }


def response(rows):
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"links": rows}, ensure_ascii=False)}]}}
        ]
    }


def caller_returning(rows):
    def _call(prompt):
        _call.prompt = prompt
        return response(rows)

    return _call


class TestParse:
    def test_it_reads_a_normal_response(self):
        out = link_assist.parse(
            response([{"sha": "a1", "key": "ECHO-1", "confidence": 0.8, "reason": "auth"}])
        )
        assert out["a1"]["key"] == "ECHO-1"

    def test_an_i_dont_know_answer_links_nothing(self):
        out = link_assist.parse(
            response([{"sha": "a1", "key": link_assist.UNKNOWN, "confidence": 0.9}])
        )
        assert out == {}

    def test_a_broken_response_does_not_kill_it(self):
        broken = {"candidates": [{"content": {"parts": [{"text": "{not json at all"}]}}]}
        assert link_assist.parse(broken) == {}
        assert link_assist.parse({}) == {}


class TestPrompt:
    def test_it_shows_every_candidate(self):
        item = {
            "commit": commit("a1", "feat: handle auth tokens"),
            "candidates": [
                {"key": "ECHO-1", "score": 0.5, "reasons": []},
                {"key": "ECHO-3", "score": 0.3, "reasons": []},
            ],
            "tasks": tasks(),
        }
        prompt = link_assist.build_prompt([item])
        assert "ECHO-1" in prompt and "ECHO-3" in prompt
        assert "feat: handle auth tokens" in prompt

    def test_the_instructions_forbid_going_outside_the_candidates(self):
        assert "Never invent a key that is not listed" in link_assist.SYSTEM
        assert "unknown" in link_assist.SYSTEM


class TestBoundaries:
    """The line the model must not cross."""

    def test_a_link_the_rules_settled_is_untouched(self):
        t = tasks()
        # Vocabulary, author and timing all line up, so the rules settle this one alone
        clear = commit("a1", "feat: implement authentication", author="Ada", files=["src/auth.py"])
        called = []

        def assist(items):
            called.append(items)
            return {"a1": {"key": "ECHO-2", "confidence": 1.0}}  # an attempt to drag it elsewhere

        linked = linking.link(t, [clear], [], {"Ada": "Ada", "Bo": "Bo"}, assist=assist)
        assert any(c["sha"] == "a1" for c in linked["ECHO-1"]["commits"])
        assert not linked["ECHO-2"]["commits"]

    def test_a_key_outside_the_candidates_is_dropped(self):
        t = tasks()
        vague = commit("b1", "chore: tidy up", author="Cal", date="2026-09-17")
        assist = link_assist.assistant(
            caller=caller_returning([{"sha": "b1", "key": "ECHO-999", "confidence": 0.9}])
        )
        linked = linking.link(t, [vague], [], assist=assist)
        assert all(not v["commits"] for v in linked.values())

    def test_a_confidence_out_of_range_is_dropped(self):
        t = tasks()
        vague = commit("b1", "chore: tidy up", author="Cal")
        for bad in (0.0, -0.5, 1.5):
            assist = link_assist.assistant(
                caller=caller_returning([{"sha": "b1", "key": "ECHO-1", "confidence": bad}])
            )
            linked = linking.link(t, [vague], [], assist=assist)
            assert all(not v["commits"] for v in linked.values()), bad

    def test_the_rule_links_survive_a_model_blowing_up(self):
        t = tasks()
        clear = commit("a1", "feat: implement authentication", author="Ada", files=["src/auth.py"])
        vague = commit("b1", "chore: tidy up", author="Cal")

        def boom(_items):
            raise RuntimeError("the model is down")

        linked = linking.link(t, [clear, vague], [], {"Ada": "Ada"}, assist=boom)
        assert any(c["sha"] == "a1" for c in linked["ECHO-1"]["commits"])

    def test_with_nothing_to_choose_between_it_does_not_ask(self):
        t = tasks()
        asked = []

        def assist(items):
            asked.append(items)
            return {}

        # A commit that overlaps nothing — with 0 or 1 candidates there is no reason to ask
        linking.link(
            t,
            [commit("z1", "chore: tidy up", author="nobody we know", date="2020-01-01")],
            [],
            assist=assist,
        )
        assert not asked or all(len(i["candidates"]) >= 2 for batch in asked for i in batch)


class TestQuality:
    def test_model_decisions_are_counted_separately(self):
        t = tasks()
        vague = commit("b1", "chore: tidy up a little", author="Ada", date="2026-09-17")
        assist = link_assist.assistant(
            caller=caller_returning(
                [{"sha": "b1", "key": "ECHO-1", "confidence": 0.7, "reason": "owner and timing"}]
            )
        )
        linked = linking.link(t, [vague], [], {"Ada": "Ada"}, assist=assist)
        quality = linking.quality(linked)
        assert quality["by_model"] == 1
        link = linked["ECHO-1"]["links"][0]
        assert link["how"] == "model"
        assert "model call" in link["reasons"][0]

    def test_the_quality_tally_runs_without_a_model(self):
        linked = linking.link(
            tasks(), [commit("a1", "feat: implement authentication")], [], {"Ada": "Ada"}
        )
        assert linking.quality(linked)["by_model"] == 0
