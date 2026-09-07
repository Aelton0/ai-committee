"""Unit tests for TerminalRenderer verifying clean presentation and secret safety."""

from uuid import uuid4
import pytest

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, CommitteeState, Confidence, DecisionStatus, Severity
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord, ReviewTrigger, TradeOffContract
from schemas.defense import ArchitectDefense
from schemas.events import EventEnvelope, SessionCreatedPayload
from schemas.learning import LearningPathStep, LearningReference, LearningReport, ObservedKnowledgeGap
from schemas.proposals import ArchitectProposal, CostEstimate, EffortLevel, ReversibilityAssessment, ReversibilityLevel
from schemas.synthesis import DeliberationSynthesis, TradeOffDimension
from src.committee.cli.renderer import TerminalRenderer, box_panel, wrap_text
from src.committee.llm.mock import MockLLMProvider
from src.committee.session import Session


def test_wrap_text_handles_empty_and_multiline() -> None:
    """wrap_text splits long paragraphs while preserving empty lines."""
    assert wrap_text("") == []
    assert wrap_text("Hello\n\nWorld", width=20) == ["Hello", "", "World"]
    wrapped = wrap_text("A very long sentence that needs to be wrapped across multiple lines of text.", width=25)
    assert len(wrapped) >= 2
    for line in wrapped:
        assert len(line) <= 25


def test_box_panel_renders_borders() -> None:
    """box_panel produces rounded Unicode frame."""
    box = box_panel("TEST BOX", ["Line 1", "Line 2"], width=30)
    assert box.startswith("╭─ TEST BOX")
    assert box.endswith("╯")
    assert "│ Line 1" in box
    assert "│ Line 2" in box


def test_render_banner() -> None:
    """render_banner produces expected title frame."""
    banner = TerminalRenderer.render_banner()
    assert "AI COMMITTEE" in banner
    assert "╔" in banner and "╝" in banner


def test_render_phase_header() -> None:
    """render_phase_header renders standardized divider."""
    header = TerminalRenderer.render_phase_header("Fase 1 — Divergência Cega")
    assert "FASE 1 — DIVERGÊNCIA CEGA" in header
    assert "═" * 70 in header


def test_render_investigation_card() -> None:
    """render_investigation_card displays question and metadata."""
    card = TerminalRenderer.render_investigation_card(
        question="Qual a latência de SLA sob pico?",
        rationale="Necessário para dimensionar conexão do banco",
        impact="HIGH",
    )
    assert "FACILITADOR — INVESTIGAÇÃO" in card
    assert "Qual a latência de SLA sob pico?" in card
    assert "Impacto da Incerteza: HIGH" in card


def test_render_proposal_with_epistemic_section() -> None:
    """render_proposal renders both core proposal and structured epistemic breakdown."""
    provider = MockLLMProvider()
    prop = provider._generate_default(ArchitectProposal, {})
    rendered = TerminalRenderer.render_proposal(prop)

    assert "ARQUITETO" in rendered
    assert "SOLUÇÃO:" in rendered
    assert "FATOS:" in rendered
    assert "PREMISSAS:" in rendered
    assert "INFERÊNCIAS:" in rendered
    assert "DESCONHECIDOS:" in rendered
    assert "RECOMENDAÇÕES CONDICIONAIS:" in rendered
    assert prop.title in rendered


def test_render_audit_report() -> None:
    """render_audit_report renders findings and SPOFs."""
    provider = MockLLMProvider()
    report = provider._generate_default(AuditReport, {})
    rendered = TerminalRenderer.render_audit_report(report)

    assert "AUDITOR / SRE — CONFRONTO" in rendered
    assert "APONTAMENTOS — PROPOSTA DO ARQUITETO:" in rendered
    assert "APONTAMENTOS — PROPOSTA DO PRAGMÁTICO:" in rendered
    assert "PONTOS ÚNICOS DE FALHA (SPOFs)" in rendered


