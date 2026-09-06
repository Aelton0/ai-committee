"""Context Builder constructing role-and-phase sanitized contexts enforcing docs/context-visibility.md."""

from typing import Any

from schemas.common import CommitteeRole
from src.committee.agents.base import ContextIsolationError
from src.committee.event_store import EventStore
from src.committee.session import Session


class ContextBuilder:
    """Builds strictly isolated and sanitized contexts for AI Committee agents."""

    def __init__(self, event_store: EventStore | None = None) -> None:
        self.event_store = event_store

    def build_context(
        self,
        session: Session,
        role: CommitteeRole,
        phase: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Construct sanitized input context for a specific agent role according to current phase."""
        current_phase = phase or session.current_phase
        context: dict[str, Any] = {
            "session_id": str(session.session_id),
            "phase": current_phase,
        }

        if extra_data:
            context.update(extra_data)

        # 1. Base Problem Context
        if session.problem_context is not None:
            context["problem_context"] = session.problem_context.model_dump(mode="json")

        # 2. Phase-specific and Role-specific filtering
        if role == CommitteeRole.ARCHITECT:
            self._build_architect_context(session, current_phase, context)
        elif role == CommitteeRole.PRAGMATIST:
            self._build_pragmatist_context(session, current_phase, context)
        elif role == CommitteeRole.AUDITOR_SRE:
            self._build_auditor_context(session, current_phase, context)
        elif role == CommitteeRole.FACILITATOR:
            self._build_facilitator_context(session, current_phase, context)
        elif role == CommitteeRole.DECISOR:
            self._build_decisor_context(session, current_phase, context)
        elif role == CommitteeRole.MENTOR:
            self._build_mentor_context(session, current_phase, context)
        else:
            raise ValueError(f"Unsupported role for context building: {role}")

        # Post-construction isolation invariant verification
        self._verify_isolation_invariants(role, current_phase, context)

        return context

    def _build_architect_context(
        self, session: Session, phase: str, context: dict[str, Any]
    ) -> None:
        if phase in ("PHASE_1_DIVERGENCE", "DRAFT", "PHASE_0_INVESTIGATION"):
            # BLIND DIVERGENCE: MUST NOT see Pragmatic proposal or defense
            return

        if phase == "PHASE_3_DEFENSE":
            if CommitteeRole.ARCHITECT in session.proposals:
                context["architect_proposal"] = session.proposals[
                    CommitteeRole.ARCHITECT
                ].model_dump(mode="json")
            if session.audit_report is not None:
                context["audit_report"] = session.audit_report.model_dump(mode="json")
            # In Phase 3, Architect does NOT see Pragmatist defense

    def _build_pragmatist_context(
        self, session: Session, phase: str, context: dict[str, Any]
    ) -> None:
        if phase in ("PHASE_1_DIVERGENCE", "DRAFT", "PHASE_0_INVESTIGATION"):
            # BLIND DIVERGENCE: MUST NOT see Architect proposal or defense
            return

        if phase == "PHASE_3_DEFENSE":
            if CommitteeRole.PRAGMATIST in session.proposals:
                context["pragmatic_proposal"] = session.proposals[
                    CommitteeRole.PRAGMATIST
                ].model_dump(mode="json")
            if session.audit_report is not None:
                context["audit_report"] = session.audit_report.model_dump(mode="json")
            # In Phase 3, Pragmatist does NOT see Architect defense

    def _build_auditor_context(
        self, session: Session, phase: str, context: dict[str, Any]
    ) -> None:
        # Auditor sees ProblemContext and both proposals
        if CommitteeRole.ARCHITECT in session.proposals:
            context["architect_proposal"] = session.proposals[
                CommitteeRole.ARCHITECT
            ].model_dump(mode="json")
        if CommitteeRole.PRAGMATIST in session.proposals:
            context["pragmatic_proposal"] = session.proposals[
                CommitteeRole.PRAGMATIST
            ].model_dump(mode="json")
        # Auditor MUST NOT see defenses during Phase 2 audit

    def _build_facilitator_context(
        self, session: Session, phase: str, context: dict[str, Any]
    ) -> None:
        if phase == "PHASE_4_CONVERGENCE":
            if CommitteeRole.ARCHITECT in session.proposals:
                context["architect_proposal"] = session.proposals[
                    CommitteeRole.ARCHITECT
                ].model_dump(mode="json")
            if CommitteeRole.PRAGMATIST in session.proposals:
                context["pragmatic_proposal"] = session.proposals[
                    CommitteeRole.PRAGMATIST
                ].model_dump(mode="json")
            if session.audit_report is not None:
                context["audit_report"] = session.audit_report.model_dump(mode="json")
            if CommitteeRole.ARCHITECT in session.defenses:
                context["architect_defense"] = session.defenses[
                    CommitteeRole.ARCHITECT
                ].model_dump(mode="json")
            if CommitteeRole.PRAGMATIST in session.defenses:
                context["pragmatic_defense"] = session.defenses[
                    CommitteeRole.PRAGMATIST
                ].model_dump(mode="json")
            # Facilitator NEVER receives DecisionRecord

    def _build_decisor_context(
        self, session: Session, phase: str, context: dict[str, Any]
    ) -> None:
        if CommitteeRole.ARCHITECT in session.proposals:
            context["architect_proposal"] = session.proposals[
                CommitteeRole.ARCHITECT
            ].model_dump(mode="json")
        if CommitteeRole.PRAGMATIST in session.proposals:
            context["pragmatic_proposal"] = session.proposals[
                CommitteeRole.PRAGMATIST
            ].model_dump(mode="json")
        if session.audit_report is not None:
            context["audit_report"] = session.audit_report.model_dump(mode="json")
        if CommitteeRole.ARCHITECT in session.defenses:
            context["architect_defense"] = session.defenses[
                CommitteeRole.ARCHITECT
            ].model_dump(mode="json")
        if CommitteeRole.PRAGMATIST in session.defenses:
            context["pragmatic_defense"] = session.defenses[
                CommitteeRole.PRAGMATIST
            ].model_dump(mode="json")
        if session.deliberation_synthesis is not None:
            context["deliberation_synthesis"] = session.deliberation_synthesis.model_dump(
                mode="json"
            )

    def _build_mentor_context(
        self, session: Session, phase: str, context: dict[str, Any]
    ) -> None:
        self._build_decisor_context(session, phase, context)
        if session.decision_record is not None:
            context["decision_record"] = session.decision_record.model_dump(mode="json")

    def _verify_isolation_invariants(
        self, role: CommitteeRole, phase: str, context: dict[str, Any]
    ) -> None:
        """Enforce strict isolation invariants at the code level."""
        # 1. Blind divergence isolation
        if role == CommitteeRole.ARCHITECT and phase == "PHASE_1_DIVERGENCE":
            if "pragmatic_proposal" in context:
                raise ContextIsolationError(
                    "Blind divergence violated: Pragmatic proposal leaked to Architect."
                )
        if role == CommitteeRole.PRAGMATIST and phase == "PHASE_1_DIVERGENCE":
            if "architect_proposal" in context:
                raise ContextIsolationError(
                    "Blind divergence violated: Architect proposal leaked to Pragmatic."
                )

        # 2. Defense isolation
        if role == CommitteeRole.ARCHITECT and phase == "PHASE_3_DEFENSE":
            if "pragmatic_defense" in context:
                raise ContextIsolationError(
                    "Defense isolation violated: Pragmatic defense leaked to Architect."
                )
        if role == CommitteeRole.PRAGMATIST and phase == "PHASE_3_DEFENSE":
            if "architect_defense" in context:
                raise ContextIsolationError(
                    "Defense isolation violated: Architect defense leaked to Pragmatic."
                )

        # 3. Auditor isolation
        if role == CommitteeRole.AUDITOR_SRE and phase == "PHASE_2_CONFRONTATION":
            if "architect_defense" in context or "pragmatic_defense" in context:
                raise ContextIsolationError(
                    "Auditor isolation violated: Auditor received defense before audit completion."
                )

        # 4. Facilitator neutrality
        if role == CommitteeRole.FACILITATOR:
            if "decision_record" in context:
                raise ContextIsolationError(
                    "Facilitator neutrality violated: Facilitator received DecisionRecord."
                )
