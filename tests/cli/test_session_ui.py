"""Unit tests for SessionUI covering prompts, normalization, and user interaction loops."""

from uuid import uuid4
import pytest

from schemas.common import CommitteeRole, Severity
from schemas.context import OpenQuestion
from src.committee.cli.commands import CommandHandler
from src.committee.cli.renderer import TerminalRenderer
from src.committee.cli.session_ui import SessionUI
from src.committee.event_store import EventStore
from src.committee.llm.mock import MockLLMProvider
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.orchestration.orchestrator import CommitteeOrchestrator
from src.committee.orchestration.runner import AgentRunner
from src.committee.state_machine import StateMachine


def create_test_dependencies():
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
    session = orchestrator.create_session(
        session_id=uuid4(),
        problem_statement="Test statement",
    )
    return orchestrator, session


def test_normalize_unknown() -> None:
    """_normalize_unknown maps empty or uninformative responses to 'UNKNOWN'."""
    assert SessionUI._normalize_unknown("") == "UNKNOWN"
    assert SessionUI._normalize_unknown("desconhecido") == "UNKNOWN"
    assert SessionUI._normalize_unknown("UNKNOWN") == "UNKNOWN"
    assert SessionUI._normalize_unknown("não sei") == "UNKNOWN"
    assert SessionUI._normalize_unknown("nao sei") == "UNKNOWN"
    assert SessionUI._normalize_unknown("n/a") == "UNKNOWN"
    assert SessionUI._normalize_unknown("-") == "UNKNOWN"
    assert SessionUI._normalize_unknown("3 devs backend") == "3 devs backend"


def test_prompt_problem_statement_with_normalizations() -> None:
    """prompt_problem_statement gathers problem and operational fields with UNKNOWN normalization."""
    outputs: list[str] = []
    inputs = [
        "",  # initial empty problem, triggers retry
        "Migração de monolito para microsserviços",  # valid problem
        "4 engenheiros",  # team
        "",  # budget (empty -> UNKNOWN)
        "3 meses",  # deadline
        "não sei",  # objective (não sei -> UNKNOWN)
        "Zero downtime",  # success_criteria
    ]

    ui = SessionUI(
        input_func=lambda _: inputs.pop(0),
        print_func=outputs.append,
    )

    statement = ui.prompt_problem_statement()

    assert "Migração de monolito para microsserviços" in statement
    assert "- Equipe: 4 engenheiros" in statement
    assert "- Orçamento: UNKNOWN" in statement
    assert "- Prazo: 3 meses" in statement
    assert "- Objetivo: UNKNOWN" in statement
    assert "- Critérios de sucesso: Zero downtime" in statement
    assert any("AI COMMITTEE" in msg for msg in outputs)


def test_prompt_question_answer() -> None:
    """prompt_question_answer renders investigation card and collects non-empty response."""
    outputs: list[str] = []
    inputs = [
        "",  # empty, triggers retry
        "   ",  # spaces, triggers retry
        "Esperamos no máximo 500 req/s de pico.",  # valid answer
    ]

    ui = SessionUI(
        input_func=lambda _: inputs.pop(0),
        print_func=outputs.append,
    )

    question = OpenQuestion(
        id="Q1",
        question="Qual o volume esperado de requisições?",
        why_critical="Necessário para dimensionar brokers",
    )

    ans = ui.prompt_question_answer(question)
    assert ans == "Esperamos no máximo 500 req/s de pico."
    assert any("INVESTIGAÇÃO" in msg for msg in outputs)
    assert any("Qual o volume esperado" in msg for msg in outputs)


def test_prompt_decision_acceptance_valid_and_invalid() -> None:
    """prompt_decision_acceptance retries on invalid input and returns valid integer choice."""
    outputs: list[str] = []
    inputs = ["invalid", "5", "1"]

    ui = SessionUI(
        input_func=lambda _: inputs.pop(0),
        print_func=outputs.append,
    )

    choice = ui.prompt_decision_acceptance()
    assert choice == 1
    assert any("Opção inválida" in msg for msg in outputs)

    # Test choice 2
    inputs = ["2"]
    assert ui.prompt_decision_acceptance() == 2

    # Test choice 3
    inputs = ["3"]
    assert ui.prompt_decision_acceptance() == 3


def test_prompt_reflection_close_valid_and_invalid() -> None:
    """prompt_reflection_close retries on invalid input and returns 1 or 2."""
    outputs: list[str] = []
    inputs = ["abc", "2"]

    ui = SessionUI(
        input_func=lambda _: inputs.pop(0),
        print_func=outputs.append,
    )

    choice = ui.prompt_reflection_close()
    assert choice == 2
    assert any("Opção inválida" in msg for msg in outputs)

    # Test choice 1
    inputs = ["1"]
    assert ui.prompt_reflection_close() == 1


def test_prompt_step_advance_direct_enter() -> None:
    """Pressing Enter directly returns True to proceed."""
    orchestrator, session = create_test_dependencies()
    handler = CommandHandler(orchestrator, session)
    inputs = [""]

    ui = SessionUI(input_func=lambda _: inputs.pop(0))
    res = ui.prompt_step_advance(handler)
    assert res is True


def test_prompt_step_advance_intermediate_commands_then_proceed() -> None:
    """Executing status or help before pressing Enter still proceeds."""
    orchestrator, session = create_test_dependencies()
    outputs: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=outputs.append)
    inputs = ["status", "help", ""]

    ui = SessionUI(
        input_func=lambda _: inputs.pop(0),
        print_func=outputs.append,
    )
    res = ui.prompt_step_advance(handler)
    assert res is True
    assert any("STATUS DA SESSÃO" in msg for msg in outputs)
    assert any("COMANDOS DISPONÍVEIS" in msg for msg in outputs)


def test_prompt_step_advance_abort() -> None:
    """Executing abort command in step advance returns False."""
    orchestrator, session = create_test_dependencies()
    outputs: list[str] = []
    handler = CommandHandler(orchestrator, session, print_func=outputs.append)
    inputs = ["abort Cancelamento manual"]

    ui = SessionUI(
        input_func=lambda _: inputs.pop(0),
        print_func=outputs.append,
    )
    res = ui.prompt_step_advance(handler)
    assert res is False
