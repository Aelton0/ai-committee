"""Facilitator Agent orchestrating deliberation methodology and objective synthesis."""

from typing import Any

from pydantic import BaseModel
from schemas.common import CommitteeRole
from schemas.context import ContextDelta, ProblemContext
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
                if context.get("action") == "INTERPRET_RESPONSE" or "answered_questions" in context:
                    return ContextDelta
                return ProblemContext
        return DeliberationSynthesis

    def validate_input_context(self, context: dict[str, Any]) -> None:
        forbidden = [
            ("decision_record", "Facilitator isolation violated: Facilitator received DecisionRecord."),
        ]
        allowed_phases = {
            "PHASE_0_INVESTIGATION", "INVESTIGATION", "DRAFT",
            "PHASE_4_CONVERGENCE", "CONVERGENCE",
        }
        required = {
            "PHASE_0_INVESTIGATION": [("problem_statement", "problem_context")],
            "INVESTIGATION": [("problem_statement", "problem_context")],
            "DRAFT": [("problem_statement", "problem_context")],
            "PHASE_4_CONVERGENCE": [
                ("architect_defense", "pragmatic_defense", "problem_context", "audit_report", "architect_proposal", "pragmatic_proposal")
            ],
            "CONVERGENCE": [
                ("architect_defense", "pragmatic_defense", "problem_context", "audit_report", "architect_proposal", "pragmatic_proposal")
            ],
        }
        self._validate_context_policy(context, allowed_phases, required, forbidden)