def test_render_defense() -> None:
    """render_defense renders proponent arguments and stances."""
    provider = MockLLMProvider()
    defense = provider._generate_default(ArchitectDefense, {})
    rendered = TerminalRenderer.render_defense(defense)

    assert "DEFESA — ARQUITETO" in rendered
    assert "RESPOSTAS ÀS CRÍTICAS DA AUDITORIA:" in rendered
    assert defense.proposal_action.value in rendered


def test_render_synthesis_never_contains_recommendations() -> None:
    """render_synthesis renders consensus and trade-offs without directing choices."""
    provider = MockLLMProvider()
    synthesis = provider._generate_default(DeliberationSynthesis, {})
    rendered = TerminalRenderer.render_synthesis(synthesis)

    assert "FACILITADOR — CONVERGÊNCIA (IMPARCIAL)" in rendered
    assert "PONTOS DE CONSENSO:" in rendered
    assert "PONTOS DE DIVERGÊNCIA:" in rendered
    assert "TRADE-OFFS PRINCIPAIS:" in rendered
    assert "recomendo a proposta" not in rendered.lower()
    assert "a melhor opção é" not in rendered.lower()


def test_render_decision() -> None:
    """render_decision displays verdict, trade-offs, and debts."""
    provider = MockLLMProvider()
    decision = provider._generate_default(DecisionRecord, {})
    rendered = TerminalRenderer.render_decision(decision)

    assert "DECISOR — VEREDITO DO COMITÊ" in rendered
    assert "STATUS: RECOMMENDED" in rendered
    assert "TRADE-OFFS ASSUMIDOS:" in rendered
    assert "DÍVIDAS TÉCNICAS E OPERACIONAIS:" in rendered
    assert "GATILHOS OBJETIVOS DE REVISÃO:" in rendered


def test_render_mentor_reflection() -> None:
    """render_mentor_reflection displays concepts and study roadmap."""
    provider = MockLLMProvider()
    lrn = provider._generate_default(LearningReport, {})
    rendered = TerminalRenderer.render_mentor_reflection(lrn)

    assert "MENTOR — REFLEXÃO E APRENDIZADO" in rendered
    assert "CONCEITOS FUNDAMENTAIS:" in rendered
    assert "LACUNAS DE CONHECIMENTO OBSERVADAS:" in rendered
    assert "TRILHA DE ESTUDOS RECOMENDADA:" in rendered


def test_render_telemetry_masks_secrets() -> None:
    """render_telemetry displays counts and latencies without leaking keys."""
    data = {
        "provider": "openai",
        "model": "gpt-4o",
        "llm_calls": 9,
        "input_tokens": 5200,
        "output_tokens": 1800,
        "total_tokens": 7000,
        "total_latency_seconds": 12.45,
    }
    rendered = TerminalRenderer.render_telemetry(data)

    assert "TELEMETRIA DA DELIBERAÇÃO" in rendered
    assert "gpt-4o" in rendered
    assert "7,000" in rendered
    assert "12.45s" in rendered
    assert "sk-" not in rendered
    assert "AIza" not in rendered


def test_render_context_summary_and_status() -> None:
    """render_context_summary and render_session_status format session projections."""
    provider = MockLLMProvider()
    ctx = provider._generate_default(ProblemContext, {})
    ctx_rendered = TerminalRenderer.render_context_summary(ctx)

    assert "CONTEXTO ATUAL DO PROBLEMA" in ctx_rendered
    assert "FATOS CONHECIDOS:" in ctx_rendered
    assert "RESTRIÇÕES:" in ctx_rendered

    session = Session(session_id=uuid4(), current_state=CommitteeState.INVESTIGATION)
    status_rendered = TerminalRenderer.render_session_status(session)
    assert "STATUS DA SESSÃO" in status_rendered
    assert "INVESTIGATION" in status_rendered
