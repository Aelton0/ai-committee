"""Session UI controller managing user interactions, prompts, and phase transitions."""

from typing import Callable

from schemas.context import OpenQuestion
from src.committee.cli.commands import CommandHandler
from src.committee.cli.renderer import TerminalRenderer


class SessionUI:
    """Handles terminal input and output dialogues for the interactive committee session."""

    def __init__(
        self,
        renderer: TerminalRenderer | None = None,
        input_func: Callable[[str], str] = input,
        print_func: Callable[[str], None] = print,
    ) -> None:
        self.renderer = renderer or TerminalRenderer()
        self.input_func = input_func
        self.print_func = print_func

    def prompt_problem_statement(self) -> str:
        """Prompt user for the initial problem description and structured context fields."""
        self.print_func(self.renderer.render_banner())
        self.print_func("Nova deliberação\n")
        self.print_func("Descreva o problema:")
        problem = self.input_func("> ").strip()
        while not problem:
            self.print_func("O problema não pode ser vazio. Descreva o problema:")
            problem = self.input_func("> ").strip()

        self.print_func("\nContexto Operacional Básico (Pressione Enter para campos desconhecidos):")
        team = self._normalize_unknown(self.input_func("Equipe: ").strip())
        budget = self._normalize_unknown(self.input_func("Orçamento: ").strip())
        deadline = self._normalize_unknown(self.input_func("Prazo: ").strip())
        objective = self._normalize_unknown(self.input_func("Objetivo: ").strip())
        success_criteria = self._normalize_unknown(self.input_func("Critérios de sucesso: ").strip())

        full_statement = (
            f"{problem}\n\n"
            f"Contexto declarado pelo usuário:\n"
            f"- Equipe: {team}\n"
            f"- Orçamento: {budget}\n"
            f"- Prazo: {deadline}\n"
            f"- Objetivo: {objective}\n"
            f"- Critérios de sucesso: {success_criteria}"
        )
        return full_statement

    def prompt_question_answer(self, question: OpenQuestion) -> str:
        """Render Facilitator open question and prompt user for answer."""
        card = self.renderer.render_investigation_card(
            question=question.question,
            rationale=question.why_critical,
            impact="CRITICAL",
        )
        self.print_func("\n" + card)
        self.print_func("Resposta:")
        answer = self.input_func("> ").strip()
        while not answer:
            self.print_func("A resposta não pode ser vazia. Digite a resposta:")
            answer = self.input_func("> ").strip()
        return answer

    def prompt_decision_acceptance(self, is_insufficient_evidence: bool = False) -> int:
        """Ask user whether to accept, reject with revision, or abort the recommendation/verdict."""
        self.print_func("\n" + "=" * 70)
        if is_insufficient_evidence:
            self.print_func("O Comitê concluiu por INSUFFICIENT_EVIDENCE (dados insuficientes para decidir).\n")
            self.print_func("Como deseja proceder?\n")
            self.print_func("  [1] Aceitar conclusão e encerrar")
            self.print_func("  [2] Rejeitar e solicitar revisão (injetar novos dados)")
            self.print_func("  [3] Abortar")
        else:
            self.print_func("O Comitê fez uma recomendação.\n")
            self.print_func("Você aceita a recomendação?\n")
            self.print_func("  [1] Aceitar")
            self.print_func("  [2] Rejeitar e solicitar revisão")
            self.print_func("  [3] Abortar")
        self.print_func("=" * 70)

        while True:
            choice = self.input_func("Opção (1, 2 ou 3): ").strip()
            if choice in ("1", "2", "3"):
                return int(choice)
            self.print_func("[ERRO] Opção inválida. Digite 1, 2 ou 3.")

    def prompt_reflection_close(self) -> int:
        """Ask user whether to close the session or request revision after reflection."""
        self.print_func("\n" + "=" * 70)
        self.print_func("Você deseja encerrar a sessão?\n")
        self.print_func("  [1] Encerrar")
        self.print_func("  [2] Revisar")
        self.print_func("=" * 70)

        while True:
            choice = self.input_func("Opção (1 ou 2): ").strip()
            if choice in ("1", "2"):
                return int(choice)
            self.print_func("[ERRO] Opção inválida. Digite 1 ou 2.")

    def prompt_step_advance(self, command_handler: CommandHandler) -> bool:
        """Prompt user to continue or execute intermediate commands between phases.

        Returns True to proceed to next phase, False if execution was aborted.
        """
        while True:
            raw = self.input_func(
                "\nPressione [Enter] para continuar ou digite comando (help, status, context, abort...): "
            ).strip()
            if not raw:
                return True

            res = command_handler.handle(raw)
            if res.should_abort:
                return False
            if res.should_revise:
                return True
            if res.should_resume:
                return True
            # if res.handled or unhandled, loop and allow user to enter next command or continue

    @staticmethod
    def _normalize_unknown(val: str) -> str:
        """Normalize empty or 'desconhecido' inputs to UNKNOWN."""
        if not val or val.lower() in ("desconhecido", "unknown", "não sei", "nao sei", "n/a", "-"):
            return "UNKNOWN"
        return val
