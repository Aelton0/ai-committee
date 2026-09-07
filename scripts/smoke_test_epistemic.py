#!/usr/bin/env python3
"""Smoke test script for Epistemic Discipline in the AI Committee platform.

Flow:
  ProblemContext (Minimalist + Unknowns)
       │
       ▼
  ArchitectAgent (with Epistemic Discipline prompt)
       │
       ▼
  LLM Provider (OpenAI / Mock)
       │
       ▼
  ArchitectProposal (with validated EpistemicSection)
       │
       ▼
  Epistemic Evaluation (Fact Grounding, Assumption Transparency, Unknown Visibility, etc.)

Verifies:
  - Strict distinction of facts vs assumptions.
  - Transparent hypotheses with invalidation conditions.
  - Inferences explicitly citing dependencies.
  - Preservation of critical unknowns.
  - Guarded recommendations (IF ... THEN ...) for complex tools.
"""

import asyncio
import os
import sys
from uuid import uuid4

from schemas.common import CommitteeRole, CommitteeState, Confidence, Severity
from schemas.context import (
    Assumption,
    Constraint,
    ConstraintType,
    Fact,
    ProblemContext,
    Unknown,
)
from schemas.proposals import ArchitectProposal
from src.committee.agents.architect import ArchitectAgent
from src.committee.evaluation.criteria import (
    evaluate_assumption_transparency,
    evaluate_epistemic_integrity,
    evaluate_fact_grounding,
    evaluate_inference_traceability,
    evaluate_recommendation_grounding,
    evaluate_unknown_visibility,
)
from src.committee.llm.config import LLMConfig, mask_secret
from src.committee.llm.mock import MockLLMProvider
from src.committee.llm.openai import OpenAILLMProvider
from src.committee.orchestration.runner import AgentRunner
from src.committee.session import Session


def get_provider(use_mock: bool = False):
    """Resolve provider: Mock if requested or if no API key; else OpenAI."""
    if use_mock or "--mock" in sys.argv:
        print("[INFO] Utilizando MockLLMProvider para simulação determinística.")
        return MockLLMProvider(), "mock"

    key = os.getenv("OPENAI_API_KEY")
    if not key or not key.strip():
        print("=" * 70)
        print("AI COMMITTEE — EPISTEMIC DISCIPLINE SMOKE TEST")
        print("=" * 70)
        print("[AVISO] Variável OPENAI_API_KEY não configurada.")
        print("Executando com MockLLMProvider. Para executar com o modelo real:")
        print("    export OPENAI_API_KEY=\"sua-chave-aqui\"")
        print("    PYTHONPATH=. .venv/bin/python scripts/smoke_test_epistemic.py\n")
        print("=" * 70)
        return MockLLMProvider(), "mock"

    config = LLMConfig.from_env()
    config.provider = "openai"
    return OpenAILLMProvider(config=config), "openai"


