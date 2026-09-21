"""Notion adapter tests — no token, no network.

Every call goes through one injectable function, so what is under test is the part that
actually breaks: reading a real Notion payload. Notion returns text as lists of styled
runs, dates nested two levels down, and property names that differ in every workspace.

The adapter also has to stay the same shape as the local one, or cause.py would have to
know which is connected — which is the whole point of the Protocol.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt

import pytest

from pmo_agent import ports
from pmo_agent.adapters.memory_notes import MemoryNotes
from pmo_agent.adapters.notion import NotionError, NotionNotes

TODAY = dt.date(2026, 9, 21)


def text(value: str) -> list:
    return [{"plain_text": value}]


def row(title, day, author=None, page_id="p1", kind="people"):
    props: dict = {
        "Name": {"type": "title", "title": text(title)},
        "When": {"type": "date", "date": {"start": day}},
    }
    if author is not None:
        if kind == "people":
            props["Owner"] = {"type": "people", "people": [{"name": author}]}
        elif kind == "rich_text":
            props["Owner"] = {"type": "rich_text", "rich_text": text(author)}
        else:
            props["Owner"] = {"type": "select", "select": {"name": author}}
    return {"id": page_id, "url": f"https://notion.so/{page_id}", "properties": props}


def caller(rows, body="", sources=("ds-1",)):
    """Stands in for the network: the data source lookup, the query, the page body."""

    def call(path, payload=None):
        call.seen.append((path, payload))
        if "/children" in path:
            return {"results": [{"type": "paragraph", "paragraph": {"rich_text": text(body)}}]}
        if path.startswith("/databases/"):
            return {"data_sources": [{"id": s, "name": "Notes"} for s in sources]}
        return {"results": rows, "has_more": False, "next_cursor": None}

    call.seen = []
    return call


def notion(rows, body="", sources=("ds-1",), **kw):
    return NotionNotes(token="t", database="d", call=caller(rows, body, sources), **kw)


class TestDataSource:
    """Notion split databases from data sources in 2025-09-03; queries go to the latter."""

    def test_it_looks_the_data_source_up_from_the_database(self):
        client = notion([], sources=("ds-42",))
        client.notes(start=dt.date(2026, 9, 1))
        paths = [path for path, _ in client._call.seen]
        assert "/databases/d" in paths
        assert any(p.startswith("/data_sources/ds-42/query") for p in paths)

    def test_the_lookup_happens_once(self):
        client = notion([], sources=("ds-42",))
        client.notes(start=dt.date(2026, 9, 1))
        client.notes(start=dt.date(2026, 9, 1))
        assert [path for path, _ in client._call.seen].count("/databases/d") == 1

    def test_an_id_that_is_already_a_data_source_still_works(self):
        # Someone who pasted a data source id into .env should not have to care
        def call(path, payload=None):
            if path.startswith("/databases/"):
                raise NotionError("not a database")
            if "/children" in path:
                return {"results": []}
            return {"results": [row("Sync", "2026-09-15", "Maya")]}

        client = NotionNotes(token="t", database="ds-9", call=call)
        assert client.notes(start=dt.date(2026, 9, 1))[0]["title"] == "Sync"
        assert client.data_source() == "ds-9"


class TestShape:
    def test_it_is_the_same_shape_as_the_local_archive(self):
        # If these ever diverge, cause.py starts caring which one is connected
        assert isinstance(notion([]), ports.Notes)
        assert isinstance(MemoryNotes(data={"notes": []}), ports.Notes)

    def test_there_are_no_write_methods(self):
        # An agent has no business editing what someone typed in a meeting
        forbidden = {"create", "update", "write", "post", "edit", "delete", "append"}
        assert not forbidden & set(dir(NotionNotes))

    def test_a_note_comes_back_in_the_local_archives_shape(self):
        got = notion([row("Incident response", "2026-09-15", "Maya")], body="Blocked on the IdP")
        note = got.notes(days=30, start=dt.date(2026, 9, 1))[0]
        assert set(note) >= {"date", "author", "title", "body"}
        assert note["date"] == "2026-09-15"
        assert note["author"] == "Maya"
        assert note["title"] == "Incident response"
        assert note["body"] == "Blocked on the IdP"


class TestReading:
    def test_it_joins_the_styled_runs_of_a_title(self):
        page = row("", "2026-09-15", "Maya")
        page["properties"]["Name"]["title"] = [{"plain_text": "Incident "}, {"plain_text": "call"}]
        assert notion([page]).notes(start=dt.date(2026, 9, 1))[0]["title"] == "Incident call"

    @pytest.mark.parametrize("kind", ["people", "rich_text", "select"])
    def test_the_author_can_be_any_of_the_usual_property_types(self, kind):
        got = notion([row("Sync", "2026-09-15", "Maya", kind=kind)])
        assert got.notes(start=dt.date(2026, 9, 1))[0]["author"] == "Maya"

    def test_a_people_property_wins_over_a_text_one(self):
        page = row("Sync", "2026-09-15", "Maya", kind="people")
        page["properties"]["Scribe"] = {"type": "rich_text", "rich_text": text("Someone else")}
        assert notion([page]).notes(start=dt.date(2026, 9, 1))[0]["author"] == "Maya"

    def test_a_long_text_column_is_not_mistaken_for_an_author(self):
        # A "Summary" column looks exactly like an author column to a type-based match.
        # A paragraph in the author field is wrong in a way nobody notices.
        page = row("Sync", "2026-09-15")
        page["properties"]["Summary"] = {
            "type": "rich_text",
            "rich_text": text("We went through the whole board and agreed to move the date out"),
        }
        assert notion([page]).notes(start=dt.date(2026, 9, 1))[0]["author"] == ""

    def test_a_named_author_column_is_taken_whatever_its_length(self):
        page = row("Sync", "2026-09-15")
        page["properties"]["Scribe"] = {
            "type": "rich_text",
            "rich_text": text("Maya Okonkwo, standing in for Leo Fischer this week"),
        }
        got = notion([page], author_property="Scribe").notes(start=dt.date(2026, 9, 1))
        assert got[0]["author"].startswith("Maya Okonkwo")

    def test_a_missing_author_is_empty_not_an_error(self):
        assert (
            notion([row("Sync", "2026-09-15")]).notes(start=dt.date(2026, 9, 1))[0]["author"] == ""
        )

    def test_an_unreadable_body_still_yields_the_note(self):
        # The title alone is often enough to tie a note to a task
        def call(path, payload=None):
            if "/children" in path:
                raise NotionError("no access to that block")
            return {"results": [row("Incident response", "2026-09-15", "Maya")]}

        got = NotionNotes(token="t", database="d", call=call)
        note = got.notes(start=dt.date(2026, 9, 1))[0]
        assert note["title"] == "Incident response"
        assert note["body"] == ""

    def test_it_falls_back_to_the_created_time_with_no_date_property(self):
        page = row("Sync", "2026-09-15")
        page["properties"].pop("When")
        page["created_time"] = "2026-09-16T09:00:00.000Z"
        assert notion([page]).notes(start=dt.date(2026, 9, 1))[0]["date"] == "2026-09-16"


class TestWindow:
    def test_notes_outside_the_window_are_dropped(self):
        rows = [row("Old", "2026-08-01", "Maya", page_id="a"), row("New", "2026-09-15", "Maya")]
        got = notion(rows).notes(days=30, start=dt.date(2026, 9, 1))
        assert [n["title"] for n in got] == ["New"]

    def test_the_window_is_pushed_to_notion_when_the_date_property_is_named(self):
        # A busy workspace has years of notes; the agent wants a fortnight of them
        client = notion([], date_property="When")
        client.notes(days=14, start=dt.date(2026, 9, 1))
        query = next(p for path, p in client._call.seen if "query" in path)
        assert query["filter"]["and"][0]["date"]["on_or_after"] == "2026-09-01"
        assert query["filter"]["and"][1]["date"]["before"] == "2026-09-15"

    def test_it_filters_by_author(self):
        rows = [
            row("A", "2026-09-15", "Maya", page_id="a"),
            row("B", "2026-09-16", "Leo", page_id="b"),
        ]
        got = notion(rows).notes(author="Leo", start=dt.date(2026, 9, 1))
        assert [n["title"] for n in got] == ["B"]

    def test_notes_come_back_in_date_order(self):
        rows = [
            row("later", "2026-09-17", "Maya", page_id="a"),
            row("earlier", "2026-09-15", "Maya", page_id="b"),
        ]
        got = notion(rows).notes(start=dt.date(2026, 9, 1))
        assert [n["title"] for n in got] == ["earlier", "later"]


class TestConfiguration:
    def test_without_a_token_it_says_so_rather_than_calling(self):
        # env is slotted in empty on purpose: with a real .env present the constructor
        # would pick the values up from there and the test would pass for no reason
        import pmo_agent.adapters.notion as mod

        keep, mod.env = mod.env, lambda k, d="": d
        try:
            client = NotionNotes(token="", database="")
            with pytest.raises(NotionError) as caught:
                client.notes()
            assert "NOTION_TOKEN" in str(caught.value)
        finally:
            mod.env = keep

    def test_the_id_is_taken_exactly_as_pasted(self):
        # Notion accepts a UUID dashed or not, so normalising it only risks mangling
        # something that is not a UUID at all
        dashed = "1a2b3c4d-5e6f-7890-abcd-ef1234567890"
        assert NotionNotes(token="t", database=dashed, call=lambda *a: {}).database == dashed
        assert NotionNotes(token="t", database=" ds-9 ", call=lambda *a: {}).database == "ds-9"
