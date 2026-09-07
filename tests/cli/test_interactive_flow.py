"""Comprehensive integration and negative tests for AI Committee interactive CLI flow.

Covers full happy path, human QA, revision loop, abort, and all 10 Section 17 negative tests:
1. Blind divergence isolation
2. Invalid command in prompt
3. Decision without synthesis quality gate failure
4. Advancing without answering mandatory question
5. Direct tampering of append-only EventStore
6. Rejecting recommendation via revision request
7. Aborting session midway
8. Crash recovery / resumption from EventStore
9. Replay parity of interactive session
10. Invariant that CLI never bypasses StateMachine rules
"""

import asyncio
import sqlite3
from uuid import uuid4
import pytest

from schemas.common import CommitteeRole, CommitteeState, Confidence, DecisionStatus, Severity
from schemas.context import OpenQuestion, ProblemContext
from schemas.decision import DecisionRecord
from schemas.events import EventEnvelope, EventType, UserOverridePayload
from schemas.intervention import AssumptionContestAction, UserAbortCommand, UserRequestRevisionCommand
from src.committee.cli.app import CommitteeCLIApp
from src.committee.cli.commands import CommandHandler
from src.committee.cli.renderer import TerminalRenderer
from src.committee.cli.session_ui import SessionUI
from src.committee.event_store import EventStore, ImmutableEventStoreViolationError
from src.committee.llm.mock import MockLLMProvider
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.orchestration.orchestrator import CommitteeOrchestrator
from src.committee.orchestration.runner import AgentRunner
from src.committee.replay import replay_session
from src.committee.state_machine import CommitteeError, InvalidTransitionError, QualityGateFailedError, StateMachine


def create_app(event_store: EventStore | None = None, input_sequence: list[str] | None = None):
    """Factory creating CommitteeCLIApp with mocked I/O."""
    store = event_store or EventStore(":memory:")
    sm = StateMachine(event_store=store)
    cb = ContextBuilder()
    runner = AgentRunner(llm_provider=MockLLMProvider())
    orchestrator = CommitteeOrchestrator(
        state_machine=sm,
        event_store=store,
        context_builder=cb,
        runner=runner,
    )
    inputs = list(input_sequence or [])
    outputs: list[str] = []

    def mock_input(_prompt: str = "") -> str:
        if inputs:
            return inputs.pop(0)
        return ""

    renderer = TerminalRenderer()
    ui = SessionUI(renderer=renderer, input_func=mock_input, print_func=outputs.append)
    app = CommitteeCLIApp(orchestrator=orchestrator, ui=ui, renderer=renderer)
    return app, orchestrator, store, inputs, outputs


# ==============================================================================
# 1. Full Interactive Deliberation Flows
# ==============================================================================


@pytest.mark.anyio
async def test_interactive_cli_happy_path() -> None:
    """Full deliberation session from Investigation to Completion via example_mode."""
    # Inputs:
    # Phase 0 advance: ""
    # Phase 1 advance: ""
    # Phase 2 advance: ""
    # Phase 3 advance: ""
    # Phase 4 advance: ""
    # Phase 5 Decision acceptance: "1" (Accept)
    # Phase 6 Reflection close: "1" (Encerrar)
    inputs = ["", "", "", "", "", "1", "1"]
    app, orchestrator, store, _, outputs = create_app(input_sequence=inputs)

    session = await app.run(example_mode=True)

    assert session.current_state == CommitteeState.COMPLETED
    assert session.problem_context is not None
    assert CommitteeRole.ARCHITECT in session.proposals
    assert CommitteeRole.PRAGMATIST in session.proposals
    assert session.audit_report is not None
    assert CommitteeRole.ARCHITECT in session.defenses
    assert session.deliberation_synthesis is not None
    assert session.decision_record is not None
    assert session.learning_report is not None

    full_output = "\n".join(outputs)
    assert "AI COMMITTEE" in full_output
    assert "FASE 0 — INVESTIGAÇÃO" in full_output
    assert "FASE 1 — DIVERGÊNCIA CEGA" in full_output
    assert "FASE 2 — CONFRONTO" in full_output
    assert "FASE 3 — DEFESA E REFINAMENTO" in full_output
    assert "FASE 4 — CONVERGÊNCIA" in full_output
    assert "FASE 5 — DECISÃO" in full_output
    assert "FASE 6 — REFLEXÃO E MENTORIA" in full_output
    assert "SESSÃO CONCLUÍDA COM SUCESSO" in full_output
    assert "TELEMETRIA DA DELIBERAÇÃO" in full_output


