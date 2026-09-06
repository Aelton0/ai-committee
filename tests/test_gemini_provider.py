"""Comprehensive unit tests for GeminiLLMProvider and LLMConfig."""

from dataclasses import dataclass
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import BaseModel, Field

from schemas.common import CommitteeRole, Severity
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from src.committee.agents.architect import ArchitectAgent
from src.committee.llm.config import (
    LLMConfig,
    mask_secret,
    sanitize_secrets_from_text,
)
from src.committee.llm.gemini import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiLLMProvider,
    GeminiTimeoutError,
    clean_schema_for_gemini,
)
from src.committee.orchestration.runner import AgentExecutionFailed, AgentRunner


# --- Dummy Models and Helpers for Testing ---
class SampleArtifact(BaseModel):
    title: str = Field(..., min_length=1)
    score: int = Field(..., ge=1, le=10)


@dataclass
class MockUsageMetadata:
    prompt_token_count: int = 150
    candidates_token_count: int = 220
    total_token_count: int = 370


class MockGenerateResponse:
    def __init__(
        self,
        text: str | None = None,
        parsed: Any = None,
        usage_metadata: MockUsageMetadata | None = None,
    ) -> None:
        self.text = text
        self.parsed = parsed
        self.usage_metadata = usage_metadata or MockUsageMetadata()


def build_sample_architect_proposal_dict() -> dict[str, Any]:
    """Return a dictionary valid under ArchitectProposal schema."""
    return {
        "artifact_id": "PROP-ARCH-001",
        "version": 1,
        "title": "Decoupled Event-Driven Microservices",
        "solution": "Event streaming via Kafka with schema registry.",
        "rationale": "Enables independent service evolution and fault isolation.",
        "benefits": ["Domain decoupling", "Independent scalability"],
        "costs": {
            "implementation_effort": "HIGH",
            "infrastructure_cost_estimate": "$200/mo",
            "additional_costs": ["Observability"],
        },
        "risks": ["Distributed tracing complexity"],
        "complexity": "HIGH",
        "reversibility": {
            "score": "LOW",
            "rationale": "Data migration required to revert.",
        },
        "future_implications": "Multi-region ready.",
        "assumptions": ["Team learns event streaming."],
        "invalidation_conditions": ["Throughput drops permanently below 10 req/s."],
        "modularity_strategy": "Event contracts enforced in CI/CD.",
        "evolution_path": "Phase 1: Outbox pattern.",
    }


# --- 1. Configuration & Secret Masking Tests ---
def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_TIMEOUT_SECONDS", raising=False)

    config = LLMConfig.from_env()
    assert config.provider == "gemini"
    assert config.gemini_api_key is None
    assert config.gemini_model == "gemini-2.5-flash"
    assert config.gemini_timeout_seconds == 60.0


def test_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSySecretTestKey1234567890")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "45.5")

    config = LLMConfig.from_env()
    assert config.gemini_api_key == "AIzaSySecretTestKey1234567890"
    assert config.gemini_model == "gemini-1.5-pro"
    assert config.gemini_timeout_seconds == 45.5


def test_config_repr_does_not_leak_key() -> None:
    secret = "AIzaSySuperSecretKey9876543210"
    config = LLMConfig(gemini_api_key=secret)

    repr_str = repr(config)
    str_str = str(config)

    assert secret not in repr_str
    assert secret not in str_str
    assert "AIza...3210" in repr_str


def test_mask_secret_helper() -> None:
    assert mask_secret(None) == "None"
    assert mask_secret("") == "None"
    assert mask_secret("short") == "***"
    assert mask_secret("AIzaSyLongSecretKey12345") == "AIza...2345"


def test_sanitize_secrets_from_text() -> None:
    secret = "AIzaSySuperSecretLiveKey0011223344"
    text = (
        f"Failed to connect to https://generativelanguage.googleapis.com/v1beta/models?key={secret} "
        f"with header x-goog-api-key: {secret}"
    )

    sanitized = sanitize_secrets_from_text(text, secret)
    assert secret not in sanitized
    assert "[REDACTED" in sanitized


# --- 2. Provider Initialization & Model Selection Tests ---
def test_provider_missing_api_key_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    config = LLMConfig(gemini_api_key=None)
    with pytest.raises(GeminiConfigurationError) as exc_info:
        GeminiLLMProvider(config=config)

    assert "GEMINI_API_KEY environment variable or explicit api_key is required" in str(
        exc_info.value
    )


