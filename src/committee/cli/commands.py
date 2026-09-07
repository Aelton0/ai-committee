"""Command handler for AI Committee interactive CLI."""

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, ConfigDict
from schemas.common import CommitteeState
from schemas.intervention import (
    AssumptionContestAction,
    UserAbortCommand,
    UserContestAssumptionCommand,
    UserRequestRevisionCommand,
)
from src.committee.cli.renderer import TerminalRenderer
from src.committee.orchestration.orchestrator import CommitteeOrchestrator
from src.committee.session import Session


@dataclass
class CommandResult:
    """Outcome of processing an interactive CLI command."""

    handled: bool
    message: str = ""
    should_pause: bool = False
    should_resume: bool = False
    should_abort: bool = False
    should_revise: bool = False


class CommandHandler:
    """Parses and executes user commands during interactive deliberation."""

    def __init__(
        self,
        orchestrator: CommitteeOrchestrator,
        session: Session,
        renderer: TerminalRenderer | None = None,
        input_func: Callable[[str], str] = input,
        print_func: Callable[[str], None] = print,
    ) -> None:
        self.orchestrator = orchestrator
        self.session = session
        self.renderer = renderer or TerminalRenderer()
        self.input_func = input_func
        self.print_func = print_func

    def handle(self, command_line: str) -> CommandResult:
        """Parse and execute a command string entered by the human user."""
        raw = command_line.strip()
        if not raw:
            return CommandResult(handled=True, should_resume=True)

        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "help":
            self.print_func(self.renderer.render_help())
            return CommandResult(handled=True)

        elif cmd == "status":
            self.print_func(self.renderer.render_session_status(self.session))
            return CommandResult(handled=True)

        elif cmd == "context":
            if self.session.problem_context:
                self.print_func(self.renderer.render_context_summary(self.session.problem_context))
            else:
                self.print_func("[INFO] ProblemContext ainda não foi inicializado nesta sessão.")
            return CommandResult(handled=True)

        elif cmd == "events":
            if self.orchestrator.event_store:
                events = self.orchestrator.event_store.get_events(self.session.session_id)
                self.print_func(self.renderer.render_events_table(events))
            else:
                self.print_func("[INFO] EventStore não disponível.")
            return CommandResult(handled=True)

        elif cmd == "pause":
            self.print_func("\n[PAUSA] Deliberação pausada pelo usuário. Digite 'resume' ou pressione Enter para continuar.")
            return CommandResult(handled=True, should_pause=True)

        elif cmd in ("resume", "continue"):
            self.print_func("[RETOMADA] Continuando a deliberação...")
            return CommandResult(handled=True, should_resume=True)

        elif cmd == "abort":
            return self._handle_abort(args)

        elif cmd == "contest":
            return self._handle_contest(args)

        elif cmd == "revise":
            return self._handle_revise(args)

        else:
            msg = f"[ERRO] Comando desconhecido: '{cmd}'. Digite 'help' para listar os comandos."
            self.print_func(msg)
            return CommandResult(handled=False, message=msg)

    def _handle_abort(self, reason: str) -> CommandResult:
        """Execute UserAbortCommand."""
        if not reason.strip():
            reason = self.input_func("Motivo do cancelamento: ").strip()
            if not reason:
                reason = "Cancelado pelo usuário interativo."

        cmd = UserAbortCommand(
            session_id=self.session.session_id,
            reason=reason,
        )
        self.orchestrator.user_override(self.session, cmd)
        self.print_func(f"\n[ABORTADO] Sessão cancelada pelo usuário. Motivo: {reason}")
        return CommandResult(handled=True, should_abort=True)

    def _handle_contest(self, assumption_id: str) -> CommandResult:
        """Execute UserContestAssumptionCommand."""
        if not assumption_id.strip():
            assumption_id = self.input_func("ID da premissa a contestar (ex: A1): ").strip()

        if not assumption_id:
            self.print_func("[ERRO] ID da premissa não informado.")
            return CommandResult(handled=True, message="ID não informado.")

        self.print_func(f"Contestando premissa '{assumption_id}':")
        self.print_func("  [1] Rejeitar premissa completamente")
        self.print_func("  [2] Modificar descrição da premissa")
        choice = self.input_func("Escolha (1 ou 2): ").strip()

        if choice == "2":
            action = AssumptionContestAction.MODIFY
            new_desc = self.input_func("Nova descrição para a premissa: ").strip()
            if not new_desc:
                self.print_func("[ERRO] Nova descrição não pode ser vazia ao modificar.")
                return CommandResult(handled=True, message="Descrição vazia.")
        else:
            action = AssumptionContestAction.REJECT
            new_desc = None

        justification = self.input_func("Justificativa da contestação: ").strip()
        if not justification or len(justification) < 5:
            justification = f"Contestação da premissa {assumption_id} realizada pelo usuário."

        cmd = UserContestAssumptionCommand(
            session_id=self.session.session_id,
            assumption_id=assumption_id,
            action=action,
            justification=justification,
            new_description=new_desc,
        )
        self.orchestrator.user_override(self.session, cmd)
        self.print_func(f"[OK] Premissa '{assumption_id}' contestada com sucesso via evento auditable.")
        return CommandResult(handled=True)

    def _handle_revise(self, args: str) -> CommandResult:
        """Execute UserRequestRevisionCommand."""
        if self.session.current_state not in (
            CommitteeState.DECISION,
            CommitteeState.INSUFFICIENT_EVIDENCE,
            CommitteeState.REFLECTION,
            CommitteeState.COMPLETED,
        ):
            self.print_func(
                f"[ERRO] Solicitação de revisão só permitida após formulação da decisão (estado atual: {self.session.current_state.value})."
            )
            return CommandResult(handled=True, message="Revisão não permitida nesta fase.")

        decision_id = (
            self.session.decision_record.artifact_id
            if self.session.decision_record
            else "DEC-001"
        )
        reason = self.input_func("Motivo da rejeição da recomendação: ").strip()
        if not reason or len(reason) < 5:
            reason = "Recomendação rejeitada para inclusão de novas restrições técnicas."

        constraints_input = self.input_func(
            "Novas restrições adicionais (separadas por vírgula): "
        ).strip()
        constraints = [c.strip() for c in constraints_input.split(",") if c.strip()]
        if not constraints:
            constraints = ["Restrição adicional especificada pelo usuário humano."]

        cmd = UserRequestRevisionCommand(
            session_id=self.session.session_id,
            target_decision_id=decision_id,
            reason_for_rejection=reason,
            additional_constraints=constraints,
        )
        self.orchestrator.user_override(self.session, cmd)
        self.print_func("\n[REVISÃO SOLICITADA] Deliberação retrocedeu para a FASE 1 (Divergência) com novas restrições.")
        return CommandResult(handled=True, should_revise=True)
