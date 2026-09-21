"""The interfaces an adapter has to keep.

"The Jira adapter and the local board are the same shape" was, until now, held up by
comments and tests alone. Written here as a Protocol, the type checker enforces it —
add a method to one side only and mypy catches it. The claim that this is not tied to
one PM tool then rests on a check result rather than on documentation.

These are Protocols, so adapters never import this module (structural typing).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Board(Protocol):
    """A task board. Jira Cloud and the local JSON board both take this shape.

    Every write method takes an `approve` argument, defaulting to "do not apply".
    """

    project: str
    site: str

    # reads
    def whoami(self) -> dict[str, Any]: ...
    def project_info(self) -> dict[str, Any]: ...
    def search(self, jql: str | None = ..., limit: int = ...) -> list[dict[str, Any]]: ...
    def issue(self, key: str) -> dict[str, Any]: ...
    def transitions(self, key: str) -> list[dict[str, Any]]: ...
    def done_since(self, days: int = ..., limit: int = ...) -> list[dict[str, Any]]: ...

    # writes (approve=False returns the dry-run result only)
    def comment(self, key: str, text: str, approve: bool = ...) -> dict[str, Any]: ...
    def set_fields(
        self, key: str, fields: dict[str, Any], approve: bool = ...
    ) -> dict[str, Any]: ...
    def transition(self, key: str, to_name: str, approve: bool = ...) -> dict[str, Any]: ...
    def link(
        self, inward_key: str, outward_key: str, link_type: str = ..., approve: bool = ...
    ) -> dict[str, Any]: ...


@runtime_checkable
class Repo(Protocol):
    """A code repository. GitHub and the local JSON repo both take this shape.

    **Read-only.** Do not add a write method here — the moment you do, the guarantee
    that there is no path to create anything in someone else's repository is gone.
    """

    repo: str

    def whoami(self) -> str: ...
    def repo_info(self) -> dict[str, Any]: ...
    def commits(self, limit: int = ..., branch: str = ...) -> list[dict[str, Any]]: ...
    def pulls(self, state: str = ..., limit: int = ...) -> list[dict[str, Any]]: ...
    def reviews(self, number: int) -> list[dict[str, Any]]: ...
    def branches(self) -> list[str]: ...
    def commit_files(self, sha: str) -> list[str]: ...
    def snapshot(self, commit_limit: int = ..., with_files: bool = ...) -> dict[str, Any]: ...


@runtime_checkable
class Calendar(Protocol):
    """A calendar. MS Graph (Outlook) and the local JSON calendar both take this shape.

    **Read-only.** There is no path to create or delete anyone's events.
    Unlike the board and the repo, what comes out of here is not "what was done" but
    "how much time is left to do it in" — the input to capacity.py. Asked about days
    that have already gone, it answers the other question too: where the time went,
    which is what cause.py needs to explain a stall.
    """

    source: str

    def whoami(self) -> str: ...
    def events(
        self, days: int = ..., attendee: str = ..., start: Any = ...
    ) -> list[dict[str, Any]]: ...
    def busy_hours(self, days: int = ...) -> dict[str, dict[str, float]]: ...


@runtime_checkable
class Notes(Protocol):
    """A meeting-notes archive. The local JSON archive takes this shape; Notion,
    Confluence or Google Docs would sit behind the same one.

    **Read-only.** An agent has no business editing what someone wrote in a meeting,
    and the only way to guarantee that is for the method not to exist.

    This is the one tool that holds *words*. The board has a status, the repo has a
    diff, the calendar has hours — only a note says what was decided, and it says it
    in prose, with no ticket key in sight.
    """

    source: str

    def whoami(self) -> str: ...
    def notes(
        self, days: int = ..., author: str = ..., start: Any = ...
    ) -> list[dict[str, Any]]: ...
