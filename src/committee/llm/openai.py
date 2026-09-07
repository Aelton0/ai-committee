"""OpenAI LLM provider implementation using official openai SDK and Structured Outputs."""

import json
import time
from typing import Any, Literal

import httpx
import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from src.committee.llm.config import LLMConfig, sanitize_secrets_from_text
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
from src.committee.llm.provider import LLMCallMetadata, LLMProvider


class OpenAILLMProvider:
    """OpenAI LLM provider generating structured Pydantic artifacts via Responses API or Chat Completions."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        base_url: str | None = None,
        client: Any | None = None,
        api_mode: Literal["auto", "responses", "chat_completions"] = "auto",
    ) -> None:
        self.config = config or LLMConfig.from_env()
        resolved_key = api_key or self.config.openai_api_key
        self._api_key = resolved_key.strip() if resolved_key and resolved_key.strip() else None
        self.model = model or self.config.openai_model
        self.timeout = timeout if timeout is not None else self.config.openai_timeout_seconds
        self.base_url = base_url or self.config.openai_base_url
        self.api_mode = api_mode

        self.last_metadata: LLMCallMetadata | None = None
        self.metadata_history: list[LLMCallMetadata] = []

        if client is not None:
            self._client = client
        else:
            if not self._api_key:
                raise ProviderConfigurationError(
                    "OPENAI_API_KEY environment variable or explicit api_key is required for OpenAILLMProvider."
                )
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )

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
        """Generate a validated Pydantic model instance from OpenAI structured outputs.

        Prioritizes the Responses API (client.responses.parse) and falls back
        gracefully to Chat Completions (client.chat.completions.parse) when appropriate.
        Does not perform retries internally; propagates mapped ProviderError exceptions
        for AgentRunner to manage.
        """
        start_time = time.perf_counter()

        context_json = json.dumps(input_context, indent=2, ensure_ascii=False)
        user_content = (
            "Deliberation Context:\n"
            f"{context_json}\n\n"
            "Instructions:\n"
            "Analyze the deliberation context strictly according to your specialized role "
            "and instructions, and produce the requested artifact conforming to the output schema."
        )

        parsed_model: BaseModel | None = None
        request_id: str | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None
        total_tokens: int | None = None

        try:
            # Determine API path: Responses API vs Chat Completions
            can_use_responses = (
                self.api_mode in ("auto", "responses")
                and hasattr(self._client, "responses")
                and callable(getattr(self._client.responses, "parse", None))
            )

            used_responses_api = False
            if can_use_responses:
                try:
                    response = await self._client.responses.parse(
                        model=self.model,
                        instructions=system_prompt,
                        input=user_content,
                        text_format=output_schema,
                        timeout=self.timeout,
                    )
                    used_responses_api = True

                    request_id = getattr(response, "id", None)
                    if hasattr(response, "usage") and response.usage is not None:
                        input_tokens = getattr(response.usage, "input_tokens", None)
                        output_tokens = getattr(response.usage, "output_tokens", None)
                        total_tokens = getattr(response.usage, "total_tokens", None)

                    if hasattr(response, "output_parsed") and isinstance(
                        response.output_parsed, output_schema
                    ):
                        parsed_model = response.output_parsed
                    elif hasattr(response, "output_text") and response.output_text:
                        parsed_model = output_schema.model_validate_json(response.output_text)
                    else:
                        raise ProviderResponseError(
                            "OpenAI responses API returned empty or unparseable output."
                        )
                except openai.NotFoundError:
                    if self.api_mode == "responses":
                        raise
                    # Fallback to Chat Completions if Responses endpoint is unavailable
                    used_responses_api = False

            if not used_responses_api:
                # Chat Completions structured output path
                response = await self._client.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    response_format=output_schema,
                    timeout=self.timeout,
                )

                request_id = getattr(response, "id", None)
                if hasattr(response, "usage") and response.usage is not None:
                    input_tokens = getattr(response.usage, "prompt_tokens", None)
                    output_tokens = getattr(response.usage, "completion_tokens", None)
                    total_tokens = getattr(response.usage, "total_tokens", None)

                choices = getattr(response, "choices", [])
                if not choices:
                    raise ProviderResponseError("OpenAI completion returned empty choices.")

                choice = choices[0]
                message = getattr(choice, "message", None)
                if not message:
                    raise ProviderResponseError("OpenAI choice missing message.")

                refusal = getattr(message, "refusal", None)
                if refusal:
                    raise ProviderSchemaError(
                        f"Model refused to generate structured response: {refusal}"
                    )

                if hasattr(message, "parsed") and isinstance(message.parsed, output_schema):
                    parsed_model = message.parsed
                elif hasattr(message, "content") and message.content:
                    parsed_model = output_schema.model_validate_json(message.content)
                else:
                    raise ProviderResponseError(
                        "OpenAI completion message contained neither parsed schema nor content."
                    )

        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise ProviderAuthenticationError(
                f"OpenAI authentication failed: {self._sanitize(str(exc))}"
            ) from None
        except openai.RateLimitError as exc:
            raise ProviderRateLimitError(
                f"OpenAI rate limit exceeded: {self._sanitize(str(exc))}"
            ) from None
        except (openai.APITimeoutError, TimeoutError, httpx.TimeoutException) as exc:
            raise ProviderTimeoutError(
                f"OpenAI request timed out after {self.timeout}s: {self._sanitize(str(exc))}"
            ) from None
        except (openai.InternalServerError, openai.APIConnectionError, httpx.NetworkError) as exc:
            raise ProviderTemporaryError(
                f"OpenAI temporary connection error: {self._sanitize(str(exc))}"
            ) from None
        except (openai.LengthFinishReasonError, openai.ContentFilterFinishReasonError) as exc:
            raise ProviderSchemaError(
                f"OpenAI generation aborted: {self._sanitize(str(exc))}"
            ) from None
        except openai.BadRequestError as exc:
            raise ProviderSchemaError(
                f"OpenAI bad request: {self._sanitize(str(exc))}"
            ) from None
        except openai.APIStatusError as exc:
            sanitized = self._sanitize(str(exc))
            if exc.status_code in (401, 403):
                raise ProviderAuthenticationError(
                    f"OpenAI auth error ({exc.status_code}): {sanitized}"
                ) from None
            if exc.status_code == 429:
                raise ProviderRateLimitError(
                    f"OpenAI rate limit ({exc.status_code}): {sanitized}"
                ) from None
            if exc.status_code == 408:
                raise ProviderTimeoutError(
                    f"OpenAI timeout ({exc.status_code}): {sanitized}"
                ) from None
            if exc.status_code >= 500:
                raise ProviderTemporaryError(
                    f"OpenAI server error ({exc.status_code}): {sanitized}"
                ) from None
            raise ProviderResponseError(
                f"OpenAI API status error ({exc.status_code}): {sanitized}"
            ) from None
        except ValidationError as exc:
            raise ProviderSchemaError(
                f"Schema validation failed: {self._sanitize(str(exc))}"
            ) from None
        except (ProviderError,):
            raise
        except openai.OpenAIError as exc:
            raise ProviderError(
                f"OpenAI error: {self._sanitize(str(exc))}"
            ) from None
        except Exception as exc:
            exc_str = str(exc).lower()
            sanitized = self._sanitize(str(exc))
            if "timeout" in exc_str or "timed out" in exc_str:
                raise ProviderTimeoutError(
                    f"OpenAI request timed out: {sanitized}"
                ) from None
            raise ProviderResponseError(
                f"OpenAI generation failed: {sanitized}"
            ) from None

        if parsed_model is None:
            raise ProviderResponseError("OpenAI returned no parsed model output.")

        latency = time.perf_counter() - start_time

        self.last_metadata = LLMCallMetadata(
            model=self.model,
            latency_seconds=round(latency, 4),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            request_id=request_id,
        )
        self.metadata_history.append(self.last_metadata)

        return parsed_model

    def __repr__(self) -> str:
        return f"OpenAILLMProvider(model={self.model!r}, timeout={self.timeout})"

    def __str__(self) -> str:
        return self.__repr__()
