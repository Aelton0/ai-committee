"""Synthesis schemas produced by the Facilitador in Phase 4."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import BaseArtifact, CommitteeRole


class TradeOffDimension(BaseModel):
    """Comparative evaluation of a single architectural or strategic trade-off dimension."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: Annotated[str, Field(min_length=1)]
    option_a: Annotated[str, Field(min_length=1)]
    option_b: Annotated[str, Field(min_length=1)]
    notes: str | None = None


class DeliberationSynthesis(BaseArtifact):
    """Impartial consolidation of the deliberation produced by the Facilitador.

    Explicitly excludes any 'recommended_solution' or winner choice, as the Facilitador
    does not hold decision-making authority.
    """

    facilitator_role: Literal[CommitteeRole.FACILITATOR] = CommitteeRole.FACILITATOR
    consolidated_facts: list[str] = Field(default_factory=list)
    consolidated_constraints: list[str] = Field(default_factory=list)
    consolidated_assumptions: list[str] = Field(default_factory=list)
    consolidated_unknowns: list[str] = Field(default_factory=list)
    consensus_points: list[str] = Field(default_factory=list)
    divergence_points: list[str] = Field(default_factory=list)
    arguments_by_alternative: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Keyed by alternative identifier (e.g. 'PROPOSAL_A', 'PROPOSAL_B')",
    )
    unresolved_risks: list[str] = Field(default_factory=list)
    trade_offs: list[TradeOffDimension] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
