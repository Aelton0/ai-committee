"""Session state representation tracking logical state, phase, and active artifacts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import BaseDefense
from schemas.events import (
    CriticalErrorPayload,
    EventEnvelope,
    EventType,
    PhaseRollbackPayload,
    QuestionRaisedPayload,
    SessionCreatedPayload,
    UserOverridePayload,
    UserRespondedPayload,
)
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
    CommitteeState.BLOCKED: "BLOCKED",
    CommitteeState.CANCELLED: "CANCELLED",
}


class RoundStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED_BY_ROLLBACK = "SUPERSEDED_BY_ROLLBACK"
    SUPERSEDED_BY_REVISION = "SUPERSEDED_BY_REVISION"
    COMPLETED = "COMPLETED"


class DeliberationRound(BaseModel):
    """Archived record of an invalidated or completed deliberation round.

    Preserves historical artifacts without mutating or deleting past data.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    round_number: int
    status: RoundStatus | str
    reason: str | None = None
    proposals: dict[CommitteeRole, BaseProposal] = Field(default_factory=dict)
    audit_report: AuditReport | None = None
    defenses: dict[CommitteeRole, BaseDefense] = Field(default_factory=dict)
    deliberation_synthesis: DeliberationSynthesis | None = None
    decision_record: DecisionRecord | None = None
    archived_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Session(BaseModel):
    """Represents the mutable in-memory logical projection of a committee session.

    History is not retained here; it belongs to the Event Store.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: UUID
    current_state: CommitteeState = CommitteeState.DRAFT
    current_phase: str = "DRAFT"
    version: int = 1
    problem_statement: str | None = None
    user_id: str | None = None
    initial_context: str | None = None
    critical_error: CriticalErrorPayload | None = None

    # Iteration tracking
    current_round: int = 1
    historical_rounds: list[DeliberationRound] = Field(default_factory=list)

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

    def get_historical_proposals(self) -> list[tuple[int, CommitteeRole, BaseProposal]]:
        """Return all proposals from superseded historical rounds."""
        res: list[tuple[int, CommitteeRole, BaseProposal]] = []
        for r in self.historical_rounds:
            for role, p in r.proposals.items():
                res.append((r.round_number, role, p))
        return res

    def get_historical_artifacts(self) -> list[BaseModel]:
        """Return all artifacts from superseded historical rounds."""
        artifacts: list[BaseModel] = []
        for r in self.historical_rounds:
            artifacts.extend(r.proposals.values())
            if r.audit_report:
                artifacts.append(r.audit_report)
            artifacts.extend(r.defenses.values())
            if r.deliberation_synthesis:
                artifacts.append(r.deliberation_synthesis)
            if r.decision_record:
                artifacts.append(r.decision_record)
        return artifacts

    def apply_event(self, envelope: EventEnvelope, target_state: CommitteeState) -> None:
        """Apply an approved, gate-validated event to update internal session state."""
        self.current_state = target_state
        self.current_phase = STATE_PHASE_MAP.get(target_state, "UNKNOWN")
        self.version += 1

        payload = envelope.payload

        if isinstance(payload, SessionCreatedPayload):
            self.problem_statement = payload.problem_statement
            self.user_id = payload.user_id
            self.initial_context = payload.initial_context
        elif isinstance(payload, CriticalErrorPayload):
            self.critical_error = payload
        elif isinstance(payload, ProblemContext):
            self.problem_context = payload
        elif isinstance(payload, QuestionRaisedPayload):
            if self.problem_context is None:
                self.problem_context = ProblemContext(
                    artifact_id="CTX-INVESTIGATION",
                    version=1,
                    problem="Investigação em andamento",
                    open_questions=[payload.question],
                    success_criteria=["Critério pendente de validação"],
                )
            elif not any(q.id == payload.question.id for q in self.problem_context.open_questions):
                self.problem_context = self.problem_context.model_copy(
                    update={"open_questions": list(self.problem_context.open_questions) + [payload.question]}
                )
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
            # Archive current round before resetting active artifacts
            archived_round = DeliberationRound(
                round_number=self.current_round,
                status=RoundStatus.SUPERSEDED_BY_ROLLBACK,
                reason=payload.reason,
                proposals=dict(self.proposals),
                audit_report=self.audit_report,
                defenses=dict(self.defenses),
                deliberation_synthesis=self.deliberation_synthesis,
                decision_record=self.decision_record,
                archived_at=envelope.timestamp,
            )
            self.historical_rounds.append(archived_round)
            self.current_round += 1
            self.rollback_history.append(payload.model_dump())
            self.proposals = {}
            self.defenses = {}
            self.audit_report = None
            self.deliberation_synthesis = None
            self.decision_record = None
            self.learning_report = None
        elif isinstance(payload, UserOverridePayload):
            self.interventions.append(payload.intervention)
            from schemas.intervention import (
                AssumptionContestAction,
                UserContestAssumptionCommand,
                UserRequestRevisionCommand,
            )
            cmd = payload.intervention
            if isinstance(cmd, UserRequestRevisionCommand):
                # Archive current round before starting revised round
                archived_round = DeliberationRound(
                    round_number=self.current_round,
                    status=RoundStatus.SUPERSEDED_BY_REVISION,
                    reason=cmd.reason_for_rejection,
                    proposals=dict(self.proposals),
                    audit_report=self.audit_report,
                    defenses=dict(self.defenses),
                    deliberation_synthesis=self.deliberation_synthesis,
                    decision_record=self.decision_record,
                    archived_at=envelope.timestamp,
                )
                self.historical_rounds.append(archived_round)
                self.current_round += 1
                self.proposals = {}
                self.defenses = {}
                self.audit_report = None
                self.deliberation_synthesis = None
                self.decision_record = None
                self.learning_report = None
                if self.problem_context and cmd.additional_constraints:
                    from schemas.context import Constraint
                    new_constraints = list(self.problem_context.constraints)
                    for c_desc in cmd.additional_constraints:
                        new_constraints.append(
                            Constraint(id=f"C-REV-{len(new_constraints) + 1}", description=c_desc)
                        )
                    self.problem_context = self.problem_context.model_copy(
                        update={"constraints": new_constraints}
                    )
            elif isinstance(cmd, UserContestAssumptionCommand) and self.problem_context:
                updated_assumptions = []
                for a in self.problem_context.assumptions:
                    if a.id == cmd.assumption_id:
                        if cmd.action == AssumptionContestAction.MODIFY and cmd.new_description:
                            updated_assumptions.append(
                                a.model_copy(update={"description": cmd.new_description})
                            )
                        # if REJECT, do not re-add
                    else:
                        updated_assumptions.append(a)
                self.problem_context = self.problem_context.model_copy(
                    update={"assumptions": updated_assumptions}
                )
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
