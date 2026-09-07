"""Terminal renderer for AI Committee deliberation sessions.

Produces clean, structured Unicode box-drawing visual output without external dependencies.
"""

import textwrap
from typing import Any

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState, DecisionStatus
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import BaseDefense
from schemas.events import EventEnvelope
from schemas.learning import LearningReport
from schemas.proposals import BaseProposal
from schemas.synthesis import DeliberationSynthesis
from src.committee.session import Session


def wrap_text(text: str, width: int = 66) -> list[str]:
    """Wrap text to fit inside box panels."""
    if not text:
        return []
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
        else:
            lines.extend(textwrap.wrap(paragraph, width=width))
    return lines


def box_panel(title: str, content_lines: list[str], width: int = 70) -> str:
    """Create a clean Unicode rounded box with a header."""
    inner_width = width - 4
    top = "╭─ " + title + " " + "─" * max(0, width - len(title) - 5) + "╮"
    bottom = "╰" + "─" * (width - 2) + "╯"

    body: list[str] = []
    for line in content_lines:
        if line.startswith("───"):
            # Section divider inside box
            div = "├" + "─" * (width - 2) + "┤"
            body.append(div)
        else:
            # Pad line to inner width
            padding = " " * max(0, inner_width - len(line))
            body.append(f"│ {line}{padding} │")

    return "\n".join([top] + body + [bottom])


