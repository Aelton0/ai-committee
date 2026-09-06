"""Finite State Machine driving deterministic deliberation transitions."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from schemas.common import CommitteeRole, CommitteeState, EventType
from schemas.events import EventEnvelope, SessionCreatedPayload
from src.committee.event_store import EventStore
from src.committee.session import Session
from src.committee.transitions import find_transition_rule


class CommitteeError(Exception):
    """Base exception for AI Committee operational failures."""


class InvalidTransitionError(CommitteeError):
    """Raised when an event is submitted that is not allowed from the current state."""


class QualityGateFailedError(CommitteeError):
    """Raised when a process Quality Gate rejects the transition."""


class SessionNotFoundError(CommitteeError):
    """Raised when referencing a session that does not exist in the store."""


class TransitionResult(BaseModel):
    """Outcome of successfully executing a state transition."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    from_state: CommitteeState
    to_state: CommitteeState
    event: EventEnvelope
    session: Session
    gate_name: str


class StateMachine:
    """Deterministic, un-opinionated engine governing committee state transitions.

    Never invokes LLMs, executes prompts, or accepts free-form textual decisions.
    """

    def __init__(self, event_store: EventStore) -> None:
        self.event_store = event_store

    def create_session(
        self, session_id: UUID, problem_statement: str, user_id: str | None = None
    ) -> Session:
        """Instantiate a new session in DRAFT and immediately transition to INVESTIGATION."""
        session = Session(session_id=session_id, current_state=CommitteeState.DRAFT)
        payload = SessionCreatedPayload(
            problem_statement=problem_statement,
            user_id=user_id,
        )
        envelope = EventEnvelope(
            session_id=session_id,
            event_type=EventType.SESSION_CREATED,
            actor=CommitteeRole.HUMAN_USER,
            payload=payload,
        )
        self.handle_event(session, envelope)
        return session

    def handle_event(self, session: Session, envelope: EventEnvelope) -> TransitionResult:
        """Process a validated event envelope through the transition table and gates.

        1. Verifies that the event is compatible with the current session state.
        2. Evaluates the mandatory Quality Gate.
        3. Persists the event atomically in the append-only event store.
        4. Updates the logical session projection.
        """
        from_state = session.current_state
        rule = find_transition_rule(from_state, envelope.event_type)

        if not rule:
            raise InvalidTransitionError(
                f"Invalid transition: No transition defined from state '{from_state.value}' "
                f"via event '{envelope.event_type.value}'."
            )

        # 2. Evaluate Quality Gate
        gate_res = rule.gate(session, envelope)
        if not gate_res.passed:
            raise QualityGateFailedError(
                f"Quality gate '{gate_res.gate_name}' rejected transition: {gate_res.reason}"
            )

        # 3. Resolve Target State
        if callable(rule.to_state):
            to_state = rule.to_state(session, envelope)
        else:
            to_state = rule.to_state

        # 4. Atomic Persistence in Append-Only Store
        self.event_store.append(envelope)

        # 5. Apply Mutation to Session Projection
        session.apply_event(envelope, to_state)

        return TransitionResult(
            from_state=from_state,
            to_state=to_state,
            event=envelope,
            session=session,
            gate_name=gate_res.gate_name,
        )
