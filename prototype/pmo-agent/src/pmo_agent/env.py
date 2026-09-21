"""Settings and paths, read in one place.

Adapters used to import a private helper (`_env`) sitting next to one of them. Reading
configuration is not an adapter's job, so it moved here — which breaks the loop where
llm.py imported the Jira adapter.

Values come from the process environment first, then from .env at the project root.
.env is never committed (.gitignore).
"""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """prototype/pmo-agent/ — two levels above src/pmo_agent/env.py."""
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
    """Environment variable, then .env, then the default."""
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
