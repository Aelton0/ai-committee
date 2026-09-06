"""Unit tests verifying each of the 12 analytical evaluation criteria."""

from uuid import uuid4
import pytest

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, CommitteeState, DecisionStatus, Severity
from schemas.context import Assumption, ProblemContext
from schemas.decision import DecisionRecord, RejectedAlternative, ReviewTrigger, TradeOffContract
from schemas.defense import ArchitectDefense, CritiqueResponse, DefenseStance, PragmaticDefense, ProposalAction
from schemas.learning import LearningPathStep, LearningReference, LearningReport, ObservedKnowledgeGap
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from schemas.synthesis import DeliberationSynthesis, TradeOffDimension
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
from src.committee.evaluation.models import EvaluationCriterion
from src.committee.llm.mock import MockLLMProvider
from src.committee.session import Session


@pytest.fixture
def base_session() -> Session:
    provider = MockLLMProvider()
    session = Session(session_id=uuid4(), current_state=CommitteeState.COMPLETED)
    session.problem_context = provider._generate_default(ProblemContext, {})
    session.proposals[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectProposal, {})
    session.proposals[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticProposal, {})
    session.audit_report = provider._generate_default(AuditReport, {})
    session.defenses[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectDefense, {})
    session.defenses[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticDefense, {})
    session.deliberation_synthesis = provider._generate_default(DeliberationSynthesis, {})
    session.decision_record = provider._generate_default(DecisionRecord, {})
    session.learning_report = provider._generate_default(LearningReport, {})
    return session


def test_evaluate_proposal_divergence_high(base_session: Session) -> None:
    """Distinct solutions with different complexity and effort achieve high divergence."""
    score_obj, findings = evaluate_proposal_divergence(base_session)
    assert score_obj.score >= 4.5
    assert score_obj.passed is True
    assert len(score_obj.evidence) >= 3
    assert len(findings) == 0


def test_evaluate_proposal_divergence_missing_proposals() -> None:
    """Missing proposals yield 0 score and finding."""
    session = Session(session_id=uuid4())
    score_obj, findings = evaluate_proposal_divergence(session)
    assert score_obj.score == 0.0
    assert score_obj.passed is False
    assert len(findings) == 1


def test_evaluate_proposal_divergence_false_conflict(base_session: Session) -> None:
    """Proposals with identical architecture and high text overlap trigger false conflict finding."""
    base_session.proposals[CommitteeRole.ARCHITECT] = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Modular Monolith with Celery Workers",
        solution="Single deployable Python service using Postgres and Celery for async processing.",
        rationale="Maximizes time-to-value by delivering in 10 days with minimal operational complexity.",
        benefits=["Immediate delivery"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$35/mo"),
        risks=["Database connection saturation"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Easily swappable"),
        future_implications="Scale to redis later",
        assumptions=["Postgres handles queue"],
        invalidation_conditions=["Traffic exceeds 2000 req/s"],
    )
    score_obj, findings = evaluate_proposal_divergence(base_session)
    assert score_obj.score <= 2.0
    assert score_obj.passed is False
    assert any(f.id == "F-DIV-FALSE-CONFLICT" for f in findings)


def test_evaluate_assumption_coverage(base_session: Session) -> None:
    """Proposals referencing context assumptions receive high coverage score."""
    score_obj, findings = evaluate_assumption_coverage(base_session)
    assert score_obj.score >= 4.0
    assert score_obj.passed is True


def test_evaluate_risk_coverage(base_session: Session) -> None:
    """Audit report covering SPOFs, hidden costs, and fragile assumptions achieves 5/5."""
    score_obj, findings = evaluate_risk_coverage(base_session)
    assert score_obj.score == 5.0
    assert score_obj.passed is True


def test_evaluate_adversarial_quality_strong_vs_superficial(base_session: Session) -> None:
    """Strong audit report scores 5/5, whereas empty findings score 1/5."""
    score_strong, findings_strong = evaluate_adversarial_quality(base_session)
    assert score_strong.score == 5.0
    assert len(findings_strong) == 0

    base_session.audit_report = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[],
        findings_proposal_b=[],
    )
    score_weak, findings_weak = evaluate_adversarial_quality(base_session)
    assert score_weak.score == 1.0
    assert score_weak.passed is False
    assert any(f.id == "F-ADV-NO-FINDINGS" for f in findings_weak)


