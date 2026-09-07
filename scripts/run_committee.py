#!/usr/bin/env python3
"""Interactive CLI entry point for the AI Committee deliberation platform.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/run_committee.py
  PYTHONPATH=. .venv/bin/python scripts/run_committee.py --example
  PYTHONPATH=. .venv/bin/python scripts/run_committee.py --mock
"""

import argparse
import asyncio
import os
import sys

from src.committee.cli.app import CommitteeCLIApp
from src.committee.event_store import EventStore
from src.committee.llm.config import LLMConfig
from src.committee.llm.factory import create_llm_provider
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.orchestration.orchestrator import CommitteeOrchestrator
from src.committee.orchestration.runner import AgentRunner
from src.committee.state_machine import StateMachine


def build_app(
    example_mode: bool = False,
    force_mock: bool = False,
    provider_override: str | None = None,
    db_path: str = "data/committee.db",
) -> CommitteeCLIApp:
    """Instantiate and wire all components for the interactive CLI application."""
    config = LLMConfig.from_env()

    if force_mock or "--mock" in sys.argv:
        provider_name = "mock"
    elif provider_override:
        provider_name = provider_override.strip().lower()
    elif os.getenv("OPENAI_API_KEY") and not os.getenv("GEMINI_API_KEY") and not os.getenv("LLM_PROVIDER"):
        provider_name = "openai"
    elif not os.getenv("OPENAI_API_KEY") and not os.getenv("GEMINI_API_KEY") and not os.getenv("LLM_PROVIDER"):
        print("[INFO] Nenhuma chave de API (OPENAI_API_KEY / GEMINI_API_KEY) detectada.")
        print("[INFO] Iniciando com MockLLMProvider (simulação determinística).\n")
        provider_name = "mock"
    else:
        provider_name = config.provider

    llm_provider = create_llm_provider(provider_name=provider_name, config=config)
    runner = AgentRunner(llm_provider=llm_provider, max_retries=3, retry_delay_seconds=1.0)
    event_store = EventStore(db_path=db_path)
    state_machine = StateMachine(event_store=event_store)
    context_builder = ContextBuilder()

    orchestrator = CommitteeOrchestrator(
        state_machine=state_machine,
        event_store=event_store,
        context_builder=context_builder,
        runner=runner,
    )

    return CommitteeCLIApp(orchestrator=orchestrator)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Committee — Interactive Deliberation CLI")
    parser.add_argument(
        "--example",
        action="store_true",
        help="Executa em modo de demonstração com um cenário pré-configurado de arquitetura.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Força o uso de MockLLMProvider sem requisições a APIs externas.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["mock", "openai", "gemini"],
        default=None,
        help="Seleciona explicitamente o provedor de LLM (mock, openai, gemini).",
    )
    parser.add_argument(
        "--openai",
        action="store_true",
        help="Atalho para selecionar o provedor OpenAI.",
    )
    parser.add_argument(
        "--gemini",
        action="store_true",
        help="Atalho para selecionar o provedor Google Gemini.",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="Utiliza banco de dados SQLite volátil em memória (:memory:).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/committee.db",
        help="Caminho do arquivo do Event Store SQLite (padrão: data/committee.db).",
    )
    args = parser.parse_args()

    provider_override = args.provider
    if args.openai:
        provider_override = "openai"
    elif args.gemini:
        provider_override = "gemini"

    db_path = ":memory:" if args.memory else args.db
    app = build_app(
        example_mode=args.example,
        force_mock=args.mock,
        provider_override=provider_override,
        db_path=db_path,
    )

    try:
        asyncio.run(app.run(example_mode=args.example))
    except KeyboardInterrupt:
        print("\n\n[INFO] Sessão interrompida pelo teclado (Ctrl+C). Encerrando.")
        sys.exit(0)
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "invalid_api_key" in err_msg or "authentication failed" in err_msg.lower():
            print(f"\n[ERRO DE AUTENTICAÇÃO] A API Key fornecida é inválida ou expirou.")
            print("[DICA] Certifique-se de substituir o valor de exemplo pela sua chave real:")
            print('       export OPENAI_API_KEY="sk-proj-sua-chave-aqui"')
            print("       Ou execute com o provedor Mock determinístico (não requer chave de API):")
            print("       PYTHONPATH=. .venv/bin/python scripts/run_committee.py --mock\n")
            sys.exit(1)
        elif "503" in err_msg or "UNAVAILABLE" in err_msg:
            print(f"\n[ERRO DE PROVEDOR] O serviço LLM retornou 503 UNAVAILABLE (alta demanda).")
            print("[DICA] Você pode executar a deliberação com outro provedor adicionando a flag:")
            print("       --openai   (para usar OpenAI)")
            print("       --mock     (para testar offline com Mock determinístico)\n")
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
