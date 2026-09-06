"""Base agent class defining role, prompt loading, context validation, and output schema."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from schemas.common import CommitteeRole


class ContextIsolationError(ValueError):
    """Raised when an agent receives forbidden context violating isolation boundaries."""


class BaseAgent(ABC):
    """Abstract base class for all AI Committee specialized agents."""

    def __init__(self, prompt_override: str | None = None) -> None:
        self._prompt_override = prompt_override

    @property
    @abstractmethod
    def role(self) -> CommitteeRole:
        """The formal role of the agent."""
        ...

    @property
    @abstractmethod
    def prompt_filename(self) -> str:
        """Name of the markdown file containing the prompt (e.g. 'architect.md')."""
        ...

    @property
    @abstractmethod
    def output_schema(self) -> type[BaseModel]:
        """Default output schema produced by this agent."""
        ...

    @property
    def system_prompt(self) -> str:
        """Load and return the system prompt from the markdown file or override."""
        if self._prompt_override:
            return self._prompt_override

        prompt_path = Path(__file__).resolve().parents[3] / "agents" / self.prompt_filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found at {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def get_output_schema(self, context: dict[str, Any] | None = None) -> type[BaseModel]:
        """Return expected output schema based on context, defaulting to self.output_schema."""
        return self.output_schema

    @abstractmethod
    def validate_input_context(self, context: dict[str, Any]) -> None:
        """Validate that required context is present and forbidden keys are absent."""
        ...
