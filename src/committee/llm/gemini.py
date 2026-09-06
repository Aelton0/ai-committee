"""Google Gemini LLM provider implementation using official google-genai SDK."""

import json
import time
from typing import Any

from google import genai
from google.genai import types
import httpx
from pydantic import BaseModel, ValidationError

from src.committee.llm.config import LLMConfig, sanitize_secrets_from_text
from src.committee.llm.provider import LLMCallMetadata, LLMProvider


class GeminiError(Exception):
    """Base exception for all Gemini integration errors."""


class GeminiConfigurationError(GeminiError):
    """Raised when configuration or credentials for Gemini are missing or invalid."""


class GeminiTimeoutError(GeminiError):
    """Raised when a request to Gemini times out."""


class GeminiAPIError(GeminiError):
    """Raised when the Gemini API returns an error or unparseable response."""


def clean_schema_for_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Clean and adapt a Pydantic v2 JSON schema for compatibility with Google GenAI / OpenAPI.

    - Replaces OpenAPI 3.1 `exclusiveMinimum: N` with `minimum: N + 1` (integers) or `minimum: N`.
    - Replaces OpenAPI 3.1 `exclusiveMaximum: N` with `maximum: N - 1` (integers) or `maximum: N`.
    - Strips unsupported schema metadata properties like '$schema'.
    """
    if isinstance(schema, dict):
        cleaned: dict[str, Any] = {}
        for k, v in schema.items():
            if k == "$schema":
                continue
            elif k == "exclusiveMinimum":
                if isinstance(v, int):
                    cleaned["minimum"] = v + 1
                else:
                    cleaned["minimum"] = v
            elif k == "exclusiveMaximum":
                if isinstance(v, int):
                    cleaned["maximum"] = v - 1
                else:
                    cleaned["maximum"] = v
            else:
                cleaned[k] = clean_schema_for_gemini(v)
        return cleaned
    elif isinstance(schema, list):
        return [clean_schema_for_gemini(item) for item in schema]
    return schema


class GeminiLLMProvider:
    """Google Gemini LLM provider generating structured Pydantic artifacts."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: Any | None = None,
    ) -> None:
        self.config = config or LLMConfig.from_env()
        resolved_key = (
            api_key
            or self.config.gemini_api_key
        )
        self._api_key = resolved_key.strip() if resolved_key and resolved_key.strip() else None
        self.model = model or self.config.gemini_model
        self.timeout = timeout if timeout is not None else self.config.gemini_timeout_seconds

        self.last_metadata: LLMCallMetadata | None = None
        self.metadata_history: list[LLMCallMetadata] = []

        if client is not None:
            self._client = client
        else:
            if not self._api_key:
                raise GeminiConfigurationError(
                    "GEMINI_API_KEY environment variable or explicit api_key is required for GeminiLLMProvider."
                )
            # Timeout in HttpOptions is represented in milliseconds
            http_options = types.HttpOptions(timeout=int(self.timeout * 1000))
            self._client = genai.Client(api_key=self._api_key, http_options=http_options)

    def _sanitize(self, text: str) -> str:
        """Sanitize error messages and URLs to prevent secret leakage."""
        return sanitize_secrets_from_text(text, self._api_key)

    async def generate(
        self,
        *,
        system_prompt: str,
        input_context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Generate a validated Pydantic model instance from Gemini structured output.

        Does not perform retries internally; propagates exceptions for AgentRunner retry policy.
        """
        start_time = time.perf_counter()

        # Format input context as structured JSON prompt
        context_json = json.dumps(input_context, indent=2, ensure_ascii=False)
        user_content = (
            "Deliberation Context:\n"
            f"{context_json}\n\n"
            "Instructions:\n"
            "Analyze the deliberation context strictly according to your specialized role "
            "and instructions, and produce the requested artifact conforming to the output schema."
        )

        # Prepare schema with OpenAPI/GenAI compatibility adaptations
        cleaned_schema = clean_schema_for_gemini(output_schema.model_json_schema())

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=cleaned_schema,
            http_options=types.HttpOptions(timeout=int(self.timeout * 1000)),
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=user_content,
                config=config,
            )
        except (TimeoutError, httpx.TimeoutException) as exc:
            sanitized = self._sanitize(str(exc))
            raise GeminiTimeoutError(
                f"Gemini API request timed out after {self.timeout}s: {sanitized}"
            ) from None
        except Exception as exc:
            exc_str = str(exc).lower()
            sanitized = self._sanitize(str(exc))
            if "timeout" in exc_str or "timed out" in exc_str:
                raise GeminiTimeoutError(
                    f"Gemini API request timed out: {sanitized}"
                ) from None
            raise GeminiAPIError(f"Gemini API generation failed: {sanitized}") from None

        latency = time.perf_counter() - start_time

        # Extract telemetry
        input_tokens = None
        output_tokens = None
        total_tokens = None
        if hasattr(response, "usage_metadata") and response.usage_metadata is not None:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", None)
            total_tokens = getattr(response.usage_metadata, "total_token_count", None)

        self.last_metadata = LLMCallMetadata(
            model=self.model,
            latency_seconds=round(latency, 4),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        self.metadata_history.append(self.last_metadata)

        # Parse and validate output
        return self._parse_and_validate(response, output_schema)

    def _parse_and_validate(
        self, response: Any, output_schema: type[BaseModel]
    ) -> BaseModel:
        """Parse the Gemini structured response into the target Pydantic model."""
        # 1. SDK already parsed into requested Pydantic model
        if hasattr(response, "parsed") and isinstance(response.parsed, output_schema):
            return response.parsed

        # 2. Parse from response.text (JSON string)
        raw_text = getattr(response, "text", None)
        if raw_text:
            text = raw_text.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            return output_schema.model_validate_json(text)

        # 3. Parse from response.parsed dictionary
        if hasattr(response, "parsed") and isinstance(response.parsed, dict):
            return output_schema.model_validate(response.parsed)

        raise GeminiAPIError("Gemini response contained neither text nor parsed model.")

    def __repr__(self) -> str:
        return f"GeminiLLMProvider(model={self.model!r}, timeout={self.timeout})"

    def __str__(self) -> str:
        return self.__repr__()
