"""Session state representation tracking logical state, phase, and active artifacts."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import BaseDefense
from schemas.events import EventEnvelope, EventType, PhaseRollbackPayload, UserOverridePayload, UserRespondedPayload
from schemas.intervention import HumanInterventionCommand, UserRespondCommand
from schemas.learning import LearningReport
from schemas.proposals import BaseProposal
from schemas.synthesis import DeliberationSynthesis

# Mapping of CommitteeState to formal Phase identifier
STATE_PHASE_MAP: dict[CommitteeState, str] = {
    CommitteeState.DRAFT: "DRAFT",
    CommitteeState.INVESTIGATION: "PHASE_0_INVESTIGATION",
    CommitteeState.WAITING_FOR_USER: "PHASE_0_INVESTIGATION",
    CommitteeState.DIVERGENCE: "PHASE_1_DIVERGENCE",
    CommitteeState.CONFRONTATION: "PHASE_2_CONFRONTATION",
    CommitteeState.DEFENSE: "PHASE_3_DEFENSE",
    CommitteeState.CONVERGENCE: "PHASE_4_CONVERGENCE",
    CommitteeState.DECISION: "PHASE_5_DECISION",
    CommitteeState.INSUFFICIENT_EVIDENCE: "PHASE_5_DECISION",
    CommitteeState.REFLECTION: "PHASE_6_REFLECTION",
    CommitteeState.COMPLETED: "COMPLETED",
    CommitteeState.ROLLED_BACK: "PHASE_0_INVESTIGATION",
    CommitteeState.BLOCKED: "BLOCKED",
    CommitteeState.CANCELLED: "CANCELLED",
}


class Session(BaseModel):
    """Represents the mutable in-memory logical projection of a committee session.

    History is not retained here; it belongs to the Event Store.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: UUID
    current_state: CommitteeState = CommitteeState.DRAFT
    current_phase: str = "DRAFT"
    version: int = 1

    # Active artifacts tracked for validation and Quality Gate evaluations
    problem_context: ProblemContext | None = None
    proposals: dict[CommitteeRole, BaseProposal] = Field(default_factory=dict)
    audit_report: AuditReport | None = None
    defenses: dict[CommitteeRole, BaseDefense] = Field(default_factory=dict)
    deliberation_synthesis: DeliberationSynthesis | None = None
    decision_record: DecisionRecord | None = None
    learning_report: LearningReport | None = None
    interventions: list[HumanInterventionCommand] = Field(default_factory=list)
    rollback_history: list[dict[str, Any]] = Field(default_factory=list)

    def has_both_proposals(self) -> bool:
        """Check whether both Architect and Pragmatist proposals have been submitted."""
        return (
            CommitteeRole.ARCHITECT in self.proposals
            and CommitteeRole.PRAGMATIST in self.proposals
        )

    def has_both_defenses(self) -> bool:
        """Check whether both Architect and Pragmatist defenses have been submitted."""
        return (
            CommitteeRole.ARCHITECT in self.defenses
            and CommitteeRole.PRAGMATIST in self.defenses
        )

    def apply_event(self, envelope: EventEnvelope, target_state: CommitteeState) -> None:
        """Apply an approved, gate-validated event to update internal session state."""
        self.current_state = target_state
        self.current_phase = STATE_PHASE_MAP.get(target_state, "UNKNOWN")
        self.version += 1

        payload = envelope.payload

        if isinstance(payload, ProblemContext):
            self.problem_context = payload
        elif isinstance(payload, BaseProposal):
            self.proposals[payload.proponent_role] = payload
        elif isinstance(payload, AuditReport):
            self.audit_report = payload
        elif isinstance(payload, BaseDefense):
            self.defenses[payload.proponent_role] = payload
        elif isinstance(payload, DeliberationSynthesis):
            self.deliberation_synthesis = payload
        elif isinstance(payload, DecisionRecord):
            self.decision_record = payload
        elif isinstance(payload, LearningReport):
            self.learning_report = payload
        elif isinstance(payload, PhaseRollbackPayload):
            self.rollback_history.append(payload.model_dump())
        elif isinstance(payload, UserOverridePayload):
            self.interventions.append(payload.intervention)
        elif isinstance(payload, (UserRespondCommand, UserRespondedPayload)):
            self.interventions.append(payload)
            # If answering a question on problem context, mark question answered
            if self.problem_context:
                updated_questions = []
                for q in self.problem_context.open_questions:
                    if q.id == payload.question_id:
                        updated_questions.append(
                            q.model_copy(update={"answer": payload.answer})
                        )
                    else:
                        updated_questions.append(q)
                self.problem_context = self.problem_context.model_copy(
                    update={"open_questions": updated_questions}
                )
