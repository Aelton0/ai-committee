"""Pragmatic Agent prioritizing time-to-value, simplicity, and low complexity."""

from typing import Any

from pydantic import BaseModel
from schemas.common import CommitteeRole
from schemas.defense import PragmaticDefense
from schemas.proposals import PragmaticProposal
from src.committee.agents.base import BaseAgent, ContextIsolationError


class PragmaticAgent(BaseAgent):
    """Pragmatic Engineer Agent prioritizing delivery speed, KISS, and operational simplicity."""

    @property
    def role(self) -> CommitteeRole:
        return CommitteeRole.PRAGMATIST

    @property
    def prompt_filename(self) -> str:
        return "pragmatic.md"

    @property
    def output_schema(self) -> type[BaseModel]:
        return PragmaticProposal

    def get_output_schema(self, context: dict[str, Any] | None = None) -> type[BaseModel]:
        if context:
            phase = context.get("phase")
            if phase in ("PHASE_3_DEFENSE", "DEFENSE") or "audit_report" in context:
                return PragmaticDefense
        return PragmaticProposal

    def validate_input_context(self, context: dict[str, Any]) -> None:
        forbidden = [
            ("architect_proposal", "Blind divergence violated: Pragmatic received Architect proposal."),
            ("architect_defense", "Defense isolation violated: Pragmatic received Architect defense."),
        ]
        allowed_phases = {"PHASE_1_DIVERGENCE", "DIVERGENCE", "PHASE_3_DEFENSE", "DEFENSE"}
        required = {
            "PHASE_1_DIVERGENCE": [("problem_context", "problem_statement")],
            "DIVERGENCE": [("problem_context", "problem_statement")],
            "PHASE_3_DEFENSE": ["audit_report"],
            "DEFENSE": ["audit_report"],
        }
        self._validate_context_policy(context, allowed_phases, required, forbidden)
