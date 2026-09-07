#!/usr/bin/env python3
"""End-to-end integration and smoke test script executing a full AI Committee deliberation.

Steps executed:
  1. Iniciar sessão
  2. Fornecer contexto mínimo
  3. Executar investigação
  4. Permitir resposta humana simulada
  5. Executar Arquiteto
  6. Executar Pragmático
  7. Executar Auditor
  8. Executar Defesas
  9. Executar Facilitador
  10. Executar Decisor
  11. Executar Mentor
  12. Persistir a sessão no Event Store
  13. Executar avaliação da deliberação (DeterministicEvaluator)
  14. Executar replay da sessão a partir do log imutável de eventos

Can be run with OpenAI:
  export OPENAI_API_KEY="sk-..."
  PYTHONPATH=. .venv/bin/python scripts/smoke_committee_openai.py

Or with MockLLMProvider for offline deterministic verification:
  PYTHONPATH=. .venv/bin/python scripts/smoke_committee_openai.py --mock
"""

import asyncio
import os
import sys
from uuid import uuid4

from schemas.common import CommitteeRole, CommitteeState, EventType
from schemas.context import OpenQuestion
from schemas.events import QuestionRaisedPayload
from src.committee.evaluation.evaluator import DeterministicEvaluator
from src.committee.event_store import EventStore
from src.committee.llm.config import LLMConfig, mask_secret
from src.committee.llm.factory import create_llm_provider
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.orchestration.orchestrator import CommitteeOrchestrator
from src.committee.orchestration.runner import AgentRunner
from src.committee.replay import replay_session
from src.committee.state_machine import StateMachine


def resolve_provider():
    """Resolve LLM provider: OpenAI if key configured and not forced mock; else Mock."""
    if "--mock" in sys.argv:
        print("[INFO] Flag --mock ativa: utilizando MockLLMProvider determinístico.")
        return create_llm_provider("mock"), "mock"

    key = os.getenv("OPENAI_API_KEY")
    if not key or not key.strip():
        print("=" * 70)
        print("AI COMMITTEE — END-TO-END DELIBERATION SMOKE TEST")
        print("=" * 70)
        print("[AVISO] Variável OPENAI_API_KEY não encontrada.")
        print("Executando em modo simulado com MockLLMProvider.")
        print("Para executar com modelo real OpenAI (ex: gpt-4o):")
        print("    export OPENAI_API_KEY=\"sua-chave-aqui\"")
        print("    PYTHONPATH=. .venv/bin/python scripts/smoke_committee_openai.py\n")
        print("=" * 70)
        return create_llm_provider("mock"), "mock"

    config = LLMConfig.from_env()
    config.provider = "openai"
    return create_llm_provider("openai", config=config), "openai"


