"""Unit tests for CLI CommandHandler."""

from uuid import uuid4
import pytest

from schemas.common import CommitteeRole, CommitteeState, Confidence, DecisionStatus, Severity
from schemas.context import Assumption, Constraint, Fact, ProblemContext, Unknown
from schemas.decision import DecisionRecord, ReviewTrigger, TradeOffContract
from schemas.events import EventEnvelope, SessionCreatedPayload
from schemas.intervention import AssumptionContestAction, UserAbortCommand, UserContestAssumptionCommand, UserRequestRevisionCommand
from src.committee.cli.commands import CommandHandler, CommandResult
from src.committee.cli.renderer import TerminalRenderer
from src.committee.event_store import EventStore
from src.committee.llm.mock import MockLLMProvider
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.orchestration.orchestrator import CommitteeOrchestrator
from src.committee.orchestration.runner import AgentRunner
from src.committee.session import Session
from src.committee.state_machine import StateMachine


def create_test_session() -> tuple[CommitteeOrchestrator, Session, EventStore]:
    """Create orchestrator and session with in-memory SQLite store."""
    store = EventStore(":memory:")
    sm = StateMachine(event_store=store)
    cb = ContextBuilder()
    runner = AgentRunner(llm_provider=MockLLMProvider())
    orchestrator = CommitteeOrchestrator(
        state_machine=sm,
        event_store=store,
        context_builder=cb,
        runner=runner,
    )
    session_id = uuid4()
    session = orchestrator.create_session(
        session_id=session_id,
        problem_statement="Construir arquitetura para sistema financeiro",
    )
    return orchestrator, session, store


def test_command_empty_and_resume() -> None:
    """Empty line or resume returns should_resume=True."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    res_empty = handler.handle("")
    assert res_empty.handled is True
    assert res_empty.should_resume is True

    res_resume = handler.handle("resume")
    assert res_resume.handled is True
    assert res_resume.should_resume is True
    assert any("RETOMADA" in msg for msg in output)

    res_continue = handler.handle("continue")
    assert res_continue.handled is True
    assert res_continue.should_resume is True


def test_command_help() -> None:
    """help command renders command catalog."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    res = handler.handle("help")
    assert res.handled is True
    assert any("COMANDOS DISPONÍVEIS" in msg for msg in output)


def test_command_status() -> None:
    """status command displays current session state."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    res = handler.handle("status")
    assert res.handled is True
    assert any("STATUS DA SESSÃO" in msg for msg in output)
    assert any("INVESTIGATION" in msg for msg in output)


def test_command_context() -> None:
    """context command displays problem context or info when empty."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    # Empty context
    session.problem_context = None
    res = handler.handle("context")
    assert res.handled is True
    assert any("ainda não foi inicializado" in msg for msg in output)

    # Populated context
    output.clear()
    session.problem_context = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Test Problem",
        facts=[Fact(id="F1", description="Fato 1", source="user")],
        assumptions=[Assumption(id="A1", description="Premissa 1", rationale="R1", risk_level=Severity.HIGH)],
        constraints=[Constraint(id="C1", description="Restrição 1")],
        unknowns=[],
        success_criteria=["Critério 1"],
    )
    res = handler.handle("context")
    assert res.handled is True
    assert any("CONTEXTO ATUAL DO PROBLEMA" in msg for msg in output)
    assert any("Fato 1" in msg for msg in output)


def test_command_events() -> None:
    """events command lists audit trail from event store."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    res = handler.handle("events")
    assert res.handled is True
    assert any("EVENT STORE" in msg for msg in output)
    assert any("SESSION_CREATED" in msg for msg in output)


def test_command_pause() -> None:
    """pause command returns should_pause=True."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    res = handler.handle("pause")
    assert res.handled is True
    assert res.should_pause is True
    assert any("PAUSA" in msg for msg in output)


def test_command_abort_with_args() -> None:
    """abort command with inline reason executes abort override."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    res = handler.handle("abort Requisitos alterados pelo cliente")
    assert res.handled is True
    assert res.should_abort is True
    assert session.current_state == CommitteeState.CANCELLED
    assert any("ABORTADO" in msg for msg in output)


def test_command_abort_interactive_input() -> None:
    """abort command without inline reason prompts user."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    inputs = ["Cancelamento emergencial"]
    handler = CommandHandler(
        orchestrator,
        session,
        input_func=lambda _: inputs.pop(0),
        print_func=output.append,
    )

    res = handler.handle("abort")
    assert res.handled is True
    assert res.should_abort is True
    assert session.current_state == CommitteeState.CANCELLED


