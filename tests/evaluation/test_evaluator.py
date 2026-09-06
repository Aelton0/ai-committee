"""Unit tests verifying DeterministicEvaluator execution, score aggregation, and report generation."""

from uuid import uuid4
import pytest

from schemas.common import CommitteeRole, CommitteeState, DecisionStatus
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.learning import LearningReport
from schemas.proposals import ArchitectProposal, PragmaticProposal
from schemas.synthesis import DeliberationSynthesis
from src.committee.evaluation.evaluator import DeterministicEvaluator
from src.committee.evaluation.models import EvaluationCriterion, EvaluationMetadata, EvaluationResult
from src.committee.llm.mock import MockLLMProvider
from src.committee.session import Session


@pytest.fixture
def completed_session() -> Session:
    """Fixture providing a completed deliberation session from MockLLMProvider."""
    provider = MockLLMProvider()
    session = Session(session_id=uuid4(), current_state=CommitteeState.COMPLETED)
    session.problem_context = provider._generate_default(ProblemContext, {})
    session.proposals[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectProposal, {})
    session.proposals[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticProposal, {})
    session.audit_report = provider._generate_default(ArchitectDefense, {})  # will be overridden
    session.audit_report = provider._generate_default(provider.__class__.__init__.__annotations__.get("AuditReport", None) or type(session.audit_report), {}) if hasattr(session, "foo") else provider._generate_default(type(session.audit_report), {})
    from schemas.audit import AuditReport
    session.audit_report = provider._generate_default(AuditReport, {})
    session.defenses[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectDefense, {})
    session.defenses[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticDefense, {})
    session.deliberation_synthesis = provider._generate_default(DeliberationSynthesis, {})
    session.decision_record = provider._generate_default(DecisionRecord, {})
    session.learning_report = provider._generate_default(LearningReport, {})
    return session


def test_deterministic_evaluator_evaluates_all_twelve_criteria(completed_session: Session) -> None:
    """DeterministicEvaluator produces scores for all 12 criteria."""
    evaluator = DeterministicEvaluator()
    meta = EvaluationMetadata(
        model="gemini-2.5-pro",
        prompt_version="v1.0",
        scenario_id="scenario-01-different-solutions",
    )
    result = evaluator.evaluate_session(completed_session, metadata=meta)

    assert isinstance(result, EvaluationResult)
    assert result.session_id == completed_session.session_id
    assert len(result.summary.criterion_scores) == 12

    # Check each criterion is represented
    for crit in EvaluationCriterion:
        assert crit in result.summary.criterion_scores
        score_obj = result.summary.criterion_scores[crit]
        assert 0.0 <= score_obj.score <= 5.0
        assert len(score_obj.evidence) >= 1

    # Check overall score is calculated correctly
    scores = [cs.score for cs in result.summary.criterion_scores.values()]
    expected_overall = round(sum(scores) / len(scores), 1)
    assert result.summary.overall_score == expected_overall
    assert result.summary.overall_score >= 4.0

    # Metadata checks
    assert result.metadata.model == "gemini-2.5-pro"
    assert result.metadata.prompt_version == "v1.0"
    assert result.metadata.scenario_id == "scenario-01-different-solutions"


def test_evaluator_does_not_mutate_session(completed_session: Session) -> None:
    """Evaluation must be strictly read-only and never alter session state or artifacts."""
    initial_version = completed_session.version
    initial_state = completed_session.current_state
    initial_prop_a_id = completed_session.proposals[CommitteeRole.ARCHITECT].artifact_id

    evaluator = DeterministicEvaluator()
    evaluator.evaluate_session(completed_session)

    assert completed_session.version == initial_version
    assert completed_session.current_state == initial_state
    assert completed_session.proposals[CommitteeRole.ARCHITECT].artifact_id == initial_prop_a_id


def test_evaluator_report_formatting(completed_session: Session) -> None:
    """format_report produces complete readable dossier."""
    evaluator = DeterministicEvaluator()
    meta = EvaluationMetadata(
        scenario_id="test-report-formatting",
        model="mock-provider-v1",
        prompt_version="1.0.0",
    )
    result = evaluator.evaluate_session(completed_session, metadata=meta)
    report = result.format_report()

    assert "AI COMMITTEE EVALUATION" in report
    assert "Overall Score:" in report
    assert "CRITERIA SCORES:" in report
    assert "Proposal Divergence" in report
    assert "Adversarial Quality" in report
    assert "Decision Traceability" in report
    assert "STRENGTHS:" in report
