"""어댑터가 지켜야 할 인터페이스.

"Jira 어댑터와 로컬 보드는 같은 모양"이라는 말은 지금까지 주석과 테스트로만 유지됐다.
여기에 Protocol 로 적어 두면 타입 검사기가 강제한다 — 한쪽에만 메서드를 추가하면 mypy 가 잡는다.
PM 도구에 종속되지 않는다는 주장의 근거가 문서가 아니라 검사 결과가 된다.

Protocol 이라 어댑터가 이 모듈을 import 할 필요는 없다 (구조적 타이핑).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Board(Protocol):
    """태스크 보드. Jira Cloud 와 로컬 JSON 보드가 이 모양을 따른다.

    쓰기 메서드는 전부 approve 인자를 받고, 기본값은 '반영하지 않음'이다.
    """

    project: str
    site: str

    # 읽기
    def whoami(self) -> dict[str, Any]: ...
    def project_info(self) -> dict[str, Any]: ...
    def search(self, jql: str | None = ..., limit: int = ...) -> list[dict[str, Any]]: ...
    def issue(self, key: str) -> dict[str, Any]: ...
    def transitions(self, key: str) -> list[dict[str, Any]]: ...
    def done_since(self, days: int = ..., limit: int = ...) -> list[dict[str, Any]]: ...

    # 쓰기 (approve=False 면 dry_run 결과만 돌려준다)
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
    """코드 저장소. GitHub 과 로컬 JSON 저장소가 이 모양을 따른다.

    **읽기 전용이다.** 쓰기 메서드를 여기 추가하지 않는다 — 추가하면 그 순간
    '남의 저장소에 무언가를 만들 경로가 없다'는 보장이 사라진다.
    """

    repo: str

    def whoami(self) -> str: ...
    def repo_info(self) -> dict[str, Any]: ...
    def commits(self, limit: int = ..., branch: str = ...) -> list[dict[str, Any]]: ...
    def pulls(self, state: str = ..., limit: int = ...) -> list[dict[str, Any]]: ...
    def reviews(self, number: int) -> list[dict[str, Any]]: ...
    def branches(self) -> list[str]: ...
    def snapshot(self, commit_limit: int = ...) -> dict[str, Any]: ...


@runtime_checkable
class Calendar(Protocol):
    """캘린더. MS Graph(Outlook) 와 로컬 JSON 캘린더가 이 모양을 따른다.

    **읽기 전용이다.** 남의 일정을 만들거나 지울 경로를 두지 않는다.
    보드·저장소와 달리 여기서 나오는 값은 '무엇을 했나'가 아니라
    '무엇을 할 시간이 남았나'다 — capacity.py 의 입력이다.
    """

    source: str

    def whoami(self) -> str: ...
    def events(self, days: int = ..., attendee: str = ...) -> list[dict[str, Any]]: ...
    def busy_hours(self, days: int = ...) -> dict[str, dict[str, float]]: ...
