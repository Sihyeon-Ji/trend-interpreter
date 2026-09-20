import asyncio
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from builder_cup.config import Settings
from builder_cup.database import connection
from builder_cup.graph_lab import GraphResult, run_graph
from builder_cup.graph_trace import GraphTrace, NodeRecord, safe_error_code
from builder_cup.lab_scenarios import Scenario
from builder_cup.providers import PROMPT_VERSION, Provider


class WorkflowRun(BaseModel):
    id: UUID
    scenario: Scenario = "normal"
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    status: Literal["running", "completed", "failed", "cancelled"] = "running"
    outcome: Literal["accepted", "needs_revision"] | None = None
    provider: str
    model: str
    prompt_version: str
    attempts: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_code: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


class RunDetail(WorkflowRun):
    nodes: list[NodeRecord]


def start_run(settings: Settings, run: WorkflowRun, trace: GraphTrace) -> None:
    with connection(settings) as conn:
        conn.execute(
            """INSERT INTO lab.workflow_runs
               (id, started_at, status, provider, model, prompt_version, scenario)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                run.id,
                run.started_at,
                run.status,
                run.provider,
                run.model,
                run.prompt_version,
                run.scenario,
            ),
        )
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO lab.workflow_nodes (run_id, node, position, status)
                   VALUES (%s, %s, %s, %s)""",
                [(run.id, node.node, node.position, node.status) for node in trace.nodes.values()],
            )


def finish_run(settings: Settings, run: WorkflowRun, trace: GraphTrace) -> None:
    with connection(settings) as conn:
        conn.execute(
            """UPDATE lab.workflow_runs SET
               finished_at = %s, duration_ms = %s, status = %s, outcome = %s,
               attempts = %s, input_tokens = %s, output_tokens = %s,
               error_code = %s, reason_codes = %s WHERE id = %s""",
            (
                run.finished_at,
                run.duration_ms,
                run.status,
                run.outcome,
                run.attempts,
                run.input_tokens,
                run.output_tokens,
                run.error_code,
                Jsonb(run.reason_codes),
                run.id,
            ),
        )
        with conn.cursor() as cursor:
            cursor.executemany(
                """UPDATE lab.workflow_nodes SET status = %s, started_at = %s,
                   finished_at = %s, duration_ms = %s, attempts = %s,
                   input_tokens = %s, output_tokens = %s, error_code = %s
                   WHERE run_id = %s AND node = %s""",
                [
                    (
                        node.status,
                        node.started_at,
                        node.finished_at,
                        node.duration_ms,
                        node.attempts,
                        node.input_tokens,
                        node.output_tokens,
                        node.error_code,
                        run.id,
                        node.node,
                    )
                    for node in trace.nodes.values()
                ],
            )


def list_runs(settings: Settings, limit: int = 20) -> list[WorkflowRun]:
    with connection(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM lab.workflow_runs ORDER BY started_at DESC, id DESC LIMIT %s", (limit,)
        ).fetchall()
        return [WorkflowRun.model_validate(row) for row in rows]


def read_run(settings: Settings, run_id: UUID) -> RunDetail | None:
    with connection(settings) as conn:
        row = conn.execute(
            """SELECT r.*, COALESCE(
                 jsonb_agg(to_jsonb(n) - 'run_id' ORDER BY n.position)
                 FILTER (WHERE n.node IS NOT NULL), '[]'::jsonb
               ) AS nodes
               FROM lab.workflow_runs r LEFT JOIN lab.workflow_nodes n ON n.run_id = r.id
               WHERE r.id = %s GROUP BY r.id""",
            (run_id,),
        ).fetchone()
        return RunDetail.model_validate(row) if row else None


async def run_with_history(
    text: str,
    request_id: str,
    provider: Provider,
    settings: Settings,
    scenario: Scenario = "normal",
) -> GraphResult:
    trace = GraphTrace()
    run = WorkflowRun(
        id=UUID(request_id),
        scenario=scenario,
        started_at=trace.started_at,
        provider=settings.model_provider,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
    )
    await asyncio.to_thread(start_run, settings, run, trace)
    try:
        result = await run_graph(text, request_id, provider, settings, trace, scenario=scenario)
        run.status = "completed"
        run.outcome = result.decision.outcome
        run.reason_codes = result.decision.reason_codes
    except (Exception, asyncio.CancelledError) as exc:
        run.status = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
        run.error_code = safe_error_code(exc)
        trace.skip_pending()
        raise
    finally:
        run.finished_at = datetime.now(UTC)
        run.duration_ms = int((time.monotonic() - trace.started_clock) * 1000)
        model_node = trace.nodes["extract"]
        run.attempts = model_node.attempts
        run.input_tokens = model_node.input_tokens
        run.output_tokens = model_node.output_tokens
        # A result is not returned until its run and node snapshots commit together.
        await asyncio.shield(asyncio.to_thread(finish_run, settings, run, trace))
    return result
