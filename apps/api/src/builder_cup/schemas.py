from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000, pattern=r"\S")


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=1500)
    key_points: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        min_length=1, max_length=5
    )

    @field_validator("summary")
    @classmethod
    def nonblank_summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("summary must contain non-whitespace text")
        return value.strip()

    @field_validator("key_points")
    @classmethod
    def nonblank_key_points(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("key points must contain non-whitespace text")
        return [value.strip() for value in values]


class Usage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class AnalyzeResponse(BaseModel):
    request_id: str
    provider: str
    model: str
    prompt_version: str
    result: Analysis
    usage: Usage
    duration_ms: int
    attempts: int
    estimated_cost_usd: float | None