def test_provider_model_selection_and_routing() -> None:
    config = LLMConfig(
        gemini_api_key="AIzaSyDummyKey12345",
        gemini_model="gemini-2.5-flash",
        agent_models={"ARCHITECT": "gemini-1.5-pro", "PRAGMATIST": "gemini-1.5-flash"},
    )
    # Default model from config
    mock_client = MagicMock()
    provider_default = GeminiLLMProvider(config=config, client=mock_client)
    assert provider_default.model == "gemini-2.5-flash"

    # Explicit override
    provider_custom = GeminiLLMProvider(
        config=config, model="gemini-2.0-flash", client=mock_client
    )
    assert provider_custom.model == "gemini-2.0-flash"

    # Per-agent routing resolution
    assert config.get_model_for_agent("ARCHITECT") == "gemini-1.5-pro"
    assert config.get_model_for_agent("PRAGMATIST") == "gemini-1.5-flash"
    assert config.get_model_for_agent("AUDITOR_SRE") == "gemini-2.5-flash"


def test_provider_repr_does_not_leak_key() -> None:
    secret = "AIzaSyDummySecretKey123456"
    mock_client = MagicMock()
    provider = GeminiLLMProvider(
        api_key=secret, model="gemini-2.5-flash", timeout=30.0, client=mock_client
    )

    repr_str = repr(provider)
    assert secret not in repr_str
    assert "GeminiLLMProvider(model='gemini-2.5-flash', timeout=30.0)" == repr_str


# --- 3. Schema Cleaning & Compatibility Tests ---
def test_clean_schema_exclusive_bounds() -> None:
    raw_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "version": {"type": "integer", "exclusiveMinimum": 0},
            "ratio": {"type": "integer", "exclusiveMaximum": 100},
            "float_ratio": {"type": "number", "exclusiveMaximum": 99.5},
        },
    }

    cleaned = clean_schema_for_gemini(raw_schema)
    assert "$schema" not in cleaned
    assert "exclusiveMinimum" not in cleaned["properties"]["version"]
    assert cleaned["properties"]["version"]["minimum"] == 1
    assert "exclusiveMaximum" not in cleaned["properties"]["ratio"]
    assert cleaned["properties"]["ratio"]["maximum"] == 99
    assert "exclusiveMaximum" not in cleaned["properties"]["float_ratio"]
    assert cleaned["properties"]["float_ratio"]["maximum"] == 99.5


def test_clean_schema_architect_proposal_validates_with_genai_transformer() -> None:
    import google.genai._transformers as tr

    cleaned = clean_schema_for_gemini(ArchitectProposal.model_json_schema())
    sdk_schema = tr.t_schema(None, cleaned)
    assert sdk_schema is not None
    assert sdk_schema.type == "OBJECT"
    assert "title" in sdk_schema.properties


# --- 4. Generation & Structured Output Mapping Tests ---
def test_successful_generation_from_json_text() -> None:
    async def _test():
        proposal_dict = build_sample_architect_proposal_dict()
        json_text = json.dumps(proposal_dict)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=MockGenerateResponse(text=json_text)
        )

        provider = GeminiLLMProvider(
            api_key="AIzaSyDummyKey12345",
            model="gemini-2.5-flash",
            client=mock_client,
        )

        context = {"problem_statement": "Migrate database", "phase": "PHASE_1_DIVERGENCE"}
        result = await provider.generate(
            system_prompt="You are the Architect.",
            input_context=context,
            output_schema=ArchitectProposal,
        )

        assert isinstance(result, ArchitectProposal)
        assert result.title == "Decoupled Event-Driven Microservices"
        assert result.complexity == Severity.HIGH
        assert result.reversibility.score == ReversibilityLevel.LOW

        # Verify call parameters sent to generate_content
        mock_client.aio.models.generate_content.assert_awaited_once()
        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash"
        assert "Migrate database" in call_kwargs["contents"]
        assert call_kwargs["config"].system_instruction == "You are the Architect."
        assert call_kwargs["config"].response_mime_type == "application/json"

    import asyncio

    asyncio.run(_test())


def test_successful_generation_from_markdown_fenced_json() -> None:
    async def _test():
        proposal_dict = build_sample_architect_proposal_dict()
        fenced_text = f"```json\n{json.dumps(proposal_dict)}\n```"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=MockGenerateResponse(text=fenced_text)
        )

        provider = GeminiLLMProvider(api_key="AIzaSyDummyKey12345", client=mock_client)
        result = await provider.generate(
            system_prompt="Architect instructions",
            input_context={},
            output_schema=ArchitectProposal,
        )

        assert isinstance(result, ArchitectProposal)
        assert result.artifact_id == "PROP-ARCH-001"

    import asyncio

    asyncio.run(_test())


