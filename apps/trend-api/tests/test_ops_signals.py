"""운영 신호(Plan 05·06): 게시 시각의 신선도, PC 없이 도는 유지보수, Gemini 요청 한 번마다 이벤트 한 줄 — 임시 스키마에서."""
from __future__ import annotations

import importlib.util
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from google.genai import errors

from trend_agents import config, logging_setup, model_client
from trend_agents.pipeline import gemini
from trend_agents.storage import db, dictionary_store as ds

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _ran(con, stage: str, status: str, hours_ago: float, count: int = 1) -> str:
    """끝난 실행 하나를 hours_ago 시간 전 것으로 남기고 그 끝난 시각을 돌려준다."""
    rid = ds.run_start(con, stage)
    ds.run_finish(con, rid, count, status)
    when = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    con.execute("UPDATE pipeline_runs SET started_at=?, finished_at=? WHERE run_id=?", (when, when, rid))
    con.commit()
    return when


def _ago(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


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


def _maintenance():
    spec = importlib.util.spec_from_file_location("maintenance", SCRIPTS / "maintenance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _one_event(out: str) -> dict:
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, lines
    return json.loads(lines[0])


def _calls(caplog) -> list[dict]:
    return [r.fields for r in caplog.records if getattr(r, "event", None) == "gemini_call"]


# ---------- 게시 시각과 오래된 자료 ----------

def test_meta_freshness_comes_from_publication_not_from_collectors(monkeypatch):
    """수집만 끝난 실행은 갱신이 아니다. /meta 의 last_run 은 지도·대시보드 게시가 모두 성공한 때이고 12시간보다 오래면 stale —
    전에는 어느 단계든 끝난 때(0건·건너뜀 포함)라, 09-28 지도 단계가 19:33·23:33(한국 시각)에 실패한 동안에도 23:33 을 새 자료로 냈다."""
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api

    con = db.connect(":memory:")
    board30 = _ran(con, "board", "ok", 30)
    dash30 = _ran(con, "dashboard", "ok", 30)
    _ran(con, "collect.news", "ok", 1)
    _ran(con, "collect.retention", "ok", 1)
    _ran(con, "board", "zero", 1)          # 빈 지도로 덮은 것은 정상 게시가 아니다
    _ran(con, "dashboard", "skipped", 1)
    monkeypatch.setattr(api, "_con", con)
    c = TestClient(api.app)
    body = c.get("/meta").json()
    assert body["last_run"] == board30 and body["stale"] is True

    board2 = _ran(con, "board", "ok", 2)   # 지도만 새로 — 대시보드는 아직 30시간 전 것
    body = c.get("/meta").json()
    assert body["last_run"] == dash30 and body["stale"] is True
    _ran(con, "dashboard", "ok", 2)
    body = c.get("/meta").json()
    assert body["last_run"] == board2 and body["stale"] is False


def test_nothing_published_is_stale():
    con = db.connect(":memory:")
    _ran(con, "collect.youtube", "ok", 0.5)
    _ran(con, "board", "ok", 0.5)          # 대시보드는 한 번도 성공하지 않았다
    assert ds.last_published(con) is None and ds.is_stale(None)


def test_the_overnight_gap_is_not_stale_but_a_missed_run_is():
    """23:15 실행 뒤 다음 날 09:15 실행까지 게시가 10시간 빈다(09-17~09-28 실측 10.0~10.5시간) — 8시간 한계는 밤마다 울린다."""
    assert ds.STALE_AFTER_HOURS >= 12
    assert not ds.is_stale(_ago(10.5))
    assert ds.is_stale(_ago(ds.STALE_AFTER_HOURS + 0.5))


# ---------- PC 없이 도는 유지보수 ----------

def test_maintenance_prunes_user_text_and_logs_one_event_without_it(monkeypatch, capsys):
    con = db.connect(":memory:")
    ds.explain_cache_set(con, "ko", "오래된 문장", [], None)
    ds.explain_cache_set(con, "ko", "새 문장", [], None)
    con.execute("UPDATE explain_cache SET created_at=? WHERE text=?", (_ago(24 * 8), "오래된 문장"))
    ds.log_lookup_miss(con, "오래된 질문", "ko")
    ds.log_lookup_miss(con, "새 질문", "ko")
    con.execute("UPDATE lookups SET last_at=? WHERE text=?", (_ago(24 * 31), "오래된 질문"))
    con.commit()
    _ran(con, "board", "ok", 1)
    _ran(con, "dashboard", "ok", 1)
    m = _maintenance()
    monkeypatch.setattr(m, "connect", lambda: con)
    monkeypatch.setattr(con, "close", lambda: None)      # 지운 결과를 보려고 연결을 남긴다
    monkeypatch.setenv("LOG_FORMAT", "json")

    with _logging_restored():
        assert m.main() == 0
    out = capsys.readouterr().out
    e = _one_event(out)
    assert e["event"] == "maintenance" and e["status"] == "ok" and e["severity"] == "INFO"
    assert e["explain_cache_deleted"] == 1 and e["lookups_deleted"] == 1
    assert e["stale"] is False and e["stale_after_hours"] == ds.STALE_AFTER_HOURS and 0.9 < e["published_age_hours"] < 1.1
    assert "문장" not in out and "질문" not in out       # 사용자 문장은 로그에 남기지 않는다
    assert ds.explain_cache_get(con, "ko", "새 문장") is not None and ds.explain_cache_get(con, "ko", "오래된 문장") is None
    assert [t for _, t, _ in ds.pending_lookups(con)] == ["새 질문"]


def test_maintenance_exit_code_separates_stale_from_failure(monkeypatch, capsys):
    """0 정상, 1 정리·점검 실패, 2 게시본이 오래됨(정리는 한다) — Job 이 0 이 아니면 실패로 남아 경보가 잡는다."""
    m = _maintenance()
    monkeypatch.setenv("LOG_FORMAT", "json")
    con = db.connect(":memory:")
    ds.explain_cache_set(con, "ko", "오래된 문장", [], None)
    con.execute("UPDATE explain_cache SET created_at=?", (_ago(24 * 8),))
    con.commit()
    _ran(con, "collect.news", "ok", 0.5)                  # 수집만 돌았고 게시는 없었다
    monkeypatch.setattr(m, "connect", lambda: con)
    with _logging_restored():
        assert m.main() == 2
    e = _one_event(capsys.readouterr().out)
    assert e["status"] == "stale" and e["severity"] == "ERROR" and e["last_published"] is None and e["explain_cache_deleted"] == 1

    def down():
        raise psycopg.OperationalError('connection to server at "secret-host" (10.0.0.9), port 5432 failed: password authentication failed')

    monkeypatch.setattr(m, "connect", down)
    with _logging_restored():
        assert m.main() == 1
    out = capsys.readouterr().out
    e = _one_event(out)
    assert e["status"] == "error" and e["error"] == "OperationalError" and "secret-host" not in out   # 오류는 종류만


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
