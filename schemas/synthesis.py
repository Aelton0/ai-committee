"""Synthesis schemas produced by the Facilitador in Phase 4."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.common import BaseArtifact, CommitteeRole


class TradeOffDimension(BaseModel):
    """Comparative evaluation of a single architectural or strategic trade-off dimension."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: Annotated[str, Field(min_length=1)]
    option_a: Annotated[str, Field(min_length=1)]
    option_b: Annotated[str, Field(min_length=1)]
    notes: str | None = None


class AlternativeArguments(BaseModel):
    """Arguments mapped to an alternative or proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alternative_id: Annotated[
        str,
        Field(
            min_length=1,
            description="Alternative identifier (e.g. 'PROPOSAL_A', 'PROPOSAL_B', 'architect_proposal_001')",
        ),
    ]
    arguments: list[str] = Field(
        default_factory=list,
        description="Arguments supporting or defending this alternative",
    )


class DeliberationSynthesis(BaseArtifact):
    """Impartial consolidation of the deliberation produced by the Facilitador.

    Explicitly excludes any 'recommended_solution' or winner choice, as the Facilitador
    does not hold decision-making authority.
    """

    facilitator_role: Literal[CommitteeRole.FACILITATOR] = CommitteeRole.FACILITATOR
    consolidated_facts: list[str] = Field(default_factory=list)
    consolidated_constraints: list[str] = Field(default_factory=list)
    consolidated_assumptions: list[str] = Field(default_factory=list)
    consolidated_inferences: list[str] = Field(default_factory=list)
    consolidated_unknowns: list[str] = Field(default_factory=list)
    consensus_points: list[str] = Field(default_factory=list)
    divergence_points: list[str] = Field(default_factory=list)
    arguments_by_alternative: list[AlternativeArguments] = Field(
        default_factory=list,
        description="List of arguments grouped by alternative identifier",
    )
    unresolved_risks: list[str] = Field(default_factory=list)
    trade_offs: list[TradeOffDimension] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_arguments_by_alternative(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw = data.get("arguments_by_alternative")
            if isinstance(raw, dict):
                converted = [
                    {"alternative_id": str(k), "arguments": list(v)}
                    for k, v in raw.items()
                ]
                data = dict(data)
                data["arguments_by_alternative"] = converted
        return data

    @property
    def arguments_dict(self) -> dict[str, list[str]]:
        """Convenience dictionary mapping alternative_id to arguments."""
        return {item.alternative_id: item.arguments for item in self.arguments_by_alternative}

