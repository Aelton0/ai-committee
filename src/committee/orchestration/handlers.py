"""Step handlers for each phase of the deliberation workflow."""

from typing import TYPE_CHECKING

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState, DecisionStatus, EventType
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.events import EventEnvelope, QuestionRaisedPayload, SessionCreatedPayload
from schemas.learning import LearningReport
from schemas.synthesis import DeliberationSynthesis
from src.committee.orchestration.parallel import (
    run_defenses_parallel,
    run_divergence_parallel,
)

if TYPE_CHECKING:
    from src.committee.orchestration.orchestrator import CommitteeOrchestrator
    from src.committee.session import Session


async def handle_investigation_step(
    orchestrator: "CommitteeOrchestrator", session: "Session"
) -> bool:
    """Handle investigation phase: construct ProblemContext or raise questions if incomplete."""
    if session.problem_context is None:
        # Retrieve problem statement from event store
        problem_statement = "Deliberation problem statement."
        if orchestrator.event_store:
            events = orchestrator.event_store.get_events(session.session_id)
            for ev in events:
                if ev.event_type == EventType.SESSION_CREATED:
                    if isinstance(ev.payload, SessionCreatedPayload):
                        problem_statement = ev.payload.problem_statement
                    elif isinstance(ev.payload, dict) and "problem_statement" in ev.payload:
                        problem_statement = ev.payload["problem_statement"]
                    break

        input_context = {
            "phase": "PHASE_0_INVESTIGATION",
            "problem_statement": problem_statement,
        }

        problem_ctx = await orchestrator.runner.run(
            orchestrator.facilitator_agent,
            input_context,
            output_schema=ProblemContext,
        )

        if not isinstance(problem_ctx, ProblemContext):
            raise ValueError(f"Expected ProblemContext, got {type(problem_ctx).__name__}")

        # Check for unanswered questions
        if problem_ctx.has_unanswered_questions():
            session.problem_context = problem_ctx
            first_q = problem_ctx.unanswered_questions()[0]
            envelope = EventEnvelope(
                session_id=session.session_id,
                event_type=EventType.QUESTION_RAISED,
                actor=CommitteeRole.FACILITATOR,
                payload=QuestionRaisedPayload(question=first_q),
            )
            orchestrator.state_machine.handle_event(session, envelope)
            return False  # Now WAITING_FOR_USER, must pause

        # Otherwise validate context
        envelope = EventEnvelope(
            session_id=session.session_id,
            event_type=EventType.CONTEXT_VALIDATED,
            actor=CommitteeRole.FACILITATOR,
            artifact_id=problem_ctx.artifact_id,
            artifact_version=f"v{problem_ctx.version}",
            payload=problem_ctx,
        )
        orchestrator.state_machine.handle_event(session, envelope)
        return True

    # If problem context is already present without unanswered questions, validate it
    if not session.problem_context.has_unanswered_questions():
        envelope = EventEnvelope(
            session_id=session.session_id,
            event_type=EventType.CONTEXT_VALIDATED,
            actor=CommitteeRole.FACILITATOR,
            artifact_id=session.problem_context.artifact_id,
            artifact_version=f"v{session.problem_context.version}",
            payload=session.problem_context,
        )
        orchestrator.state_machine.handle_event(session, envelope)
        return True

    return False


async def handle_divergence_step(
    orchestrator: "CommitteeOrchestrator", session: "Session"
) -> bool:
    """Handle Phase 1 Divergence: execute Architect and Pragmatist concurrently."""
    arch_proposal, prag_proposal = await run_divergence_parallel(
        orchestrator.runner,
        orchestrator.architect_agent,
        orchestrator.pragmatic_agent,
        orchestrator.context_builder,
        session,
    )

    env_arch = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.PROPOSAL_CREATED,
        actor=CommitteeRole.ARCHITECT,
        artifact_id=arch_proposal.artifact_id,
        artifact_version=f"v{arch_proposal.version}",
        payload=arch_proposal,
    )
    orchestrator.state_machine.handle_event(session, env_arch)

    env_prag = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.PROPOSAL_CREATED,
        actor=CommitteeRole.PRAGMATIST,
        artifact_id=prag_proposal.artifact_id,
        artifact_version=f"v{prag_proposal.version}",
        payload=prag_proposal,
    )
    orchestrator.state_machine.handle_event(session, env_prag)
    return True


