"""Opt-in live integration test for OpenAI LLM Provider.

Requires:
  RUN_LIVE_LLM_TESTS=1
  OPENAI_API_KEY=<valid-key>
"""

import asyncio
import os
import pytest

from schemas.proposals import ArchitectProposal
from src.committee.agents.architect import ArchitectAgent
from src.committee.llm.config import LLMConfig
from src.committee.llm.openai import OpenAILLMProvider
from src.committee.orchestration.runner import AgentRunner

RUN_LIVE = os.getenv("RUN_LIVE_LLM_TESTS") == "1"
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))


@pytest.mark.skipif(
    not (RUN_LIVE and HAS_KEY),
    reason="Live integration tests require RUN_LIVE_LLM_TESTS=1 and OPENAI_API_KEY to be set.",
)
def test_live_openai_architect_proposal_generation() -> None:
    """Live call to OpenAI requesting an ArchitectProposal artifact."""
    async def _test():
        config = LLMConfig.from_env()
        config.provider = "openai"
        provider = OpenAILLMProvider(config=config)
        agent = ArchitectAgent()
        runner = AgentRunner(llm_provider=provider, max_retries=2)

        input_context = {
            "session_id": "live-test-session-openai-001",
            "phase": "PHASE_1_DIVERGENCE",
            "problem_context": {
                "artifact_id": "CTX-LIVE-001",
                "version": 1,
                "problem": "Migração de monólito de e-commerce com alta latência em checkout para microsserviços orientados a eventos.",
                "facts": [
                    {"id": "F1", "description": "PostgreSQL centralizado em RDS único", "source": "Diagnóstico do cliente"}
                ],
                "constraints": [
                    {"id": "C1", "description": "Orçamento mensal máximo de $500", "type": "BUDGET", "negotiable": False},
                    {"id": "C2", "description": "Prazo de entrega em 6 semanas", "type": "DEADLINE", "negotiable": False},
                ],
                "assumptions": [
                    {"id": "A1", "description": "Tráfego quadruplica na Black Friday", "rationale": "Histórico do ano anterior", "risk_level": "HIGH"}
                ],
                "unknowns": [
                    {"id": "U1", "description": "Comportamento do gateway legado sob pico", "impact_if_adverse": "HIGH"}
                ],
                "open_questions": [],
                "success_criteria": ["Tempo de checkout p99 < 300ms", "Zero perda de pedidos"],
            },
        }

        artifact = await runner.run(agent, input_context, output_schema=ArchitectProposal)

        # Assert valid Pydantic instance and non-empty structured fields
        assert isinstance(artifact, ArchitectProposal)
        assert artifact.title and len(artifact.title.strip()) > 0
        assert artifact.solution and len(artifact.solution.strip()) > 0
        assert artifact.rationale and len(artifact.rationale.strip()) > 0
        assert len(artifact.benefits) > 0
        assert artifact.costs is not None
        assert artifact.reversibility is not None

        # Verify telemetry was recorded
        assert provider.last_metadata is not None
        assert provider.last_metadata.latency_seconds > 0.0
        assert provider.last_metadata.total_tokens is not None

    asyncio.run(_test())