def test_command_contest_assumption_reject() -> None:
    """contest command with choice 1 rejects an assumption."""
    orchestrator, session, _ = create_test_session()
    session.problem_context = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Test Problem",
        facts=[],
        assumptions=[Assumption(id="A1", description="Kafka é obrigatório", rationale="R", risk_level=Severity.HIGH)],
        constraints=[],
        unknowns=[],
        success_criteria=["Critério 1"],
    )
    output: list[str] = []
    # inputs: choice 1 (reject), justification
    inputs = ["1", "Não usamos Kafka nesta infraestrutura"]
    handler = CommandHandler(
        orchestrator,
        session,
        input_func=lambda _: inputs.pop(0),
        print_func=output.append,
    )

    res = handler.handle("contest A1")
    assert res.handled is True
    # Verify assumption A1 was removed/rejected in session.problem_context
    assert not any(a.id == "A1" for a in session.problem_context.assumptions)
    assert any("contestada com sucesso" in msg for msg in output)


def test_command_contest_assumption_modify() -> None:
    """contest command with choice 2 modifies an assumption."""
    orchestrator, session, _ = create_test_session()
    session.problem_context = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Test Problem",
        facts=[],
        assumptions=[Assumption(id="A2", description="Volume de 10k req/s", rationale="R", risk_level=Severity.MEDIUM)],
        constraints=[],
        unknowns=[],
        success_criteria=["Critério 1"],
    )
    output: list[str] = []
    # inputs: choice 2 (modify), new description, justification
    inputs = ["2", "Volume máximo de 500 req/s", "Ajustado após análise de tráfego"]
    handler = CommandHandler(
        orchestrator,
        session,
        input_func=lambda _: inputs.pop(0),
        print_func=output.append,
    )

    res = handler.handle("contest A2")
    assert res.handled is True
    a2 = next(a for a in session.problem_context.assumptions if a.id == "A2")
    assert a2.description == "Volume máximo de 500 req/s"


def test_command_revise_denied_in_early_state() -> None:
    """revise command is rejected if session is not yet in DECISION or later."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    res = handler.handle("revise")
    assert res.handled is True
    assert res.should_revise is False
    assert any("só permitida após formulação da decisão" in msg for msg in output)


def test_command_revise_in_decision_state() -> None:
    """revise command executes UserRequestRevisionCommand and rolls back to DIVERGENCE."""
    orchestrator, session, _ = create_test_session()
    session.current_state = CommitteeState.DECISION
    provider = MockLLMProvider()
    session.decision_record = provider._generate_default(DecisionRecord, {})
    output: list[str] = []
    # inputs: reason, additional constraints
    inputs = ["Não atende ao requisito de custo", "Custo máximo de $50/mês, Postgres único"]
    handler = CommandHandler(
        orchestrator,
        session,
        input_func=lambda _: inputs.pop(0),
        print_func=output.append,
    )

    res = handler.handle("revise")
    assert res.handled is True
    assert res.should_revise is True
    assert session.current_state == CommitteeState.DIVERGENCE
    assert any("REVISÃO SOLICITADA" in msg for msg in output)


def test_command_unknown() -> None:
    """Unknown command outputs error message and returns handled=False."""
    orchestrator, session, _ = create_test_session()
    output: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=output.append)

    res = handler.handle("xyz_invalid_command")
    assert res.handled is False
    assert any("Comando desconhecido: 'xyz_invalid_command'" in msg for msg in output)


def test_command_abort_in_insufficient_evidence_state() -> None:
    """abort command cleanly cancels session when in INSUFFICIENT_EVIDENCE state."""
    orchestrator, session, _ = create_test_session()
    session.current_state = CommitteeState.INSUFFICIENT_EVIDENCE
    output: list[str] = []
    handler = CommandHandler(
        orchestrator,
        session,
        input_func=lambda _: "Cancelando teste de insuficiência de evidência",
        print_func=output.append,
    )

    res = handler.handle("abort")
    assert res.handled is True
    assert res.should_abort is True
    assert session.current_state == CommitteeState.CANCELLED
    assert any("ABORTADO" in msg for msg in output)