class TerminalRenderer:
    """Renders formatted, readable deliberation artifacts and status views."""

    @staticmethod
    def render_banner() -> str:
        """Render the initial welcoming banner."""
        return (
            "╔════════════════════════════════════════════════════════════════════╗\n"
            "║                          AI COMMITTEE                              ║\n"
            "║         Plataforma de Deliberação Técnica Multiagente             ║\n"
            "╚════════════════════════════════════════════════════════════════════╝\n"
        )

    @staticmethod
    def render_phase_header(phase_name: str) -> str:
        """Render clear phase transition divider."""
        border = "═" * 70
        return f"\n{border}\n  {phase_name.upper()}\n{border}\n"

    @staticmethod
    def render_investigation_card(
        question: str, rationale: str, impact: str
    ) -> str:
        """Render Facilitator investigation question card."""
        lines: list[str] = []
        lines.append("Pergunta:")
        for l in wrap_text(question, width=64):
            lines.append(f"  {l}")
        lines.append("")
        lines.append("Por que isso importa:")
        for l in wrap_text(rationale, width=64):
            lines.append(f"  {l}")
        lines.append("")
        lines.append(f"Impacto da Incerteza: {impact}")

        top = "╔════════════════════════════════════════════════════════════════════╗"
        hdr = "║ FACILITADOR — INVESTIGAÇÃO                                         ║"
        sub = "╠════════════════════════════════════════════════════════════════════╣"
        bottom = "╚════════════════════════════════════════════════════════════════════╝"
        body = [f"║ {line:<66} ║" for line in lines]
        return "\n".join([top, hdr, sub] + body + [bottom])

    @staticmethod
    def render_proposal(proposal: BaseProposal) -> str:
        """Render an architectural proposal with structured epistemic section."""
        role_label = (
            "ARQUITETO"
            if proposal.proponent_role == CommitteeRole.ARCHITECT
            else "PRAGMÁTICO"
        )
        lines: list[str] = []

        # Título e resumo
        lines.append(f"Título: {proposal.title}")
        lines.append(f"Complexidade: {proposal.complexity.value} | Esforço: {proposal.costs.implementation_effort.value}")
        lines.append(f"Custo Estimado: {proposal.costs.infrastructure_cost_estimate}")
        lines.append("───")

        # Solução
        lines.append("SOLUÇÃO:")
        for l in wrap_text(proposal.solution, width=64):
            lines.append(f"  {l}")
        lines.append("")

        # Justificativa
        lines.append("JUSTIFICATIVA:")
        for l in wrap_text(proposal.rationale, width=64):
            lines.append(f"  {l}")
        lines.append("───")

        # Seção Epistêmica Estruturada
        ep = getattr(proposal, "epistemic_section", None)
        if ep:
            lines.append("FATOS:")
            if ep.facts:
                for f in ep.facts:
                    lines.append(f"  • [{f.id}] {f.statement} (origem: {f.source})")
            else:
                lines.append("  (Nenhum fato específico isolado)")
            lines.append("")

            lines.append("PREMISSAS:")
            if ep.assumptions:
                for a in ep.assumptions:
                    lines.append(f"  • [{a.id}] {a.statement}")
                    lines.append(f"    Invalidação: {a.invalidation_condition}")
            else:
                for a_str in proposal.assumptions:
                    lines.append(f"  • {a_str}")
            lines.append("")

            lines.append("INFERÊNCIAS:")
            if ep.inferences:
                for inf in ep.inferences:
                    lines.append(f"  • [{inf.id}] {inf.statement} (depende de: {inf.depends_on})")
            else:
                lines.append("  (Nenhuma inferência intermediária isolada)")
            lines.append("")

            lines.append("DESCONHECIDOS:")
            if ep.unknowns:
                for u in ep.unknowns:
                    lines.append(f"  • [{u.id}] {u.statement}")
            else:
                lines.append("  (Nenhuma incógnita crítica identificada)")
            lines.append("")

            lines.append("RECOMENDAÇÕES CONDICIONAIS:")
            if ep.conditional_recommendations:
                for cr in ep.conditional_recommendations:
                    lines.append(f"  • {cr.condition} -> {cr.recommendation}")
            else:
                lines.append("  (Recomendação direta incondicional)")
        else:
            lines.append("PREMISSAS:")
            for a_str in proposal.assumptions:
                lines.append(f"  • {a_str}")
            lines.append("───")
            lines.append("RISCOS:")
            for r in proposal.risks[:3]:
                lines.append(f"  - {r}")

        return box_panel(role_label, lines, width=70)

    @staticmethod
    def render_audit_report(report: AuditReport) -> str:
        """Render Auditor adversarial report."""
        lines: list[str] = []
        total_findings = len(report.findings_proposal_a) + len(report.findings_proposal_b)
        lines.append(f"Achados Totais: {total_findings} ({len(report.findings_proposal_a)} Proposta A, {len(report.findings_proposal_b)} Proposta B)")
        lines.append("───")

        lines.append("APONTAMENTOS — PROPOSTA DO ARQUITETO:")
        if report.findings_proposal_a:
            for f in report.findings_proposal_a:
                lines.append(f"  [{f.severity.value}] [{f.category.value}] {f.title}")
                for dl in wrap_text(f.description, width=62):
                    lines.append(f"    {dl}")
        else:
            lines.append("  (Nenhum finding crítico apontado)")
        lines.append("")

        lines.append("APONTAMENTOS — PROPOSTA DO PRAGMÁTICO:")
        if report.findings_proposal_b:
            for f in report.findings_proposal_b:
                lines.append(f"  [{f.severity.value}] [{f.category.value}] {f.title}")
                for dl in wrap_text(f.description, width=62):
                    lines.append(f"    {dl}")
        else:
            lines.append("  (Nenhum finding crítico apontado)")
        lines.append("───")

        lines.append("PONTOS ÚNICOS DE FALHA (SPOFs) IDENTIFICADOS:")
        if report.single_points_of_failure:
            for spof in report.single_points_of_failure[:3]:
                lines.append(f"  ⚠ {spof}")
        else:
            lines.append("  (Nenhum SPOF crítico registrado)")

        return box_panel("AUDITOR / SRE — CONFRONTO", lines, width=70)

    @staticmethod
    def render_defense(defense: BaseDefense) -> str:
        """Render proponent defense."""
        role_label = (
            "DEFESA — ARQUITETO"
            if defense.proponent_role == CommitteeRole.ARCHITECT
            else "DEFESA — PRAGMÁTICO"
        )
        lines: list[str] = []
        lines.append(f"Ação Proposta: {defense.proposal_action.value}")
        lines.append(f"Proposta Original: {defense.original_proposal_id} (v{defense.original_proposal_version})")
        if defense.revised_proposal_id:
            lines.append(f"Proposta Revisada: {defense.revised_proposal_id} (v{defense.revised_proposal_version})")
        lines.append("───")

        lines.append("RESPOSTAS ÀS CRÍTICAS DA AUDITORIA:")
        for cr in defense.critique_responses:
            lines.append(f"  • Finding '{cr.finding_id}': Postura '{cr.stance.value}'")
            lines.append(f"    Resposta: {cr.response}")
            lines.append(f"    Racional: {cr.rationale}")
            if cr.proposed_modification:
                lines.append(f"    Modificação v2: {cr.proposed_modification}")

        if defense.persistent_disagreements:
            lines.append("")
            lines.append("DISCORDÂNCIAS PERSISTENTES:")
            for d in defense.persistent_disagreements:
                lines.append(f"  - {d}")

        return box_panel(role_label, lines, width=70)

    @staticmethod
    def render_synthesis(synthesis: DeliberationSynthesis) -> str:
        """Render Facilitator convergence synthesis without recommendations."""
        lines: list[str] = []

        lines.append("PONTOS DE CONSENSO:")
        if synthesis.consensus_points:
            for cp in synthesis.consensus_points:
                lines.append(f"  ✓ {cp}")
        else:
            lines.append("  (Nenhum consenso pleno registrado)")
        lines.append("───")

        lines.append("PONTOS DE DIVERGÊNCIA:")
        if synthesis.divergence_points:
            for dp in synthesis.divergence_points:
                lines.append(f"  ⚡ {dp}")
        else:
            lines.append("  (Nenhuma divergência irreconciliável)")
        lines.append("───")

        if synthesis.arguments_by_alternative:
            lines.append("ARGUMENTOS POR ALTERNATIVA:")
            for alt in synthesis.arguments_by_alternative:
                lines.append(f"  [{alt.alternative_id}]:")
                for arg in alt.arguments:
                    lines.append(f"    • {arg}")
            lines.append("───")

        lines.append("TRADE-OFFS PRINCIPAIS:")
        if synthesis.trade_offs:
            for to in synthesis.trade_offs:
                lines.append(f"  • {to.dimension}:")
                lines.append(f"      Proposta A: {to.option_a}")
                lines.append(f"      Proposta B: {to.option_b}")
                if to.notes:
                    lines.append(f"      Nota:       {to.notes}")
        lines.append("───")

        lines.append("RISCOS NÃO RESOLVIDOS:")
        if synthesis.unresolved_risks:
            for ur in synthesis.unresolved_risks:
                lines.append(f"  ⚠ {ur}")
        else:
            lines.append("  (Todos os riscos foram mitigados)")

        return box_panel("FACILITADOR — CONVERGÊNCIA (IMPARCIAL)", lines, width=70)

    @staticmethod
    def render_decision(decision: DecisionRecord) -> str:
        """Render Decision Maker verdict and trade-offs."""
        lines: list[str] = []
        status_label = decision.status.value
        lines.append(f"STATUS: {status_label}")
        if decision.chosen_alternative:
            lines.append(f"ALTERNATIVA ESCOLHIDA: {decision.chosen_alternative}")
        lines.append(f"NÍVEL DE CONFIANÇA: {decision.confidence.value}")
        lines.append("───")

        lines.append("JUSTIFICATIVA TÉCNICA:")
        for l in wrap_text(decision.rationale, width=64):
            lines.append(f"  {l}")
        lines.append("───")

        if decision.supported_by:
            lines.append("FATOS DE SUPORTE (EPISTEMIC):")
            for sf in decision.supported_by:
                lines.append(f"  • {sf}")
            lines.append("───")

        lines.append("TRADE-OFFS ASSUMIDOS:")
        for to in decision.trade_offs:
            lines.append(f"  • Ganho: {to.gain}")
            lines.append(f"    Renúncia: {to.sacrifice}")
        lines.append("───")

        lines.append("DÍVIDAS TÉCNICAS E OPERACIONAIS:")
        all_debts = [f"[TÉCNICA] {td}" for td in decision.technical_debt] + [f"[OPERACIONAL] {od}" for od in decision.operational_debt]
        if all_debts:
            for d in all_debts:
                lines.append(f"  • {d}")
        else:
            lines.append("  (Nenhuma dívida crítica assumida)")
        lines.append("───")

        lines.append("GATILHOS OBJETIVOS DE REVISÃO:")
        if decision.review_triggers:
            for rt in decision.review_triggers:
                thresh = f" (limite: {rt.metric_threshold})" if rt.metric_threshold else ""
                lines.append(f"  • {rt.condition}{thresh}")
        else:
            lines.append("  (Nenhum gatilho específico configurado)")

        if decision.conditional_recommendations:
            lines.append("───")
            lines.append("RECOMENDAÇÕES CONDICIONAIS:")
            for cr in decision.conditional_recommendations:
                lines.append(f"  • {cr.condition} -> {cr.recommendation}")

        return box_panel("DECISOR — VEREDITO DO COMITÊ", lines, width=70)

    @staticmethod
    def render_mentor_reflection(report: LearningReport) -> str:
        """Render Mentor reflection and pedagogical guide."""
        lines: list[str] = []
        lines.append("O que você deveria aprender com esta decisão?")
        lines.append("───")

        lines.append("CONCEITOS FUNDAMENTAIS:")
        for c in report.concepts:
            lines.append(f"  • {c}")
        lines.append("───")

        lines.append("LACUNAS DE CONHECIMENTO OBSERVADAS:")
        for gap in report.observed_knowledge_gaps:
            lines.append(f"  • Observação: {gap.observation}")
            lines.append(f"    Evidência:  {gap.context_evidence}")
            lines.append(f"    Estudar:    {gap.recommended_topic}")
        lines.append("───")

        lines.append("TRILHA DE ESTUDOS RECOMENDADA:")
        for step in report.learning_path:
            lines.append(f"  {step.order}. {step.topic} — {step.description}")
        lines.append("───")

        lines.append("CONEXÃO TEORIA → PRÁTICA:")
        for conn in report.theory_to_practice_connections:
            for l in wrap_text(conn, width=64):
                lines.append(f"  {l}")

        return box_panel("MENTOR — REFLEXÃO E APRENDIZADO", lines, width=70)

    @staticmethod
    def render_telemetry(data: dict[str, Any]) -> str:
        """Render session telemetry summary."""
        lines: list[str] = [
            f"Provider:       {data.get('provider', 'N/A')}",
            f"Model:          {data.get('model', 'N/A')}",
            f"LLM Calls:      {data.get('llm_calls', 0)}",
            f"Input Tokens:   {data.get('input_tokens', 0):,}",
            f"Output Tokens:  {data.get('output_tokens', 0):,}",
            f"Total Tokens:   {data.get('total_tokens', 0):,}",
            f"Total Latency:  {data.get('total_latency_seconds', 0.0):.2f}s",
        ]
        return box_panel("TELEMETRIA DA DELIBERAÇÃO", lines, width=70)

    @staticmethod
    def render_context_summary(context: ProblemContext) -> str:
        """Render ProblemContext summary for the 'context' command."""
        lines: list[str] = []
        lines.append(f"Problema: {context.problem}")
        lines.append("───")
        lines.append("FATOS CONHECIDOS:")
        for f in context.facts:
            lines.append(f"  [{f.id}] {f.description} (fonte: {f.source})")
        lines.append("")
        lines.append("RESTRIÇÕES:")
        for c in context.constraints:
            lines.append(f"  [{c.id}] {c.description} (tipo: {c.type.value})")
        lines.append("")
        lines.append("PREMISSAS DE TRABALHO:")
        for a in context.assumptions:
            lines.append(f"  [{a.id}] {a.description} (risco: {a.risk_level.value})")
        lines.append("")
        lines.append("INCÓGNITAS CRÍTICAS (DESCONHECIDOS):")
        for u in context.unknowns:
            lines.append(f"  [{u.id}] {u.description} (impacto: {u.impact_if_adverse.value})")
        return box_panel("CONTEXTO ATUAL DO PROBLEMA", lines, width=70)

    @staticmethod
    def render_session_status(session: Session) -> str:
        """Render session state and version for the 'status' command."""
        lines: list[str] = [
            f"Session ID:     {session.session_id}",
            f"Estado Atual:   {session.current_state.value}",
            f"Versão:         {session.version}",
            f"Propostas:      {list(session.proposals.keys())}",
            f"Auditoria:      {'Sim' if session.audit_report else 'Não'}",
            f"Defesas:        {list(session.defenses.keys())}",
            f"Síntese:        {'Sim' if session.deliberation_synthesis else 'Não'}",
            f"Decisão:        {'Sim' if session.decision_record else 'Não'}",
            f"Mentor:         {'Sim' if session.learning_report else 'Não'}",
            f"Intervenções:   {len(session.interventions)}",
        ]
        return box_panel("STATUS DA SESSÃO", lines, width=70)

    @staticmethod
    def render_events_table(events: list[EventEnvelope]) -> str:
        """Render chronological events recorded in the EventStore."""
        lines: list[str] = []
        for i, ev in enumerate(events, start=1):
            ts = ev.timestamp.strftime("%H:%M:%S")
            art = f" [{ev.artifact_id}]" if ev.artifact_id else ""
            lines.append(f"{i:02d}. [{ts}] {ev.event_type.value:<22} by {ev.actor.value:<14}{art}")
        return box_panel("EVENT STORE (APPEND-ONLY AUDIT LOG)", lines, width=70)

    @staticmethod
    def render_help() -> str:
        """Render CLI command catalog."""
        lines: list[str] = [
            "COMANDOS DISPONÍVEIS NA SESSÃO:",
            "  help                  Exibe este catálogo de comandos",
            "  status                Exibe estado atual, fase e contadores da sessão",
            "  context               Exibe o ProblemContext completo (fatos, premissas, etc.)",
            "  events                Lista todos os eventos append-only gravados no EventStore",
            "  pause                 Pausa o avanço automático da deliberação",
            "  resume                Retoma a deliberação pausada",
            "  abort                 Cancela e encerra a sessão imediatamente (USER_ABORT)",
            "  contest <id>          Contesta/modifica premissa (USER_CONTEST_ASSUMPTION)",
            "  revise                Rejeita e solicita revisão com novas restrições",
            "  continue / enter      Avança para a próxima etapa da deliberação",
        ]
        return box_panel("AJUDA — COMANDOS INTERATIVOS", lines, width=70)
