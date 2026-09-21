"""The Notion adapter — meeting notes where a team actually keeps them.

`memory_notes.py` proves the shape works. This is the same shape against a real service,
and it is the point at which "the agent reads your meeting notes" stops being a diagram.

Notion is the right fourth tool to connect for one reason: it is where the *words* live.
A board has a status, a repository has a diff, a calendar has hours. Only a note says what
was decided, and teams keep those in Notion far more often than anywhere an API can reach.

**Read-only.** There is no method here that creates or edits a page. An agent has no
business rewriting what someone typed in a meeting, and the only way to guarantee that is
for the code path not to exist.

What it expects: a Notion database whose rows are meeting notes. The title property is the
note's title; a date property gives the day; a people or text property gives the author.
Property names vary by workspace, so they are matched by *type* rather than by name — the
first date property is the date, and so on. A workspace that does something unusual can
name them explicitly in .env.

Setup (by hand, about three minutes):
  1. https://www.notion.so/profile/integrations → Personal access tokens → New token
     Name it, tick the Notion API capability, create, copy the `ntn_...` secret
  2. Open the notes database in Notion → ⋯ → Connections → add that token, if it is not
     already visible to you
  3. Copy the database id from its URL: notion.so/<workspace>/<DATABASE_ID>?v=...
  4. NOTION_TOKEN=ntn_... and NOTION_DATABASE_ID=... in .env

A note on the API version: Notion split databases from data sources in 2025-09-03, and
`POST /databases/{id}/query` is deprecated. This adapter pins the new version and does the
discovery step — one call to find the database's data source, then the query against that.

Every network call goes through one injectable function, so the parsing is unit-tested
without a token — the same arrangement as ingest.py and llm.py.
"""

from __future__ import annotations

import datetime as _dt
import json
import urllib.error
import urllib.request

from pmo_agent.env import env

API = "https://api.notion.com/v1"
VERSION = "2025-09-03"  # a database can hold several data sources as of this version
LEGACY_VERSION = "2022-06-28"  # what the old databases/{id}/query endpoint answered to
TIMEOUT = 30
PAGE_SIZE = 100
MAX_PAGES = 5  # a note archive this agent cares about is recent, not complete


class NotionError(RuntimeError):
    """A Notion call failed, or it is not configured."""


def _plain(rich) -> str:
    """Notion returns text as a list of styled runs. Only the text matters here."""
    if isinstance(rich, str):
        return rich
    return "".join(part.get("plain_text", "") for part in (rich or []))


def _title_of(props: dict) -> str:
    for value in props.values():
        if value.get("type") == "title":
            return _plain(value.get("title")).strip()
    return ""


def _date_of(props: dict, name: str = "") -> str:
    """The first date property, or the named one. Returns YYYY-MM-DD."""
    for key, value in props.items():
        if value.get("type") != "date" or (name and key != name):
            continue
        return ((value.get("date") or {}).get("start") or "")[:10]
    return ""


NAME_MAX = 40  # a person's name is short; a summary column is not


def _author_of(props: dict, name: str = "") -> str:
    """Whoever wrote it. A people property wins; select or a short text is the fallback.

    People first because that is what the property is for. A workspace that types names
    into a text column instead still works, which is most of them.

    The text fallback only takes short values. Without that guard a "Summary" or "Notes"
    column is just as valid a candidate as an author column, and a whole paragraph ends
    up in the author field — wrong, and wrong in a way nobody notices until a report
    prints it. Naming the column in .env skips the guessing entirely.
    """

    def pick(kinds: tuple) -> str:
        for key, value in props.items():
            if (name and key != name) or value.get("type") not in kinds:
                continue
            kind = value["type"]
            if kind == "people":
                people = value.get("people") or []
                if people:
                    return (people[0].get("name") or "").strip()
            elif kind == "rich_text":
                text = _plain(value.get("rich_text")).strip()
                if text and (name or len(text) <= NAME_MAX):
                    return text
            elif kind == "select":
                chosen = ((value.get("select") or {}).get("name") or "").strip()
                if chosen:
                    return chosen
        return ""

    return pick(("people",)) or pick(("rich_text", "select"))


