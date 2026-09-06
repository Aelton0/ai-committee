"""Deterministic and extensible deliberation evaluator implementation."""

from abc import ABC, abstractmethod
from typing import Sequence

from schemas.common import Severity
from src.committee.evaluation.criteria import (
    evaluate_adversarial_quality,
    evaluate_assumption_coverage,
    evaluate_debt_explicitness,
    evaluate_decision_traceability,
    evaluate_defense_responsiveness,
    evaluate_human_sovereignty,
    evaluate_learning_value,
    evaluate_proposal_divergence,
    evaluate_reviewability,
    evaluate_risk_coverage,
    evaluate_synthesis_neutrality,
    evaluate_trade_off_explicitness,
)
from src.committee.evaluation.models import (
    CriterionScore,
    EvaluationCriterion,
    EvaluationFinding,
    EvaluationMetadata,
    EvaluationResult,
    EvaluationSummary,
)
from src.committee.session import Session


class BaseEvaluator(ABC):
    """Abstract base class for deliberation quality evaluators.

    Allows future extensions like LLMEvaluator and HybridEvaluator without altering the core.
    """

    @abstractmethod
    def evaluate_session(
        self, session: Session, metadata: EvaluationMetadata | None = None
    ) -> EvaluationResult:
        """Evaluate a completed or active session and return structured evaluation results."""
        ...


class DeterministicEvaluator(BaseEvaluator):
    """Fully reproducible, deterministic evaluator executing all 12 analytical criteria."""

    def evaluate_session(
        self, session: Session, metadata: EvaluationMetadata | None = None
    ) -> EvaluationResult:
        """Evaluate session deterministically according to strict analytical criteria."""
        scores: dict[EvaluationCriterion, CriterionScore] = {}
        all_findings: list[EvaluationFinding] = []

        # List of all 12 criteria functions
        evaluators = [
            evaluate_proposal_divergence,
            evaluate_assumption_coverage,
            evaluate_risk_coverage,
            evaluate_adversarial_quality,
            evaluate_defense_responsiveness,
            evaluate_synthesis_neutrality,
            evaluate_trade_off_explicitness,
            evaluate_decision_traceability,
            evaluate_debt_explicitness,
            evaluate_reviewability,
            evaluate_learning_value,
            evaluate_human_sovereignty,
        ]

        for eval_fn in evaluators:
            score_obj, findings = eval_fn(session)
            scores[score_obj.criterion] = score_obj
            all_findings.extend(findings)

        # Compute overall score (unweighted mean)
        overall_score = (
            round(sum(cs.score for cs in scores.values()) / len(scores), 1)
            if scores
            else 0.0
        )

        # Categorize strengths, weaknesses, and recommendations
        strengths: list[str] = []
        weaknesses: list[str] = []
        recommended_improvements: list[str] = []

        for crit, cs in scores.items():
            if cs.score >= 4.5:
                strengths.append(f"{crit.value}: score {cs.score:.1f}/5. {cs.notes}")
            elif cs.score <= 2.5:
                weaknesses.append(f"{crit.value}: score {cs.score:.1f}/5. {cs.notes}")

        for finding in all_findings:
            if finding.recommendation and finding.recommendation not in recommended_improvements:
                recommended_improvements.append(finding.recommendation)

        summary = EvaluationSummary(
            overall_score=overall_score,
            criterion_scores=scores,
            strengths=strengths,
            weaknesses=weaknesses,
            critical_findings=all_findings,
            recommended_improvements=recommended_improvements,
        )

        return EvaluationResult(
            session_id=session.session_id,
            summary=summary,
            metadata=metadata or EvaluationMetadata(),
        )
