"""Adversarial tests demonstrating limitations of lexical/heuristic evaluation criteria.

Documented as architectural debt under CRITICAL-01 in docs/audit/independent-audit-report.md.
Proves why the future roadmap needs LLMEvaluator and HybridEvaluator beyond DeterministicEvaluator.
"""

from uuid import uuid4
import pytest

from schemas.common import CommitteeRole, CommitteeState, Confidence, DecisionStatus, Severity
from schemas.decision import DecisionRecord, RejectedAlternative, ReviewTrigger, TradeOffContract
from schemas.synthesis import AlternativeArguments, DeliberationSynthesis, TradeOffDimension
from src.committee.evaluation.criteria import evaluate_synthesis_neutrality
from src.committee.evaluation.evaluator import (
    DeterministicEvaluator,
    HybridEvaluator,
    LLMEvaluator,
)
from src.committee.evaluation.models import EvaluationCriterion
from src.committee.session import Session


def test_adversarial_subtle_bias_bypasses_lexical_neutrality() -> None:
    """Demonstrate that subtle semantic bias not matching hardcoded regexes escapes detection.

    Proves finding CRITICAL-01: lexical regexes are necessary but insufficient without semantic LLM evaluation.
    """
    session = Session(session_id=uuid4(), current_state=CommitteeState.CONVERGENCE)

    # Subtly biased synthesis favoring alternative A using non-blacklisted formulation:
    synthesis = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consensus_points=["Both agree latency is important."],
        divergence_points=["Framework choice."],
        arguments_by_alternative=[
            AlternativeArguments(
                alternative_id="A",
                arguments=["Option A presents vastly superior ergonomics and team velocity will flourish."],
            ),
            AlternativeArguments(
                alternative_id="B",
                arguments=["Option B brings considerable operational drag without clear benefit."],
            ),
        ],
        trade_offs=[
            TradeOffDimension(
                dimension="Velocity",
                option_a="Maximum speed",
                option_b="Significant sluggishness",
                notes="Option A is clearly the more pragmatic path forward.",
            )
        ],
    )
    session.deliberation_synthesis = synthesis

    score, findings = evaluate_synthesis_neutrality(session)
    # The lexical evaluator passes it (score > 0) because none of the fixed regexes match,
    # demonstrating why a future LLMEvaluator is necessary to detect semantic partiality.
    assert score.score > 0.0, "Lexical evaluation failed to catch nuanced non-regex bias (known limitation)."


def test_evaluator_architecture_readiness_for_llm_evaluator() -> None:
    """Verify that evaluator architecture defines the interfaces for future LLMEvaluator and HybridEvaluator."""
    llm_eval = LLMEvaluator()
    hybrid_eval = HybridEvaluator()

    session = Session(session_id=uuid4(), current_state=CommitteeState.COMPLETED)

    # LLMEvaluator and HybridEvaluator exist in the hierarchy and document future roadmap
    assert isinstance(llm_eval, LLMEvaluator)
    assert isinstance(hybrid_eval, HybridEvaluator)

    with pytest.raises(NotImplementedError, match="CRITICAL-01 roadmap"):
        llm_eval.evaluate_session(session)

    with pytest.raises(NotImplementedError, match="CRITICAL-01 roadmap"):
        hybrid_eval.evaluate_session(session)


def test_llm_evaluator_type_annotations_resolution() -> None:
    """Verify that type annotations in LLMEvaluator and HybridEvaluator resolve without NameError.

    Regression test for NameError: name 'Any' is not defined in evaluator.py annotations.
    """
    import inspect

    annotations_llm = inspect.get_annotations(LLMEvaluator.__init__)
    assert "llm_provider" in annotations_llm
    annotations_hybrid = inspect.get_annotations(HybridEvaluator.__init__)
    assert "deterministic_evaluator" in annotations_hybrid

