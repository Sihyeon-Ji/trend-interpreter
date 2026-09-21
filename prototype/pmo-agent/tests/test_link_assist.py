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


class TestItSaysWhatTheModelDid:
    """A rate-limited run looks exactly like a rules-only run from the outside.

    That is fine at runtime — the commit stays unlinked, which is true — but a caller who
    then reports the figure as "with model assist" is publishing the rules-only number
    under a name that claims otherwise. So the assistant records what happened.
    """

    def items(self, n=2):
        known = tasks()
        return [
            {
                "commit": commit(f"s{i}", f"feat: work {i}"),
                "candidates": [
                    {"key": "ECHO-1", "score": 0.5, "reasons": []},
                    {"key": "ECHO-2", "score": 0.4, "reasons": []},
                ],
                "tasks": known,
            }
            for i in range(n)
        ]

    def test_it_counts_what_it_asked_and_what_came_back(self):
        assist = link_assist.assistant(
            caller_returning([{"sha": "s0", "key": "ECHO-1", "confidence": 0.8}])
        )
        assist(self.items(2))
        assert assist.stats["asked"] == 2
        assert assist.stats["answered"] == 1
        assert assist.stats["failed_batches"] == 0

    def test_a_failed_batch_is_recorded_not_swallowed(self):
        from pmo_agent import llm

        def boom(_prompt):
            raise llm.LLMError("Gemini 429: {\n  quota\n}")

        assist = link_assist.assistant(boom)
        assert assist(self.items(2)) == {}
        assert assist.stats["failed_batches"] == 1
        assert assist.stats["answered"] == 0

    def test_the_recorded_error_is_one_line(self):
        # A provider error is a JSON blob with newlines in it; unflattened it wrecks a report
        from pmo_agent import llm

        def boom(_prompt):
            raise llm.LLMError('Gemini 429: {\n  "error": {\n    "code": 429\n  }\n}')

        assist = link_assist.assistant(boom)
        assist(self.items(1))
        assert "\n" not in assist.stats["error"]
        assert assist.stats["error"].startswith("Gemini 429")

    def test_one_bad_batch_does_not_take_the_others_down(self):
        from pmo_agent import llm

        calls = {"n": 0}

        def flaky(_prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                raise llm.LLMError("429")
            return response([{"sha": "s2", "key": "ECHO-1", "confidence": 0.8}])

        assist = link_assist.assistant(flaky, batch=2)
        got = assist(self.items(4))
        assert list(got) == ["s2"] and got["s2"]["key"] == "ECHO-1"
        assert (assist.stats["batches"], assist.stats["failed_batches"]) == (2, 1)


class TestTheMeasurementRefusesToOverclaim:
    def row(self, asked, answered, failed=0, error=""):
        return {
            "assist": {
                "asked": asked,
                "answered": answered,
                "batches": 1,
                "failed_batches": failed,
                "error": error,
            }
        }

    def test_a_silent_model_is_called_out_in_capitals(self):
        import measure_links

        said = measure_links.assist_note([self.row(8, 0, failed=1, error="Gemini 429")])
        assert "ANSWERED NOTHING" in said
        assert "do not report them as assisted" in said
        assert "Gemini 429" in said

    def test_a_working_model_is_reported_plainly(self):
        import measure_links

        said = measure_links.assist_note([self.row(8, 8)])
        assert said == "the model placed 8 of the 8 commits the rules left open."

    def test_nothing_left_open_means_the_model_was_never_called(self):
        import measure_links

        said = measure_links.assist_note([self.row(0, 0)])
        assert "never called" in said

    def test_a_partly_working_model_still_reports_the_failures(self):
        import measure_links

        said = measure_links.assist_note([self.row(8, 4, failed=1)])
        assert "placed 4 of the 8" in said
        assert "1 batch failed" in said  # not "1 batches"
        assert measure_links.assist_note([self.row(8, 4, failed=2)]).endswith("2 batches failed.")
