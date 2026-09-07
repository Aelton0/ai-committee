"""Deterministic Quality Gates enforcing deliberation process rules."""

from typing import Callable

from pydantic import BaseModel

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState, DecisionStatus
from schemas.context import OpenQuestion, ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import BaseDefense
from schemas.events import (
    CriticalErrorPayload,
    EventEnvelope,
    PhaseRollbackPayload,
    UserOverridePayload,
    UserRespondedPayload,
)
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
    if not envelope.payload.success_criteria or any(not str(sc).strip() for sc in envelope.payload.success_criteria):
        return fail_gate(gate, "ProblemContext must specify at least one non-empty success criteria.")
    for fact in envelope.payload.facts:
        if not fact.id.strip() or not fact.description.strip() or not fact.source.strip():
            return fail_gate(gate, f"Fact '{fact.id}' is incomplete: id, description, and source are required.")
    for constraint in envelope.payload.constraints:
        if not constraint.id.strip() or not constraint.description.strip():
            return fail_gate(gate, f"Constraint '{constraint.id}' is incomplete: id and description are required.")
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
    if envelope.payload.proponent_role in session.proposals:
        return fail_gate(
            gate,
            f"Duplicate proposal: Proposal already registered for role '{envelope.payload.proponent_role.value}' in the active round.",
        )
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

    registered_ids = {p.artifact_id for p in session.proposals.values()}
    target_ids = {envelope.payload.target_proposal_a_id, envelope.payload.target_proposal_b_id}
    if target_ids != registered_ids:
        return fail_gate(
            gate,
            f"Audit report targets {target_ids} do not match registered proposal IDs {registered_ids}.",
        )
    if not envelope.payload.all_findings():
        return fail_gate(gate, "Audit report must contain at least one finding.")
    for finding in envelope.payload.all_findings():
        if finding.target_proposal_id not in registered_ids:
            return fail_gate(
                gate,
                f"Finding '{finding.id}' targets unknown proposal '{finding.target_proposal_id}'.",
            )
        if not finding.title.strip() or not finding.description.strip() or not finding.justification.strip():
            return fail_gate(
                gate,
                f"Finding '{finding.id}' is missing required fields (title, description, or justification).",
            )

    # Ensure auditor evaluated both proposals (findings_for_A >= 1 and findings_for_B >= 1)
    findings_a = [
        f for f in envelope.payload.all_findings()
        if f.target_proposal_id == envelope.payload.target_proposal_a_id
    ]
    findings_b = [
        f for f in envelope.payload.all_findings()
        if f.target_proposal_id == envelope.payload.target_proposal_b_id
    ]
    if len(findings_a) < 1 or len(findings_b) < 1:
        return fail_gate(
            gate,
            f"Audit report must cover both proposals with at least one finding each (found {len(findings_a)} for proposal A, {len(findings_b)} for proposal B).",
        )

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
    if envelope.payload.proponent_role in session.defenses:
        return fail_gate(
            gate,
            f"Duplicate defense: Defense already submitted for role '{envelope.payload.proponent_role.value}' in active round.",
        )
    if session.audit_report is None:
        return fail_gate(gate, "Defense cannot be submitted before an AuditReport is recorded.")

    original_prop = session.proposals.get(envelope.payload.proponent_role)
    if original_prop and envelope.payload.original_proposal_id != original_prop.artifact_id:
        return fail_gate(
            gate,
            f"Defense original_proposal_id '{envelope.payload.original_proposal_id}' does not match "
            f"active proposal '{original_prop.artifact_id}'.",
        )
    valid_finding_ids = {f.id for f in session.audit_report.all_findings()}
    for cr in envelope.payload.critique_responses:
        if cr.finding_id not in valid_finding_ids:
            return fail_gate(
                gate,
                f"Defense responds to unknown audit finding '{cr.finding_id}'.",
            )
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
    if hasattr(envelope.payload, "recommendation") or hasattr(envelope.payload, "chosen_alternative"):
        return fail_gate(gate, "Synthesis must remain neutral and cannot contain recommendation or chosen alternative.")
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

    if envelope.payload.status == DecisionStatus.RECOMMENDED:
        if not envelope.payload.chosen_alternative or not envelope.payload.chosen_alternative.strip():
            return fail_gate(gate, "Recommended decision must specify a non-empty chosen_alternative.")
        if not envelope.payload.recommendation or not envelope.payload.recommendation.strip():
            return fail_gate(gate, "Recommended decision must specify a non-empty recommendation.")
        if not envelope.payload.trade_offs:
            return fail_gate(gate, "Recommended decision must specify at least one trade-off contract.")
        if not envelope.payload.review_triggers:
            return fail_gate(gate, "Recommended decision must specify at least one review trigger.")
        if not envelope.payload.rejected_alternatives:
            return fail_gate(gate, "Recommended decision must document rejected alternatives.")

        # Validate chosen_alternative against active proposals in current round
        chosen = envelope.payload.chosen_alternative.strip()
        active_proposal_ids = {p.artifact_id for p in session.proposals.values()}

        # Must reject alternatives from historical rounds
        historical_proposal_ids = {
            p.artifact_id
            for r in session.historical_rounds
            for p in r.proposals.values()
        }
        if chosen in historical_proposal_ids and chosen not in active_proposal_ids:
            return fail_gate(
                gate,
                f"Chosen alternative '{chosen}' references a proposal from a superseded historical round.",
            )

        # Build valid active alternative references
        valid_active_alternatives = set(active_proposal_ids)
        for role, p in session.proposals.items():
            valid_active_alternatives.add(p.title)
            valid_active_alternatives.add(role.value)
            if role == CommitteeRole.ARCHITECT:
                valid_active_alternatives.update(["PROPOSAL_A", "PROPOSAL_ARCH", "PROPOSAL_ARCH_V1", "PROPOSAL_ARCH_V2"])
            elif role == CommitteeRole.PRAGMATIST:
                valid_active_alternatives.update(["PROPOSAL_B", "PROPOSAL_PRAG", "PROPOSAL_PRAG_V1", "PROPOSAL_PRAG_V2"])
        for d in session.defenses.values():
            if d.revised_proposal_id:
                valid_active_alternatives.add(d.revised_proposal_id)

        if chosen not in valid_active_alternatives:
            return fail_gate(
                gate,
                f"Chosen alternative '{chosen}' does not reference an active proposal in the current round.",
            )

    elif envelope.payload.status == DecisionStatus.INSUFFICIENT_EVIDENCE:
        if envelope.payload.chosen_alternative is not None:
            return fail_gate(gate, "INSUFFICIENT_EVIDENCE decision must not choose any alternative.")
        if not envelope.payload.information_that_could_change_decision:
            return fail_gate(
                gate,
                "INSUFFICIENT_EVIDENCE decision must declare information_that_could_change_decision.",
            )
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
    gate = "GateCriticalError"
    if not isinstance(envelope.payload, CriticalErrorPayload):
        return fail_gate(gate, "Payload must be a CriticalErrorPayload.")
    return pass_gate(gate)
