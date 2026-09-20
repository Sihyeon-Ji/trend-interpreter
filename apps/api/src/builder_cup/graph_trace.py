import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ValidationError

from builder_cup.providers import ProviderFailure

NodeName = Literal["validate_input", "extract", "inspect_document", "join", "route"]
NODE_ORDER: tuple[NodeName, ...] = (
    "validate_input",
    "extract",
    "inspect_document",
    "join",
    "route",
)
NodeOutcome = Literal["completed", "failed", "cancelled"]


def safe_error_code(error: BaseException) -> str:
    if isinstance(error, asyncio.CancelledError):
        return "cancelled"
    if isinstance(error, ValidationError):
        return "invalid_input"
    if isinstance(error, ProviderFailure) and error.code in {
        "model_timeout",
        "model_unavailable",
        "invalid_model_response",
    }:
        return error.code
    return "workflow_failed"


class NodeEvent(BaseModel):
    node: NodeName
    state: Literal["started", "completed", "failed", "cancelled"]


class NodeRecord(BaseModel):
    node: NodeName
    position: int
    status: Literal["pending", "running", "completed", "failed", "cancelled", "skipped"] = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    attempts: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_code: str | None = None


class GraphTrace:
    def __init__(self) -> None:
        self.started_at = datetime.now(UTC)
        self.started_clock = time.monotonic()
        self.events: list[NodeEvent] = []
        self.nodes = {
            name: NodeRecord(node=name, position=position)
            for position, name in enumerate(NODE_ORDER)
        }

    @contextmanager
    def step(self, name: NodeName) -> Iterator[NodeRecord]:
        record = self.nodes[name]
        record.status = "running"
        record.started_at = datetime.now(UTC)
        started = time.monotonic()
        self.events.append(NodeEvent(node=name, state="started"))
        outcome: NodeOutcome = "completed"
        try:
            yield record
        except asyncio.CancelledError as exc:
            outcome = "cancelled"
            record.error_code = safe_error_code(exc)
            raise
        except Exception as exc:
            outcome = "failed"
            record.error_code = safe_error_code(exc)
            raise
        finally:
            record.status = outcome
            record.finished_at = datetime.now(UTC)
            record.duration_ms = int((time.monotonic() - started) * 1000)
            self.events.append(NodeEvent(node=name, state=outcome))

    def skip_pending(self) -> None:
        for record in self.nodes.values():
            if record.status == "pending":
                record.status = "skipped"
