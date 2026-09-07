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

    def _validate_context_policy(
        self,
        context: dict[str, Any],
        allowed_phases: set[str],
        required_keys_by_phase: dict[str, list[str | tuple[str, ...]]],
        forbidden_keys: list[tuple[str, str]],
    ) -> None:
        """Centralized fail-closed context validation policy for committee agents."""
        # 1. Negative firewall: check forbidden keys first so specific isolation violation is reported
        for key, error_msg in forbidden_keys:
            if key in context and context[key] is not None:
                raise ContextIsolationError(error_msg)

        # 2. Reject empty context
        if not context:
            raise ContextIsolationError(
                f"{self.role.value} received empty input context."
            )

        # 3. Reject context without phase
        phase = context.get("phase")
        if not phase or not isinstance(phase, str) or not phase.strip():
            raise ContextIsolationError(
                f"{self.role.value} context missing mandatory 'phase' key."
            )

        # 4. Check if phase is valid for this agent
        if phase not in allowed_phases:
            raise ContextIsolationError(
                f"Phase '{phase}' is invalid for {self.role.value}."
            )

        # 5. Positive validation: check required keys for this phase
        required_specs = required_keys_by_phase.get(phase, [])
        for spec in required_specs:
            if isinstance(spec, (tuple, list, set)):
                if not any(k in context and context[k] is not None for k in spec):
                    raise ContextIsolationError(
                        f"{self.role.value} requires at least one of {spec} in phase '{phase}'."
                    )
            else:
                if spec not in context or context[spec] is None:
                    raise ContextIsolationError(
                        f"{self.role.value} requires '{spec}' in phase '{phase}'."
                    )

    @abstractmethod
    def validate_input_context(self, context: dict[str, Any]) -> None:
        """Validate that required context is present and forbidden keys are absent."""
        ...
