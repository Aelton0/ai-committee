"""Unit tests for deterministic session replay and reconstruction."""

from uuid import uuid4

import pytest

from schemas.common import CommitteeRole, CommitteeState, EventType
from schemas.context import ProblemContext
from schemas.events import EventEnvelope
from src.committee.event_store import EventStore
from src.committee.replay import replay_session
from src.committee.state_machine import SessionNotFoundError, StateMachine


@pytest.fixture
def event_store(tmp_path):
    store = EventStore(tmp_path / "test_replay.db")
    yield store
    store.close()


def test_replay_session_matches_active_state(event_store) -> None:
    """Test replaying historical events yields exact same state projection."""
    sm = StateMachine(event_store)
    session_id = uuid4()

    # Step 1: Create session
    session = sm.create_session(session_id, "Replay test problem.")

    # Step 2: Validate context
    ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Replay test problem.",
        success_criteria=["Success 1"],
    )
    env_ctx = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=ctx,
    )
    sm.handle_event(session, env_ctx)
    assert session.current_state == CommitteeState.DIVERGENCE

    # Perform replay
    replayed = replay_session(session_id, event_store)

    assert replayed.session_id == session.session_id
    assert replayed.current_state == session.current_state
    assert replayed.current_phase == session.current_phase
    assert replayed.version == session.version
    assert replayed.problem_context is not None
    assert replayed.problem_context.artifact_id == "CTX-001"


def test_replay_nonexistent_session_fails(event_store) -> None:
    """Test replaying an unknown session raises SessionNotFoundError."""
    with pytest.raises(SessionNotFoundError):
        replay_session(uuid4(), event_store)
