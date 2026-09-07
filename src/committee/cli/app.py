"""Main application controller for the AI Committee interactive CLI."""

import asyncio
from uuid import UUID, uuid4

from schemas.common import CommitteeRole, CommitteeState, DecisionStatus
from src.committee.cli.commands import CommandHandler
from src.committee.cli.renderer import TerminalRenderer
from src.committee.cli.session_ui import SessionUI
from src.committee.orchestration.orchestrator import CommitteeOrchestrator
from src.committee.session import Session


class CommitteeCLIApp:
    """Coordinates the interactive terminal deliberation session for a human user."""

    def __init__(
        self,
        orchestrator: CommitteeOrchestrator,
        ui: SessionUI | None = None,
        renderer: TerminalRenderer | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.renderer = renderer or TerminalRenderer()
        self.ui = ui or SessionUI(renderer=self.renderer)

    async def run(
        self,
        example_mode: bool = False,
        session_id: UUID | None = None,
    ) -> Session:
        """Execute an interactive deliberation session from start to finish."""
        sid = session_id or uuid4()

        if example_mode:
            self.ui.print_func(self.renderer.render_banner())
            self.ui.print_func("[MODO DEMONSTRAÇÃO ATIVO] Carregando cenário de exemplo pré-configurado...\n")
            problem_statement = (
                "Sistema de e-commerce enfrentando saturação de conexões no PostgreSQL 15 e timeouts "
                "de checkout durante picos de campanha com 1.200 req/s.\n\n"
                "Contexto declarado pelo usuário:\n"
                "- Equipe: 3 desenvolvedores backend (nível pleno)\n"
                "- Orçamento: $400/mês adicional máximo\n"
                "- Prazo: 4 semanas para homologação\n"
                "- Objetivo: Estabilizar o banco eliminando timeouts e erros 504 no checkout\n"
                "- Critérios de sucesso: Latência p95 < 100ms e zero erros sob carga de 1.500 req/s"
            )
        else:
            problem_statement = self.ui.prompt_problem_statement()

        # 1. Criação formal da sessão via StateMachine
        session = self.orchestrator.create_session(
            session_id=sid,
            problem_statement=problem_statement,
            user_id="cli-human-operator",
        )
        cmd_handler = CommandHandler(
            orchestrator=self.orchestrator,
            session=session,
            renderer=self.renderer,
            input_func=self.ui.input_func,
            print_func=self.ui.print_func,
        )

        self.ui.print_func(f"\n[INFO] Sessão iniciada com ID: {session.session_id}")

        # 2. Loop de Deliberação Interativa
        while session.current_state not in (
            CommitteeState.COMPLETED,
            CommitteeState.CANCELLED,
            CommitteeState.BLOCKED,
        ):
            state = session.current_state

            if state == CommitteeState.INVESTIGATION:
                # Executa passo de investigação
                await self.orchestrator.step(session)

                # Se Facilitador levantou perguntas abertas, interagir com o usuário
                if session.current_state == CommitteeState.WAITING_FOR_USER:
                    unanswered = (
                        session.problem_context.unanswered_questions()
                        if session.problem_context
                        else []
                    )
                    for q in unanswered:
                        ans = self.ui.prompt_question_answer(q)
                        self.orchestrator.user_respond(session, q.id, ans)

                    # Retoma investigação com as respostas
                    await self.orchestrator.step(session)

                if session.current_state == CommitteeState.DIVERGENCE:
                    self.ui.print_func(self.renderer.render_phase_header("Fase 0 — Investigação Concluída"))
                    if session.problem_context:
                        self.ui.print_func(self.renderer.render_context_summary(session.problem_context))
                    if not self.ui.prompt_step_advance(cmd_handler):
                        break

            elif state == CommitteeState.WAITING_FOR_USER:
                unanswered = (
                    session.problem_context.unanswered_questions()
                    if session.problem_context
                    else []
                )
                for q in unanswered:
                    ans = self.ui.prompt_question_answer(q)
                    self.orchestrator.user_respond(session, q.id, ans)

                # Retoma investigação com as respostas
                await self.orchestrator.step(session)

                if session.current_state == CommitteeState.DIVERGENCE:
                    self.ui.print_func(self.renderer.render_phase_header("Fase 0 — Investigação Concluída"))
                    if session.problem_context:
                        self.ui.print_func(self.renderer.render_context_summary(session.problem_context))
                    if not self.ui.prompt_step_advance(cmd_handler):
                        break

            elif state == CommitteeState.DIVERGENCE:
                self.ui.print_func(self.renderer.render_phase_header("Fase 1 — Divergência Cega"))
                self.ui.print_func("Executando geração independente de propostas concorrentes...")

                await self.orchestrator.step(session)

                arch_prop = session.proposals.get(CommitteeRole.ARCHITECT)
                prag_prop = session.proposals.get(CommitteeRole.PRAGMATIST)

                if arch_prop:
                    self.ui.print_func("\n" + self.renderer.render_proposal(arch_prop))
                if prag_prop:
                    self.ui.print_func("\n" + self.renderer.render_proposal(prag_prop))

                if not self.ui.prompt_step_advance(cmd_handler):
                    break

            elif state == CommitteeState.CONFRONTATION:
                self.ui.print_func(self.renderer.render_phase_header("Fase 2 — Confronto (Auditoria Adversarial)"))
                self.ui.print_func("Auditor / SRE avaliando vulnerabilidades, SPOFs e riscos...")

                await self.orchestrator.step(session)

                if session.audit_report:
                    self.ui.print_func("\n" + self.renderer.render_audit_report(session.audit_report))

                if not self.ui.prompt_step_advance(cmd_handler):
                    break

            elif state == CommitteeState.DEFENSE:
                self.ui.print_func(self.renderer.render_phase_header("Fase 3 — Defesa e Refinamento"))
                self.ui.print_func("Arquiteto e Pragmático respondendo aos achados da auditoria...")

                await self.orchestrator.step(session)

                arch_def = session.defenses.get(CommitteeRole.ARCHITECT)
                prag_def = session.defenses.get(CommitteeRole.PRAGMATIST)

                if arch_def:
                    self.ui.print_func("\n" + self.renderer.render_defense(arch_def))
                if prag_def:
                    self.ui.print_func("\n" + self.renderer.render_defense(prag_def))

                if not self.ui.prompt_step_advance(cmd_handler):
                    break

            elif state == CommitteeState.CONVERGENCE:
                self.ui.print_func(self.renderer.render_phase_header("Fase 4 — Convergência"))
                self.ui.print_func("Facilitador elaborando síntese imparcial do debate contraditório...")

                await self.orchestrator.step(session)

                if session.deliberation_synthesis:
                    self.ui.print_func("\n" + self.renderer.render_synthesis(session.deliberation_synthesis))

                if not self.ui.prompt_step_advance(cmd_handler):
                    break

            elif state == CommitteeState.DECISION:
                self.ui.print_func(self.renderer.render_phase_header("Fase 5 — Decisão"))
                self.ui.print_func("Decisor formulando veredito técnico e balanço de trade-offs...")

                await self.orchestrator.step(session)

                if session.decision_record:
                    self.ui.print_func("\n" + self.renderer.render_decision(session.decision_record))

                # Interação Humana de Aceite/Rejeição/Abort da Recomendação
                is_insufficient = (
                    session.decision_record is not None
                    and session.decision_record.status == DecisionStatus.INSUFFICIENT_EVIDENCE
                )
                choice = self.ui.prompt_decision_acceptance(is_insufficient_evidence=is_insufficient)

                if choice == 1:
                    # Aceitar recomendação ou aceitar conclusão de INSUFFICIENT_EVIDENCE
                    self.ui.print_func("\n[HUMAN-IN-THE-LOOP] Decisão aceita pelo operador humano.")
                    if is_insufficient:
                        break
                elif choice == 2:
                    # Rejeitar e solicitar revisão: volta para divergência com novas restrições
                    cmd_handler._handle_revise("")
                elif choice == 3:
                    # Abortar deliberação
                    cmd_handler._handle_abort("Rejeitado pelo operador humano na fase de decisão.")
                    break

            elif state == CommitteeState.REFLECTION:
                self.ui.print_func(self.renderer.render_phase_header("Fase 6 — Reflexão e Mentoria"))
                self.ui.print_func("Mentor estruturando material pedagógico e fundamentação teórica...")

                await self.orchestrator.step(session)

                if session.learning_report:
                    self.ui.print_func("\n" + self.renderer.render_mentor_reflection(session.learning_report))

                # Pergunta se deseja encerrar ou revisar
                close_choice = self.ui.prompt_reflection_close()
                if close_choice == 2:
                    cmd_handler._handle_revise("")

            elif state == CommitteeState.INSUFFICIENT_EVIDENCE:
                self.ui.print_func("\n[INSUFFICIENT_EVIDENCE] Deliberação suspensa por falta de dados críticos.")
                self.ui.print_func("Utilize o comando 'revise' para injetar novos dados ou 'abort' para encerrar.")
                if not self.ui.prompt_step_advance(cmd_handler):
                    break
                break

            else:
                self.ui.print_func(f"[INFO] Estado sem handler automático de UI: {state.value}")
                break

        # 3. Finalização e Telemetria
        self._render_completion(session)
        return session

    def _render_completion(self, session: Session) -> None:
        """Render session termination summary and telemetry."""
        status_msg = (
            "SESSÃO CONCLUÍDA COM SUCESSO!"
            if session.current_state == CommitteeState.COMPLETED
            else f"SESSÃO ENCERRADA COM STATUS: {session.current_state.value}"
        )
        self.ui.print_func("\n" + "=" * 70)
        self.ui.print_func(f"  {status_msg}")
        self.ui.print_func("=" * 70 + "\n")

        # Coleta de telemetria sem expor segredos
        provider = self.orchestrator.runner.llm_provider
        history = getattr(provider, "metadata_history", [])
        total_latency = sum(m.latency_seconds for m in history)
        input_tokens = sum(m.input_tokens for m in history)
        output_tokens = sum(m.output_tokens for m in history)
        total_tokens = sum(m.total_tokens for m in history)
        model_name = (
            history[-1].model
            if history
            else getattr(provider, "model", "mock-deterministic")
        )
        provider_name = provider.__class__.__name__.replace("LLMProvider", "").lower()

        telemetry = {
            "provider": provider_name,
            "model": model_name,
            "llm_calls": len(history),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "total_latency_seconds": total_latency,
        }
        self.ui.print_func(self.renderer.render_telemetry(telemetry))
