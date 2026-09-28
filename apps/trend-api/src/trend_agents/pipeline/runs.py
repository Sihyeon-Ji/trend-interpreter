"""단계 실행 기록 + '조용한 0' 카나리. 단계가 예외 없이 0건을 내면 경고로 남긴다."""
from __future__ import annotations

import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field

from ..storage import dictionary_store as ds
from ..storage.db import Connection


@dataclass
class Result:
    stage: str
    count: int = 0
    status: str = "ok"
    note: str = ""
    detail: dict = field(default_factory=dict)


@contextmanager
def stage(con: Connection, name: str):
    rid = ds.run_start(con, name)
    res = Result(stage=name)
    try:
        yield res
        if res.count == 0 and res.status == "ok" and not res.note:
            res.status = "zero"
            res.note = res.note or "0건 — 소스·키·네트워크 확인"
    except Exception as e:  # 한 단계의 실패가 다른 단계를 막지 않는다
        res.status = "error"
        res.note = f"{type(e).__name__}: {str(e)[:300]}"
        res.detail["trace"] = traceback.format_exc()[-1500:]
    finally:
        ds.run_finish(con, rid, res.count, res.status, res.note)
