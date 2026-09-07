"""Test provider substitution: proving the same agent runs across Mock, Gemini, and OpenAI."""

import asyncio
from dataclasses import dataclass
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest

from schemas.proposals import ArchitectProposal
from src.committee.agents.architect import ArchitectAgent
from src.committee.llm.factory import create_llm_provider
from src.committee.llm.gemini import GeminiLLMProvider
from src.committee.llm.mock import MockLLMProvider
from src.committee.llm.openai import OpenAILLMProvider
from src.committee.orchestration.runner import AgentRunner


def build_sample_architect_proposal() -> ArchitectProposal:
    return ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Decoupled Event-Driven Microservices",
        solution="Event streaming via Kafka with schema registry.",
        rationale="Enables independent service evolution and fault isolation.",
        benefits=["Domain decoupling", "Independent scalability"],
        costs={
            "implementation_effort": "HIGH",
            "infrastructure_cost_estimate": "$200/mo",
            "additional_costs": ["Observability"],
        },
        risks=["Distributed tracing complexity"],
        complexity="HIGH",
        reversibility={
            "score": "LOW",
            "rationale": "Data migration required to revert.",
        },
        future_implications="Multi-region ready.",
        assumptions=["Team learns event streaming."],
        invalidation_conditions=["Throughput drops permanently below 10 req/s."],
        modularity_strategy="Event contracts enforced in CI/CD.",
        evolution_path="Phase 1: Outbox pattern.",
    )


@dataclass
class DummyResponsesUsage:
    input_tokens: int = 150
    output_tokens: int = 250
    total_tokens: int = 400


class DummyParsedResponse:
    def __init__(self, output_parsed: Any) -> None:
        self.id = "resp-subst-1"
        self.output_parsed = output_parsed
        self.usage = DummyResponsesUsage()


class MockGeminiResponse:
    def __init__(self, parsed: Any) -> None:
        self.parsed = parsed
        self.usage_metadata = MagicMock(
            prompt_token_count=140,
            candidates_token_count=240,
            total_token_count=380,
        )


def test_agent_runs_with_mock_provider() -> None:
    expected_proposal = build_sample_architect_proposal()
    mock_provider = MockLLMProvider(
        custom_generators={ArchitectProposal: lambda ctx: expected_proposal}
    )

    runner = AgentRunner(llm_provider=mock_provider)
    agent = ArchitectAgent()

    async def _test() -> None:
        result = await runner.run(
            agent,
            {"phase": "PHASE_1_DIVERGENCE", "problem_statement": "System scalability"},
            output_schema=ArchitectProposal,
        )
        assert isinstance(result, ArchitectProposal)
        assert result.artifact_id == "PROP-ARCH-001"
        assert result.title == "Decoupled Event-Driven Microservices"

    asyncio.run(_test())


def test_agent_runs_with_gemini_provider() -> None:
    expected_proposal = build_sample_architect_proposal()

    gemini_client = MagicMock()
    gemini_client.aio.models.generate_content = AsyncMock(
        return_value=MockGeminiResponse(parsed=expected_proposal)
    )

    gemini_provider = GeminiLLMProvider(
        api_key="AIzaSyTestKey123456789012345678901234",
        client=gemini_client,
    )

    runner = AgentRunner(llm_provider=gemini_provider)
    agent = ArchitectAgent()

    async def _test() -> None:
        result = await runner.run(
            agent,
            {"phase": "PHASE_1_DIVERGENCE", "problem_statement": "System scalability"},
            output_schema=ArchitectProposal,
        )
        assert isinstance(result, ArchitectProposal)
        assert result.artifact_id == "PROP-ARCH-001"
        assert result.title == "Decoupled Event-Driven Microservices"
        assert gemini_provider.last_metadata is not None
        assert gemini_provider.last_metadata.total_tokens == 380

    asyncio.run(_test())


def test_agent_runs_with_openai_provider() -> None:
    expected_proposal = build_sample_architect_proposal()

    openai_client = MagicMock()
    openai_client.responses = MagicMock()
    openai_client.responses.parse = AsyncMock(
        return_value=DummyParsedResponse(output_parsed=expected_proposal)
    )

    openai_provider = OpenAILLMProvider(
        api_key="sk-proj-testkey123456789012345678901234",
        client=openai_client,
    )

    runner = AgentRunner(llm_provider=openai_provider)
    agent = ArchitectAgent()

    async def _test() -> None:
        result = await runner.run(
            agent,
            {"phase": "PHASE_1_DIVERGENCE", "problem_statement": "System scalability"},
            output_schema=ArchitectProposal,
        )
        assert isinstance(result, ArchitectProposal)
        assert result.artifact_id == "PROP-ARCH-001"
        assert result.title == "Decoupled Event-Driven Microservices"
        assert openai_provider.last_metadata is not None
        assert openai_provider.last_metadata.request_id == "resp-subst-1"
        assert openai_provider.last_metadata.total_tokens == 400

    asyncio.run(_test())


def test_agent_runner_retries_transient_openai_error() -> None:
    expected_proposal = build_sample_architect_proposal()

    openai_client = MagicMock()
    openai_client.responses = MagicMock()

    # First attempt: 503 InternalServerError (mapped to ProviderTemporaryError)
    # Second attempt: success
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp_503 = httpx.Response(503, request=req)
    openai_client.responses.parse = AsyncMock(
        side_effect=[
            openai.InternalServerError("Service Unavailable", response=resp_503, body=None),
            DummyParsedResponse(output_parsed=expected_proposal),
        ]
    )

    openai_provider = OpenAILLMProvider(
        api_key="sk-proj-testkey123456789012345678901234",
        client=openai_client,
    )

    runner = AgentRunner(llm_provider=openai_provider, max_retries=3)
    agent = ArchitectAgent()

    async def _test() -> None:
        result = await runner.run(
            agent,
            {"phase": "PHASE_1_DIVERGENCE", "problem_statement": "System scalability"},
            output_schema=ArchitectProposal,
        )
        assert isinstance(result, ArchitectProposal)
        assert result.artifact_id == "PROP-ARCH-001"
        assert openai_client.responses.parse.await_count == 2

    asyncio.run(_test())
