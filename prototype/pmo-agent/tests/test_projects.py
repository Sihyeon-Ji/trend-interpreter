"""The project registry — no network, no real config file.

Four of the things worth building next (an issue register, telling the right people, an
executive roll-up, a view for operations rather than delivery) are all about *several*
projects at once, and none of them is half-buildable on one. So this is a small module
with a lot resting on it, and most of what matters here is what it refuses.

The refusals: an unknown key raises rather than quietly answering about the default, and
a project with no board key is dropped rather than half-registered.

Run: pytest -q
"""

from __future__ import annotations

import json

import pytest

from pmo_agent import projects


def write(tmp_path, rows):
    path = tmp_path / "projects.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


class TestReadingTheFile:
    def test_it_reads_a_plain_list(self, tmp_path):
        path = write(tmp_path, [{"key": "ECHO"}, {"key": "OPS", "kind": "run"}])
        assert [p.key for p in projects.all(path)] == ["ECHO", "OPS"]

    def test_it_reads_a_wrapped_list_too(self, tmp_path):
        # Both shapes turn up in hand-written config, and neither is wrong
        path = write(tmp_path, {"projects": [{"key": "ECHO"}]})
        assert [p.key for p in projects.all(path)] == ["ECHO"]

    def test_the_order_in_the_file_is_the_order_out(self, tmp_path):
        path = write(tmp_path, [{"key": "C"}, {"key": "A"}, {"key": "B"}])
        assert [p.key for p in projects.all(path)] == ["C", "A", "B"]
        assert projects.default(path).key == "C"

    def test_every_field_survives_the_trip(self, tmp_path):
        path = write(
            tmp_path,
            [
                {
                    "key": "OPS",
                    "name": "Operations",
                    "kind": "run",
                    "repo": "o/r",
                    "notes": "db1",
                    "tags": ["billing"],
                }
            ],
        )
        got = projects.get("OPS", path)
        assert (got.name, got.kind, got.repo, got.notes, got.tags) == (
            "Operations",
            "run",
            "o/r",
            "db1",
            ["billing"],
        )


class TestWhatItRefuses:
    def test_a_project_with_no_key_is_dropped(self, tmp_path):
        # A board key is the one thing every other tool is looked up by
        path = write(tmp_path, [{"name": "nameless"}, {"key": "ECHO"}])
        assert [p.key for p in projects.all(path)] == ["ECHO"]

    def test_an_unknown_kind_falls_back_rather_than_inventing_one(self, tmp_path):
        path = write(tmp_path, [{"key": "X", "kind": "somethingelse"}])
        assert projects.get("X", path).kind == projects.BUILD

    def test_an_unknown_key_raises_rather_than_answering_about_another(self, tmp_path):
        # Quietly returning the default would mean a typo answers about the wrong project
        path = write(tmp_path, [{"key": "ECHO"}])
        assert projects.get("NOPE", path) is None
        with pytest.raises(KeyError) as caught:
            projects.resolve("NOPE", path)
        assert "ECHO" in str(caught.value), "the error should say what it does watch"

    def test_an_empty_key_means_the_default_not_an_error(self, tmp_path):
        # "you did not say" has a sensible answer; "you said something wrong" does not
        path = write(tmp_path, [{"key": "ECHO"}, {"key": "OPS"}])
        assert projects.resolve("", path).key == "ECHO"
        assert projects.resolve("  ", path).key == "ECHO"

    def test_a_corrupt_file_falls_back_to_the_environment(self, tmp_path):
        path = tmp_path / "projects.json"
        path.write_text("{not json", encoding="utf-8")
        assert len(projects.all(path)) == 1

    def test_a_missing_file_is_a_single_project_setup(self, tmp_path):
        # Not a fallback so much as the honest description of having one project
        found = projects.all(tmp_path / "nope.json")
        assert len(found) == 1 and found[0].key


class TestKinds:
    def test_a_delivery_project_is_asked_when_it_finishes(self, tmp_path):
        path = write(tmp_path, [{"key": "ECHO", "kind": "build"}])
        assert not projects.get("ECHO", path).is_run

    def test_an_operations_project_is_not(self, tmp_path):
        # "when does it finish" is a category error for work that does not end
        path = write(tmp_path, [{"key": "OPS", "kind": "run"}])
        assert projects.get("OPS", path).is_run

    def test_the_label_falls_back_to_the_key(self, tmp_path):
        path = write(tmp_path, [{"key": "ECHO"}, {"key": "OPS", "name": "Operations"}])
        assert [p.label for p in projects.all(path)] == ["ECHO", "Operations"]


class TestLookup:
    def test_the_key_is_matched_whatever_the_case(self, tmp_path):
        path = write(tmp_path, [{"key": "ECHO"}])
        assert projects.get("echo", path).key == "ECHO"
        assert projects.resolve("Echo", path).key == "ECHO"

    def test_the_summary_says_whether_notes_are_configured(self, tmp_path):
        path = write(tmp_path, [{"key": "A", "notes": "db1"}, {"key": "B"}])
        assert [row["notes"] for row in projects.summary(path)] == [True, False]


class TestTheToolLayerFollowsIt:
    def test_each_project_gets_its_own_board(self, monkeypatch):
        from pmo_agent import tools

        monkeypatch.setattr(tools, "env", lambda k, d="": "memory" if "BACKEND" in k else d)
        monkeypatch.setattr(
            projects, "all", lambda path=None: [projects.Project("A"), projects.Project("B")]
        )
        tools.forget_adapters()
        assert tools.jira("A") is not tools.jira("B")
        assert tools.jira("A") is tools.jira("A"), "it should be built once and kept"
        tools.forget_adapters()

    def test_a_pinned_adapter_wins_for_every_project(self, monkeypatch):
        from pmo_agent import tools

        sentinel = object()
        monkeypatch.setattr(
            projects, "all", lambda path=None: [projects.Project("A"), projects.Project("B")]
        )
        tools.pin(board=sentinel)
        try:
            assert tools.jira("A") is sentinel and tools.jira("B") is sentinel
        finally:
            tools.pin(board=None)
