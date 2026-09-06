"""Deterministic session replay and state reconstruction from append-only events."""

from uuid import UUID

from schemas.common import CommitteeState
from src.committee.event_store import EventStore
from src.committee.session import Session
from src.committee.state_machine import (
    InvalidTransitionError,
    QualityGateFailedError,
    SessionNotFoundError,
)
from src.committee.transitions import find_transition_rule


def replay_session(session_id: UUID, event_store: EventStore) -> Session:
    """Reconstruct session state deterministically by replaying its historical events.

    1. Retrieves all events in recorded sequence order.
    2. Starts from DRAFT state.
    3. Re-evaluates transitions and process quality gates step-by-step.
    4. Produces an exact, auditable session projection.
    """
    events = event_store.get_events(session_id)
    if not events:
        raise SessionNotFoundError(f"No events found in event store for session '{session_id}'.")

    session = Session(session_id=session_id, current_state=CommitteeState.DRAFT)

    for i, envelope in enumerate(events, start=1):
        rule = find_transition_rule(session.current_state, envelope.event_type)
        if not rule:
            raise InvalidTransitionError(
                f"Replay integrity error at step {i} (event {envelope.event_id}): "
                f"No transition permitted from state '{session.current_state.value}' "
                f"via event '{envelope.event_type.value}'."
            )

        gate_res = rule.gate(session, envelope)
        if not gate_res.passed:
            raise QualityGateFailedError(
                f"Replay gate failure at step {i}: Quality gate '{gate_res.gate_name}' "
                f"rejected event '{envelope.event_type.value}': {gate_res.reason}"
            )

        if callable(rule.to_state):
            to_state = rule.to_state(session, envelope)
        else:
            to_state = rule.to_state

        session.apply_event(envelope, to_state)

    return session