async def handle_confrontation_step(
    orchestrator: "CommitteeOrchestrator", session: "Session"
) -> bool:
    """Handle Phase 2 Confrontation: execute Auditor to critique both proposals."""
    context_auditor = orchestrator.context_builder.build_context(
        session, CommitteeRole.AUDITOR_SRE, phase="PHASE_2_CONFRONTATION"
    )
    audit_report = await orchestrator.runner.run(
        orchestrator.auditor_agent,
        context_auditor,
        output_schema=AuditReport,
    )

    env_audit = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.AUDIT_COMPLETED,
        actor=CommitteeRole.AUDITOR_SRE,
        artifact_id=audit_report.artifact_id,
        artifact_version=f"v{audit_report.version}",
        payload=audit_report,
    )
    orchestrator.state_machine.handle_event(session, env_audit)
    return True


async def handle_defense_step(
    orchestrator: "CommitteeOrchestrator", session: "Session"
) -> bool:
    """Handle Phase 3 Defense: execute Architect and Pragmatist defenses concurrently."""
    arch_defense, prag_defense = await run_defenses_parallel(
        orchestrator.runner,
        orchestrator.architect_agent,
        orchestrator.pragmatic_agent,
        orchestrator.context_builder,
        session,
    )

    env_arch_def = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.DEFENSE_SUBMITTED,
        actor=CommitteeRole.ARCHITECT,
        artifact_id=arch_defense.artifact_id,
        artifact_version=f"v{arch_defense.version}",
        payload=arch_defense,
    )
    orchestrator.state_machine.handle_event(session, env_arch_def)

    env_prag_def = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.DEFENSE_SUBMITTED,
        actor=CommitteeRole.PRAGMATIST,
        artifact_id=prag_defense.artifact_id,
        artifact_version=f"v{prag_defense.version}",
        payload=prag_defense,
    )
    orchestrator.state_machine.handle_event(session, env_prag_def)
    return True


async def handle_convergence_step(
    orchestrator: "CommitteeOrchestrator", session: "Session"
) -> bool:
    """Handle Phase 4 Convergence: execute Facilitator to synthesize the debate."""
    context_facilitator = orchestrator.context_builder.build_context(
        session, CommitteeRole.FACILITATOR, phase="PHASE_4_CONVERGENCE"
    )
    synthesis = await orchestrator.runner.run(
        orchestrator.facilitator_agent,
        context_facilitator,
        output_schema=DeliberationSynthesis,
    )

    env_synthesis = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.SYNTHESIS_CREATED,
        actor=CommitteeRole.FACILITATOR,
        artifact_id=synthesis.artifact_id,
        artifact_version=f"v{synthesis.version}",
        payload=synthesis,
    )
    orchestrator.state_machine.handle_event(session, env_synthesis)
    return True


async def handle_decision_step(
    orchestrator: "CommitteeOrchestrator", session: "Session"
) -> bool:
    """Handle Phase 5 Decision: execute Decisor to formulate recommendation or declare insufficient evidence."""
    context_decisor = orchestrator.context_builder.build_context(
        session, CommitteeRole.DECISOR, phase="PHASE_5_DECISION"
    )
    decision = await orchestrator.runner.run(
        orchestrator.decision_maker_agent,
        context_decisor,
        output_schema=DecisionRecord,
    )

    event_type = (
        EventType.DECISION_FAILED
        if decision.status == DecisionStatus.INSUFFICIENT_EVIDENCE
        else EventType.DECISION_RECORDED
    )

    env_decision = EventEnvelope(
        session_id=session.session_id,
        event_type=event_type,
        actor=CommitteeRole.DECISOR,
        artifact_id=decision.artifact_id,
        artifact_version=f"v{decision.version}",
        payload=decision,
    )
    orchestrator.state_machine.handle_event(session, env_decision)
    return True


async def handle_reflection_step(
    orchestrator: "CommitteeOrchestrator", session: "Session"
) -> bool:
    """Handle Phase 6 Reflection: execute Mentor to generate pedagogical study guide."""
    context_mentor = orchestrator.context_builder.build_context(
        session, CommitteeRole.MENTOR, phase="PHASE_6_REFLECTION"
    )
    learning_report = await orchestrator.runner.run(
        orchestrator.mentor_agent,
        context_mentor,
        output_schema=LearningReport,
    )

    env_learning = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.LEARNING_REPORT_CREATED,
        actor=CommitteeRole.MENTOR,
        artifact_id=learning_report.artifact_id,
        artifact_version=f"v{learning_report.version}",
        payload=learning_report,
    )
    orchestrator.state_machine.handle_event(session, env_learning)
    return True
