"""Auditor Agent specialized in adversarial critique, failure modes, and reliability."""

from typing import Any

from pydantic import BaseModel
from schemas.audit import AuditReport
from schemas.common import CommitteeRole
from src.committee.agents.base import BaseAgent, ContextIsolationError


class AuditorAgent(BaseAgent):
    """Reliability and SRE Auditor Agent detecting failure modes and overengineering."""

    @property
    def role(self) -> CommitteeRole:
        return CommitteeRole.AUDITOR_SRE

    @property
    def prompt_filename(self) -> str:
        return "auditor.md"

    @property
    def output_schema(self) -> type[BaseModel]:
        return AuditReport

    def validate_input_context(self, context: dict[str, Any]) -> None:
        # Auditor isolation: Auditor MUST NOT receive defenses
        if "architect_defense" in context and context["architect_defense"] is not None:
            raise ContextIsolationError(
                "Auditor isolation violated: Auditor received Architect defense."
            )
        if "pragmatic_defense" in context and context["pragmatic_defense"] is not None:
            raise ContextIsolationError(
                "Auditor isolation violated: Auditor received Pragmatic defense."
            )
