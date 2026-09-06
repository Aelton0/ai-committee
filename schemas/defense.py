"""Defense and refinement schemas for responding to audit findings."""

from enum import Enum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from schemas.common import BaseArtifact, CommitteeRole


class DefenseStance(str, Enum):
    """Position taken by a proponent in response to an audit critique."""

    CONCEDED_WITH_REFINEMENT = "CONCEDED_WITH_REFINEMENT"
    CONTESTED = "CONTESTED"
    ACKNOWLEDGED_ACCEPTING_RISK = "ACKNOWLEDGED_ACCEPTING_RISK"


class ProposalAction(str, Enum):
    """Explicit declaration on whether the original proposal was maintained or modified."""

    MAINTAIN = "MAINTAIN"
    MODIFY = "MODIFY"


class CritiqueResponse(BaseModel):
    """Structured answer to a specific finding raised by the Auditor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: Annotated[str, Field(min_length=1, description="Reference to AuditFinding.id")]
    stance: DefenseStance
    response: Annotated[str, Field(min_length=5, description="Technical response to the critique")]
    rationale: Annotated[str, Field(min_length=5, description="Justification for the chosen stance")]
    proposed_modification: str | None = None


class BaseDefense(BaseArtifact):
    """Base class for responses formulated by proponents in Phase 3.

    References the original proposal immutably and declares whether modifications are made.
    """

    proponent_role: CommitteeRole
    original_proposal_id: Annotated[str, Field(min_length=1)]
    original_proposal_version: PositiveInt = 1
    critique_responses: Annotated[list[CritiqueResponse], Field(min_length=1)]
    proposal_action: ProposalAction
    persistent_disagreements: list[str] = Field(default_factory=list)
    revised_proposal_id: str | None = None
    revised_proposal_version: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_modification_consistency(self) -> Self:
        if self.proposal_action == ProposalAction.MODIFY:
            if self.revised_proposal_version is None:
                raise ValueError(
                    "When proposal_action is 'MODIFY', 'revised_proposal_version' must be specified."
                )
            if self.revised_proposal_version <= self.original_proposal_version:
                raise ValueError(
                    f"Revised version ({self.revised_proposal_version}) must be strictly greater "
                    f"than original version ({self.original_proposal_version})."
                )
        elif self.proposal_action == ProposalAction.MAINTAIN:
            if self.revised_proposal_version is not None:
                raise ValueError(
                    "When proposal_action is 'MAINTAIN', 'revised_proposal_version' must not be set."
                )
        return self


class ArchitectDefense(BaseDefense):
    """Defense submitted by the Architect."""

    proponent_role: Literal[CommitteeRole.ARCHITECT] = CommitteeRole.ARCHITECT


class PragmaticDefense(BaseDefense):
    """Defense submitted by the Pragmatist."""

    proponent_role: Literal[CommitteeRole.PRAGMATIST] = CommitteeRole.PRAGMATIST
