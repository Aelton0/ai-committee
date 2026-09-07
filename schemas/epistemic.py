"""Formal schemas and data models for Epistemic Discipline in the AI Committee."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import Confidence, Severity


class EpistemicCategory(str, Enum):
    """Canonical epistemic categories separating verified knowledge from hypotheses and proposals."""

    FACT = "FACT"
    ASSUMPTION = "ASSUMPTION"
    INFERENCE = "INFERENCE"
    UNKNOWN = "UNKNOWN"
    RECOMMENDATION = "RECOMMENDATION"


class FactItem(BaseModel):
    """Objective, verified datum directly provided by the user or derived deterministically."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1, description="Identifier, e.g. F1, FACT-1")]
    statement: Annotated[str, Field(min_length=3, description="Objective verified fact")]
    source: Annotated[str, Field(min_length=1, description="Origin, e.g. User input, metrics, logs")]
    verified: bool = True


class AssumptionItem(BaseModel):
    """Working hypothesis provisionally adopted when factual evidence is insufficient."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1, description="Identifier, e.g. A1, ASM-1")]
    statement: Annotated[str, Field(min_length=3, description="Hypothesis statement")]
    reason: Annotated[str, Field(min_length=3, description="Technical or operational reason for assuming this")]
    confidence: Confidence = Confidence.MEDIUM
    invalidation_condition: Annotated[
        str,
        Field(min_length=3, description="Measurable or observable condition that invalidates this assumption"),
    ]
    risk_level: Severity = Severity.MEDIUM


class InferenceItem(BaseModel):
    """Intermediate conclusion deduced logically from facts and/or declared assumptions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1, description="Identifier, e.g. I1, INF-1")]
    statement: Annotated[str, Field(min_length=3, description="Intermediate logical conclusion")]
    rationale: Annotated[str, Field(min_length=3, description="Logical argument deriving this inference")]
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of Fact or Assumption IDs supporting this inference, e.g. ['F1', 'A1']",
    )
    confidence: Confidence = Confidence.MEDIUM


class UnknownItem(BaseModel):
    """Relevant piece of information that is currently missing, unmeasured, or unknowable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1, description="Identifier, e.g. U1, UNK-1")]
    statement: Annotated[str, Field(min_length=3, description="Missing information description")]
    impact_if_adverse: Severity = Severity.HIGH
    how_to_resolve: str | None = Field(
        default=None,
        description="Suggested action, measurement, or spike to resolve this unknown",
    )


class ConditionalRecommendation(BaseModel):
    """Recommendation guarded by an explicit condition when the underlying need is unproven."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition: Annotated[
        str,
        Field(min_length=3, description="Pre-condition, e.g. 'IF peak throughput > 2,000 req/s'"),
    ]
    recommendation: Annotated[
        str,
        Field(min_length=3, description="Guarded proposal, e.g. 'THEN adopt Redis Streams'"),
    ]
    evidence: list[str] = Field(
        default_factory=list,
        description="IDs of facts, assumptions, or inferences underpinning the condition/action",
    )


class RecommendationItem(BaseModel):
    """Action or architectural choice proposed by an agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = ""
    statement: Annotated[str, Field(min_length=3, description="Recommended architectural or design choice")]
    rationale: str = ""
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of inferences, assumptions, or facts underpinning this recommendation",
    )
    is_conditional: bool = False
    condition: str | None = None


class EpistemicSection(BaseModel):
    """Aggregated epistemic breakdown answering: What do I know? What do I assume/infer/not know/recommend?"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: list[FactItem] = Field(
        default_factory=list,
        description="What do I know? (Verified facts grounded in ProblemContext)",
    )
    assumptions: list[AssumptionItem] = Field(
        default_factory=list,
        description="What am I assuming? (Hypotheses adopted provisionally)",
    )
    inferences: list[InferenceItem] = Field(
        default_factory=list,
        description="What am I inferring? (Logical deductions from facts/assumptions)",
    )
    unknowns: list[UnknownItem] = Field(
        default_factory=list,
        description="What don't I know? (Explicit gaps and unmeasured variables)",
    )
    conditional_recommendations: list[ConditionalRecommendation] = Field(
        default_factory=list,
        description="What do I recommend conditionally? (IF condition THEN action)",
    )
    recommendations: list[RecommendationItem] = Field(
        default_factory=list,
        description="What do I recommend unconditionally?",
    )

    def fact_ids(self) -> set[str]:
        return {f.id for f in self.facts}

    def assumption_ids(self) -> set[str]:
        return {a.id for a in self.assumptions}

    def inference_ids(self) -> set[str]:
        return {i.id for i in self.inferences}

    def unknown_ids(self) -> set[str]:
        return {u.id for u in self.unknowns}

    def validate_dependency_references(self) -> list[str]:
        """Verify whether inferences reference declared fact or assumption IDs."""
        known_sources = self.fact_ids() | self.assumption_ids()
        missing_refs = []
        for inf in self.inferences:
            for dep in inf.depends_on:
                if dep and dep not in known_sources:
                    missing_refs.append(f"Inference '{inf.id}' references undeclared dependency '{dep}'")
        return missing_refs
