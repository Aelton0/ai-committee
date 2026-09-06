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
        # Blind divergence check (Phase 1)
        if "architect_proposal" in context and context["architect_proposal"] is not None:
            raise ContextIsolationError(
                "Blind divergence violated: Pragmatic received Architect proposal."
            )
        # Defense isolation check (Phase 3)
        if "architect_defense" in context and context["architect_defense"] is not None:
            raise ContextIsolationError(
                "Defense isolation violated: Pragmatic received Architect defense."
            )
