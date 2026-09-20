import asyncio
from typing import Literal

import httpx

from builder_cup.providers import Generation, MockProvider
from builder_cup.schemas import Usage

Scenario = Literal["normal", "timeout", "invalid_json", "branch_failure", "transient_error"]
LAB_TIMEOUT_SECONDS = 1.0
LAB_MAX_ATTEMPTS = 2
SIMULATED_DELAY_SECONDS = 10


class DocumentCheckFailure(Exception):
    pass


class ScenarioProvider(MockProvider):
    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.calls = 0

    async def generate(self, text: str) -> Generation:
        self.calls += 1
        if self.scenario in {"timeout", "branch_failure"}:
            await asyncio.sleep(SIMULATED_DELAY_SECONDS)
        if self.scenario == "invalid_json":
            return Generation(text="{invalid-json", usage=Usage(input_tokens=0, output_tokens=0))
        if self.scenario == "transient_error" and self.calls == 1:
            raise httpx.ConnectError("Simulated local connection failure")
        return await super().generate(text)
