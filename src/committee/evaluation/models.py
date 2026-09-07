"""Data models for the Deliberation Quality Evaluation Framework."""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.common import Severity, ensure_timezone_aware


class EvaluationCriterion(str, Enum):
    """The 12 formal evaluation criteria measuring deliberative quality."""

    PROPOSAL_DIVERGENCE = "Proposal Divergence"
    ASSUMPTION_COVERAGE = "Assumption Coverage"
    RISK_COVERAGE = "Risk Coverage"
    ADVERSARIAL_QUALITY = "Adversarial Quality"
    DEFENSE_RESPONSIVENESS = "Defense Responsiveness"
    SYNTHESIS_NEUTRALITY = "Synthesis Neutrality"
    TRADE_OFF_EXPLICITNESS = "Trade-off Explicitness"
    DECISION_TRACEABILITY = "Decision Traceability"
    DEBT_EXPLICITNESS = "Debt Explicitness"
    REVIEWABILITY = "Reviewability"
    LEARNING_VALUE = "Learning Value"
    HUMAN_SOVEREIGNTY = "Human Sovereignty"


class EpistemicCriterion(str, Enum):
    """Criteria measuring Epistemic Discipline and ground truth adherence."""

    EPISTEMIC_INTEGRITY = "Epistemic Integrity"
    FACT_GROUNDING = "Fact Grounding"
    ASSUMPTION_TRANSPARENCY = "Assumption Transparency"
    UNKNOWN_VISIBILITY = "Unknown Visibility"
    INFERENCE_TRACEABILITY = "Inference Traceability"
    RECOMMENDATION_GROUNDING = "Recommendation Grounding"


class EvaluationFinding(BaseModel):
    """Specific finding or deficiency identified during evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1)]
    criterion: EvaluationCriterion | EpistemicCriterion
    severity: Severity
    description: Annotated[str, Field(min_length=5)]
    evidence: Annotated[str, Field(min_length=1)]
    recommendation: str | None = None


class CriterionScore(BaseModel):
    """Score, evidence, and qualitative findings for a specific criterion.

    Scale:
    0 = ausente
    1 = fraco
    2 = parcial
    3 = adequado
    4 = forte
    5 = excelente
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion: EvaluationCriterion | EpistemicCriterion
    score: Annotated[float, Field(ge=0.0, le=5.0)]
    evidence: list[str] = Field(min_length=1)
    severity: Severity | None = None
    notes: str = ""
    passed: bool = True

    @field_validator("evidence")
    @classmethod
    def validate_non_empty_evidence(cls, v: list[str]) -> list[str]:
        if not v or any(not item.strip() for item in v):
            raise ValueError("Evidence cannot be empty or contain blank entries.")
        return v


class EvaluationSummary(BaseModel):
    """Consolidated summary of scores, findings, and qualitative feedback."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    overall_score: Annotated[float, Field(ge=0.0, le=5.0)]
    criterion_scores: dict[EvaluationCriterion, CriterionScore]
    epistemic_scores: dict[EpistemicCriterion, CriterionScore] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    critical_findings: list[EvaluationFinding] = Field(default_factory=list)
    recommended_improvements: list[str] = Field(default_factory=list)


class EvaluationMetadata(BaseModel):
    """Metadata tracking model version, prompt iteration, scenario and timestamp."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str | None = None
    prompt_version: str | None = None
    scenario_id: str | None = None
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("evaluated_at")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        return ensure_timezone_aware(v)


class EvaluationResult(BaseModel):
    """Complete evaluation report for a deliberation session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    summary: EvaluationSummary
    metadata: EvaluationMetadata = Field(default_factory=EvaluationMetadata)

    def format_report(self) -> str:
        """Produce a human-readable textual evaluation report."""
        lines = [
            "==================================================",
            "             AI COMMITTEE EVALUATION              ",
            "==================================================",
            f"Session ID:    {self.session_id}",
            f"Overall Score: {self.summary.overall_score:.1f}/5",
        ]
        if self.metadata.scenario_id:
            lines.append(f"Scenario:      {self.metadata.scenario_id}")
        if self.metadata.model:
            lines.append(f"Model:         {self.metadata.model}")
        if self.metadata.prompt_version:
            lines.append(f"Prompt Ver:    {self.metadata.prompt_version}")

        lines.append("-" * 50)
        lines.append("CRITERIA SCORES:")
        for crit, score_obj in self.summary.criterion_scores.items():
            status_tag = "PASS" if score_obj.passed else "FAIL"
            lines.append(f"  {crit.value:<26} {score_obj.score:.1f}/5  [{status_tag}]")

        if self.summary.epistemic_scores:
            lines.append("-" * 50)
            lines.append("EPISTEMIC DISCIPLINE SCORES:")
            for e_crit, e_score in self.summary.epistemic_scores.items():
                e_tag = "PASS" if e_score.passed else "FAIL"
                lines.append(f"  {e_crit.value:<26} {e_score.score:.1f}/5  [{e_tag}]")

        if self.summary.critical_findings:
            lines.append("-" * 50)
            lines.append("CRITICAL FINDINGS:")
            for finding in self.summary.critical_findings:
                lines.append(f"  [{finding.severity.value}] {finding.criterion.value}: {finding.description}")
                lines.append(f"    Evidence: {finding.evidence}")
                if finding.recommendation:
                    lines.append(f"    Recommendation: {finding.recommendation}")

        if self.summary.strengths:
            lines.append("-" * 50)
            lines.append("STRENGTHS:")
            for s in self.summary.strengths:
                lines.append(f"  • {s}")

        if self.summary.weaknesses:
            lines.append("-" * 50)
            lines.append("WEAKNESSES:")
            for w in self.summary.weaknesses:
                lines.append(f"  • {w}")

        if self.summary.recommended_improvements:
            lines.append("-" * 50)
            lines.append("RECOMMENDED IMPROVEMENTS:")
            for imp in self.summary.recommended_improvements:
                lines.append(f"  • {imp}")

        lines.append("==================================================")
        return "\n".join(lines)
