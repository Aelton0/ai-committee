"""Facilitator Agent orchestrating deliberation methodology and objective synthesis."""

from typing import Any

from pydantic import BaseModel
from schemas.common import CommitteeRole
from schemas.context import ProblemContext
from schemas.synthesis import DeliberationSynthesis
from src.committee.agents.base import BaseAgent, ContextIsolationError


class FacilitatorAgent(BaseAgent):
    """Facilitator Agent driving protocol execution and structured debate synthesis."""

    @property
    def role(self) -> CommitteeRole:
        return CommitteeRole.FACILITATOR

    @property
    def prompt_filename(self) -> str:
        return "facilitator.md"

    @property
    def output_schema(self) -> type[BaseModel]:
        return DeliberationSynthesis

    def get_output_schema(self, context: dict[str, Any] | None = None) -> type[BaseModel]:
        if context:
            phase = context.get("phase")
            if phase in ("PHASE_0_INVESTIGATION", "INVESTIGATION"):
                return ProblemContext
        return DeliberationSynthesis

    def validate_input_context(self, context: dict[str, Any]) -> None:
        # Facilitator MUST NOT decide or receive decision record
        if "decision_record" in context and context["decision_record"] is not None:
            raise ContextIsolationError(
                "Facilitator isolation violated: Facilitator received DecisionRecord."
            )
