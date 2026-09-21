"""Fill an empty Notion database with the simulated meeting notes.

`notion_csv.py` writes a file for Notion's "Merge with CSV", which works but is four
clicks and a file picker. This does the same thing over the API, and adds the Date and
Author columns the notes need — a fresh Notion database has only a title column, so
without them every note would arrive dateless and the agent would read an empty window.

Why this is not in the adapter. `adapters/notion.py` has no method that writes, on
purpose: the agent has no business editing what someone typed in a meeting, and the only
way to promise that is for the code path not to exist. This is a *setup* script, run by a
person with their own token, in the same place as `retitle_jira.py`. Nothing the agent
does at runtime can reach it.

Three guards, because this writes into somebody's real workspace:

  · nothing happens without --approve; the default run prints the plan
  · a database that already has rows is refused. An empty database is a demo fixture,
    a populated one is somebody's actual notes, and this cannot tell which by name
  · only columns that are missing are added. An existing Date column is used as it is,
    never retyped

Run:
  python tools/notion_seed.py             show what would be created (dry run)
  python tools/notion_seed.py --approve   create the pages
  python tools/notion_seed.py --approve --force   add rows to a database that has some
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

import notion_csv

from pmo_agent.adapters.notion import API, TIMEOUT, VERSION, NotionError, NotionNotes

# What the notes need beyond the title every Notion database starts with.
WANTED: dict[str, dict] = {"Date": {"date": {}}, "Author": {"rich_text": {}}}
BODY_MAX = 1900  # Notion rejects a rich text run over 2000 characters


def request(token: str, path: str, body: dict | None = None, method: str = "") -> dict:
    """One door, like the adapter's — except this one is allowed to PATCH and POST."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        method=method or ("POST" if data else "GET"),
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        raise NotionError(
            f"Notion {method or 'POST'} {path} -> {e.code}: "
            f"{e.read()[:300].decode('utf-8', 'ignore')}"
        ) from None
    except urllib.error.URLError as e:
        raise NotionError(f"network error reaching Notion: {e}") from None


def existing(client: NotionNotes) -> int:
    """How many rows are already in there. Anything above zero stops the run."""
    found = client._request(f"/data_sources/{client.data_source()}/query", {"page_size": 1})
    return len(found.get("results") or [])


def columns(client: NotionNotes) -> dict:
    """{name: type} of the data source as it stands."""
    info = client._request(f"/data_sources/{client.data_source()}")
    return {name: value.get("type") for name, value in (info.get("properties") or {}).items()}


def missing(have: dict) -> dict:
    """The wanted columns that are absent, matched by *type* so a renamed one counts.

    The adapter finds the date column by type rather than by name, so a workspace whose
    date column is called "When" is already served and must not get a second one.
    """
    kinds = set(have.values())
    return {name: spec for name, spec in WANTED.items() if next(iter(spec)) not in kinds}


def add_columns(token: str, source: str, add: dict) -> None:
    request(token, f"/data_sources/{source}", {"properties": add}, method="PATCH")


def page(source: str, note: dict, have: dict) -> dict:
    """One note as a Notion page: properties for the columns, body as a paragraph."""
    title = next((n for n, t in have.items() if t == "title"), "Name")
    date = next((n for n, t in have.items() if t == "date"), "Date")
    author = next((n for n, t in have.items() if t in ("rich_text", "people")), "Author")
    props: dict = {title: {"title": [{"text": {"content": note["Name"][:200]}}]}}
    if note.get("Date"):
        props[date] = {"date": {"start": note["Date"]}}
    if note.get("Author") and have.get(author, "rich_text") == "rich_text":
        props[author] = {"rich_text": [{"text": {"content": note["Author"][:200]}}]}
    body = (note.get("Body") or "").strip()
    return {
        "parent": {"type": "data_source_id", "data_source_id": source},
        "properties": props,
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": body[:BODY_MAX]}}]},
            }
        ]
        if body
        else [],
    }


def main(argv: list) -> int:
    approve = "--approve" in argv
    force = "--force" in argv
    notes = notion_csv.rows()

    try:
        client = NotionNotes()
        source = client.data_source()
        have = columns(client)
        count = existing(client)
    except NotionError as e:
        print(f"cannot reach Notion: {e}")
        print("  NOTION_TOKEN and NOTION_DATABASE_ID in .env, and the database shared")
        print("  with the integration (database -> ... -> Connections).")
        return 2

    add = missing(have)
    shape = ", ".join(f"{n}({t})" for n, t in have.items())
    print(f"data source {source[:8]}  ·  columns: {shape}")
    print(f"rows already there: {count}")
    if add:
        print(f"columns to add: {', '.join(f'{n} ({next(iter(s))})' for n, s in add.items())}")
    print(f"notes to create: {len(notes)}")
    for note in notes[:3]:
        print(f"  {note['Date']}  {note['Author']:<14} {note['Name'][:46]}")
    if len(notes) > 3:
        print(f"  ... and {len(notes) - 3} more")

    if count and not force:
        print("\nrefused: that database already has rows.")
        print("  An empty database is a demo fixture; a populated one is somebody's notes,")
        print("  and this cannot tell which from here. Point it at an empty one, or pass")
        print("  --force if you are certain.")
        return 1
    if not approve:
        print("\ndry run - nothing was written. Add --approve to create these pages.")
        return 0

    try:
        if add:
            add_columns(client.token, source, add)
            have = columns(client)
        for note in notes:
            request(client.token, "/pages", page(source, note, have))
    except NotionError as e:
        print(f"\nfailed partway: {e}")
        return 2

    print(f"\ncreated {len(notes)} pages.")
    print("Check it reads back: python tools/check_env.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
