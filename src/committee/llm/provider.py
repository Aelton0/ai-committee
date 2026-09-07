"""LLM provider abstraction producing validated Pydantic artifacts directly."""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


@dataclass(frozen=True)
class LLMCallMetadata:
    """Metadata recorded for an LLM call (model, latency, token metrics)."""

    model: str
    latency_seconds: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    request_id: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM provider implementations.

    Receives system prompt, filtered context, and expected output schema,
    and returns a validated Pydantic model instance without regex extraction.
    """

    async def generate(
        self,
        *,
        system_prompt: str,
        input_context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Generate a validated Pydantic model instance conforming to output_schema."""
        ...
