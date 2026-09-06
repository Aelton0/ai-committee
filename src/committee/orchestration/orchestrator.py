"""Committee Orchestrator coordinating StateMachine, EventStore, ContextBuilder, and AgentRunner."""

from uuid import UUID

from schemas.common import CommitteeRole, CommitteeState, EventType
from schemas.events import (
    EventEnvelope,
    SessionCancelledPayload,
    UserOverridePayload,
    UserRespondedPayload,
)
from schemas.intervention import HumanInterventionCommand, UserAbortCommand
from src.committee.agents.architect import ArchitectAgent
from src.committee.agents.auditor import AuditorAgent
from src.committee.agents.decision_maker import DecisionMakerAgent
from src.committee.agents.facilitator import FacilitatorAgent
from src.committee.agents.mentor import MentorAgent
from src.committee.agents.pragmatic import PragmaticAgent
from src.committee.event_store import EventStore
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.orchestration.handlers import (
    handle_confrontation_step,
    handle_convergence_step,
    handle_decision_step,
    handle_defense_step,
    handle_divergence_step,
    handle_investigation_step,
    handle_reflection_step,
)
from src.committee.orchestration.runner import AgentRunner
from src.committee.session import Session
from src.committee.state_machine import StateMachine


class CommitteeOrchestrator:
    """Coordinates multi-agent deliberation without bypassing or duplicating StateMachine rules."""

    def __init__(
        self,
        state_machine: StateMachine,
        event_store: EventStore,
        context_builder: ContextBuilder,
        runner: AgentRunner,
        architect_agent: ArchitectAgent | None = None,
        pragmatic_agent: PragmaticAgent | None = None,
        auditor_agent: AuditorAgent | None = None,
        facilitator_agent: FacilitatorAgent | None = None,
        decision_maker_agent: DecisionMakerAgent | None = None,
        mentor_agent: MentorAgent | None = None,
    ) -> None:
        self.state_machine = state_machine
        self.event_store = event_store
        self.context_builder = context_builder
        self.runner = runner

        # Instantiate specialized agents with default prompts if not supplied
        self.architect_agent = architect_agent or ArchitectAgent()
        self.pragmatic_agent = pragmatic_agent or PragmaticAgent()
        self.auditor_agent = auditor_agent or AuditorAgent()
        self.facilitator_agent = facilitator_agent or FacilitatorAgent()
        self.decision_maker_agent = decision_maker_agent or DecisionMakerAgent()
        self.mentor_agent = mentor_agent or MentorAgent()

    def create_session(
        self, session_id: UUID, problem_statement: str, user_id: str | None = None
    ) -> Session:
        """Create a new deliberation session forwarding directly to the StateMachine."""
        return self.state_machine.create_session(
            session_id=session_id,
            problem_statement=problem_statement,
            user_id=user_id,
        )

    async def step(self, session: Session) -> bool:
        """Execute a single logical automated step based on current session state.

        Returns True if progress was made and further automated steps can follow.
        Returns False if execution must pause (e.g. WAITING_FOR_USER) or is terminal.
        """
        state = session.current_state

        if state == CommitteeState.INVESTIGATION:
            return await handle_investigation_step(self, session)
        elif state == CommitteeState.DIVERGENCE:
            return await handle_divergence_step(self, session)
        elif state == CommitteeState.CONFRONTATION:
            return await handle_confrontation_step(self, session)
        elif state == CommitteeState.DEFENSE:
            return await handle_defense_step(self, session)
        elif state == CommitteeState.CONVERGENCE:
            return await handle_convergence_step(self, session)
        elif state == CommitteeState.DECISION:
            return await handle_decision_step(self, session)
        elif state == CommitteeState.REFLECTION:
            return await handle_reflection_step(self, session)
        elif state in (
            CommitteeState.WAITING_FOR_USER,
            CommitteeState.COMPLETED,
            CommitteeState.INSUFFICIENT_EVIDENCE,
            CommitteeState.CANCELLED,
            CommitteeState.BLOCKED,
        ):
            return False

        raise ValueError(f"No automated step handler for state {state.value}")

    async def run_until_pause(self, session: Session, max_steps: int = 25) -> Session:
        """Execute automated deliberation steps until paused for user input or terminated."""
        steps = 0
        while steps < max_steps:
            if session.current_state in (
                CommitteeState.WAITING_FOR_USER,
                CommitteeState.COMPLETED,
                CommitteeState.INSUFFICIENT_EVIDENCE,
                CommitteeState.CANCELLED,
                CommitteeState.BLOCKED,
            ):
                break
            can_continue = await self.step(session)
            steps += 1
            if not can_continue:
                break
        return session

    def user_respond(self, session: Session, question_id: str, answer: str) -> None:
        """Submit a user answer to an open question via the StateMachine."""
        envelope = EventEnvelope(
            session_id=session.session_id,
            event_type=EventType.USER_RESPONDED,
            actor=CommitteeRole.HUMAN_USER,
            payload=UserRespondedPayload(question_id=question_id, answer=answer),
        )
        self.state_machine.handle_event(session, envelope)

    def user_override(
        self, session: Session, intervention: HumanInterventionCommand
    ) -> None:
        """Submit an explicit human intervention command via the StateMachine."""
        if isinstance(intervention, UserAbortCommand):
            envelope = EventEnvelope(
                session_id=session.session_id,
                event_type=EventType.SESSION_CANCELLED,
                actor=CommitteeRole.HUMAN_USER,
                payload=SessionCancelledPayload(
                    reason=intervention.reason,
                    cancelled_by=CommitteeRole.HUMAN_USER,
                ),
            )
        else:
            envelope = EventEnvelope(
                session_id=session.session_id,
                event_type=EventType.USER_OVERRIDE,
                actor=CommitteeRole.HUMAN_USER,
                payload=UserOverridePayload(intervention=intervention),
            )
        self.state_machine.handle_event(session, envelope)
