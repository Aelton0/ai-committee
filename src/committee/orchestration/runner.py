import asyncio
from typing import Any

from pydantic import BaseModel, ValidationError

from src.committee.agents.base import BaseAgent
from src.committee.llm.provider import LLMProvider


class AgentExecutionFailed(Exception):
    """Raised when an agent execution fails after exhausting maximum retries."""


class AgentRunner:
    """Stateless runner executing an agent against an LLMProvider with retries.

    Does not touch StateMachine or EventStore.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.0,
    ) -> None:
        self.llm_provider = llm_provider
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    async def run(
        self,
        agent: BaseAgent,
        input_context: dict[str, Any],
        output_schema: type[BaseModel] | None = None,
    ) -> BaseModel:
        """Execute the agent, validating context, calling LLMProvider with retries, and returning the artifact."""
        # 1. Defense-in-depth: Validate input context against agent isolation rules
        agent.validate_input_context(input_context)

        # 2. Determine output schema
        schema = output_schema or agent.get_output_schema(input_context)

        # 3. System prompt
        prompt = agent.system_prompt

        # 4. Retry loop
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                artifact = await self.llm_provider.generate(
                    system_prompt=prompt,
                    input_context=input_context,
                    output_schema=schema,
                )
                if not isinstance(artifact, schema):
                    raise ValueError(
                        f"Expected artifact of type {schema.__name__}, got {type(artifact).__name__}"
                    )
                return artifact
            except (ValidationError, ValueError, Exception) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                if self.retry_delay_seconds > 0:
                    await asyncio.sleep(self.retry_delay_seconds * attempt)

        raise AgentExecutionFailed(
            f"Agent {agent.__class__.__name__} ({agent.role.value}) failed after {self.max_retries} attempts. Last error: {last_error}"
        ) from last_error