def test_evaluate_defense_responsiveness(base_session: Session) -> None:
    """Defenses responding to all audit findings receive high responsiveness score."""
    score_obj, findings = evaluate_defense_responsiveness(base_session)
    assert score_obj.score == 5.0
    assert score_obj.passed is True


def test_evaluate_synthesis_neutrality_failure_on_bias(base_session: Session) -> None:
    """Synthesis containing explicit recommendation fails neutrality with score 0."""
    score_neutral, findings_neutral = evaluate_synthesis_neutrality(base_session)
    assert score_neutral.score == 5.0
    assert score_neutral.passed is True

    base_session.deliberation_synthesis = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consensus_points=["Recomendo a proposta B como vencedora."],
    )
    score_biased, findings_biased = evaluate_synthesis_neutrality(base_session)
    assert score_biased.score == 0.0
    assert score_biased.passed is False
    assert any(f.severity == Severity.CRITICAL for f in findings_biased)


def test_evaluate_trade_off_explicitness(base_session: Session) -> None:
    """Explicit trade-off contracts score 5/5."""
    score_obj, findings = evaluate_trade_off_explicitness(base_session)
    assert score_obj.score == 5.0
    assert score_obj.passed is True


def test_evaluate_decision_traceability(base_session: Session) -> None:
    """Traceable decision scores 5/5; unreferenced alternative fails with 1/5."""
    score_valid, findings_valid = evaluate_decision_traceability(base_session)
    assert score_valid.score == 5.0
    assert score_valid.passed is True

    # Invent unvetted alternative
    base_session.decision_record = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        recommendation="Magic box solution.",
        chosen_alternative="PROPOSAL_MAGIC_BOX_NEVER_DISCUSSED",
        rationale="Comprehensive rationale for unvetted magic option.",
        trade_offs=base_session.decision_record.trade_offs,
        review_triggers=base_session.decision_record.review_triggers,
        confidence=base_session.decision_record.confidence,
    )
    score_invalid, findings_invalid = evaluate_decision_traceability(base_session)
    assert score_invalid.score == 1.0
    assert score_invalid.passed is False
    assert any(f.id == "F-TRC-UNTRACEABLE-ALTERNATIVE" for f in findings_invalid)


def test_evaluate_debt_explicitness(base_session: Session) -> None:
    """Documenting both technical and operational debt scores 5/5."""
    score_obj, findings = evaluate_debt_explicitness(base_session)
    assert score_obj.score == 5.0
    assert score_obj.passed is True


def test_evaluate_reviewability(base_session: Session) -> None:
    """Objective review triggers score 5/5."""
    score_obj, findings = evaluate_reviewability(base_session)
    assert score_obj.score == 5.0
    assert score_obj.passed is True


def test_evaluate_learning_value_grounded_vs_generic(base_session: Session) -> None:
    """Grounded learning report scores 5/5; generic buzzwords without evidence score 1.5/5."""
    score_good, findings_good = evaluate_learning_value(base_session)
    assert score_good.score == 5.0
    assert score_good.passed is True

    # Make mentor generic
    base_session.learning_report = LearningReport(
        artifact_id="LRN-001",
        version=1,
        concepts=["Architecture", "Databases"],
        concepts_required_to_understand_decision=["General software concepts"],
        observed_knowledge_gaps=[
            ObservedKnowledgeGap(
                observation="Needs training on systems",
                context_evidence="No specific evidence recorded in dialogue.",
                recommended_topic="Topic",
            )
        ],
        study_questions=["Study questions?"],
        learning_path=[
            LearningPathStep(
                order=1,
                topic="Topic",
                description="Study topic description.",
            )
        ],
        theory_to_practice_connections=["General connection text without mentioning any trade-off."],
        references=[
            LearningReference(title="Book", url_or_citation="Citation")
        ],
    )
    score_generic, findings_generic = evaluate_learning_value(base_session)
    assert score_generic.score <= 2.0
    assert score_generic.passed is False
    assert any(f.id == "F-LRN-GENERIC" for f in findings_generic)


def test_evaluate_human_sovereignty(base_session: Session) -> None:
    """Human sovereignty criterion scores 5/5 for consultative recommendations."""
    score_obj, findings = evaluate_human_sovereignty(base_session)
    assert score_obj.score == 5.0
    assert score_obj.passed is True
