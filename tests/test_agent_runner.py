"""Unit tests verifying AgentRunner retry loop, error handling, and stateless behavior."""

import asyncio
import pytest
from pydantic import BaseModel

from schemas.proposals import ArchitectProposal
from src.committee.agents import ArchitectAgent, ContextIsolationError
from src.committee.llm import MockLLMProvider
from src.committee.orchestration.runner import AgentExecutionFailed, AgentRunner


def test_runner_successful_execution() -> None:
    """AgentRunner executes agent and returns validated Pydantic artifact."""
    async def _test():
        provider = MockLLMProvider()
        runner = AgentRunner(provider, max_retries=3)
        agent = ArchitectAgent()

        result = await runner.run(agent, {"phase": "PHASE_1_DIVERGENCE", "problem_statement": "Test"})
        assert isinstance(result, ArchitectProposal)
        assert len(provider.call_history) == 1

    asyncio.run(_test())


def test_runner_retries_on_failure_and_recovers() -> None:
    """AgentRunner catches transient failures and succeeds on subsequent retry."""
    async def _test():
        # Program 2 failures for ArchitectProposal
        provider = MockLLMProvider(failure_counts={ArchitectProposal: 2})
        runner = AgentRunner(provider, max_retries=3)
        agent = ArchitectAgent()

        result = await runner.run(agent, {"phase": "PHASE_1_DIVERGENCE", "problem_statement": "Test"})
        assert isinstance(result, ArchitectProposal)
        assert len(provider.call_history) == 3

    asyncio.run(_test())


def test_runner_exhausts_retries_and_raises() -> None:
    """AgentRunner raises AgentExecutionFailed when max retries are exhausted."""
    async def _test():
        provider = MockLLMProvider(failure_counts={ArchitectProposal: 3})
        runner = AgentRunner(provider, max_retries=3)
        agent = ArchitectAgent()

        with pytest.raises(AgentExecutionFailed, match="failed after 3 attempts"):
            await runner.run(agent, {"phase": "PHASE_1_DIVERGENCE", "problem_statement": "Test"})

        assert len(provider.call_history) == 3

    asyncio.run(_test())


def test_runner_enforces_context_isolation_before_calling_llm() -> None:
    """AgentRunner invokes agent.validate_input_context before sending context to LLM."""
    async def _test():
        provider = MockLLMProvider()
        runner = AgentRunner(provider)
        agent = ArchitectAgent()

        forbidden_context = {
            "phase": "PHASE_1_DIVERGENCE",
            "pragmatic_proposal": {"title": "Leaked"},
        }

        with pytest.raises(ContextIsolationError, match="Blind divergence violated"):
            await runner.run(agent, forbidden_context)

        assert len(provider.call_history) == 0

    asyncio.run(_test())


def test_runner_validates_returned_schema_type() -> None:
    """AgentRunner rejects an object if LLMProvider returns an unexpected schema."""
    async def _test():
        class FakeArtifact(BaseModel):
            val: str = "fake"

        provider = MockLLMProvider(custom_generators={ArchitectProposal: lambda ctx: FakeArtifact()})
        runner = AgentRunner(provider, max_retries=2)
        agent = ArchitectAgent()

        with pytest.raises(AgentExecutionFailed, match="Expected artifact of type ArchitectProposal"):
            await runner.run(agent, {"phase": "PHASE_1_DIVERGENCE"})

    asyncio.run(_test())
