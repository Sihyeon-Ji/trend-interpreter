"""PostgreSQL 연결 어댑터.

파이프라인·API 코드는 SQLite 시절의 qmark(?) 자리표시자와 INSERT OR REPLACE / INSERT OR IGNORE 문장을 그대로 쓴다.
이 모듈이 psycopg 형식(%s, ON CONFLICT)으로 바꿔 보내므로 저장소 함수는 SQL 방언을 신경 쓰지 않는다.
테스트는 connect(":memory:") 로 연결마다 임시 스키마를 받는다. 닫으면 스키마째 지운다.
"""
from __future__ import annotations

import atexit
import hashlib
import re
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg_pool import ConnectionPool

from ..config import DATABASE_URL, DB_POOL_SIZE

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


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
        self._atomic = False
        self._atomic_failed = False

    @property
    def raw(self) -> psycopg.Connection:
        return self._raw

    @property
    def broken(self) -> bool:
        return self._raw.closed or self._raw.broken

    def execute(self, sql: str, params=None):
        self._check_atomic()
        values = tuple(_param(p) for p in params) if params else None
        try:
            cur = self._raw.execute(translate(sql, values is not None), values)
        except psycopg.Error:
            if self._atomic:
                self._atomic_failed = True
            else:
                self._raw.rollback()
                self._dirty = False
            raise
        if _is_read(sql):
            if not self._dirty and not self._atomic:
                self._raw.commit()
        else:
            self._dirty = True
        return cur

    def executemany(self, sql: str, seq_of_params) -> None:
        self._check_atomic()
        rows = [tuple(_param(p) for p in params) for params in seq_of_params]
        if not rows:
            return
        try:
            self._raw.cursor().executemany(translate(sql, True), rows)
        except psycopg.Error:
            if self._atomic:
                self._atomic_failed = True
            else:
                self._raw.rollback()
                self._dirty = False
            raise
        self._dirty = True

    def executescript(self, sql: str) -> None:
        self._check_atomic()
        try:
            self._raw.execute(sql)
        except psycopg.Error:
            if self._atomic:
                self._atomic_failed = True
            else:
                self._raw.rollback()
                self._dirty = False
            raise
        self.commit()

    def commit(self) -> None:
        self._check_atomic()
        if self._atomic:
            return
        self._raw.commit()
        self._dirty = False

    def rollback(self) -> None:
        if self._atomic:
            self._atomic_failed = True
            raise RuntimeError("Atomic operation requested rollback")
        self._raw.rollback()
        self._dirty = False

    def _check_atomic(self) -> None:
        if self._atomic_failed:
            raise RuntimeError("Atomic transaction already failed")

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Group legacy helpers' internal commits into one indivisible operation."""
        if self._atomic or self._dirty:
            raise RuntimeError("Transaction requires a clean, non-nested connection")
        self._atomic = True
        self._atomic_failed = False
        try:
            with self._raw.transaction():
                yield self
                self._check_atomic()
        finally:
            self._atomic = False
            self._atomic_failed = False
            self._dirty = False

    def close(self) -> None:
        if self._schema and not self.broken:
            self._raw.rollback()
            self._raw.execute(f"DROP SCHEMA IF EXISTS {self._schema} CASCADE")
            self._raw.commit()
            _EPHEMERAL.discard(self._schema)
        self._raw.close()


_lock = threading.RLock()  # pool() 이 잠금을 쥔 채 connect() 를 부른다
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
            apply_migrations(con)
            _ensured.add(key)
    return con


def connect_existing(url: str | None = None) -> Connection:
    """Open a prepared database without DDL; reject a mismatched runtime schema."""
    from . import dictionary_store, store  # noqa: F401

    try:
        raw = psycopg.connect(url or DATABASE_URL, application_name="trend-publication")
    except psycopg.Error:
        raise RuntimeError("publication_database_unavailable") from None
    con = Connection(raw)
    try:
        expected = {int(path.name.split("_", 1)[0]): hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
                    for path in sorted(MIGRATIONS_DIR.glob("*.sql"))}
        actual = dict(con.execute("SELECT version, checksum FROM schema_migrations").fetchall())
        if actual != expected:
            raise RuntimeError("publication_schema_not_ready")
        return con
    except Exception:
        raw.close()
        raise RuntimeError("publication_schema_not_ready") from None


def connect_read_only(url: str | None = None) -> Connection:
    """읽기만 하는 연결(평가·표본 스크립트). 스키마 준비(DDL·마이그레이션)를 하지 않고, 쓰기는 서버가 거부한다 —
    connect() 로 붙으면 병합 전 가지의 마이그레이션이 운영 DB 에 적용되고 checksum 이 남아, 그 파일이 병합 전에 고쳐지면
    그 DB 의 모든 연결(API 포함)이 거부된다."""
    url = url or DATABASE_URL
    try:
        raw = psycopg.connect(url, application_name="trend-eval", options="-c default_transaction_read_only=on")
    except psycopg.OperationalError as e:
        raise RuntimeError(f"PostgreSQL 에 연결할 수 없습니다 ({redacted(url)}). DATABASE_URL 이 맞는지 확인하세요.") from e
    return Connection(raw)


def apply_migrations(con: Connection, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """번호가 붙은 SQL 파일을 순서대로 한 번씩 적용한다. 적용 기록은 schema_migrations 에 남고, 적용된 파일이 바뀌면 거부한다.

    기본 표는 DDL 의 CREATE TABLE IF NOT EXISTS 가 만들고, 그 뒤의 컬럼 추가·표 추가·데이터 보정은 여기 파일로 한다.
    파일 이름은 NNN_설명.sql 이며 한 파일은 한 트랜잭션이다.
    """
    con.executescript(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version BIGINT PRIMARY KEY, name TEXT, checksum TEXT, applied_at TEXT)"
    )
    applied = dict(con.execute("SELECT version, checksum FROM schema_migrations").fetchall())
    done: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        version = int(path.name.split("_", 1)[0])
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode()).hexdigest()
        if version in applied:
            if applied[version] != checksum:
                raise RuntimeError(f"마이그레이션 {path.name} 은 이미 적용된 뒤 내용이 바뀌었습니다. 새 번호의 파일로 추가하세요.")
            continue
        try:
            con.raw.execute(sql)
            con.execute("INSERT INTO schema_migrations VALUES (?,?,?,?)",
                        (version, path.stem, checksum, datetime.now(timezone.utc).isoformat()))
            con.commit()
        except psycopg.Error:
            con.rollback()
            raise
        done.append(path.name)
    return done


_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    """API 프로세스가 공유하는 연결 풀. 크기는 DB_POOL_SIZE 이며 Cloud Run 의 인스턴스당 동시 요청 수와 같게 맞춘다."""
    global _pool
    with _lock:
        if _pool is None:
            connect().close()  # 스키마와 마이그레이션을 먼저 맞춰 둔다
            _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=DB_POOL_SIZE, timeout=30,
                                   kwargs={"application_name": "trend-api"}, open=True)
    return _pool


@contextmanager
def session() -> Iterator[Connection]:
    """풀에서 연결 하나를 빌려 쓰고 돌려준다. 블록이 예외로 끝나면 풀이 롤백한다."""
    with pool().connection() as raw:
        yield Connection(raw)


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
