import asyncio
from typing import Literal

from pydantic import BaseModel

from builder_cup.config import Settings
from builder_cup.graph_trace import GraphTrace, NodeEvent, NodeRecord
from builder_cup.lab_scenarios import DocumentCheckFailure, Scenario
from builder_cup.providers import Provider
from builder_cup.schemas import AnalyzeRequest, AnalyzeResponse
from builder_cup.workflow import ModelMetrics, analyze

REQUIRED_SECTIONS = ("일정", "준비")
HEADING_PREFIX = "## "


class DocumentChecks(BaseModel):
    character_count: int
    missing_sections: list[str]
    empty_sections: list[str]


class WorkflowInput(BaseModel):
    text: str
    scenario: Scenario = "normal"


class RoutingDecision(BaseModel):
    outcome: Literal["accepted", "needs_revision"]
    reason_codes: list[str]


class JoinedData(BaseModel):
    analysis: AnalyzeResponse
    document_checks: DocumentChecks


class GraphResult(JoinedData):
    decision: RoutingDecision
    events: list[NodeEvent]
    nodes: list[NodeRecord]


def inspect_document(text: str) -> DocumentChecks:
    sections: dict[str, list[str]] = {}
    current_section = None
    for line in text.splitlines():
        if line.startswith(HEADING_PREFIX):
            current_section = line[len(HEADING_PREFIX) :].strip()
            sections.setdefault(current_section, [])
        elif current_section is not None and line.strip():
            sections[current_section].append(line.strip())
    return DocumentChecks(
        character_count=len(text),
        missing_sections=[name for name in REQUIRED_SECTIONS if name not in sections],
        empty_sections=[
            name for name in REQUIRED_SECTIONS if name in sections and not sections[name]
        ],
    )


def route(checks: DocumentChecks) -> RoutingDecision:
    reasons = []
    if checks.missing_sections:
        reasons.append("missing_required_sections")
    if checks.empty_sections:
        reasons.append("empty_required_sections")
    return RoutingDecision(
        outcome="needs_revision" if reasons else "accepted", reason_codes=reasons
    )


async def run_graph(
    text: str,
    request_id: str,
    provider: Provider,
    settings: Settings,
    trace: GraphTrace | None = None,
    scenario: Scenario = "normal",
) -> GraphResult:
    trace = trace or GraphTrace()
    with trace.step("validate_input"):
        validated = AnalyzeRequest(text=text)

    extraction_started = asyncio.Event()

    async def extract() -> AnalyzeResponse:
        with trace.step("extract") as record:
            metrics = ModelMetrics()
            try:
                extraction_started.set()
                return await analyze(validated.text, request_id, provider, settings, metrics)
            finally:
                record.attempts = metrics.attempts
                record.input_tokens = metrics.usage.input_tokens
                record.output_tokens = metrics.usage.output_tokens

    async def inspect() -> DocumentChecks:
        with trace.step("inspect_document"):
            if scenario == "branch_failure":
                await extraction_started.wait()
                raise DocumentCheckFailure()
            return await asyncio.to_thread(inspect_document, validated.text)

    extraction = asyncio.create_task(extract())
    inspection = asyncio.create_task(inspect())
    try:
        analysis_result, document_checks = await asyncio.gather(extraction, inspection)
    finally:
        for task in (extraction, inspection):
            if not task.done():
                task.cancel()
        await asyncio.gather(extraction, inspection, return_exceptions=True)

    with trace.step("join"):
        joined = JoinedData(analysis=analysis_result, document_checks=document_checks)
    with trace.step("route"):
        decision = route(joined.document_checks)
    return GraphResult(
        analysis=joined.analysis,
        document_checks=joined.document_checks,
        decision=decision,
        events=trace.events,
        nodes=list(trace.nodes.values()),
    )
