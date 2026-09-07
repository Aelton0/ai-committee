"""Deterministic and extensible deliberation evaluator implementation."""

from abc import ABC, abstractmethod
from typing import Any, Sequence

from schemas.common import Severity
from src.committee.evaluation.criteria import (
    evaluate_adversarial_quality,
    evaluate_assumption_coverage,
    evaluate_debt_explicitness,
    evaluate_decision_traceability,
    evaluate_defense_responsiveness,
    evaluate_epistemic_integrity,
    evaluate_fact_grounding,
    evaluate_human_sovereignty,
    evaluate_inference_traceability,
    evaluate_learning_value,
    evaluate_proposal_divergence,
    evaluate_recommendation_grounding,
    evaluate_reviewability,
    evaluate_risk_coverage,
    evaluate_synthesis_neutrality,
    evaluate_trade_off_explicitness,
    evaluate_unknown_visibility,
    evaluate_assumption_transparency,
)
from src.committee.evaluation.models import (
    CriterionScore,
    EpistemicCriterion,
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


class LLMEvaluator(BaseEvaluator):
    """Evaluator performing deep semantic analysis via language model reasoning.

    Architectural Roadmap (CRITICAL-01):
    Planned to evaluate semantic criteria (e.g. cross-referencing epistemic claims,
    detecting genuine hallucinations, evaluating nuanced trade-offs) beyond lexical patterns.
    """

    def __init__(self, llm_provider: Any = None) -> None:
        self.llm_provider = llm_provider

    def evaluate_session(
        self, session: Session, metadata: EvaluationMetadata | None = None
    ) -> EvaluationResult:
        raise NotImplementedError(
            "LLMEvaluator is planned for future semantic evaluation phase (CRITICAL-01 roadmap)."
        )


class HybridEvaluator(BaseEvaluator):
    """Pipeline orchestrating deterministic checks followed by LLM semantic evaluation.

    Architectural Roadmap (CRITICAL-01):
    Pipeline:
      DeterministicEvaluator -> Structural Quality Gate -> LLMEvaluator -> Hybrid Evaluation
    """

    def __init__(
        self,
        deterministic_evaluator: "DeterministicEvaluator | None" = None,
        llm_evaluator: LLMEvaluator | None = None,
    ) -> None:
        self.deterministic_evaluator = deterministic_evaluator
        self.llm_evaluator = llm_evaluator or LLMEvaluator()

    def evaluate_session(
        self, session: Session, metadata: EvaluationMetadata | None = None
    ) -> EvaluationResult:
        raise NotImplementedError(
            "HybridEvaluator is planned for future multi-stage evaluation pipeline (CRITICAL-01 roadmap)."
        )


class DeterministicEvaluator(BaseEvaluator):
    """Fully reproducible, deterministic evaluator executing all 12 analytical criteria and 6 epistemic criteria."""

    def evaluate_session(
        self, session: Session, metadata: EvaluationMetadata | None = None
    ) -> EvaluationResult:
        """Evaluate session deterministically according to strict analytical criteria."""
        scores: dict[EvaluationCriterion, CriterionScore] = {}
        epistemic_scores: dict[EpistemicCriterion, CriterionScore] = {}
        all_findings: list[EvaluationFinding] = []

        # List of all 12 standard criteria functions
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

        # List of 6 epistemic discipline criteria functions
        epistemic_evaluators = [
            evaluate_fact_grounding,
            evaluate_assumption_transparency,
            evaluate_unknown_visibility,
            evaluate_inference_traceability,
            evaluate_recommendation_grounding,
            evaluate_epistemic_integrity,
        ]

        for ep_fn in epistemic_evaluators:
            score_obj, findings = ep_fn(session)
            epistemic_scores[score_obj.criterion] = score_obj
            all_findings.extend(findings)

        # Compute overall score (unweighted mean of standard criteria)
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

        for ep_crit, cs in epistemic_scores.items():
            if cs.score >= 4.5:
                strengths.append(f"{ep_crit.value}: score {cs.score:.1f}/5. {cs.notes}")
            elif cs.score <= 2.5:
                weaknesses.append(f"{ep_crit.value}: score {cs.score:.1f}/5. {cs.notes}")

        for finding in all_findings:
            if finding.recommendation and finding.recommendation not in recommended_improvements:
                recommended_improvements.append(finding.recommendation)

        summary = EvaluationSummary(
            overall_score=overall_score,
            criterion_scores=scores,
            epistemic_scores=epistemic_scores,
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
