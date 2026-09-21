"""설정값과 경로를 한 군데서 읽는다.

예전에는 어댑터가 자기 옆에 붙은 비공개 헬퍼(`_env`)를 서로 import 하고 있었다.
설정 읽기는 어댑터의 일이 아니므로 여기로 옮겼다 — llm.py 가 Jira 어댑터를 import 하던 고리가
끊긴다.

값은 프로세스 환경변수를 먼저 보고, 없으면 프로젝트 루트의 .env 를 본다.
.env 는 커밋되지 않는다 (.gitignore).
"""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """prototype/pmo-agent/ — src/pmo_agent/env.py 기준 두 단계 위."""
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return project_root() / "data"


def logs_dir() -> Path:
    return project_root() / "logs"


def reports_dir() -> Path:
    return project_root() / "reports"


def samples_dir() -> Path:
    return project_root() / "samples"


def env(key: str, default: str = "") -> str:
    """환경변수 → .env → 기본값 순."""
    value = os.environ.get(key)
    if value:
        return value
    path = project_root() / ".env"
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default
