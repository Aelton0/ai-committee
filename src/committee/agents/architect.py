"""Architect Agent specialized in structural longevity and modularity."""

from typing import Any

from pydantic import BaseModel
from schemas.common import CommitteeRole
from schemas.defense import ArchitectDefense
from schemas.proposals import ArchitectProposal
from src.committee.agents.base import BaseAgent, ContextIsolationError


class ArchitectAgent(BaseAgent):
    """Software Architect Agent prioritizing long-term modularity and structural integrity."""

    @property
    def role(self) -> CommitteeRole:
        return CommitteeRole.ARCHITECT

    @property
    def prompt_filename(self) -> str:
        return "architect.md"

    @property
    def output_schema(self) -> type[BaseModel]:
        return ArchitectProposal

    def get_output_schema(self, context: dict[str, Any] | None = None) -> type[BaseModel]:
        if context:
            phase = context.get("phase")
            if phase in ("PHASE_3_DEFENSE", "DEFENSE") or "audit_report" in context:
                return ArchitectDefense
        return ArchitectProposal

    def validate_input_context(self, context: dict[str, Any]) -> None:
        forbidden = [
            ("pragmatic_proposal", "Blind divergence violated: Architect received Pragmatic proposal."),
            ("pragmatic_defense", "Defense isolation violated: Architect received Pragmatic defense."),
        ]
        allowed_phases = {"PHASE_1_DIVERGENCE", "DIVERGENCE", "PHASE_3_DEFENSE", "DEFENSE"}
        required = {
            "PHASE_1_DIVERGENCE": [("problem_context", "problem_statement")],
            "DIVERGENCE": [("problem_context", "problem_statement")],
            "PHASE_3_DEFENSE": ["audit_report"],
            "DEFENSE": ["audit_report"],
        }
        self._validate_context_policy(context, allowed_phases, required, forbidden)
