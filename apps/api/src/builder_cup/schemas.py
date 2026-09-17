from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000, pattern=r"\S")


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=1500)
    key_points: list[str] = Field(min_length=1, max_length=5)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


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
