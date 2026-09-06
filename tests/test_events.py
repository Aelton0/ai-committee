"""Unit tests for EventEnvelope and payload validation."""

from uuid import uuid4

from pydantic import ValidationError
import pytest

from schemas.audit import AuditReport
from schemas.common import (
    CommitteeRole,
    Confidence,
    DecisionStatus,
    EventType,
    Severity,
)
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord, ReviewTrigger, TradeOffContract
from schemas.events import (
    EventEnvelope,
    PhaseRollbackPayload,
    SessionCreatedPayload,
)
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    ReversibilityAssessment,
    ReversibilityLevel,
)


@pytest.fixture
def session_id():
    return uuid4()


@pytest.fixture
def valid_problem_context():
    return ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Valid problem description.",
        success_criteria=["Criteria 1"],
    )


@pytest.fixture
def valid_architect_proposal():
    return ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Microservices architecture",
        solution="Decoupled services with Kafka streaming",
        rationale="Maximizes modularity across teams",
        benefits=["High decoupling"],
        costs=CostEstimate(implementation_effort=EffortLevel.HIGH, infrastructure_cost_estimate="$150/mo"),
        risks=["Tracing complexity"],
        complexity=Severity.HIGH,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.LOW, rationale="Hard rollback"),
        future_implications="Scale to 10k req/s",
        assumptions=["Team learns Kafka"],
        invalidation_conditions=["Volume stays under 10 req/s"],
    )


def test_valid_session_created_event(session_id) -> None:
    """Test valid SESSION_CREATED event envelope."""
    payload = SessionCreatedPayload(problem_statement="Need to redesign checkout service.")
    envelope = EventEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_CREATED,
        actor=CommitteeRole.HUMAN_USER,
        payload=payload,
    )
    assert envelope.event_type == EventType.SESSION_CREATED
    assert envelope.actor == CommitteeRole.HUMAN_USER


def test_valid_context_validated_event(session_id, valid_problem_context) -> None:
    """Test valid CONTEXT_VALIDATED event with matching artifact metadata."""
    envelope = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        artifact_id="CTX-001",
        artifact_version="v1",
        payload=valid_problem_context,
    )
    assert envelope.artifact_id == "CTX-001"
    assert envelope.artifact_version == "v1"


def test_valid_proposal_created_event(session_id, valid_architect_proposal) -> None:
    """Test valid PROPOSAL_CREATED event."""
    envelope = EventEnvelope(
        session_id=session_id,
        event_type=EventType.PROPOSAL_CREATED,
        actor=CommitteeRole.ARCHITECT,
        artifact_id="PROP-ARCH-001",
        artifact_version="v1",
        payload=valid_architect_proposal,
    )
    assert envelope.event_type == EventType.PROPOSAL_CREATED


def test_valid_decision_events(session_id) -> None:
    """Test DECISION_RECORDED and DECISION_FAILED payload status enforcement."""
    rec_record = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        recommendation="Recommended solution",
        chosen_alternative="ALT_A",
        rationale="Thorough rationale for the recommendation.",
        confidence=Confidence.HIGH,
        trade_offs=[TradeOffContract(gain="speed", sacrifice="coupling")],
        review_triggers=[ReviewTrigger(condition="traffic > 1000 req/s")],
    )
    # Correct status for DECISION_RECORDED
    envelope_rec = EventEnvelope(
        session_id=session_id,
        event_type=EventType.DECISION_RECORDED,
        actor=CommitteeRole.DECISOR,
        payload=rec_record,
    )
    assert envelope_rec.event_type == EventType.DECISION_RECORDED

    # Incompatible status for DECISION_RECORDED must fail
    insufficient_record = DecisionRecord(
        artifact_id="DEC-002",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        rationale="Missing critical info to make decision.",
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Need load test data"],
    )
    with pytest.raises(ValidationError, match="requires payload status to be 'RECOMMENDED'"):
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.DECISION_RECORDED,
            actor=CommitteeRole.DECISOR,
            payload=insufficient_record,
        )

    # Correct status for DECISION_FAILED
    envelope_fail = EventEnvelope(
        session_id=session_id,
        event_type=EventType.DECISION_FAILED,
        actor=CommitteeRole.DECISOR,
        payload=insufficient_record,
    )
    assert envelope_fail.event_type == EventType.DECISION_FAILED


def test_incompatible_payload_type_fails(session_id, valid_architect_proposal) -> None:
    """Test that passing a Proposal payload to AUDIT_COMPLETED fails validation."""
    with pytest.raises(ValidationError, match="incompatible with event"):
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.AUDIT_COMPLETED,  # Expects AuditReport
            actor=CommitteeRole.AUDITOR_SRE,
            payload=valid_architect_proposal,  # Wrong payload type!
        )


def test_artifact_id_mismatch_fails(session_id, valid_problem_context) -> None:
    """Test that envelope artifact_id must match payload artifact_id."""
    with pytest.raises(ValidationError, match="does not match payload artifact_id"):
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.CONTEXT_VALIDATED,
            actor=CommitteeRole.FACILITATOR,
            artifact_id="WRONG-ID-999",  # Mismatch with CTX-001
            payload=valid_problem_context,
        )


def test_artifact_version_mismatch_fails(session_id, valid_problem_context) -> None:
    """Test that envelope artifact_version must match payload version."""
    with pytest.raises(ValidationError, match="does not match payload version"):
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.CONTEXT_VALIDATED,
            actor=CommitteeRole.FACILITATOR,
            artifact_version="v2",  # Mismatch with CTX-001 (version=1, i.e. v1)
            payload=valid_problem_context,
        )


def test_phase_rollback_event(session_id) -> None:
    """Test PHASE_ROLLBACK event envelope."""
    payload = PhaseRollbackPayload(
        from_phase="PHASE_2_CONFRONTATION",
        to_phase="PHASE_0_INVESTIGATION",
        reason="Discovered fundamental offline requirement invalidated streaming assumption.",
        superseded_artifacts=["PROP-ARCH-001:v1", "PROP-PRAG-001:v1"],
    )
    envelope = EventEnvelope(
        session_id=session_id,
        event_type=EventType.PHASE_ROLLBACK,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=payload,
    )
    assert envelope.event_type == EventType.PHASE_ROLLBACK
