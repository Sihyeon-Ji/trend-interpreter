import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx
from pydantic import ValidationError

from builder_cup.config import Settings
from builder_cup.providers import PROMPT_VERSION, Provider, ProviderFailure
from builder_cup.schemas import Analysis, AnalyzeResponse, Usage

logger = logging.getLogger("builder_cup")


@dataclass
class ModelMetrics:
    attempts: int = 0
    usage: Usage = field(default_factory=Usage)


async def analyze(
    text: str,
    request_id: str,
    provider: Provider,
    settings: Settings,
    metrics: ModelMetrics | None = None,
) -> AnalyzeResponse:
    start = time.monotonic()
    for attempt in range(1, settings.model_max_attempts + 1):
        if metrics is not None:
            metrics.attempts = attempt
        try:
            async with asyncio.timeout(settings.model_timeout_seconds):
                generation = await provider.generate(text)
            if metrics is not None:
                metrics.usage = generation.usage
            result = Analysis.model_validate_json(generation.text)
            cost = None
            if (
                (settings.input_price_per_million or settings.output_price_per_million)
                and generation.usage.input_tokens is not None
                and generation.usage.output_tokens is not None
            ):
                cost = (
                    generation.usage.input_tokens * settings.input_price_per_million
                    + generation.usage.output_tokens * settings.output_price_per_million
                ) / 1_000_000
            return AnalyzeResponse(
                request_id=request_id,
                provider=settings.model_provider,
                model=provider.model,
                prompt_version=PROMPT_VERSION,
                result=result,
                usage=generation.usage,
                duration_ms=int((time.monotonic() - start) * 1000),
                attempts=attempt,
                estimated_cost_usd=cost,
            )
        except (TimeoutError, httpx.TimeoutException) as exc:
            failure = ProviderFailure("model_timeout", retryable=True)
            failure.__cause__ = exc
        except httpx.TransportError as exc:
            failure = ProviderFailure("model_unavailable", retryable=True)
            failure.__cause__ = exc
        except ValidationError as exc:
            raise ProviderFailure("invalid_model_response") from exc
        except ProviderFailure as exc:
            failure = exc
        if not failure.retryable or attempt == settings.model_max_attempts:
            raise failure
        logger.warning(
            "model_retry",
            extra={
                "fields": {
                    "request_id": request_id,
                    "attempt": attempt,
                    "error_code": failure.code,
                }
            },
        )
        await asyncio.sleep(0.25 * attempt)
    raise AssertionError("Unreachable")
