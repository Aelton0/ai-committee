#!/usr/bin/env python3
"""Smoke test script for Google Gemini LLM Provider integration in AI Committee.

Flow:
  Gemini -> Agent (Architect) -> Structured Output -> Pydantic (ArchitectProposal)

Does NOT persist the session in the Event Store.
Does NOT execute the full committee.
"""

import asyncio
import os
import sys

from schemas.common import Severity
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
from src.committee.llm.config import LLMConfig, mask_secret
from src.committee.llm.gemini import GeminiLLMProvider
from src.committee.orchestration.runner import AgentRunner


def check_api_key() -> str:
    """Verify presence of GEMINI_API_KEY or GOOGLE_API_KEY."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key or not key.strip():
        print("=" * 70)
        print("AI COMMITTEE — GOOGLE GEMINI SMOKE TEST")
        print("=" * 70)
        print("[ERRO] Variável de ambiente GEMINI_API_KEY não encontrada.\n")
        print("Para executar o smoke test com o modelo real do Gemini, configure a chave:")
        print("    export GEMINI_API_KEY=\"sua-chave-de-api-aqui\"")
        print("    PYTHONPATH=. .venv/bin/python scripts/smoke_test_gemini.py\n")
        print("Opcionalmente, você também pode configurar:")
        print("    export GEMINI_MODEL=\"gemini-2.5-flash\"  (ou outro modelo suportado)")
        print("    export GEMINI_TIMEOUT_SECONDS=\"60.0\"")
        print("=" * 70)
        sys.exit(1)
    return key.strip()


async def run_smoke_test() -> None:
    api_key = check_api_key()
    config = LLMConfig.from_env()

    print("=" * 70)
    print("AI COMMITTEE — GOOGLE GEMINI SMOKE TEST")
    print("=" * 70)
    print(f"Provider:    {config.provider}")
    print(f"Model:       {config.gemini_model}")
    print(f"Timeout:     {config.gemini_timeout_seconds}s")
    print(f"API Key:     {mask_secret(api_key)}")
    print("-" * 70)
    print("[1/4] Construindo ProblemContext minimalista em memória...")

    problem_context = ProblemContext(
        artifact_id="CTX-SMOKE-001",
        version=1,
        problem=(
            "O sistema atual é um monólito em Python/PostgreSQL processando 1.200 req/s "
            "com picos de concorrência gerando saturação de conexões no banco e timeouts "
            "na finalização de compras."
        ),
        facts=[
            Fact(id="F1", description="PostgreSQL 15 em instância única RDS db.m5.xlarge", source="Inventário de Infra"),
            Fact(id="F2", description="Throughput de pico atinge 1.200 req/s", source="Métricas Datadog"),
        ],
        constraints=[
            Constraint(id="C1", description="Orçamento mensal adicional máximo de $400", type=ConstraintType.BUDGET, negotiable=False),
            Constraint(id="C2", description="Equipe de apenas 3 desenvolvedores backend", type=ConstraintType.ORGANIZATIONAL, negotiable=False),
        ],
        assumptions=[
            Assumption(id="A1", description="Pico de tráfego crescerá 20% no próximo trimestre", rationale="Projeção comercial", risk_level=Severity.MEDIUM)
        ],
        unknowns=[
            Unknown(id="U1", description="Percentual de transações que exigem consistência forte imediata", impact_if_adverse=Severity.HIGH)
        ],
        open_questions=[],
        success_criteria=["Eliminar timeouts de conexão sob 1.500 req/s", "Tempo de resposta p95 < 100ms"],
    )
    print("      ✓ ProblemContext criado com sucesso.")

    print("[2/4] Inicializando ArchitectAgent e AgentRunner...")
    agent = ArchitectAgent()
    provider = GeminiLLMProvider(config=config)
    runner = AgentRunner(llm_provider=provider, max_retries=2)

    input_context = {
        "session_id": "smoke-test-session",
        "phase": "PHASE_1_DIVERGENCE",
        "problem_context": problem_context.model_dump(mode="json"),
    }
    print("      ✓ Agente e Runner inicializados (sessão não persistida).")

    print(f"[3/4] Solicitando geração estruturada ao Gemini ({config.gemini_model})...")
    try:
        artifact = await runner.run(
            agent=agent,
            input_context=input_context,
            output_schema=ArchitectProposal,
        )
    except Exception as exc:
        print(f"\n[FALHA] Erro durante a geração: {exc}")
        sys.exit(2)

    print("[4/4] Validando artefato gerado via Pydantic...")
    assert isinstance(artifact, ArchitectProposal), f"Esperado ArchitectProposal, obtido {type(artifact)}"
    print("      ✓ Validação Pydantic concluída com sucesso.")

    # Exibir resumo sanitizado do artefato
    print("\n" + "=" * 70)
    print("ARTEFATO PRODUZIDO: ARCHITECT PROPOSAL (SANITIZADO)")
    print("=" * 70)
    print(f"ID do Artefato:     {artifact.artifact_id} (versão {artifact.version})")
    print(f"Título:             {artifact.title}")
    print(f"Solução Proposta:   {artifact.solution}")
    print(f"Justificativa:      {artifact.rationale}")
    print(f"Complexidade:       {artifact.complexity.value}")
    print(f"Reversibilidade:    {artifact.reversibility.score.value} — {artifact.reversibility.rationale}")
    print(f"Esforço Estimado:   {artifact.costs.implementation_effort.value}")
    print(f"Custo Estimado:     {artifact.costs.infrastructure_cost_estimate}")
    print(f"Benefícios ({len(artifact.benefits)}):")
    for b in artifact.benefits[:3]:
        print(f"  + {b}")
    print(f"Riscos ({len(artifact.risks)}):")
    for r in artifact.risks[:3]:
        print(f"  - {r}")
    print(f"Premissas:          {artifact.assumptions}")
    print(f"Condições Inval.:   {artifact.invalidation_conditions}")

    # Exibir telemetria
    if provider.last_metadata:
        meta = provider.last_metadata
        print("\n" + "-" * 70)
        print("TELEMETRIA DA CHAMADA:")
        print(f"  Modelo:           {meta.model}")
        print(f"  Latência:         {meta.latency_seconds:.2f} segundos")
        print(f"  Tokens Entrada:   {meta.input_tokens}")
        print(f"  Tokens Saída:     {meta.output_tokens}")
        print(f"  Tokens Totais:    {meta.total_tokens}")

    print("=" * 70)
    print("SMOKE TEST CONCLUÍDO COM SUCESSO! (Zero persistência no Event Store)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