def test_successful_generation_from_parsed_attribute() -> None:
    async def _test():
        expected_artifact = SampleArtifact(title="Sample Item", score=8)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=MockGenerateResponse(parsed=expected_artifact)
        )

        provider = GeminiLLMProvider(api_key="AIzaSyDummyKey12345", client=mock_client)
        result = await provider.generate(
            system_prompt="System prompt",
            input_context={},
            output_schema=SampleArtifact,
        )

        assert isinstance(result, SampleArtifact)
        assert result.title == "Sample Item"
        assert result.score == 8

    import asyncio

    asyncio.run(_test())


# --- 5. Telemetry & Metadata Recording Tests ---
def test_telemetry_recording() -> None:
    async def _test():
        proposal_dict = build_sample_architect_proposal_dict()
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=MockGenerateResponse(
                text=json.dumps(proposal_dict),
                usage_metadata=MockUsageMetadata(
                    prompt_token_count=180,
                    candidates_token_count=240,
                    total_token_count=420,
                ),
            )
        )

        provider = GeminiLLMProvider(
            api_key="AIzaSyDummyKey12345", model="gemini-2.5-flash", client=mock_client
        )

        await provider.generate(
            system_prompt="System prompt",
            input_context={"key": "val"},
            output_schema=ArchitectProposal,
        )

        assert provider.last_metadata is not None
        assert provider.last_metadata.model == "gemini-2.5-flash"
        assert provider.last_metadata.latency_seconds > 0.0
        assert provider.last_metadata.input_tokens == 180
        assert provider.last_metadata.output_tokens == 240
        assert provider.last_metadata.total_tokens == 420
        assert len(provider.metadata_history) == 1

    import asyncio

    asyncio.run(_test())


# --- 6. Error Handling & Timeout Tests ---
def test_error_handling_sanitizes_secret() -> None:
    async def _test():
        secret_key = "AIzaSySuperSecretKeyToSanitize999"
        mock_client = MagicMock()
        # Simulate API exception containing secret in URL or error body
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception(
                f"HTTP 403 Forbidden: Request failed for url https://generativelanguage.googleapis.com/v1beta/models?key={secret_key}"
            )
        )

        provider = GeminiLLMProvider(api_key=secret_key, client=mock_client)

        with pytest.raises(GeminiAPIError) as exc_info:
            await provider.generate(
                system_prompt="System prompt",
                input_context={},
                output_schema=ArchitectProposal,
            )

        error_msg = str(exc_info.value)
        assert secret_key not in error_msg
        assert "[REDACTED" in error_msg

    import asyncio

    asyncio.run(_test())


def test_timeout_error_handling() -> None:
    async def _test():
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=httpx.TimeoutException("Connection timed out after 30000ms")
        )

        provider = GeminiLLMProvider(
            api_key="AIzaSyDummyKey12345", timeout=30.0, client=mock_client
        )

        with pytest.raises(GeminiTimeoutError) as exc_info:
            await provider.generate(
                system_prompt="System prompt",
                input_context={},
                output_schema=ArchitectProposal,
            )

        assert "timed out after 30.0s" in str(exc_info.value)

    import asyncio

    asyncio.run(_test())


# --- 7. Integration with AgentRunner & Retry Policy ---
def test_agent_runner_retry_integration_recovers_from_transient_error() -> None:
    async def _test():
        proposal_dict = build_sample_architect_proposal_dict()

        mock_client = MagicMock()
        # First attempt raises transient API error; second attempt succeeds
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[
                Exception("Transient 503 Service Unavailable"),
                MockGenerateResponse(text=json.dumps(proposal_dict)),
            ]
        )

        provider = GeminiLLMProvider(api_key="AIzaSyDummyKey12345", client=mock_client)
        runner = AgentRunner(llm_provider=provider, max_retries=3)
        agent = ArchitectAgent()

        input_context = {"problem_statement": "Scale backend", "phase": "PHASE_1_DIVERGENCE"}
        artifact = await runner.run(agent, input_context, output_schema=ArchitectProposal)

        assert isinstance(artifact, ArchitectProposal)
        assert mock_client.aio.models.generate_content.await_count == 2

    import asyncio

    asyncio.run(_test())


def test_agent_runner_exhausts_retries_and_raises() -> None:
    async def _test():
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("Persistent connection failure")
        )

        provider = GeminiLLMProvider(api_key="AIzaSyDummyKey12345", client=mock_client)
        runner = AgentRunner(llm_provider=provider, max_retries=2)
        agent = ArchitectAgent()

        with pytest.raises(AgentExecutionFailed) as exc_info:
            await runner.run(agent, {}, output_schema=ArchitectProposal)

        assert "failed after 2 attempts" in str(exc_info.value)
        assert mock_client.aio.models.generate_content.await_count == 2

    import asyncio

    asyncio.run(_test())
