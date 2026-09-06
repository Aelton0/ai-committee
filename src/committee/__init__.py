"""AI Committee deterministic state machine, append-only event store, and process gates."""

from src.committee.event_store import (
    DuplicateEventError,
    EventStore,
    EventStoreError,
    ImmutableEventStoreViolationError,
    compute_canonical_hash,
)
from src.committee.gates import (
    GateFunction,
    QualityGateResult,
)
from src.committee.replay import replay_session
from src.committee.session import Session
from src.committee.state_machine import (
    CommitteeError,
    InvalidTransitionError,
    QualityGateFailedError,
    SessionNotFoundError,
    StateMachine,
    TransitionResult,
)
from src.committee.transitions import (
    TRANSITION_RULES,
    TransitionRule,
    find_transition_rule,
)

__all__ = [
    # Event Store
    "EventStore",
    "EventStoreError",
    "DuplicateEventError",
    "ImmutableEventStoreViolationError",
    "compute_canonical_hash",
    # Session
    "Session",
    # State Machine
    "StateMachine",
    "CommitteeError",
    "InvalidTransitionError",
    "QualityGateFailedError",
    "SessionNotFoundError",
    "TransitionResult",
    # Replay
    "replay_session",
    # Transitions & Gates
    "TransitionRule",
    "TRANSITION_RULES",
    "find_transition_rule",
    "QualityGateResult",
    "GateFunction",
]
