"""로그는 표준 출력으로만 낸다. Cloud Run 에서는 JSON 한 줄이 Cloud Logging 의 severity·message 로 읽힌다.

로컬 터미널에서는 읽기 쉬운 한 줄 텍스트다. LOG_FORMAT=json 으로 강제할 수 있고, Cloud Run(K_SERVICE 존재)에서는 기본이 JSON 이다.
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
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure(level: str | None = None) -> None:
    use_json = os.getenv("LOG_FORMAT", "json" if os.getenv("K_SERVICE") else "text") == "json"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if use_json else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%H:%M:%S"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level or os.getenv("LOG_LEVEL", "INFO"))
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers[:] = [handler]
        logger.propagate = False