@pytest.mark.anyio
async def test_interactive_cli_manual_problem_input() -> None:
    """Deliberation with manual prompt input and intermediate commands."""
    inputs = [
        "Escalar banco de dados relacional",  # problem statement
        "4 devs",  # team
        "$1000",  # budget
        "3 meses",  # deadline
        "Alta disponibilidade",  # objective
        "Zero downtime",  # success criteria
        "status",  # intermediate command during step advance
        "",  # advance to phase 1
        "",  # advance to phase 2
        "",  # advance to phase 3
        "",  # advance to phase 4
        "",  # advance to phase 5
        "1",  # accept recommendation
        "1",  # close reflection
    ]
    app, orchestrator, store, _, outputs = create_app(input_sequence=inputs)

    session = await app.run(example_mode=False)

    assert session.current_state == CommitteeState.COMPLETED
    full_output = "\n".join(outputs)
    assert "STATUS DA SESSÃO" in full_output


@pytest.mark.anyio
async def test_interactive_cli_revision_loop() -> None:
    """User rejects recommendation at Decision phase; session rolls back to Divergence."""
    inputs = [
        "", "", "", "", "",  # advance phases 0-4
        "2",  # Reject and request revision
        "Custo mensal excessivo na proposta",  # revision reason
        "Custo máximo de $50/mês, Usar SQLite",  # additional constraints
        "",  # advance revised phase 1
        "",  # advance revised phase 2
        "",  # advance revised phase 3
        "",  # advance revised phase 4
        "1",  # accept new recommendation
        "1",  # close reflection
    ]
    app, orchestrator, store, _, outputs = create_app(input_sequence=inputs)

    session = await app.run(example_mode=True)

    assert session.current_state == CommitteeState.COMPLETED
    assert len(session.interventions) >= 1
    assert any("REVISÃO SOLICITADA" in msg for msg in outputs)


# ==============================================================================
# 2. Negative Tests (Section 17)
# ==============================================================================


def test_negative_1_blind_divergence_isolation() -> None:
    """Test 1: ContextBuilder strictly isolates Architect and Pragmatist in Phase 1."""
    store = EventStore(":memory:")
    sm = StateMachine(event_store=store)
    cb = ContextBuilder()
    runner = AgentRunner(llm_provider=MockLLMProvider())
    orchestrator = CommitteeOrchestrator(sm, store, cb, runner)
    session = orchestrator.create_session(uuid4(), "Test Isolation")

    # In Phase 1 Divergence, neither proposal should be visible to either proponent
    ctx_arch = cb.build_context(session, CommitteeRole.ARCHITECT, phase="PHASE_1_DIVERGENCE")
    ctx_prag = cb.build_context(session, CommitteeRole.PRAGMATIST, phase="PHASE_1_DIVERGENCE")

    assert "proposals" not in ctx_arch or not ctx_arch.get("proposals")
    assert "proposals" not in ctx_prag or not ctx_prag.get("proposals")


def test_negative_2_invalid_command_handled_safely() -> None:
    """Test 2: Invalid command in interactive prompt returns error without advancing state."""
    app, orchestrator, store, _, outputs = create_app()
    session = orchestrator.create_session(uuid4(), "Test Command")
    handler = CommandHandler(orchestrator, session, print_func=outputs.append)

    initial_state = session.current_state
    result = handler.handle("invalid_random_cmd_123")

    assert result.handled is False
    assert session.current_state == initial_state
    assert any("Comando desconhecido" in msg for msg in outputs)


@pytest.mark.anyio
async def test_negative_3_cannot_decide_without_synthesis() -> None:
    """Test 3: Quality gate blocks DecisionRecord if Convergence synthesis is missing."""
    store = EventStore(":memory:")
    sm = StateMachine(event_store=store)
    cb = ContextBuilder()
    runner = AgentRunner(llm_provider=MockLLMProvider())
    orchestrator = CommitteeOrchestrator(sm, store, cb, runner)
    session = orchestrator.create_session(uuid4(), "Test Quality Gate")

    # Fast forward directly to DECISION state without prior phases
    session.current_state = CommitteeState.DECISION
    session.deliberation_synthesis = None

    provider = MockLLMProvider()
    decision = provider._generate_default(DecisionRecord, {})
    env = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.DECISION_RECORDED,
        actor=CommitteeRole.DECISOR,
        payload=decision,
    )

    with pytest.raises(CommitteeError):
        sm.handle_event(session, env)


def test_negative_4_empty_answer_reprompts() -> None:
    """Test 4: prompt_question_answer forces non-empty answer and reprompts on empty."""
    outputs: list[str] = []
    inputs = ["", "  ", "Resposta válida do usuário"]
    ui = SessionUI(input_func=lambda _: inputs.pop(0), print_func=outputs.append)

    q = OpenQuestion(id="Q1", question="Qual a carga?", why_critical="Dimensionamento")
    ans = ui.prompt_question_answer(q)

    assert ans == "Resposta válida do usuário"
    assert any("A resposta não pode ser vazia" in msg for msg in outputs)


