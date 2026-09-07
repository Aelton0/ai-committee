"""Factory for instantiating LLM providers based on configuration."""

from typing import Any

from src.committee.llm.config import LLMConfig
from src.committee.llm.exceptions import ProviderConfigurationError
from src.committee.llm.gemini import GeminiLLMProvider
from src.committee.llm.mock import MockLLMProvider
from src.committee.llm.openai import OpenAILLMProvider
from src.committee.llm.provider import LLMProvider


def create_llm_provider(
    provider_name: str | None = None,
    config: LLMConfig | None = None,
    **kwargs: Any,
) -> LLMProvider:
    """Instantiate and return the configured LLMProvider.

    Supported providers:
    - 'mock': MockLLMProvider for offline deterministic tests.
    - 'gemini': GeminiLLMProvider using Google GenAI SDK.
    - 'openai': OpenAILLMProvider using OpenAI SDK with Structured Outputs.
    """
    resolved_config = config or LLMConfig.from_env()
    resolved_name = (provider_name or resolved_config.provider).strip().lower()

    if resolved_name == "mock":
        return MockLLMProvider(**kwargs)
    elif resolved_name == "gemini":
        return GeminiLLMProvider(config=resolved_config, **kwargs)
    elif resolved_name == "openai":
        return OpenAILLMProvider(config=resolved_config, **kwargs)
    else:
        raise ProviderConfigurationError(
            f"Unknown or unsupported LLM provider: {resolved_name!r}. "
            "Supported providers are 'mock', 'gemini', 'openai'."
        )
