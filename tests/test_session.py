"""Unit tests for the Session logical state projection."""

from uuid import uuid4

from schemas.common import CommitteeRole, CommitteeState, EventType
from schemas.context import OpenQuestion, ProblemContext
from schemas.events import EventEnvelope, PhaseRollbackPayload, SessionCreatedPayload
from schemas.intervention import UserRespondCommand
from src.committee.session import Session


def test_session_initial_state() -> None:
    """Test initial Session properties."""
    session_id = uuid4()
    session = Session(session_id=session_id)
    assert session.session_id == session_id
    assert session.current_state == CommitteeState.DRAFT
    assert session.current_phase == "DRAFT"
    assert session.version == 1
    assert not session.has_both_proposals()
    assert not session.has_both_defenses()


def test_session_apply_event_advances_version_and_phase() -> None:
    """Test applying an event updates state, phase, and increments version."""
    session_id = uuid4()
    session = Session(session_id=session_id)

    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_CREATED,
        actor=CommitteeRole.HUMAN_USER,
        payload=SessionCreatedPayload(problem_statement="Test Problem"),
    )
    session.apply_event(env, CommitteeState.INVESTIGATION)

    assert session.current_state == CommitteeState.INVESTIGATION
    assert session.current_phase == "PHASE_0_INVESTIGATION"
    assert session.version == 2


def test_session_user_response_updates_open_question() -> None:
    """Test that applying UserRespondCommand marks open question as answered."""
    session_id = uuid4()
    session = Session(session_id=session_id)

    ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Test Problem",
        success_criteria=["Success 1"],
        open_questions=[
            OpenQuestion(id="Q1", question="What is latency goal?", why_critical="Architecture sizing")
        ],
    )
    env_ctx = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=ctx,
    )
    session.apply_event(env_ctx, CommitteeState.INVESTIGATION)
    assert session.problem_context is not None
    assert session.problem_context.has_unanswered_questions()

    # User answers Q1
    cmd = UserRespondCommand(
        session_id=session_id,
        question_id="Q1",
        answer="Under 50ms",
    )
    env_ans = EventEnvelope(
        session_id=session_id,
        event_type=EventType.USER_RESPONDED,
        actor=CommitteeRole.HUMAN_USER,
        payload=cmd,
    )
    session.apply_event(env_ans, CommitteeState.INVESTIGATION)
    assert session.problem_context is not None
    assert not session.problem_context.has_unanswered_questions()


def test_session_rollback_tracking() -> None:
    """Test that applying a rollback records entry into rollback_history."""
    session_id = uuid4()
    session = Session(session_id=session_id, current_state=CommitteeState.CONFRONTATION)

    rollback_payload = PhaseRollbackPayload(
        from_phase="PHASE_2_CONFRONTATION",
        to_phase="PHASE_0_INVESTIGATION",
        reason="Assumptions invalidated",
        superseded_artifacts=["PROP-ARCH-001:v1"],
    )
    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.PHASE_ROLLBACK,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=rollback_payload,
    )
    session.apply_event(env, CommitteeState.INVESTIGATION)

    assert session.current_state == CommitteeState.INVESTIGATION
    assert len(session.rollback_history) == 1
    assert session.rollback_history[0]["reason"] == "Assumptions invalidated"
