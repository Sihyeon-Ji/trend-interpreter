"""The projects this agent watches, and which tools belong to each.

Until now there was exactly one project, named by `JIRA_PROJECT_KEY`. Four of the things
worth building next — an issue register, telling the right people, an executive roll-up,
and a view that suits operations rather than delivery — are all about *several* projects
at once. None of them is half-buildable on a single one, so this comes first.

A project is a board key plus the tools that belong to it: its repository, its notes
database, and what **kind** of work it is. The kind matters more than it looks. A delivery
project is asked "when does it finish"; an operations project has no finish, and asking is
a category error, so the same calculation underneath has to surface different numbers.

Where the list comes from, in order:

  1. `data/projects.json`, when it exists — a real deployment has more than one
  2. otherwise one project synthesised from the environment, which is exactly what the
     agent did before this module existed

The second is not a fallback so much as the honest description of a single-project setup:
nothing to configure until there is something to configure.

Read-only. Nothing here reaches a network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from pmo_agent.env import data_dir, env

FILE = "projects.json"

BUILD = "build"  # has an end date, and the question is when
RUN = "run"  # does not end, and the question is whether it is healthy
KINDS = (BUILD, RUN)


@dataclass(frozen=True)
class Project:
    """One project and the tools behind it.

    `repo` and `notes` are per project on purpose. A team running three projects rarely
    keeps them in one repository, and pointing every project at the same one would make
    the linking worse in a way that is hard to notice: commits from another project become
    plausible candidates and the margin that protects a link gets thinner.
    """

    key: str  # the board key (ECHO), and the id used everywhere else
    name: str = ""
    kind: str = BUILD
    repo: str = ""  # owner/name, or empty to use the configured default
    notes: str = ""  # notes database id, or empty for the default
    tags: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.name or self.key

    @property
    def is_run(self) -> bool:
        return self.kind == RUN


def _from_env() -> Project:
    """The single project a plain .env describes."""
    return Project(
        key=env("JIRA_PROJECT_KEY", "ECHO"),
        name=env("PROJECT_NAME", ""),
        kind=env("PROJECT_KIND", BUILD).strip().lower() if env("PROJECT_KIND") in KINDS else BUILD,
        repo=env("GITHUB_REPO", ""),
        notes=env("NOTION_DATABASE_ID", ""),
    )


def _read(path=None) -> list:
    try:
        with open(path or (data_dir() / FILE), encoding="utf-8") as handle:
            found = json.load(handle)
    except (OSError, ValueError):
        return []
    rows = found.get("projects") if isinstance(found, dict) else found
    if not isinstance(rows, list):
        return []

    out = []
    for row in rows:
        key = str((row or {}).get("key") or "").strip()
        if not key:
            continue  # a project with no board key is not one this agent can read
        kind = str(row.get("kind") or BUILD).strip().lower()
        out.append(
            Project(
                key=key,
                name=str(row.get("name") or "").strip(),
                kind=kind if kind in KINDS else BUILD,
                repo=str(row.get("repo") or "").strip(),
                notes=str(row.get("notes") or "").strip(),
                tags=[str(t) for t in (row.get("tags") or [])],
            )
        )
    return out


def all(path=None) -> list:  # noqa: A001 - "all the projects" is what this is
    """Every project, in the order the file lists them. Never empty."""
    return _read(path) or [_from_env()]


def get(key: str, path=None) -> Project | None:
    """One project by key, case-insensitively. None when it is not one we watch.

    None rather than a guess: acting on the wrong project is worse than refusing, and a
    typo in a query string should not quietly answer about something else.
    """
    want = (key or "").strip().lower()
    return next((p for p in all(path) if p.key.lower() == want), None)


def default(path=None) -> Project:
    """The one to show when nobody said which. The first listed."""
    return all(path)[0]


def resolve(key: str = "", path=None) -> Project:
    """A project by key, falling back to the default when the key is empty.

    An *unknown* key still raises — empty means "you did not say", which has a sensible
    answer, and wrong means "you said something I cannot honour", which does not.
    """
    if not (key or "").strip():
        return default(path)
    found = get(key, path)
    if found is None:
        known = ", ".join(p.key for p in all(path))
        raise KeyError(f"unknown project: {key} (watching: {known})")
    return found


def summary(path=None) -> list:
    """The list as the API hands it out."""
    return [
        {
            "key": p.key,
            "name": p.label,
            "kind": p.kind,
            "repo": p.repo,
            "notes": bool(p.notes),
            "tags": list(p.tags),
        }
        for p in all(path)
    ]