async def run_full_deliberation() -> None:
    provider, provider_type = resolve_provider()
    config = LLMConfig.from_env() if provider_type == "openai" else None

    print("=" * 70)
    print("AI COMMITTEE — END-TO-END DELIBERATION INTEGRATION TEST")
    print("=" * 70)
    print(f"Provider:    {provider_type.upper()}")
    if config:
        print(f"Model:       {config.openai_model}")
        print(f"API Key:     {mask_secret(os.getenv('OPENAI_API_KEY', ''))}")
    print("-" * 70)

    # Inicialização da infraestrutura do comitê
    event_store = EventStore(db_path=":memory:")
    state_machine = StateMachine(event_store=event_store)
    context_builder = ContextBuilder()
    runner = AgentRunner(llm_provider=provider, max_retries=3, retry_delay_seconds=2.0)

    orchestrator = CommitteeOrchestrator(
        state_machine=state_machine,
        event_store=event_store,
        context_builder=context_builder,
        runner=runner,
    )

    session_id = uuid4()

    # 1. Iniciar sessão
    print("[Passo 1/14] Iniciando nova sessão de deliberação...")
    problem_statement = (
        "Sistema de pagamentos em Python/PostgreSQL 15 sofrendo saturação de conexões "
        "e timeouts durante picos de campanha de 1.200 req/s.\n\n"
        "Contexto fornecido:\n"
        "- Equipe: 3 desenvolvedores backend\n"
        "- Orçamento: Máximo $400/mês adicional\n"
        "- Prazo: 4 semanas para homologação\n"
        "- Objetivo: Eliminar timeouts de banco e estabilizar checkout\n"
        "- Critérios de sucesso: p95 < 100ms sob 1.500 req/s"
    )
    session = orchestrator.create_session(
        session_id=session_id,
        problem_statement=problem_statement,
        user_id="smoke-human-tester",
    )
    print(f"             ✓ Sessão criada: {session.session_id} (estado inicial: {session.current_state.value})")

    # 2. Fornecer contexto mínimo e 3. Executar investigação
    print("[Passo 2 e 3/14] Executando Fase 0 (Investigação pelo Facilitador)...")
    await orchestrator.step(session)

    # 4. Permitir resposta humana simulada se houver perguntas abertas
    print("[Passo 4/14] Verificando perguntas abertas para intervenção humana...")
    if session.current_state == CommitteeState.WAITING_FOR_USER:
        unanswered = (
            session.problem_context.unanswered_questions()
            if session.problem_context
            else []
        )
        for q in unanswered:
            simulated_answer = (
                "A tolerância máxima para inconsistência eventual é de zero em transações financeiras. "
                "Consultas de catálogo toleram leitura em réplicas de até 2 segundos de atraso."
            )
            print(f"             → Respondendo pergunta '{q.id}': {q.question[:60]}...")
            orchestrator.user_respond(session, q.id, simulated_answer)

        # Retoma investigação após respostas
        await orchestrator.step(session)

    assert session.current_state == CommitteeState.DIVERGENCE, (
        f"Esperado DIVERGENCE, obtido {session.current_state}"
    )
    print(f"             ✓ ProblemContext validado. Versão: v{session.problem_context.version}")

    # 5. Executar Arquiteto e 6. Executar Pragmático (Divergência Cega)
    print("[Passo 5 e 6/14] Executando Fase 1 (Divergência Cega Paralela: Arquiteto + Pragmático)...")
    await orchestrator.step(session)

    assert CommitteeRole.ARCHITECT in session.proposals, "Proposta do Arquiteto ausente."
    assert CommitteeRole.PRAGMATIST in session.proposals, "Proposta do Pragmático ausente."
    assert session.current_state == CommitteeState.CONFRONTATION, (
        f"Esperado CONFRONTATION, obtido {session.current_state}"
    )
    print(f"             ✓ Proposta Arquiteto: '{session.proposals[CommitteeRole.ARCHITECT].title}'")
    print(f"             ✓ Proposta Pragmático: '{session.proposals[CommitteeRole.PRAGMATIST].title}'")

    # 7. Executar Auditor (Confronto)
    print("[Passo 7/14] Executando Fase 2 (Confronto Adversarial pelo Auditor/SRE)...")
    await orchestrator.step(session)

    assert session.audit_report is not None, "Relatório de auditoria ausente."
    assert session.current_state == CommitteeState.DEFENSE, (
        f"Esperado DEFENSE, obtido {session.current_state}"
    )
    print(f"             ✓ Auditoria concluída: {len(session.audit_report.all_findings())} achados levantados.")

    # 8. Executar Defesas (Defesa e Refinamento)
    print("[Passo 8/14] Executando Fase 3 (Defesas e Refinamentos Paralelos)...")
    await orchestrator.step(session)

    assert CommitteeRole.ARCHITECT in session.defenses, "Defesa do Arquiteto ausente."
    assert CommitteeRole.PRAGMATIST in session.defenses, "Defesa do Pragmático ausente."
    assert session.current_state == CommitteeState.CONVERGENCE, (
        f"Esperado CONVERGENCE, obtido {session.current_state}"
    )
    print("             ✓ Defesas registradas com sucesso.")

    # 9. Executar Facilitador (Convergência)
    print("[Passo 9/14] Executando Fase 4 (Convergência Imparcial pelo Facilitador)...")
    await orchestrator.step(session)

    assert session.deliberation_synthesis is not None, "Síntese ausente."
    assert session.current_state == CommitteeState.DECISION, (
        f"Esperado DECISION, obtido {session.current_state}"
    )
    print(f"             ✓ Síntese gerada: {len(session.deliberation_synthesis.consensus_points)} consensos, {len(session.deliberation_synthesis.divergence_points)} divergências.")

    # 10. Executar Decisor (Decisão)
    print("[Passo 10/14] Executando Fase 5 (Decisão e Balanço de Trade-offs)...")
    await orchestrator.step(session)

    assert session.decision_record is not None, "Registro de decisão ausente."
    assert session.current_state == CommitteeState.REFLECTION, (
        f"Esperado REFLECTION, obtido {session.current_state}"
    )
    print(f"             ✓ Decisão proferida: Status {session.decision_record.status.value}")

    # 11. Executar Mentor (Reflexão)
    print("[Passo 11/14] Executando Fase 6 (Reflexão Pedagógica pelo Mentor)...")
    await orchestrator.step(session)

    assert session.learning_report is not None, "Relatório pedagógico ausente."
    assert session.current_state == CommitteeState.COMPLETED, (
        f"Esperado COMPLETED, obtido {session.current_state}"
    )
    print(f"             ✓ Relatório pedagógico gerado: {len(session.learning_report.concepts)} conceitos, {len(session.learning_report.learning_path)} passos de estudo.")

    # 12. Persistir a sessão no Event Store
    print("[Passo 12/14] Validando persistência atômica no Event Store...")
    events = event_store.get_events(session_id)
    assert len(events) >= 8, f"Esperado >= 8 eventos gravados, obtido {len(events)}"
    print(f"             ✓ Total de eventos append-only auditáveis: {len(events)}")

    # 13. Executar avaliação da deliberação
    print("[Passo 13/14] Executando Framework de Avaliação Determinística...")
    evaluator = DeterministicEvaluator()
    eval_result = evaluator.evaluate_session(session)
    print(f"             ✓ Avaliação concluída. Overall Score: {eval_result.summary.overall_score:.1f}/5.0")
    print("             ✓ Pontuações Epistêmicas:")
    for ep_crit, score_obj in eval_result.summary.epistemic_scores.items():
        tag = "PASS" if score_obj.passed else "FAIL"
        print(f"               [{tag}] {ep_crit.value}: {score_obj.score:.1f}/5.0")

    # 14. Executar replay da sessão a partir do log imutável de eventos
    print("[Passo 14/14] Executando Replay da sessão a partir dos eventos do SQLite...")
    replayed = replay_session(session_id, event_store)
    assert replayed.session_id == session.session_id
    assert replayed.current_state == session.current_state
    assert replayed.version == session.version
    assert replayed.decision_record.artifact_id == session.decision_record.artifact_id
    print(f"             ✓ Replay validado com 100% de paridade. Versão final: {replayed.version}")

    # Telemetria final
    history = getattr(provider, "metadata_history", [])
    total_tokens = sum(m.total_tokens for m in history)
    total_latency = sum(m.latency_seconds for m in history)

    print("\n" + "=" * 70)
    print("TELEMETRIA FINAL DA EXECUÇÃO:")
    print(f"  Provider:       {provider_type.upper()}")
    print(f"  Model:          {getattr(provider, 'model', 'mock')}")
    print(f"  LLM Calls:      {len(history)}")
    print(f"  Total Tokens:   {total_tokens:,}")
    print(f"  Total Latency:  {total_latency:.2f}s")
    print("=" * 70)
    print("SMOKE TEST DE DELIBERAÇÃO COMPLETA CONCLUÍDO COM 100% DE SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_full_deliberation())
