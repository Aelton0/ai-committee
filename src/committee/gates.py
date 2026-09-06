"""Deterministic Quality Gates enforcing deliberation process rules."""

from typing import Callable

from pydantic import BaseModel

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState, DecisionStatus
from schemas.context import OpenQuestion, ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import BaseDefense
from schemas.events import EventEnvelope, PhaseRollbackPayload, UserOverridePayload, UserRespondedPayload
from schemas.intervention import UserAbortCommand, UserRequestRevisionCommand, UserRespondCommand
from schemas.learning import LearningReport
from schemas.proposals import BaseProposal
from schemas.synthesis import DeliberationSynthesis
from src.committee.session import Session


class QualityGateResult(BaseModel):
    """Result of evaluating a process quality gate."""

    passed: bool
    gate_name: str
    reason: str | None = None


# Type alias for Quality Gate functions
GateFunction = Callable[[Session, EventEnvelope], QualityGateResult]


def pass_gate(name: str) -> QualityGateResult:
    """Helper for passed gate."""
    return QualityGateResult(passed=True, gate_name=name)


def fail_gate(name: str, reason: str) -> QualityGateResult:
    """Helper for failed gate."""
    return QualityGateResult(passed=False, gate_name=name, reason=reason)


def gate_session_creation(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate 0-Init: Validates initial problem submission."""
    gate = "GateSessionCreation"
    if session.current_state != CommitteeState.DRAFT:
        return fail_gate(gate, f"Session already initialized (state: {session.current_state}).")
    return pass_gate(gate)


def gate_investigation_exit(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate 0: Validates that problem context is sound and has no open questions."""
    gate = "GateInvestigationExit"
    if not isinstance(envelope.payload, ProblemContext):
        return fail_gate(gate, "Payload must be a validated ProblemContext.")
    if envelope.actor != CommitteeRole.FACILITATOR:
        return fail_gate(gate, f"Only Facilitator can validate context (actor: {envelope.actor}).")
    if envelope.payload.has_unanswered_questions():
        unanswered = envelope.payload.unanswered_questions()
        return fail_gate(
            gate,
            f"Cannot advance to Divergence: {len(unanswered)} open question(s) remain unanswered.",
        )
    if not envelope.payload.success_criteria:
        return fail_gate(gate, "ProblemContext must specify at least one success criteria.")
    return pass_gate(gate)


def gate_question_raised(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate QuestionRaised: Validates Facilitator posing questions to user."""
    gate = "GateQuestionRaised"
    if envelope.actor != CommitteeRole.FACILITATOR:
        return fail_gate(gate, f"Only Facilitator can raise questions (actor: {envelope.actor}).")
    return pass_gate(gate)


def gate_user_respond(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate UserRespond: Validates user answering open questions."""
    gate = "GateUserRespond"
    if envelope.actor != CommitteeRole.HUMAN_USER:
        return fail_gate(gate, f"Only Human User can respond (actor: {envelope.actor}).")
    if session.current_state not in (CommitteeState.WAITING_FOR_USER, CommitteeState.INVESTIGATION):
        return fail_gate(
            gate, f"User responses only permitted in WAITING_FOR_USER or INVESTIGATION (state: {session.current_state})."
        )
    return pass_gate(gate)


def gate_divergence_proposal(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate 1-Entry: Validates submission of independent proposals in Phase 1."""
    gate = "GateDivergenceProposal"
    if not isinstance(envelope.payload, BaseProposal):
        return fail_gate(gate, "Payload must be a BaseProposal subclass.")
    if envelope.actor not in (CommitteeRole.ARCHITECT, CommitteeRole.PRAGMATIST):
        return fail_gate(gate, f"Only Architect or Pragmatist can submit proposals (actor: {envelope.actor}).")
    if envelope.actor != envelope.payload.proponent_role:
        return fail_gate(gate, "Envelope actor does not match proposal proponent_role.")
    return pass_gate(gate)


def gate_confrontation_exit(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate 2: Validates adversarial audit report covering both proposals."""
    gate = "GateConfrontationExit"
    if not isinstance(envelope.payload, AuditReport):
        return fail_gate(gate, "Payload must be an AuditReport.")
    if envelope.actor != CommitteeRole.AUDITOR_SRE:
        return fail_gate(gate, f"Only Auditor/SRE can submit AuditReport (actor: {envelope.actor}).")
    if not session.has_both_proposals():
        return fail_gate(gate, "Cannot perform audit without both Architect and Pragmatic proposals registered.")
    return pass_gate(gate)


def gate_defense_submission(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate 3-Entry: Validates proponent defense against audit findings."""
    gate = "GateDefenseSubmission"
    if not isinstance(envelope.payload, BaseDefense):
        return fail_gate(gate, "Payload must be a BaseDefense subclass.")
    if envelope.actor not in (CommitteeRole.ARCHITECT, CommitteeRole.PRAGMATIST):
        return fail_gate(gate, f"Only Architect or Pragmatist can submit defenses (actor: {envelope.actor}).")
    if envelope.actor != envelope.payload.proponent_role:
        return fail_gate(gate, "Envelope actor does not match defense proponent_role.")
    return pass_gate(gate)


def gate_convergence_exit(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate 4: Validates impartial synthesis prepared by Facilitator."""
    gate = "GateConvergenceExit"
    if not isinstance(envelope.payload, DeliberationSynthesis):
        return fail_gate(gate, "Payload must be a DeliberationSynthesis.")
    if envelope.actor != CommitteeRole.FACILITATOR:
        return fail_gate(gate, f"Only Facilitator can submit synthesis (actor: {envelope.actor}).")
    if not session.has_both_defenses():
        return fail_gate(gate, "Cannot synthesize deliberation before both proponents submit defenses.")
    return pass_gate(gate)


def gate_decision_exit(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate 5: Validates DecisionRecord formulated by Decisor."""
    gate = "GateDecisionExit"
    if not isinstance(envelope.payload, DecisionRecord):
        return fail_gate(gate, "Payload must be a DecisionRecord.")
    if envelope.actor != CommitteeRole.DECISOR:
        return fail_gate(gate, f"Only Decisor can submit decision record (actor: {envelope.actor}).")
    if session.deliberation_synthesis is None:
        return fail_gate(gate, "Decision cannot be recorded before deliberation synthesis is established.")
    return pass_gate(gate)


def gate_reflection_exit(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate 6: Validates pedagogical learning report prepared by Mentor."""
    gate = "GateReflectionExit"
    if not isinstance(envelope.payload, LearningReport):
        return fail_gate(gate, "Payload must be a LearningReport.")
    if envelope.actor != CommitteeRole.MENTOR:
        return fail_gate(gate, f"Only Mentor can submit learning report (actor: {envelope.actor}).")
    if session.decision_record is None:
        return fail_gate(gate, "Learning report cannot be formulated before a decision record is finalized.")
    return pass_gate(gate)


def gate_rollback(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate Rollback: Validates rollback request triggered by fatal flaw."""
    gate = "GateRollback"
    if not isinstance(envelope.payload, PhaseRollbackPayload):
        return fail_gate(gate, "Payload must be a PhaseRollbackPayload.")
    if session.current_state not in (CommitteeState.CONFRONTATION, CommitteeState.DEFENSE):
        return fail_gate(gate, f"Rollback only allowed from CONFRONTATION or DEFENSE (state: {session.current_state}).")
    return pass_gate(gate)


def gate_user_override(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate UserOverride: Validates human intervention commands."""
    gate = "GateUserOverride"
    if envelope.actor != CommitteeRole.HUMAN_USER:
        return fail_gate(gate, f"Only Human User can issue user override (actor: {envelope.actor}).")
    if not isinstance(envelope.payload, UserOverridePayload):
        return fail_gate(gate, "Payload must be a UserOverridePayload.")

    cmd = envelope.payload.intervention
    if isinstance(cmd, UserAbortCommand):
        if session.current_state in (CommitteeState.COMPLETED, CommitteeState.CANCELLED):
            return fail_gate(gate, f"Cannot abort session in terminal state {session.current_state}.")
        return pass_gate(gate)
    elif isinstance(cmd, UserRequestRevisionCommand):
        if session.current_state not in (
            CommitteeState.DECISION,
            CommitteeState.INSUFFICIENT_EVIDENCE,
            CommitteeState.REFLECTION,
            CommitteeState.COMPLETED,
        ):
            return fail_gate(
                gate,
                f"Revision request only permitted after decision formulation (state: {session.current_state}).",
            )
        return pass_gate(gate)
    return pass_gate(gate)


def gate_session_cancelled(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate SessionCancelled: Validates formal session cancellation."""
    gate = "GateSessionCancelled"
    if session.current_state in (CommitteeState.COMPLETED, CommitteeState.CANCELLED):
        return fail_gate(gate, f"Session already in terminal state {session.current_state}.")
    return pass_gate(gate)


def gate_critical_error(session: Session, envelope: EventEnvelope) -> QualityGateResult:
    """Gate CriticalError: Unconditional transition to BLOCKED upon fatal runtime failure."""
    return pass_gate("GateCriticalError")
