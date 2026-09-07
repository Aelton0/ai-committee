"""Comprehensive unit tests for OpenAILLMProvider, LLMConfig OpenAI settings, and factory."""

import asyncio
from dataclasses import dataclass
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest
from pydantic import BaseModel, Field

from src.committee.llm.config import (
    LLMConfig,
    mask_secret,
    sanitize_secrets_from_text,
)
from src.committee.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderSchemaError,
    ProviderTemporaryError,
    ProviderTimeoutError,
)
from src.committee.llm.factory import create_llm_provider
from src.committee.llm.mock import MockLLMProvider
from src.committee.llm.openai import OpenAILLMProvider


# --- Dummy Test Schema ---
class SampleArtifact(BaseModel):
    title: str = Field(..., min_length=1)
    score: int = Field(..., ge=1, le=10)


@dataclass
class DummyResponsesUsage:
    input_tokens: int = 120
    output_tokens: int = 80
    total_tokens: int = 200


@dataclass
class DummyChatUsage:
    prompt_tokens: int = 110
    completion_tokens: int = 70
    total_tokens: int = 180


class DummyParsedResponse:
    def __init__(
        self,
        output_parsed: Any = None,
        output_text: str | None = None,
        usage: Any = None,
        request_id: str = "resp-12345",
    ) -> None:
        self.id = request_id
        self.output_parsed = output_parsed
        self.output_text = output_text
        self.usage = usage or DummyResponsesUsage()


class DummyChatMessage:
    def __init__(
        self,
        parsed: Any = None,
        content: str | None = None,
        refusal: str | None = None,
    ) -> None:
        self.parsed = parsed
        self.content = content
        self.refusal = refusal


class DummyChatChoice:
    def __init__(self, message: DummyChatMessage) -> None:
        self.message = message


class DummyChatCompletion:
    def __init__(
        self,
        choices: list[DummyChatChoice],
        usage: Any = None,
        request_id: str = "chatcmpl-99999",
    ) -> None:
        self.id = request_id
        self.choices = choices
        self.usage = usage or DummyChatUsage()


# --- Configuration Tests ---
def test_openai_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    config = LLMConfig.from_env()
    assert config.openai_api_key is None
    assert config.openai_model == "gpt-4o"
    assert config.openai_timeout_seconds == 60.0


def test_openai_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-abc1234567890abcdef123456")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "30.5")

    config = LLMConfig.from_env()
    assert config.provider == "openai"
    assert config.openai_api_key == "sk-proj-abc1234567890abcdef123456"
    assert config.openai_model == "gpt-4o-mini"
    assert config.openai_timeout_seconds == 30.5
    assert config.get_model_for_agent() == "gpt-4o-mini"


def test_openai_config_llm_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "o3-mini")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    config = LLMConfig.from_env()
    assert config.openai_model == "o3-mini"


def test_openai_config_repr_does_not_leak_key() -> None:
    secret = "sk-proj-SuperSecretKey123456789012345"
    config = LLMConfig(openai_api_key=secret)

    repr_str = repr(config)
    str_str = str(config)

    assert secret not in repr_str
    assert secret not in str_str
    assert "sk-p...2345" in repr_str


def test_openai_sanitize_secrets_helper() -> None:
    secret_key = "sk-proj-mysecretkey1234567890abcdef"
    text = f"Failed call with key {secret_key} and Bearer {secret_key}"
    sanitized = sanitize_secrets_from_text(text, secret_key)

    assert secret_key not in sanitized
    assert "[REDACTED]" in sanitized or "[REDACTED_API_KEY]" in sanitized


# --- Provider Unit Tests ---
def test_openai_provider_missing_key_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = LLMConfig(openai_api_key=None)

    with pytest.raises(ProviderConfigurationError) as exc_info:
        OpenAILLMProvider(config=config)

    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_openai_provider_generate_via_responses_api_parsed() -> None:
    expected_artifact = SampleArtifact(title="Architecture Design", score=9)
    dummy_resp = DummyParsedResponse(
        output_parsed=expected_artifact,
        request_id="resp-test-1",
        usage=DummyResponsesUsage(input_tokens=150, output_tokens=75, total_tokens=225),
    )

    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    mock_client.responses.parse = AsyncMock(return_value=dummy_resp)

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        res = await provider.generate(
            system_prompt="You are an architect.",
            input_context={"problem": "scale"},
            output_schema=SampleArtifact,
        )

        assert res == expected_artifact
        assert provider.last_metadata is not None
        assert provider.last_metadata.model == "gpt-4o"
        assert provider.last_metadata.request_id == "resp-test-1"
        assert provider.last_metadata.input_tokens == 150
        assert provider.last_metadata.output_tokens == 75
        assert provider.last_metadata.total_tokens == 225
        assert provider.last_metadata.latency_seconds >= 0.0

    asyncio.run(_test())


def test_openai_provider_generate_via_responses_api_output_text() -> None:
    raw_json = json.dumps({"title": "Parsed from JSON text", "score": 8})
    dummy_resp = DummyParsedResponse(
        output_parsed=None,
        output_text=raw_json,
        request_id="resp-text-2",
    )

    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    mock_client.responses.parse = AsyncMock(return_value=dummy_resp)

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        res = await provider.generate(
            system_prompt="You are an architect.",
            input_context={"problem": "scale"},
            output_schema=SampleArtifact,
        )

        assert isinstance(res, SampleArtifact)
        assert res.title == "Parsed from JSON text"
        assert res.score == 8
        assert provider.last_metadata.request_id == "resp-text-2"

    asyncio.run(_test())


