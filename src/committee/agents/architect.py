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
        # Blind divergence check (Phase 1)
        if "pragmatic_proposal" in context and context["pragmatic_proposal"] is not None:
            raise ContextIsolationError(
                "Blind divergence violated: Architect received Pragmatic proposal."
            )
        # Defense isolation check (Phase 3)
        if "pragmatic_defense" in context and context["pragmatic_defense"] is not None:
            raise ContextIsolationError(
                "Defense isolation violated: Architect received Pragmatic defense."
            )
