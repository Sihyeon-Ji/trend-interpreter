"""운영 신호(Plan 05·06): 게시 시각의 신선도, PC 없이 도는 유지보수, Gemini 요청 한 번마다 이벤트 한 줄 — 임시 스키마에서."""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager

from trend_agents import logging_setup


@contextmanager
def _logging_restored():
    """configure() 는 루트·uvicorn 로거의 처리기를 바꾼다. 시험 본문 안에서 되돌려야 pytest 가 이번 단계에 단 처리기도 제자리로 간다."""
    names = ("", "uvicorn", "uvicorn.error", "uvicorn.access")
    saved = {n: (logging.getLogger(n).handlers[:], logging.getLogger(n).level, logging.getLogger(n).propagate) for n in names}
    try:
        yield
    finally:
        for n, (handlers, level, propagate) in saved.items():
            lg = logging.getLogger(n)
            lg.handlers[:], lg.propagate = handlers, propagate
            lg.setLevel(level)


def _one_event(out: str) -> dict:
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, lines
    return json.loads(lines[0])


# ---------- PC 없이 도는 유지보수 ----------

def test_cloud_run_jobs_log_json_by_default(monkeypatch, capsys):
    """Cloud Run Job 에는 K_SERVICE 가 없고 CLOUD_RUN_JOB 이 있다 — 유지보수 Job 의 이벤트도 jsonPayload 로 읽혀야 지표·경보가 거른다."""
    for name in ("LOG_FORMAT", "K_SERVICE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CLOUD_RUN_JOB", "trend-maintenance")
    with _logging_restored():
        logging_setup.configure()
        logging_setup.event(logging.getLogger("trend.test"), "demo", n=3, status="ok")
    e = _one_event(capsys.readouterr().out)
    assert (e["event"], e["n"], e["status"], e["severity"], e["message"]) == ("demo", 3, "ok", "INFO", "demo n=3 status=ok")

    monkeypatch.delenv("CLOUD_RUN_JOB")
    with _logging_restored():
        logging_setup.configure()                         # 로컬 터미널은 읽기 쉬운 텍스트 그대로
        logging_setup.event(logging.getLogger("trend.test"), "demo", n=3)
    assert capsys.readouterr().out.strip().endswith("INFO trend.test demo n=3")
