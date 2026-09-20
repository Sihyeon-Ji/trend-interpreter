import asyncio
from typing import Literal

from pydantic import BaseModel

from builder_cup.config import Settings
from builder_cup.providers import Provider
from builder_cup.schemas import AnalyzeRequest, AnalyzeResponse
from builder_cup.workflow import analyze

REQUIRED_SECTIONS = ("일정", "준비")
HEADING_PREFIX = "## "


class DocumentChecks(BaseModel):
    character_count: int
    missing_sections: list[str]
    empty_sections: list[str]


class NodeEvent(BaseModel):
    node: Literal["validate_input", "extract", "inspect_document", "join", "route"]
    state: Literal["started", "completed"]


class RoutingDecision(BaseModel):
    outcome: Literal["accepted", "needs_revision"]
    reason_codes: list[str]


class JoinedData(BaseModel):
    analysis: AnalyzeResponse
    document_checks: DocumentChecks


class GraphResult(JoinedData):
    decision: RoutingDecision
    events: list[NodeEvent]


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
    text: str, request_id: str, provider: Provider, settings: Settings
) -> GraphResult:
    events = [NodeEvent(node="validate_input", state="started")]
    validated = AnalyzeRequest(text=text)
    events.append(NodeEvent(node="validate_input", state="completed"))

    async def extract() -> AnalyzeResponse:
        events.append(NodeEvent(node="extract", state="started"))
        result = await analyze(validated.text, request_id, provider, settings)
        events.append(NodeEvent(node="extract", state="completed"))
        return result

    async def inspect() -> DocumentChecks:
        events.append(NodeEvent(node="inspect_document", state="started"))
        result = await asyncio.to_thread(inspect_document, validated.text)
        events.append(NodeEvent(node="inspect_document", state="completed"))
        return result

    extraction = asyncio.create_task(extract())
    inspection = asyncio.create_task(inspect())
    try:
        analysis_result, document_checks = await asyncio.gather(extraction, inspection)
    finally:
        for task in (extraction, inspection):
            if not task.done():
                task.cancel()
        await asyncio.gather(extraction, inspection, return_exceptions=True)

    events.append(NodeEvent(node="join", state="started"))
    joined = JoinedData(
        analysis=analysis_result,
        document_checks=document_checks,
    )
    events.append(NodeEvent(node="join", state="completed"))
    events.append(NodeEvent(node="route", state="started"))
    decision = route(joined.document_checks)
    events.append(NodeEvent(node="route", state="completed"))
    return GraphResult(
        analysis=joined.analysis,
        document_checks=joined.document_checks,
        decision=decision,
        events=events,
    )
