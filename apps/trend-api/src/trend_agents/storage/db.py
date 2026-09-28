"""PostgreSQL 연결 어댑터.

파이프라인·API 코드는 SQLite 시절의 qmark(?) 자리표시자와 INSERT OR REPLACE / INSERT OR IGNORE 문장을 그대로 쓴다.
이 모듈이 psycopg 형식(%s, ON CONFLICT)으로 바꿔 보내므로 저장소 함수는 SQL 방언을 신경 쓰지 않는다.
테스트는 connect(":memory:") 로 연결마다 임시 스키마를 받는다. 닫으면 스키마째 지운다.
"""
from __future__ import annotations

import atexit
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

import psycopg

from ..config import DATABASE_URL


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]


TABLES: dict[str, Table] = {}

_CREATE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\);", re.S)
_PK_CLAUSE = re.compile(r",?\s*PRIMARY KEY\s*\(([^)]*)\)", re.I)
_INSERT_OR = re.compile(r"^\s*INSERT OR (REPLACE|IGNORE) INTO (\w+)", re.I)


def register_schema(ddl: str) -> None:
    """DDL 문자열에서 표 이름·컬럼·기본키를 읽어 둔다. INSERT OR REPLACE 를 ON CONFLICT 로 바꿀 때 쓴다."""
    for name, body in _CREATE.findall(_strip_comments(ddl)):
        clause = _PK_CLAUSE.search(body)
        pk = tuple(c.strip() for c in clause.group(1).split(",")) if clause else ()
        columns: list[str] = []
        for part in _PK_CLAUSE.sub("", body).split(","):
            part = part.strip()
            if not part:
                continue
            columns.append(part.split()[0])
            if not clause and "PRIMARY KEY" in part.upper():
                pk = (columns[-1],)
        TABLES[name] = Table(name, tuple(columns), pk)


def _strip_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


@lru_cache(maxsize=1024)
def translate(sql: str, with_params: bool) -> str:
    """qmark → %s, INSERT OR REPLACE/IGNORE → ON CONFLICT. 파라미터가 있을 때는 % 를 %% 로 피한다."""
    m = _INSERT_OR.match(sql)
    if m:
        mode, table = m.group(1).upper(), m.group(2)
        sql = sql[: m.start()] + f"INSERT INTO {table}" + sql[m.end():]
        sql = sql.rstrip().rstrip(";")
        if mode == "IGNORE":
            sql += " ON CONFLICT DO NOTHING"
        else:
            t = TABLES[table]
            updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in t.columns if c not in t.primary_key)
            sql += f" ON CONFLICT ({', '.join(t.primary_key)}) DO " + (f"UPDATE SET {updates}" if updates else "NOTHING")
    out: list[str] = []
    in_string = False
    for ch in sql:
        if ch == "'":
            in_string = not in_string
            out.append(ch)
        elif ch == "%" and with_params:
            out.append("%%")
        elif ch == "?" and not in_string:
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


