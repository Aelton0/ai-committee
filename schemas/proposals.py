"""Comparable proposal schemas for the Architect and Pragmatist agents."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import BaseArtifact, CommitteeRole, Severity


class EffortLevel(str, Enum):
    """Implementation effort estimation."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class ReversibilityLevel(str, Enum):
    """How easily the proposed decision can be reverted in the future."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CostEstimate(BaseModel):
    """Structured breakdown of financial and engineering costs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    implementation_effort: EffortLevel
    infrastructure_cost_estimate: Annotated[str, Field(min_length=1)]
    additional_costs: list[str] = Field(default_factory=list)


class ReversibilityAssessment(BaseModel):
    """Analysis of decision reversibility and rollback cost."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score: ReversibilityLevel
    rationale: Annotated[str, Field(min_length=5)]
    rollback_strategy: str | None = None


class BaseProposal(BaseArtifact):
    """Base class providing a strictly comparable structure for both proposals."""

    proponent_role: CommitteeRole
    title: Annotated[str, Field(min_length=3)]
    solution: Annotated[str, Field(min_length=10, description="Comprehensive architectural/technical solution")]
    rationale: Annotated[str, Field(min_length=10, description="Why this solution best satisfies the problem")]
    benefits: Annotated[list[str], Field(min_length=1)]
    costs: CostEstimate
    risks: Annotated[list[str], Field(min_length=1)]
    complexity: Severity
    reversibility: ReversibilityAssessment
    future_implications: Annotated[str, Field(min_length=5)]
    assumptions: Annotated[list[str], Field(min_length=1)]
    invalidation_conditions: Annotated[list[str], Field(min_length=1)]


class ArchitectProposal(BaseProposal):
    """Proposal formulated by the Architect prioritizing long-term modularity and resilience."""

    proponent_role: Literal[CommitteeRole.ARCHITECT] = CommitteeRole.ARCHITECT
    modularity_strategy: str | None = None
    evolution_path: str | None = None


class PragmaticProposal(BaseProposal):
    """Proposal formulated by the Pragmatist prioritizing KISS, YAGNI, and rapid time-to-value."""

    proponent_role: Literal[CommitteeRole.PRAGMATIST] = CommitteeRole.PRAGMATIST
    time_to_value: str | None = None
    simplifications_made: list[str] = Field(default_factory=list)