def test_openai_provider_generate_via_chat_completions_fallback_on_404() -> None:
    expected_artifact = SampleArtifact(title="Fallback Completion", score=7)
    dummy_chat = DummyChatCompletion(
        choices=[DummyChatChoice(message=DummyChatMessage(parsed=expected_artifact))],
        request_id="chatcmpl-fallback-3",
        usage=DummyChatUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )

    mock_client = MagicMock()
    # responses.parse raises NotFoundError (endpoint unavailable)
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(404, request=req)
    mock_client.responses = MagicMock()
    mock_client.responses.parse = AsyncMock(
        side_effect=openai.NotFoundError("The requested endpoint does not exist.", response=resp, body=None)
    )

    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.parse = AsyncMock(return_value=dummy_chat)

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        res = await provider.generate(
            system_prompt="You are a pragmatist.",
            input_context={"problem": "simplicity"},
            output_schema=SampleArtifact,
        )

        assert res == expected_artifact
        assert provider.last_metadata.request_id == "chatcmpl-fallback-3"
        assert provider.last_metadata.input_tokens == 100
        assert provider.last_metadata.output_tokens == 50
        assert provider.last_metadata.total_tokens == 150

    asyncio.run(_test())


def test_openai_provider_refusal_raises_schema_error() -> None:
    dummy_chat = DummyChatCompletion(
        choices=[
            DummyChatChoice(
                message=DummyChatMessage(
                    parsed=None,
                    refusal="I cannot fulfill this request due to safety policies.",
                )
            )
        ]
    )

    mock_client = MagicMock()
    mock_client.responses = None  # Force chat completions path
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.parse = AsyncMock(return_value=dummy_chat)

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
        api_mode="chat_completions",
    )

    async def _test() -> None:
        with pytest.raises(ProviderSchemaError) as exc_info:
            await provider.generate(
                system_prompt="Prompt",
                input_context={},
                output_schema=SampleArtifact,
            )
        assert "refused" in str(exc_info.value).lower()

    asyncio.run(_test())


def test_openai_provider_auth_error_mapping() -> None:
    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(401, request=req)
    mock_client.responses.parse = AsyncMock(
        side_effect=openai.AuthenticationError(
            "Incorrect API key sk-proj-dummytestkey1234567890 provided",
            response=resp,
            body=None,
        )
    )

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        with pytest.raises(ProviderAuthenticationError) as exc_info:
            await provider.generate(
                system_prompt="Prompt",
                input_context={},
                output_schema=SampleArtifact,
            )
        # Verify secret key was redacted
        assert "sk-proj-dummytestkey1234567890" not in str(exc_info.value)
        assert "[REDACTED" in str(exc_info.value)

    asyncio.run(_test())


def test_openai_provider_rate_limit_mapping() -> None:
    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(429, request=req)
    mock_client.responses.parse = AsyncMock(
        side_effect=openai.RateLimitError("Rate limit exceeded", response=resp, body=None)
    )

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        with pytest.raises(ProviderRateLimitError):
            await provider.generate(
                system_prompt="Prompt",
                input_context={},
                output_schema=SampleArtifact,
            )

    asyncio.run(_test())


def test_openai_provider_timeout_mapping() -> None:
    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    mock_client.responses.parse = AsyncMock(
        side_effect=openai.APITimeoutError(req)
    )

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        with pytest.raises(ProviderTimeoutError):
            await provider.generate(
                system_prompt="Prompt",
                input_context={},
                output_schema=SampleArtifact,
            )

    asyncio.run(_test())


def test_openai_provider_temporary_error_mapping() -> None:
    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(503, request=req)
    mock_client.responses.parse = AsyncMock(
        side_effect=openai.InternalServerError("Server overloaded", response=resp, body=None)
    )

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        with pytest.raises(ProviderTemporaryError):
            await provider.generate(
                system_prompt="Prompt",
                input_context={},
                output_schema=SampleArtifact,
            )

    asyncio.run(_test())


def test_openai_provider_bad_request_mapping() -> None:
    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(400, request=req)
    mock_client.responses.parse = AsyncMock(
        side_effect=openai.BadRequestError("Invalid schema definition", response=resp, body=None)
    )

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        with pytest.raises(ProviderSchemaError):
            await provider.generate(
                system_prompt="Prompt",
                input_context={},
                output_schema=SampleArtifact,
            )

    asyncio.run(_test())


def test_openai_provider_invalid_json_text_raises_schema_error() -> None:
    dummy_resp = DummyParsedResponse(
        output_parsed=None,
        output_text="not-json-content",
        request_id="resp-bad-1",
    )

    mock_client = MagicMock()
    mock_client.responses = MagicMock()
    mock_client.responses.parse = AsyncMock(return_value=dummy_resp)

    provider = OpenAILLMProvider(
        api_key="sk-proj-dummytestkey1234567890",
        client=mock_client,
    )

    async def _test() -> None:
        with pytest.raises(ProviderSchemaError):
            await provider.generate(
                system_prompt="Prompt",
                input_context={},
                output_schema=SampleArtifact,
            )

    asyncio.run(_test())


# --- Factory Tests ---
def test_create_llm_provider_factory() -> None:
    # 1. Mock provider
    p_mock = create_llm_provider("mock")
    assert isinstance(p_mock, MockLLMProvider)

    # 2. Gemini provider
    p_gemini = create_llm_provider(
        "gemini",
        api_key="AIzaSyTestKey123456789012345678901234",
    )
    assert p_gemini.__class__.__name__ == "GeminiLLMProvider"

    # 3. OpenAI provider
    p_openai = create_llm_provider(
        "openai",
        api_key="sk-proj-testkey123456789012345678901234",
    )
    assert isinstance(p_openai, OpenAILLMProvider)

    # 4. Unknown provider
    with pytest.raises(ProviderConfigurationError) as exc_info:
        create_llm_provider("anthropic_unknown")
    assert "Unknown or unsupported" in str(exc_info.value)
