"""Decision record schemas produced by the Decisor in Phase 5."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.common import BaseArtifact, CommitteeRole, Confidence, DecisionStatus, Severity


class RejectedAlternative(BaseModel):
    """Details and technical rationale for rejecting a considered alternative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, Field(min_length=1)]
    rejection_reason: Annotated[str, Field(min_length=5)]


class AcceptedRisk(BaseModel):
    """Residual risk acknowledged and accepted in the final decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    risk: Annotated[str, Field(min_length=3)]
    severity: Severity
    mitigation: Annotated[str, Field(min_length=3)]


class TradeOffContract(BaseModel):
    """Explicitly acknowledged trade-off contracted by the decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gain: Annotated[str, Field(min_length=3)]
    sacrifice: Annotated[str, Field(min_length=3)]


class ReviewTrigger(BaseModel):
    """Measurable threshold or qualitative condition triggering re-evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition: Annotated[str, Field(min_length=5)]
    metric_threshold: str | None = None
    trigger_type: str | None = None


class DecisionRecord(BaseArtifact):
    """Formal recommendation dossier formulated by the Decisor.

    Mandates rigorous trade-offs and review triggers for RECOMMENDED status,
    and forbids false winners when status is INSUFFICIENT_EVIDENCE.
    """

    decisor_role: Literal[CommitteeRole.DECISOR] = CommitteeRole.DECISOR
    status: DecisionStatus
    recommendation: str | None = None
    chosen_alternative: str | None = None
    rejected_alternatives: list[RejectedAlternative] = Field(default_factory=list)
    rationale: Annotated[str, Field(min_length=10, description="Comprehensive rationale of the decision")]
    trade_offs: list[TradeOffContract] = Field(default_factory=list)
    accepted_risks: list[AcceptedRisk] = Field(default_factory=list)
    technical_debt: list[str] = Field(default_factory=list)
    operational_debt: list[str] = Field(default_factory=list)
    critical_assumptions: list[str] = Field(default_factory=list)
    review_triggers: list[ReviewTrigger] = Field(default_factory=list)
    confidence: Confidence
    information_that_could_change_decision: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decision_status_invariants(self) -> Self:
        if self.status == DecisionStatus.INSUFFICIENT_EVIDENCE:
            if self.chosen_alternative is not None:
                raise ValueError(
                    "When status is 'INSUFFICIENT_EVIDENCE', 'chosen_alternative' must be None (no winner)."
                )
            if not self.information_that_could_change_decision:
                raise ValueError(
                    "When status is 'INSUFFICIENT_EVIDENCE', 'information_that_could_change_decision' "
                    "must list the missing critical data."
                )
        elif self.status == DecisionStatus.RECOMMENDED:
            if not self.chosen_alternative or not self.chosen_alternative.strip():
                raise ValueError("When status is 'RECOMMENDED', 'chosen_alternative' must be provided.")
            if not self.recommendation or not self.recommendation.strip():
                raise ValueError("When status is 'RECOMMENDED', 'recommendation' must be provided.")
            if not self.trade_offs:
                raise ValueError(
                    "When status is 'RECOMMENDED', at least one explicit trade-off must be documented (Principle 10)."
                )
            if not self.review_triggers:
                raise ValueError(
                    "When status is 'RECOMMENDED', at least one review trigger must be documented (Principle 11)."
                )
        return self
