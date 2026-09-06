"""Unit tests for the StateMachine orchestration and transition handling."""

from uuid import uuid4

import pytest

from schemas.common import CommitteeRole, CommitteeState, Confidence, DecisionStatus, EventType
from schemas.context import OpenQuestion, ProblemContext
from schemas.decision import DecisionRecord
from schemas.events import EventEnvelope, QuestionRaisedPayload, UserRespondedPayload
from src.committee.event_store import EventStore
from src.committee.state_machine import (
    InvalidTransitionError,
    QualityGateFailedError,
    StateMachine,
)


@pytest.fixture
def temp_db(tmp_path):
    store = EventStore(tmp_path / "test_sm.db")
    yield store
    store.close()


@pytest.fixture
def state_machine(temp_db):
    return StateMachine(temp_db)


def test_create_session(state_machine, temp_db) -> None:
    """Test creating session transitions from DRAFT to INVESTIGATION and persists event."""
    session_id = uuid4()
    session = state_machine.create_session(
        session_id=session_id,
        problem_statement="How should we scale payment notifications?",
        user_id="user_123",
    )

    assert session.session_id == session_id
    assert session.current_state == CommitteeState.INVESTIGATION
    assert session.current_phase == "PHASE_0_INVESTIGATION"
    assert temp_db.count_events(session_id) == 1

    last_event = temp_db.get_last_event(session_id)
    assert last_event is not None
    assert last_event.event_type == EventType.SESSION_CREATED


def test_question_clarification_cycle(state_machine, temp_db) -> None:
    """Test pausing for user in WAITING_FOR_USER and resuming upon USER_RESPONDED."""
    session_id = uuid4()
    session = state_machine.create_session(session_id, "Problem description.")

    # Facilitator raises an open question
    question = OpenQuestion(
        id="Q1",
        question="What is the expected requests/sec?",
        why_critical="Need to estimate queue buffer sizes.",
    )
    env_q = EventEnvelope(
        session_id=session_id,
        event_type=EventType.QUESTION_RAISED,
        actor=CommitteeRole.FACILITATOR,
        payload=QuestionRaisedPayload(question=question),
    )
    res_q = state_machine.handle_event(session, env_q)
    assert res_q.to_state == CommitteeState.WAITING_FOR_USER
    assert session.current_state == CommitteeState.WAITING_FOR_USER

    # User responds to question
    env_ans = EventEnvelope(
        session_id=session_id,
        event_type=EventType.USER_RESPONDED,
        actor=CommitteeRole.HUMAN_USER,
        payload=UserRespondedPayload(question_id="Q1", answer="500 req/s peak"),
    )
    res_ans = state_machine.handle_event(session, env_ans)
    assert res_ans.to_state == CommitteeState.INVESTIGATION
    assert session.current_state == CommitteeState.INVESTIGATION
    assert temp_db.count_events(session_id) == 3


def test_invalid_transition_rejected(state_machine, temp_db) -> None:
    """Negative test: Submitting DECISION_FAILED directly from INVESTIGATION must fail."""
    session_id = uuid4()
    session = state_machine.create_session(session_id, "Problem statement.")

    dec = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        rationale="Premature decision attempt.",
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Everything"],
    )
    illegal_env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.DECISION_FAILED,
        actor=CommitteeRole.DECISOR,
        payload=dec,
    )

    with pytest.raises(InvalidTransitionError, match="No transition defined"):
        state_machine.handle_event(session, illegal_env)

    # Verify session state and event count were not affected
    assert session.current_state == CommitteeState.INVESTIGATION
    assert temp_db.count_events(session_id) == 1


def test_quality_gate_failure_aborts_without_persistence(state_machine, temp_db) -> None:
    """Negative test: When a Quality Gate fails, event is not saved and state does not advance."""
    session_id = uuid4()
    session = state_machine.create_session(session_id, "Problem statement.")

    # Try to validate context with unanswered questions
    invalid_ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Problem text.",
        success_criteria=["SLA < 100ms"],
        open_questions=[OpenQuestion(id="Q1", question="Missing", why_critical="Blocker")],
    )
    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=invalid_ctx,
    )

    with pytest.raises(QualityGateFailedError, match="GateInvestigationExit"):
        state_machine.handle_event(session, env)

    assert session.current_state == CommitteeState.INVESTIGATION
    assert temp_db.count_events(session_id) == 1
