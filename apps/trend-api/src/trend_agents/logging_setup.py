"""로그는 표준 출력으로만 낸다. Cloud Run 에서는 JSON 한 줄이 Cloud Logging 의 severity·message 로 읽힌다.

로컬 터미널에서는 읽기 쉬운 한 줄 텍스트다. LOG_FORMAT=json 으로 강제할 수 있고, Cloud Run 서비스(K_SERVICE)와 Job(CLOUD_RUN_JOB)에서는
기본이 JSON 이다. 로그 기반 지표·경보가 셀 줄은 event() 로 낸다 — 이벤트 이름과 필드가 jsonPayload 최상위로 간다.
사용자가 쓴 문장·모델 출력·비밀값은 로그에 넣지 않는다.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": datetime.now(timezone.utc).isoformat(),
        }
        name = getattr(record, "event", None)
        if name:
            payload["event"] = name
            payload.update({k: v for k, v in getattr(record, "fields", {}).items() if k not in payload})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def event(logger: logging.Logger, name: str, level: int = logging.INFO, **fields: str | int | float | bool | None) -> None:
    """구조화 이벤트 한 줄. JSON 이면 {"event": name, 필드…}, 텍스트면 'name k=v …'.
    필드는 모델 이름·상태·건수·시각 같은 운영 값만 — 사용자 문장·모델 출력·비밀값·오류 메시지 원문은 넣지 않는다."""
    logger.log(level, " ".join([name, *(f"{k}={v}" for k, v in fields.items())]), extra={"event": name, "fields": fields})


def configure(level: str | None = None) -> None:
    cloud_run = os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")  # Job 에는 K_SERVICE 가 없다
    use_json = os.getenv("LOG_FORMAT", "json" if cloud_run else "text") == "json"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if use_json else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%H:%M:%S"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level or os.getenv("LOG_LEVEL", "INFO"))
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers[:] = [handler]
        logger.propagate = False
