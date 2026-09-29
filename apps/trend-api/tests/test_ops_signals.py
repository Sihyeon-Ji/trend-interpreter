"""운영 신호(Plan 05·06): 게시 시각의 신선도, PC 없이 도는 유지보수, Gemini 요청 한 번마다 이벤트 한 줄 — 임시 스키마에서."""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from google.genai import errors

from trend_agents import config, logging_setup, model_client
from trend_agents.pipeline import gemini
from trend_agents.storage import db


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


def _calls(caplog) -> list[dict]:
    return [r.fields for r in caplog.records if getattr(r, "event", None) == "gemini_call"]


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


# ---------- Gemini 요청 이벤트 ----------

def test_each_gemini_attempt_logs_one_event_without_content(monkeypatch, caplog):
    """Vertex 에 보낸 요청 한 번 = event=gemini_call 한 줄(모델·장부·결과·HTTP 코드). 로그 기반 지표가 이것을 센다.
    거절된 시도(429·503)도 보낸 요청이라 센다. 프롬프트·응답은 넣지 않는다."""
    con = db.connect(":memory:")
    tries: list[str] = []

    class Flaky:
        def generate_content(self, model, contents, config):
            tries.append(model)
            if len(tries) == 1:
                raise errors.APIError(503, {"error": {"message": "overloaded"}})
            return SimpleNamespace(text="비밀 응답")

    monkeypatch.setattr(gemini, "client", lambda: SimpleNamespace(models=Flaky()))
    monkeypatch.setattr(gemini, "local_ok", lambda: False)
    caplog.set_level(logging.INFO, logger="trend.gemini")
    assert gemini.generate(con, "비밀 프롬프트", request=True)[1] == tries[1]
    assert _calls(caplog) == [{"model": tries[0], "ledger": "request", "outcome": "rejected", "code": 503},
                              {"model": tries[1], "ledger": "request", "outcome": "ok"}]
    assert "비밀" not in caplog.text

    class Broken:
        def generate_content(self, model, contents, config):
            raise errors.APIError(400, {"error": {"message": "bad request"}})

    class Offline:
        def generate_content(self, model, contents, config):
            raise TimeoutError

    for fake, code in ((Broken(), 400), (Offline(), None)):
        monkeypatch.setattr(gemini, "client", lambda fake=fake: SimpleNamespace(models=fake))
        caplog.clear()
        with pytest.raises((errors.APIError, TimeoutError)):
            gemini.generate(con, "prompt")
        want = {"model": config.GEMINI_MODEL, "ledger": "pipeline", "outcome": "error"}
        assert _calls(caplog) == [want | ({"code": code} if code else {})]


def test_disabled_requests_log_no_call_and_spend_no_budget(monkeypatch, caplog):
    """MODEL_REQUESTS_ENABLED=false 면 장부를 깎기 전에 끝난다 — 이벤트가 0 이어야 로그 지표가 '호출 0회' 를 보인다.
    전에는 장부를 먼저 깎고 클라이언트에서 막혀, 보내지도 않은 요청이 하루 예산을 썼다(/explain 재작성은 configured() 를 보지 않고 부른다)."""
    monkeypatch.setattr(config, "MODEL_PROVIDER", "vertex")
    monkeypatch.setattr(config, "MODEL_REQUESTS_ENABLED", False)
    monkeypatch.setattr(gemini, "local_ok", lambda: False)
    model_client.client.cache_clear()
    con = db.connect(":memory:")
    before = (gemini.budget_left(con), gemini.budget_left(con, request=True))
    caplog.set_level(logging.INFO, logger="trend.gemini")
    for request in (False, True):
        with pytest.raises(model_client.ModelRequestsDisabled):
            gemini.generate(con, "prompt", request=request)
    assert (gemini.budget_left(con), gemini.budget_left(con, request=True)) == before
    assert _calls(caplog) == []