class NotionNotes:
    """Reads meeting notes out of a Notion database. No write methods, by design."""

    def __init__(
        self,
        token: str = "",
        database: str = "",
        call=None,
        source: str = "",
        date_property: str = "",
        author_property: str = "",
    ):
        self.token = token or env("NOTION_TOKEN")
        # Notion takes an id dashed or not, so it is left exactly as the person pasted it.
        # Stripping dashes "to normalise" quietly mangles anything that is not a UUID.
        self.database = (database or env("NOTION_DATABASE_ID")).strip()
        self.date_property = date_property or env("NOTION_DATE_PROPERTY")
        self.author_property = author_property or env("NOTION_AUTHOR_PROPERTY")
        self._source_id = ""
        self._call = call or self._request
        self.source = source or (f"notion/{self.database[:8]}" if self.database else "notion")

    def _request(self, path: str, body: dict | None = None) -> dict:
        """One door for every call. `body` present means POST, absent means GET."""
        if not self.token or not self.database:
            raise NotionError(
                "NOTION_TOKEN / NOTION_DATABASE_ID are not set — see the module docstring"
            )
        req = urllib.request.Request(
            f"{API}{path}",
            method="POST" if body is not None else "GET",
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": VERSION,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            raise NotionError(
                f"Notion {path} -> {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}"
            ) from None
        except urllib.error.URLError as e:
            raise NotionError(f"network error reaching Notion: {e}") from None

    # ---------- reads ----------
    def whoami(self) -> str:
        return self.source

    def data_source(self) -> str:
        """The data source to query, discovered from the database id and remembered.

        Since 2025-09-03 a database is a container that can hold several data sources, and
        queries go to one of those rather than to the database. Someone who pasted a data
        source id straight into .env should not have to care, so a failed lookup falls back
        to treating the id as already being one.
        """
        if self._source_id:
            return self._source_id
        try:
            found = self._call(f"/databases/{self.database}") or {}
        except NotionError:
            self._source_id = self.database
            return self._source_id
        sources = found.get("data_sources") or []
        self._source_id = (sources[0].get("id") if sources else self.database) or self.database
        return self._source_id

    def notes(self, days: int = 30, author: str = "", start=None) -> list:
        """Notes in the `days` days from `start` (today by default).

        Explaining a stall means looking backwards, which is why the window is explicit
        and why the filter goes to Notion rather than being applied after the fact — a
        busy workspace has years of notes and the agent wants a fortnight of them.
        """
        first = start or _dt.date.today()
        if isinstance(first, str):
            first = _dt.date.fromisoformat(first[:10])
        last = first + _dt.timedelta(days=int(days))

        rows: list = []
        cursor = None
        for _ in range(MAX_PAGES):
            body: dict = {"page_size": PAGE_SIZE}
            if self.date_property:
                body["filter"] = {
                    "and": [
                        {
                            "property": self.date_property,
                            "date": {"on_or_after": first.isoformat()},
                        },
                        {"property": self.date_property, "date": {"before": last.isoformat()}},
                    ]
                }
            if cursor:
                body["start_cursor"] = cursor
            page = self._call(f"/data_sources/{self.data_source()}/query", body)
            rows.extend(page.get("results") or [])
            cursor = page.get("next_cursor")
            if not page.get("has_more") or not cursor:
                break

        out = []
        for row in rows:
            props = row.get("properties") or {}
            day = _date_of(props, self.date_property) or (row.get("created_time") or "")[:10]
            if not (first.isoformat() <= day < last.isoformat()):
                continue  # a workspace with no date property still gets the window applied
            who = _author_of(props, self.author_property)
            if author and who != author:
                continue
            out.append(
                {
                    "date": day,
                    "author": who,
                    "title": _title_of(props),
                    # The body is what cause.py reads. Notion keeps it in child blocks,
                    # one call per page, so a note with an unreadable body still arrives
                    # with its title rather than being dropped.
                    "body": self._body(row.get("id", "")),
                    "url": row.get("url", ""),
                }
            )
        out.sort(key=lambda n: (n["date"], n["author"]))
        return out

    def _body(self, page_id: str) -> str:
        """The page's paragraph text. One call per page, so it is kept to the plain blocks."""
        if not page_id:
            return ""
        try:
            page = self._call(f"/blocks/{page_id}/children?page_size=50")
        except NotionError:
            return ""
        parts = []
        for block in page.get("results") or []:
            kind = block.get("type", "")
            if kind in ("paragraph", "bulleted_list_item", "numbered_list_item", "callout"):
                parts.append(_plain((block.get(kind) or {}).get("rich_text")))
        return " ".join(p for p in parts if p).strip()


def load(token: str = "", database: str = "") -> NotionNotes:
    return NotionNotes(token, database)


if __name__ == "__main__":
    notes = NotionNotes()
    got = notes.notes(days=60, start=_dt.date.today() - _dt.timedelta(days=60))
    print(f"{notes.whoami()}: {len(got)} notes in the last 60 days")
    for note in got[:5]:
        print(f"  {note['date']}  {note['author']:<16} {note['title'][:44]}")
        print(f"      {note['body'][:96]}")