async def run_epistemic_smoke_test() -> None:
    provider, provider_type = get_provider()
    config = LLMConfig.from_env() if provider_type == "openai" else None

    print("=" * 70)
    print("AI COMMITTEE — EPISTEMIC DISCIPLINE SMOKE TEST")
    print("=" * 70)
    print(f"Provider:    {provider_type.upper()}")
    if config:
        print(f"Model:       {config.openai_model}")
        print(f"API Key:     {mask_secret(os.getenv('OPENAI_API_KEY', ''))}")
    print("-" * 70)

    print("[1/4] Construindo ProblemContext minimalista com incógnitas declaradas...")
    problem_context = ProblemContext(
        artifact_id="CTX-EPI-001",
        version=1,
        problem=(
            "O sistema atual é um PostgreSQL 15 em instância única sofrendo timeouts "
            "e esgotamento de conexões durante campanhas de tráfego elevado."
        ),
        facts=[
            Fact(id="F1", description="PostgreSQL 15 em instância única 16GB RAM", source="Inventário de Infraestrutura"),
            Fact(id="F2", description="Ocorrência de timeouts de conexão em horários de pico", source="Logs de Aplicação"),
        ],
        constraints=[
            Constraint(id="C1", description="Orçamento mensal adicional máximo de $400", type=ConstraintType.BUDGET, negotiable=False),
            Constraint(id="C2", description="Prazo de implementação de 4 semanas", type=ConstraintType.DEADLINE, negotiable=False),
        ],
        assumptions=[
            Assumption(id="A1", description="Base de usuários ativos continuará crescendo moderadamente", rationale="Projeção comercial", risk_level=Severity.MEDIUM)
        ],
        unknowns=[
            Unknown(id="U1", description="Third-party payment gateway latency and concurrency limits under heavy load", impact_if_adverse=Severity.HIGH),
        ],
        open_questions=[],
        success_criteria=["Eliminar timeouts de banco sob pico", "Custo dentro do orçamento"],
    )
    print("      ✓ Fatos conhecidos:        F1 (PostgreSQL 15 16GB), F2 (timeouts)")
    print("      ✓ Incógnitas críticas:     U1 (vazão de pico desconhecida), U2 (razão escrita/leitura)")
    print("      ✓ Restrições financeiras:  C1 (máximo $400/mês)")

    print("\n[2/4] Inicializando ArchitectAgent com diretrizes de Disciplina Epistêmica...")
    agent = ArchitectAgent()
    runner = AgentRunner(llm_provider=provider, max_retries=3, retry_delay_seconds=2.0)

    input_context = {
        "session_id": "epistemic-smoke-test-session",
        "phase": "PHASE_1_DIVERGENCE",
        "problem_context": problem_context.model_dump(mode="json"),
    }

    print(f"\n[3/4] Solicitando geração estruturada via {provider_type.upper()}...")
    try:
        artifact = await runner.run(
            agent=agent,
            input_context=input_context,
            output_schema=ArchitectProposal,
        )
    except Exception as exc:
        print(f"\n[FALHA] Erro durante a geração: {exc}")
        sys.exit(2)

    assert isinstance(artifact, ArchitectProposal), f"Esperado ArchitectProposal, obtido {type(artifact)}"
    print("      ✓ Validação do schema Pydantic concluída com sucesso.")

    print("\n[4/4] Avaliando a Disciplina Epistêmica do artefato...")
    # Montar sessão em memória para rodar os avaliadores epistêmicos
    eval_session = Session(session_id=uuid4(), current_state=CommitteeState.DIVERGENCE)
    eval_session.problem_context = problem_context
    eval_session.proposals[CommitteeRole.ARCHITECT] = artifact

    evaluators = [
        ("Fact Grounding", evaluate_fact_grounding),
        ("Assumption Transparency", evaluate_assumption_transparency),
        ("Unknown Visibility", evaluate_unknown_visibility),
        ("Inference Traceability", evaluate_inference_traceability),
        ("Recommendation Grounding", evaluate_recommendation_grounding),
        ("Epistemic Integrity", evaluate_epistemic_integrity),
    ]

    print("\n" + "=" * 70)
    print("RELATÓRIO DE DISCIPLINA EPISTÊMICA DO ARTEFATO")
    print("=" * 70)
    print(f"Título:             {artifact.title}")
    print(f"Solução:            {artifact.solution[:100]}...")
    print(f"Complexidade:       {artifact.complexity.value}")
    print(f"Custo Estimado:     {artifact.costs.infrastructure_cost_estimate}")

    ep = artifact.epistemic_section
    print("\n" + "-" * 70)
    print("SEÇÃO EPISTÊMICA ESTRUTURADA:")
    print(f"  • Fatos verificados declarados ({len(ep.facts)}):")
    for f in ep.facts:
        print(f"      [{f.id}] {f.statement} (origem: {f.source})")

    print(f"  • Premissas explícitas ({len(ep.assumptions)}):")
    for a in ep.assumptions:
        print(f"      [{a.id}] {a.statement}")
        print(f"          Condição de Invalidação: {a.invalidation_condition}")
        print(f"          Confiança: {a.confidence.value} | Razão: {a.reason}")

    print(f"  • Inferências lógicas ({len(ep.inferences)}):")
    for inf in ep.inferences:
        print(f"      [{inf.id}] {inf.statement}")
        print(f"          Depende de: {inf.depends_on} | Racional: {inf.rationale}")

    print(f"  • Incógnitas preservadas ({len(ep.unknowns)}):")
    for u in ep.unknowns:
        print(f"      [{u.id}] {u.statement}")

    print(f"  • Recomendações condicionais ({len(ep.conditional_recommendations)}):")
    for cr in ep.conditional_recommendations:
        print(f"      [SE] {cr.condition} -> [ENTÃO] {cr.recommendation}")

    print("\n" + "-" * 70)
    print("RESULTADOS DA AVALIAÇÃO ANALÍTICA:")
    all_passed = True
    for name, eval_fn in evaluators:
        score_obj, findings = eval_fn(eval_session)
        status = "PASS" if score_obj.passed else "FAIL"
        print(f"  [{status}] {name:<28} {score_obj.score:.1f}/5.0 — {score_obj.notes}")
        for f in findings:
            print(f"         ⚠ [{f.severity.value}] {f.description}")
            print(f"           Evidência: {f.evidence}")
        if not score_obj.passed:
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("✓ SMOKE TEST DE DISCIPLINA EPISTÊMICA CONCLUÍDO COM 100% DE APROVAÇÃO!")
    else:
        print("⚠ SMOKE TEST CONCLUÍDO COM APONTAMENTOS DE MELHORIA EPISTÊMICA.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_epistemic_smoke_test())
