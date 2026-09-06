"""Unit tests verifying evaluation models, score boundaries, evidence enforcement, and reporting."""

from uuid import uuid4
import pytest
from pydantic import ValidationError

from schemas.common import Severity
from src.committee.evaluation.models import (
    CriterionScore,
    EvaluationCriterion,
    EvaluationFinding,
    EvaluationMetadata,
    EvaluationResult,
    EvaluationSummary,
)


def test_evaluation_criteria_completeness() -> None:
    """Verify that all 12 formal criteria are defined and distinct."""
    assert len(EvaluationCriterion) == 12
    expected = {
        "Proposal Divergence",
        "Assumption Coverage",
        "Risk Coverage",
        "Adversarial Quality",
        "Defense Responsiveness",
        "Synthesis Neutrality",
        "Trade-off Explicitness",
        "Decision Traceability",
        "Debt Explicitness",
        "Reviewability",
        "Learning Value",
        "Human Sovereignty",
    }
    actual = {c.value for c in EvaluationCriterion}
    assert actual == expected


def test_criterion_score_valid_ranges() -> None:
    """CriterionScore must accept scores in [0.0, 5.0] and require non-empty evidence."""
    cs = CriterionScore(
        criterion=EvaluationCriterion.PROPOSAL_DIVERGENCE,
        score=4.5,
        evidence=["Valid evidence item."],
        notes="Adequate divergence.",
        passed=True,
    )
    assert cs.score == 4.5
    assert len(cs.evidence) == 1


def test_criterion_score_rejects_out_of_bounds() -> None:
    """CriterionScore must reject scores outside [0.0, 5.0]."""
    with pytest.raises(ValidationError):
        CriterionScore(
            criterion=EvaluationCriterion.PROPOSAL_DIVERGENCE,
            score=5.5,
            evidence=["Valid evidence."],
        )

    with pytest.raises(ValidationError):
        CriterionScore(
            criterion=EvaluationCriterion.PROPOSAL_DIVERGENCE,
            score=-0.1,
            evidence=["Valid evidence."],
        )


def test_criterion_score_requires_evidence() -> None:
    """CriterionScore must reject empty evidence lists or whitespace-only items."""
    with pytest.raises(ValidationError):
        CriterionScore(
            criterion=EvaluationCriterion.PROPOSAL_DIVERGENCE,
            score=3.0,
            evidence=[],
        )

    with pytest.raises(ValidationError):
        CriterionScore(
            criterion=EvaluationCriterion.PROPOSAL_DIVERGENCE,
            score=3.0,
            evidence=["   "],
        )


def test_evaluation_finding_validation() -> None:
    """EvaluationFinding enforces required fields and immutability."""
    finding = EvaluationFinding(
        id="F-01",
        criterion=EvaluationCriterion.SYNTHESIS_NEUTRALITY,
        severity=Severity.CRITICAL,
        description="Facilitator was biased.",
        evidence="Found text: 'recomendo a proposta A'.",
        recommendation="Ensure neutral synthesis.",
    )
    assert finding.id == "F-01"
    assert finding.severity == Severity.CRITICAL

    # Immutability
    with pytest.raises(ValidationError):
        finding.id = "F-02"


def test_evaluation_result_format_report() -> None:
    """EvaluationResult formats a comprehensive textual report."""
    session_id = uuid4()
    crit_scores = {
        EvaluationCriterion.PROPOSAL_DIVERGENCE: CriterionScore(
            criterion=EvaluationCriterion.PROPOSAL_DIVERGENCE,
            score=5.0,
            evidence=["Clear architectural differences."],
            notes="Strong divergence.",
            passed=True,
        ),
        EvaluationCriterion.SYNTHESIS_NEUTRALITY: CriterionScore(
            criterion=EvaluationCriterion.SYNTHESIS_NEUTRALITY,
            score=5.0,
            evidence=["Impartial synthesis."],
            notes="No bias.",
            passed=True,
        ),
    }
    summary = EvaluationSummary(
        overall_score=5.0,
        criterion_scores=crit_scores,
        strengths=["Proposal Divergence: score 5.0/5"],
        weaknesses=[],
        critical_findings=[],
        recommended_improvements=["Keep practicing."],
    )
    res = EvaluationResult(
        session_id=session_id,
        summary=summary,
        metadata=EvaluationMetadata(scenario_id="benchmark-test-01"),
    )
    report = res.format_report()

    assert "AI COMMITTEE EVALUATION" in report
    assert f"Session ID:    {session_id}" in report
    assert "Overall Score: 5.0/5" in report
    assert "Scenario:      benchmark-test-01" in report
    assert "Proposal Divergence        5.0/5  [PASS]" in report
    assert "STRENGTHS:" in report
    assert "RECOMMENDED IMPROVEMENTS:" in report
