"""Configuration management for LLM providers with defense-in-depth secret handling."""

from dataclasses import dataclass, field
import os
import re
from typing import Optional


def mask_secret(secret: str | None) -> str:
    """Safely mask a secret for logging, string representation, or diagnostics."""
    if not secret:
        return "None"
    stripped = secret.strip()
    if len(stripped) <= 8:
        return "***"
    return f"{stripped[:4]}...{stripped[-4:]}"


def sanitize_secrets_from_text(text: str, *secrets: str | None) -> str:
    """Sanitize all known secrets and typical API key patterns from a text string."""
    sanitized = text

    # Explicit secret strings
    for s in secrets:
        if s and len(s.strip()) > 3:
            sanitized = sanitized.replace(s.strip(), "[REDACTED]")

    # Google API Key pattern (AIza...)
    sanitized = re.sub(r"AIza[0-9A-Za-z\-_]{35}", "[REDACTED_API_KEY]", sanitized)

    # URL query parameter pattern (?key=... or &key=... or &api_key=...)
    sanitized = re.sub(
        r"([?&](?:api_)?key=)[^&\s]+",
        r"\1[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Header patterns (x-goog-api-key: ... or authorization: bearer ...)
    sanitized = re.sub(
        r"(x-goog-api-key[\"']?\s*[:=]\s*[\"']?)[^\"'\s]+",
        r"\1[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )

    return sanitized


@dataclass
class LLMConfig:
    """Configuration for LLM provider execution."""

    provider: str = "gemini"
    gemini_api_key: Optional[str] = field(default=None, repr=False)
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 60.0
    agent_models: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables without hardcoding secrets."""
        api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        timeout_str = os.getenv("GEMINI_TIMEOUT_SECONDS", "60.0").strip()

        try:
            timeout = float(timeout_str)
        except ValueError:
            timeout = 60.0

        return cls(
            provider=provider,
            gemini_api_key=api_key.strip() if api_key and api_key.strip() else None,
            gemini_model=model,
            gemini_timeout_seconds=timeout,
        )

    def get_model_for_agent(self, agent_role: str | None = None) -> str:
        """Resolve the model name for a specific agent role, supporting future routing."""
        if agent_role and agent_role in self.agent_models:
            return self.agent_models[agent_role]
        return self.gemini_model

    def __repr__(self) -> str:
        masked_key = mask_secret(self.gemini_api_key)
        return (
            f"LLMConfig(provider={self.provider!r}, gemini_api_key={masked_key!r}, "
            f"gemini_model={self.gemini_model!r}, gemini_timeout_seconds={self.gemini_timeout_seconds})"
        )

    def __str__(self) -> str:
        return self.__repr__()
