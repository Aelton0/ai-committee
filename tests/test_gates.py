"""Unit tests for deterministic Quality Gates."""

from uuid import uuid4

import pytest

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, CommitteeState, Confidence, DecisionStatus, EventType, Severity
from schemas.context import OpenQuestion, ProblemContext
from schemas.decision import DecisionRecord, ReviewTrigger, TradeOffContract
from schemas.defense import ArchitectDefense, CritiqueResponse, DefenseStance, ProposalAction
from schemas.events import EventEnvelope, PhaseRollbackPayload, UserOverridePayload
from schemas.intervention import UserAbortCommand
from schemas.learning import LearningPathStep, LearningReference, LearningReport
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from schemas.synthesis import DeliberationSynthesis
from src.committee.gates import (
    gate_confrontation_exit,
    gate_convergence_exit,
    gate_decision_exit,
    gate_divergence_proposal,
    gate_investigation_exit,
    gate_reflection_exit,
    gate_rollback,
    gate_user_override,
)
from src.committee.session import Session


@pytest.fixture
def session_id():
    return uuid4()


@pytest.fixture
def session(session_id):
    return Session(session_id=session_id)


def test_gate_investigation_exit_blocks_unanswered_questions(session, session_id) -> None:
    """Test Gate 0 blocks transition when open questions remain unanswered."""
    ctx_with_unanswered = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Test problem",
        success_criteria=["Success 1"],
        open_questions=[OpenQuestion(id="Q1", question="Missing requirement?", why_critical="Blocker")],
    )
    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=ctx_with_unanswered,
    )
    result = gate_investigation_exit(session, env)
    assert not result.passed
    assert "open question(s) remain unanswered" in (result.reason or "")

    # Now with questions answered
    ctx_answered = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Test problem",
        success_criteria=["Success 1"],
        open_questions=[OpenQuestion(id="Q1", question="Missing requirement?", why_critical="Blocker", answer="Resolved")],
    )
    env_answered = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=ctx_answered,
    )
    result_answered = gate_investigation_exit(session, env_answered)
    assert result_answered.passed


def test_gate_divergence_proposal_enforces_author_role(session, session_id) -> None:
    """Test Gate 1 verifies actor matches proposal proponent_role."""
    prop = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Valid Proposal",
        solution="Solution string long enough.",
        rationale="Rationale string long enough.",
        benefits=["Benefit 1"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$10"),
        risks=["Risk 1"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="No future issues",
        assumptions=["Assumption 1"],
        invalidation_conditions=["Condition 1"],
    )
    # Actor PRAGMATIST submitting ArchitectProposal must fail gate
    env_mismatch = EventEnvelope(
        session_id=session_id,
        event_type=EventType.PROPOSAL_CREATED,
        actor=CommitteeRole.PRAGMATIST,
        payload=prop,
    )
    res_mismatch = gate_divergence_proposal(session, env_mismatch)
    assert not res_mismatch.passed
    assert "does not match proposal proponent_role" in (res_mismatch.reason or "")


def test_gate_confrontation_exit_requires_both_proposals(session, session_id) -> None:
    """Test Gate 2 requires both proposals to have been registered before audit is accepted."""
    audit = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
    )
    env_audit = EventEnvelope(
        session_id=session_id,
        event_type=EventType.AUDIT_COMPLETED,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=audit,
    )
    # Fails because session does not have both proposals
    res = gate_confrontation_exit(session, env_audit)
    assert not res.passed
    assert "both Architect and Pragmatic proposals registered" in (res.reason or "")


def test_gate_decision_exit_requires_synthesis(session, session_id) -> None:
    """Test Gate 5 requires deliberation synthesis before decision can be recorded."""
    dec = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        rationale="Missing load test data.",
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Load tests"],
    )
    env_dec = EventEnvelope(
        session_id=session_id,
        event_type=EventType.DECISION_FAILED,
        actor=CommitteeRole.DECISOR,
        payload=dec,
    )
    # Fails because session.deliberation_synthesis is None
    res = gate_decision_exit(session, env_dec)
    assert not res.passed
    assert "before deliberation synthesis is established" in (res.reason or "")


def test_gate_rollback_only_from_allowed_phases(session, session_id) -> None:
    """Test Gate Rollback only allows rollback from CONFRONTATION or DEFENSE."""
    session.current_state = CommitteeState.INVESTIGATION
    rollback_payload = PhaseRollbackPayload(
        from_phase="PHASE_2_CONFRONTATION",
        to_phase="PHASE_0_INVESTIGATION",
        reason="Baseline assumption flawed",
    )
    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.PHASE_ROLLBACK,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=rollback_payload,
    )
    res = gate_rollback(session, env)
    assert not res.passed

    # Allowed from CONFRONTATION
    session.current_state = CommitteeState.CONFRONTATION
    res_allowed = gate_rollback(session, env)
    assert res_allowed.passed
