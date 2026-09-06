"""Integration tests verifying end-to-end deliberation execution via CommitteeOrchestrator."""

import asyncio
from uuid import uuid4
import pytest

from schemas.common import CommitteeRole, CommitteeState
from schemas.context import OpenQuestion, ProblemContext
from schemas.intervention import UserAbortCommand
from schemas.proposals import ArchitectProposal
from src.committee.event_store import EventStore
from src.committee.llm import MockLLMProvider
from src.committee.orchestration import (
    AgentExecutionFailed,
    AgentRunner,
    CommitteeOrchestrator,
    ContextBuilder,
)
from src.committee.replay import replay_session
from src.committee.state_machine import StateMachine


@pytest.fixture
def orchestrator_setup(tmp_path):
    """Set up real StateMachine, EventStore, ContextBuilder, Runner and MockLLMProvider."""
    db_path = tmp_path / "orchestrator_test.db"
    store = EventStore(db_path)
    sm = StateMachine(store)
    builder = ContextBuilder(store)
    provider = MockLLMProvider()
    runner = AgentRunner(provider)
    orchestrator = CommitteeOrchestrator(
        state_machine=sm,
        event_store=store,
        context_builder=builder,
        runner=runner,
    )
    yield orchestrator, store, provider
    store.close()


def test_full_end_to_end_deliberation_with_mock_provider(orchestrator_setup) -> None:
    """Run full deliberation from SESSION_CREATED to COMPLETED and verify replay."""
    async def _test():
        orchestrator, store, provider = orchestrator_setup
        session_id = uuid4()

        # 1. Initialize session
        session = orchestrator.create_session(
            session_id=session_id,
            problem_statement="Determine distributed caching architecture under 500 req/s.",
            user_id="lead_architect",
        )
        assert session.current_state == CommitteeState.INVESTIGATION

        # 2. Run automated pipeline until completion
        final_session = await orchestrator.run_until_pause(session, max_steps=20)

        # 3. Assertions on final session state
        assert final_session.current_state == CommitteeState.COMPLETED
        assert final_session.current_phase == "COMPLETED"

        # Verify all artifacts are present in session projection
        assert final_session.problem_context is not None
        assert CommitteeRole.ARCHITECT in final_session.proposals
        assert CommitteeRole.PRAGMATIST in final_session.proposals
        assert final_session.audit_report is not None
        assert CommitteeRole.ARCHITECT in final_session.defenses
        assert CommitteeRole.PRAGMATIST in final_session.defenses
        assert final_session.deliberation_synthesis is not None
        assert final_session.decision_record is not None
        assert final_session.learning_report is not None

        # 4. Verify EventStore records all corresponding events
        events = store.get_events(session_id)
        event_types = [e.event_type.value for e in events]

        assert "SESSION_CREATED" in event_types
        assert "CONTEXT_VALIDATED" in event_types
        assert event_types.count("PROPOSAL_CREATED") == 2
        assert "AUDIT_COMPLETED" in event_types
        assert event_types.count("DEFENSE_SUBMITTED") == 2
        assert "SYNTHESIS_CREATED" in event_types
        assert "DECISION_RECORDED" in event_types
        assert "LEARNING_REPORT_CREATED" in event_types

        # 5. Deterministic replay verification
        replayed = replay_session(session_id, store)
        assert replayed.current_state == CommitteeState.COMPLETED
        assert replayed.version == final_session.version
        assert replayed.decision_record.recommendation == final_session.decision_record.recommendation
        assert replayed.learning_report.artifact_id == final_session.learning_report.artifact_id

    asyncio.run(_test())


def test_orchestrator_pauses_on_waiting_for_user(orchestrator_setup) -> None:
    """Verify that open questions cause Facilitator to pause deliberation on WAITING_FOR_USER."""
    async def _test():
        orchestrator, store, provider = orchestrator_setup
        session_id = uuid4()

        # Custom generator for ProblemContext that includes an open question
        def custom_ctx_gen(context: dict) -> ProblemContext:
            return ProblemContext(
                artifact_id="CTX-001",
                version=1,
                problem="Problem with question.",
                open_questions=[
                    OpenQuestion(
                        id="Q1",
                        question="What is the peak concurrency?",
                        why_critical="Essential for sizing database connection pool.",
                    )
                ],
                success_criteria=["Low latency"],
            )

        provider.custom_generators[ProblemContext] = custom_ctx_gen

        session = orchestrator.create_session(
            session_id=session_id,
            problem_statement="Problem statement requiring user clarification.",
        )
        assert session.current_state == CommitteeState.INVESTIGATION

        # First step runs investigation and should raise QuestionRaised -> WAITING_FOR_USER
        session = await orchestrator.run_until_pause(session, max_steps=5)
        assert session.current_state == CommitteeState.WAITING_FOR_USER

        # Human answers the question
        orchestrator.user_respond(session, question_id="Q1", answer="Peak concurrency is 400 req/s.")
        assert session.current_state == CommitteeState.INVESTIGATION

        # Now change custom generator so no open questions remain
        def resolved_ctx_gen(context: dict) -> ProblemContext:
            return ProblemContext(
                artifact_id="CTX-001",
                version=1,
                problem="Problem with question resolved.",
                open_questions=[],
                success_criteria=["Low latency"],
            )

        provider.custom_generators[ProblemContext] = resolved_ctx_gen

        # Resume orchestration to completion
        session = await orchestrator.run_until_pause(session, max_steps=20)
        assert session.current_state == CommitteeState.COMPLETED

    asyncio.run(_test())


def test_agent_failure_does_not_corrupt_store(orchestrator_setup) -> None:
    """When an agent fails exhausting retries, no false event is written to the store."""
    async def _test():
        orchestrator, store, provider = orchestrator_setup
        session_id = uuid4()

        # Force Architect proposal to always fail
        provider.failure_counts[ArchitectProposal] = 10

        session = orchestrator.create_session(
            session_id=session_id,
            problem_statement="Problem where architect fails.",
        )

        # Step 1: Investigation succeeds (CONTEXT_VALIDATED)
        progress = await orchestrator.step(session)
        assert progress is True
        assert session.current_state == CommitteeState.DIVERGENCE

        initial_event_count = len(store.get_events(session_id))

        # Step 2: Divergence fails because Architect fails
        with pytest.raises(AgentExecutionFailed):
            await orchestrator.step(session)

        # Verify session remains in DIVERGENCE and no event was committed for Architect
        assert session.current_state == CommitteeState.DIVERGENCE
        assert len(store.get_events(session_id)) == initial_event_count

    asyncio.run(_test())


def test_user_abort_override_halts_deliberation(orchestrator_setup) -> None:
    """User abort intervention halts deliberation and transitions state to CANCELLED."""
    async def _test():
        orchestrator, store, _ = orchestrator_setup
        session_id = uuid4()

        session = orchestrator.create_session(
            session_id=session_id,
            problem_statement="Session to be aborted by user.",
        )
        await orchestrator.step(session)  # Advances to DIVERGENCE

        # User aborts
        orchestrator.user_override(
            session,
            UserAbortCommand(session_id=session_id, reason="Requirements changed fundamentally."),
        )
        assert session.current_state == CommitteeState.CANCELLED

        # Subsequent orchestrator step returns False
        res = await orchestrator.step(session)
        assert res is False

    asyncio.run(_test())