def _param(value):
    """SQLite 어댑터가 하던 변환을 그대로 한다. 표는 TEXT·BIGINT 로 되어 있어 bool 은 정수, 날짜는 ISO 문자열이다."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _is_read(sql: str) -> bool:
    return sql.lstrip().upper().startswith(("SELECT", "WITH"))


class Connection:
    """psycopg 연결을 감싼다. 읽기만 한 트랜잭션은 바로 닫아 idle in transaction 으로 남지 않게 한다.

    문장이 실패하면 롤백하고 예외를 다시 던진다. PostgreSQL 은 실패한 트랜잭션 안에서 다음 문장을 받지 않으므로,
    단계가 예외를 삼키고 실행 기록을 남기는 파이프라인 흐름을 위해 연결을 깨끗한 상태로 되돌린다.
    """

    def __init__(self, raw: psycopg.Connection, schema: str | None = None):
        self._raw = raw
        self._schema = schema
        self._dirty = False

    @property
    def raw(self) -> psycopg.Connection:
        return self._raw

    @property
    def broken(self) -> bool:
        return self._raw.closed or self._raw.broken

    def execute(self, sql: str, params=None):
        values = tuple(_param(p) for p in params) if params else None
        try:
            cur = self._raw.execute(translate(sql, values is not None), values)
        except psycopg.Error:
            self._raw.rollback()
            self._dirty = False
            raise
        if _is_read(sql):
            if not self._dirty:
                self._raw.commit()
        else:
            self._dirty = True
        return cur

    def executemany(self, sql: str, seq_of_params) -> None:
        rows = [tuple(_param(p) for p in params) for params in seq_of_params]
        if not rows:
            return
        try:
            self._raw.cursor().executemany(translate(sql, True), rows)
        except psycopg.Error:
            self._raw.rollback()
            self._dirty = False
            raise
        self._dirty = True

    def executescript(self, sql: str) -> None:
        try:
            self._raw.execute(sql)
        except psycopg.Error:
            self._raw.rollback()
            self._dirty = False
            raise
        self._raw.commit()
        self._dirty = False

    def commit(self) -> None:
        self._raw.commit()
        self._dirty = False

    def rollback(self) -> None:
        self._raw.rollback()
        self._dirty = False

    def close(self) -> None:
        if self._schema and not self.broken:
            self._raw.rollback()
            self._raw.execute(f"DROP SCHEMA IF EXISTS {self._schema} CASCADE")
            self._raw.commit()
            _EPHEMERAL.discard(self._schema)
        self._raw.close()


_lock = threading.Lock()
_ensured: set[str] = set()
_EPHEMERAL: set[str] = set()
_EPHEMERAL_URL: str | None = None


def redacted(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def connect(path: str | None = None, *, url: str | None = None) -> Connection:
    """기본은 DATABASE_URL 의 공용 스키마. path=":memory:" 는 이 연결만 쓰는 임시 스키마(테스트)."""
    global _EPHEMERAL_URL
    from . import dictionary_store, store

    url = url or DATABASE_URL
    try:
        raw = psycopg.connect(url, application_name="trend-api")
    except psycopg.OperationalError as e:
        raise RuntimeError(
            f"PostgreSQL 에 연결할 수 없습니다 ({redacted(url)}). 저장소 루트에서 docker compose up -d db 를 실행했는지, "
            "DATABASE_URL 이 맞는지 확인하세요."
        ) from e
    schema = None
    if path == ":memory:":
        schema = f"t_{uuid.uuid4().hex[:12]}"
        raw.execute(f"CREATE SCHEMA {schema}")
        raw.execute(f"SET search_path TO {schema}")
        raw.commit()
        _EPHEMERAL.add(schema)
        _EPHEMERAL_URL = url
    con = Connection(raw, schema)
    key = f"{url}|{schema}"
    with _lock:
        if schema or key not in _ensured:
            con.executescript(store.DDL)
            con.executescript(dictionary_store.DDL)
            _ensured.add(key)
    return con


def drop_ephemeral_schemas(url: str | None = None, *, stale: bool = False) -> int:
    """이 프로세스가 만든 임시 스키마(또는 stale=True 면 남아 있는 t_ 스키마 전부)를 지운다. 실패해도 조용히 넘어간다."""
    url = url or _EPHEMERAL_URL or DATABASE_URL
    names = set(_EPHEMERAL)
    try:
        with psycopg.connect(url, autocommit=True) as raw:
            if stale:
                names |= {r[0] for r in raw.execute("SELECT nspname FROM pg_namespace WHERE nspname LIKE 't\\_%'")}
            for name in names:
                raw.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")
    except psycopg.Error:
        return 0
    _EPHEMERAL.difference_update(names)
    return len(names)


atexit.register(lambda: _EPHEMERAL and drop_ephemeral_schemas())
