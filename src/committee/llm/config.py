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

    # OpenAI API Key pattern (sk-...)
    sanitized = re.sub(r"sk-[0-9A-Za-z\-_]{20,}", "[REDACTED_API_KEY]", sanitized)

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
    sanitized = re.sub(
        r"(bearer\s+)[a-zA-Z0-9\-_.]{20,}",
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
    gemini_model: str = "gemini-flash-latest"
    gemini_timeout_seconds: float = 60.0
    openai_api_key: Optional[str] = field(default=None, repr=False)
    openai_model: str = "gpt-4o"
    openai_timeout_seconds: float = 60.0
    openai_base_url: Optional[str] = None
    agent_models: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables without hardcoding secrets."""
        gemini_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        openai_key = os.getenv("OPENAI_API_KEY")
        provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
        llm_model = os.getenv("LLM_MODEL")
        if llm_model:
            llm_model = llm_model.strip()

        gemini_model = (
            (llm_model if provider == "gemini" and llm_model else None)
            or os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
        )
        openai_model = (
            (llm_model if provider == "openai" and llm_model else None)
            or os.getenv("OPENAI_MODEL", "gpt-4o").strip()
        )

        gemini_timeout_str = os.getenv("GEMINI_TIMEOUT_SECONDS", "60.0").strip()
        try:
            gemini_timeout = float(gemini_timeout_str)
        except ValueError:
            gemini_timeout = 60.0

        openai_timeout_str = os.getenv("OPENAI_TIMEOUT_SECONDS", "60.0").strip()
        try:
            openai_timeout = float(openai_timeout_str)
        except ValueError:
            openai_timeout = 60.0

        openai_base_url = os.getenv("OPENAI_BASE_URL")
        if openai_base_url:
            openai_base_url = openai_base_url.strip()

        return cls(
            provider=provider,
            gemini_api_key=gemini_key.strip() if gemini_key and gemini_key.strip() else None,
            gemini_model=gemini_model,
            gemini_timeout_seconds=gemini_timeout,
            openai_api_key=openai_key.strip() if openai_key and openai_key.strip() else None,
            openai_model=openai_model,
            openai_timeout_seconds=openai_timeout,
            openai_base_url=openai_base_url or None,
        )

    def get_model_for_agent(self, agent_role: str | None = None) -> str:
        """Resolve the model name for a specific agent role, supporting future routing."""
        if agent_role and agent_role in self.agent_models:
            return self.agent_models[agent_role]
        if self.provider == "openai":
            return self.openai_model
        return self.gemini_model

    def __repr__(self) -> str:
        masked_gemini = mask_secret(self.gemini_api_key)
        masked_openai = mask_secret(self.openai_api_key)
        return (
            f"LLMConfig(provider={self.provider!r}, gemini_api_key={masked_gemini!r}, "
            f"gemini_model={self.gemini_model!r}, gemini_timeout_seconds={self.gemini_timeout_seconds}, "
            f"openai_api_key={masked_openai!r}, openai_model={self.openai_model!r}, "
            f"openai_timeout_seconds={self.openai_timeout_seconds})"
        )

    def __str__(self) -> str:
        return self.__repr__()
