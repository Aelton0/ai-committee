"""Typed transitions table governing state transitions and gate validations."""

from typing import Callable, Union

from pydantic import BaseModel, ConfigDict

from schemas.common import CommitteeRole, CommitteeState, EventType
from schemas.events import EventEnvelope, UserOverridePayload
from schemas.intervention import (
    UserAbortCommand,
    UserContestAssumptionCommand,
    UserRequestRevisionCommand,
)
from schemas.proposals import BaseProposal
from src.committee.gates import (
    GateFunction,
    gate_confrontation_exit,
    gate_convergence_exit,
    gate_critical_error,
    gate_decision_exit,
    gate_defense_submission,
    gate_divergence_proposal,
    gate_investigation_exit,
    gate_question_raised,
    gate_reflection_exit,
    gate_rollback,
    gate_session_cancelled,
    gate_session_creation,
    gate_user_override,
    gate_user_respond,
)
from src.committee.session import Session

TargetStateResolver = Callable[[Session, EventEnvelope], CommitteeState]
TargetState = Union[CommitteeState, TargetStateResolver]


class TransitionRule(BaseModel):
    """Declarative definition of a valid state transition with its quality gate."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    from_state: CommitteeState
    event_type: EventType
    to_state: TargetState
    gate: GateFunction
    description: str


def resolve_divergence_target_state(session: Session, envelope: EventEnvelope) -> CommitteeState:
    """When a proposal arrives, transition to CONFRONTATION only if both proposals are ready."""
    payload = envelope.payload
    if isinstance(payload, BaseProposal):
        other_role = (
            CommitteeRole.PRAGMATIST
            if payload.proponent_role == CommitteeRole.ARCHITECT
            else CommitteeRole.ARCHITECT
        )
        if other_role in session.proposals:
            return CommitteeState.CONFRONTATION
    return CommitteeState.DIVERGENCE


def resolve_defense_target_state(session: Session, envelope: EventEnvelope) -> CommitteeState:
    """When a defense arrives, transition to CONVERGENCE only if both defenses are ready."""
    payload = envelope.payload
    if hasattr(payload, "proponent_role"):
        other_role = (
            CommitteeRole.PRAGMATIST
            if payload.proponent_role == CommitteeRole.ARCHITECT
            else CommitteeRole.ARCHITECT
        )
        if other_role in session.defenses:
            return CommitteeState.CONVERGENCE
    return CommitteeState.DEFENSE


def resolve_user_override_target_state(session: Session, envelope: EventEnvelope) -> CommitteeState:
    """Determine target state depending on the human intervention command type."""
    if isinstance(envelope.payload, UserOverridePayload):
        cmd = envelope.payload.intervention
        if isinstance(cmd, UserAbortCommand):
            return CommitteeState.CANCELLED
        elif isinstance(cmd, UserRequestRevisionCommand):
            return CommitteeState.DIVERGENCE
        elif isinstance(cmd, UserContestAssumptionCommand):
            return session.current_state
    return session.current_state


TRANSITION_RULES: list[TransitionRule] = [
    # 1. Session Initialization
    TransitionRule(
        from_state=CommitteeState.DRAFT,
        event_type=EventType.SESSION_CREATED,
        to_state=CommitteeState.INVESTIGATION,
        gate=gate_session_creation,
        description="Initialize draft session with user problem statement.",
    ),
    # 2. Questions & User Clarification
    TransitionRule(
        from_state=CommitteeState.INVESTIGATION,
        event_type=EventType.QUESTION_RAISED,
        to_state=CommitteeState.WAITING_FOR_USER,
        gate=gate_question_raised,
        description="Facilitator pauses deliberation to await missing user input.",
    ),
    TransitionRule(
        from_state=CommitteeState.WAITING_FOR_USER,
        event_type=EventType.USER_RESPONDED,
        to_state=CommitteeState.INVESTIGATION,
        gate=gate_user_respond,
        description="User supplies answers to open questions, returning to investigation.",
    ),
    TransitionRule(
        from_state=CommitteeState.INVESTIGATION,
        event_type=EventType.USER_RESPONDED,
        to_state=CommitteeState.INVESTIGATION,
        gate=gate_user_respond,
        description="User supplies answers while in investigation phase.",
    ),
    # 3. Context Validated -> Divergence
    TransitionRule(
        from_state=CommitteeState.INVESTIGATION,
        event_type=EventType.CONTEXT_VALIDATED,
        to_state=CommitteeState.DIVERGENCE,
        gate=gate_investigation_exit,
        description="ProblemContext validated and frozen in v1; opens Phase 1 Divergence.",
    ),
    # 4. Divergence Proposals (Architect & Pragmatic)
    TransitionRule(
        from_state=CommitteeState.DIVERGENCE,
        event_type=EventType.PROPOSAL_CREATED,
        to_state=resolve_divergence_target_state,
        gate=gate_divergence_proposal,
        description="Record independent proposals; advance to CONFRONTATION once both are present.",
    ),
    # 5. Confrontation Audit
    TransitionRule(
        from_state=CommitteeState.CONFRONTATION,
        event_type=EventType.AUDIT_COMPLETED,
        to_state=CommitteeState.DEFENSE,
        gate=gate_confrontation_exit,
        description="Auditor attacks vulnerabilities and SPOFs; opens Phase 3 Defense.",
    ),
    # 6. Rollback from Confrontation
    TransitionRule(
        from_state=CommitteeState.CONFRONTATION,
        event_type=EventType.PHASE_ROLLBACK,
        to_state=CommitteeState.INVESTIGATION,
        gate=gate_rollback,
        description="Fatal flaw in assumptions discovered by Auditor; controlled rollback to Phase 0.",
    ),
    # 7. Defense Submissions
    TransitionRule(
        from_state=CommitteeState.DEFENSE,
        event_type=EventType.DEFENSE_SUBMITTED,
        to_state=resolve_defense_target_state,
        gate=gate_defense_submission,
        description="Record proponent defenses; advance to CONVERGENCE once both are present.",
    ),
    # 8. Rollback from Defense
    TransitionRule(
        from_state=CommitteeState.DEFENSE,
        event_type=EventType.PHASE_ROLLBACK,
        to_state=CommitteeState.INVESTIGATION,
        gate=gate_rollback,
        description="Proponents identify irreconcilable baseline error; rollback to Phase 0.",
    ),
    # 9. Convergence Synthesis
    TransitionRule(
        from_state=CommitteeState.CONVERGENCE,
        event_type=EventType.SYNTHESIS_CREATED,
        to_state=CommitteeState.DECISION,
        gate=gate_convergence_exit,
        description="Facilitator compiles impartial synthesis; opens Phase 5 Decision.",
    ),
    # 10. Decision Outcomes
    TransitionRule(
        from_state=CommitteeState.DECISION,
        event_type=EventType.DECISION_RECORDED,
        to_state=CommitteeState.REFLECTION,
        gate=gate_decision_exit,
        description="Decisor issues RECOMMENDED decision with trade-offs; opens Phase 6 Reflection.",
    ),
    TransitionRule(
        from_state=CommitteeState.DECISION,
        event_type=EventType.DECISION_FAILED,
        to_state=CommitteeState.INSUFFICIENT_EVIDENCE,
        gate=gate_decision_exit,
        description="Decisor formally attests INSUFFICIENT_EVIDENCE without guessing a winner.",
    ),
    # 11. Reflection & Completion
    TransitionRule(
        from_state=CommitteeState.REFLECTION,
        event_type=EventType.LEARNING_REPORT_CREATED,
        to_state=CommitteeState.COMPLETED,
        gate=gate_reflection_exit,
        description="Mentor delivers pedagogical analysis and study guide; session completed.",
    ),
    # 12. Human Interventions (Universal or phase-specific)
    TransitionRule(
        from_state=CommitteeState.COMPLETED,
        event_type=EventType.USER_OVERRIDE,
        to_state=resolve_user_override_target_state,
        gate=gate_user_override,
        description="User requests revision after completion, triggering new divergence round.",
    ),
    TransitionRule(
        from_state=CommitteeState.INSUFFICIENT_EVIDENCE,
        event_type=EventType.USER_OVERRIDE,
        to_state=resolve_user_override_target_state,
        gate=gate_user_override,
        description="User injects missing facts to re-open deliberation from divergence.",
    ),
    # 13. Cancellation
    TransitionRule(
        from_state=CommitteeState.INVESTIGATION,
        event_type=EventType.SESSION_CANCELLED,
        to_state=CommitteeState.CANCELLED,
        gate=gate_session_cancelled,
        description="User aborts session during investigation.",
    ),
    TransitionRule(
        from_state=CommitteeState.WAITING_FOR_USER,
        event_type=EventType.SESSION_CANCELLED,
        to_state=CommitteeState.CANCELLED,
        gate=gate_session_cancelled,
        description="User aborts session while waiting for input.",
    ),
    TransitionRule(
        from_state=CommitteeState.DIVERGENCE,
        event_type=EventType.SESSION_CANCELLED,
        to_state=CommitteeState.CANCELLED,
        gate=gate_session_cancelled,
        description="User aborts session during divergence.",
    ),
    TransitionRule(
        from_state=CommitteeState.CONFRONTATION,
        event_type=EventType.SESSION_CANCELLED,
        to_state=CommitteeState.CANCELLED,
        gate=gate_session_cancelled,
        description="User aborts session during confrontation.",
    ),
    TransitionRule(
        from_state=CommitteeState.DEFENSE,
        event_type=EventType.SESSION_CANCELLED,
        to_state=CommitteeState.CANCELLED,
        gate=gate_session_cancelled,
        description="User aborts session during defense.",
    ),
    TransitionRule(
        from_state=CommitteeState.CONVERGENCE,
        event_type=EventType.SESSION_CANCELLED,
        to_state=CommitteeState.CANCELLED,
        gate=gate_session_cancelled,
        description="User aborts session during convergence.",
    ),
    TransitionRule(
        from_state=CommitteeState.DECISION,
        event_type=EventType.SESSION_CANCELLED,
        to_state=CommitteeState.CANCELLED,
        gate=gate_session_cancelled,
        description="User aborts session during decision.",
    ),
    TransitionRule(
        from_state=CommitteeState.REFLECTION,
        event_type=EventType.SESSION_CANCELLED,
        to_state=CommitteeState.CANCELLED,
        gate=gate_session_cancelled,
        description="User aborts session during reflection.",
    ),
]


def find_transition_rule(
    current_state: CommitteeState, event_type: EventType
) -> TransitionRule | None:
    """Find the specific transition rule registered for the state-event pair."""
    for rule in TRANSITION_RULES:
        if rule.from_state == current_state and rule.event_type == event_type:
            return rule
    return None