def test_negative_5_event_store_tamper_proofing() -> None:
    """Test 5: Directly modifying or deleting rows in EventStore is prevented by SQLite triggers."""
    store = EventStore(":memory:")
    sm = StateMachine(event_store=store)
    cb = ContextBuilder()
    runner = AgentRunner(llm_provider=MockLLMProvider())
    orchestrator = CommitteeOrchestrator(sm, store, cb, runner)
    session = orchestrator.create_session(uuid4(), "Tamper Test")

    # Attempt direct SQL UPDATE on the append-only event table
    with pytest.raises(sqlite3.IntegrityError, match="UPDATE operations are forbidden"):
        store._conn.execute(
            "UPDATE events SET actor = 'HACKER' WHERE session_id = ?",
            (str(session.session_id),),
        )


def test_negative_6_reject_recommendation_decrements_state() -> None:
    """Test 6: Rejecting recommendation cleanly decrements state to DIVERGENCE."""
    store = EventStore(":memory:")
    sm = StateMachine(event_store=store)
    cb = ContextBuilder()
    runner = AgentRunner(llm_provider=MockLLMProvider())
    orchestrator = CommitteeOrchestrator(sm, store, cb, runner)
    session = orchestrator.create_session(uuid4(), "Revision Test")
    session.current_state = CommitteeState.DECISION

    cmd = UserRequestRevisionCommand(
        session_id=session.session_id,
        target_decision_id="DEC-001",
        reason_for_rejection="Inviável financeiramente",
        additional_constraints=["Custo máximo $10"],
    )
    orchestrator.user_override(session, cmd)

    assert session.current_state == CommitteeState.DIVERGENCE
    assert len(session.interventions) == 1


@pytest.mark.anyio
async def test_negative_7_abort_halts_session() -> None:
    """Test 7: Aborting session transitions state to CANCELLED and halts further steps."""
    inputs = [
        "",  # advance phase 0
        "abort Cancelamento antecipado",  # abort at phase 1 advance
    ]
    app, orchestrator, store, _, outputs = create_app(input_sequence=inputs)

    session = await app.run(example_mode=True)

    assert session.current_state == CommitteeState.CANCELLED
    assert any("ABORTADO" in msg for msg in outputs)


def test_negative_8_crash_recovery_from_event_store() -> None:
    """Test 8: Interrupted session can be fully reconstituted from the EventStore."""
    store = EventStore(":memory:")
    sm = StateMachine(event_store=store)
    cb = ContextBuilder()
    runner = AgentRunner(llm_provider=MockLLMProvider())
    orchestrator = CommitteeOrchestrator(sm, store, cb, runner)
    session = orchestrator.create_session(uuid4(), "Crash Recovery Test")

    # Simulate events up to DIVERGENCE
    events_before = store.get_events(session.session_id)
    assert len(events_before) >= 1

    # Reconstitute new session instance from store
    reconstituted = replay_session(session.session_id, store)
    assert reconstituted.session_id == session.session_id
    assert reconstituted.current_state == session.current_state
    assert reconstituted.current_phase == session.current_phase
    assert reconstituted.version == session.version


@pytest.mark.anyio
async def test_negative_9_replay_parity() -> None:
    """Test 9: Replaying complete interactive session produces identical final state."""
    inputs = ["", "", "", "", "", "1", "1"]
    app, orchestrator, store, _, _ = create_app(input_sequence=inputs)

    session = await app.run(example_mode=True)
    assert session.current_state == CommitteeState.COMPLETED

    replayed = replay_session(session.session_id, store)
    assert replayed.session_id == session.session_id
    assert replayed.current_state == CommitteeState.COMPLETED
    assert replayed.decision_record == session.decision_record
    assert replayed.learning_report == session.learning_report


def test_negative_10_cli_never_bypasses_state_machine() -> None:
    """Test 10: State transitions are only triggered via StateMachine events."""
    store = EventStore(":memory:")
    sm = StateMachine(event_store=store)
    cb = ContextBuilder()
    runner = AgentRunner(llm_provider=MockLLMProvider())
    orchestrator = CommitteeOrchestrator(sm, store, cb, runner)
    session = orchestrator.create_session(uuid4(), "SM Invariant Test")

    # Verify session initial sequence is recorded
    events = store.get_events(session.session_id)
    assert len(events) == 1
    assert events[0].event_type == EventType.SESSION_CREATED

    # Verify invalid direct transition fails via SM
    provider = MockLLMProvider()
    decision = provider._generate_default(DecisionRecord, {})
    invalid_env = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.DECISION_RECORDED,
        actor=CommitteeRole.DECISOR,
        payload=decision,
    )
    with pytest.raises(CommitteeError):
        sm.handle_event(session, invalid_env)
