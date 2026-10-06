"""단계 실행 기록 + '조용한 0' 카나리. 단계가 예외 없이 0건을 내면 경고로 남긴다."""
from __future__ import annotations

import traceback
from contextlib import contextmanager
from contextvars import ContextVar
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
    models: set[str] = field(default_factory=set)   # 이 실행이 부른 모델 ID — record_model() 이 채우고 실행 기록에 남는다
    calls: dict[str, list[float]] = field(default_factory=dict)   # 모델 ID → [성공한 호출 수, 걸린 초] (Plan 14 0단계: 관리 화면 '모델 기록')


_current: ContextVar[Result | None] = ContextVar("pipeline_stage", default=None)


def record_model(model: str, seconds: float | None = None, n: int = 1) -> None:
    """지금 도는 단계 실행이 이 모델을 불렀다고 적는다(Plan 06 완료 기준 1: 로컬 편집 결과를 모델에 묶는다).
    모델 호출이 성공한 곳(pipeline/gemini.py 등)이 부른다. 단계 밖(이용자 요청)에서는 아무것도 하지 않는다.
    seconds 를 주면 호출 n 번과 걸린 시간을 센다 — 호출을 실제로 잰 곳(local_llm·gemini.generate 등)만 주고,
    같은 호출을 다시 적는 바깥 층은 주지 않는다(두 번 세지 않게)."""
    r = _current.get()
    if r is not None and model:
        r.models.add(model)
        if seconds is not None:
            c = r.calls.setdefault(model, [0, 0.0])
            c[0] += n
            c[1] += seconds


@contextmanager
def stage(con: Connection, name: str):
    rid = ds.run_start(con, name)
    res = Result(stage=name)
    token = _current.set(res)
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
        _current.reset(token)
        ds.run_finish(con, rid, res.count, res.status, res.note, sorted(res.models), res.calls)
