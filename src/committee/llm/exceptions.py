"""Provider-agnostic error taxonomy for LLM integrations in AI Committee."""


class ProviderError(Exception):
    """Base exception for all LLM provider errors."""


class ProviderConfigurationError(ProviderError):
    """Raised when provider configuration or credentials are missing or invalid."""


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication fails (e.g. invalid API key, 401 Unauthorized, 403 Forbidden)."""


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limits or quotas are exceeded (429 Too Many Requests)."""


class ProviderTimeoutError(ProviderError):
    """Raised when an external LLM request times out."""


class ProviderTemporaryError(ProviderError):
    """Raised when a temporary/transient server error occurs (5xx, connection dropped)."""


class ProviderResponseError(ProviderError):
    """Raised when the provider returns an unparseable or malformed response."""


class ProviderSchemaError(ProviderError):
    """Raised when response fails schema validation or model refuses structured format."""
