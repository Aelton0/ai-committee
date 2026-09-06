"""Unit tests verifying concurrent execution of divergence and defense phases."""

import asyncio
from uuid import uuid4
import pytest

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState
from schemas.context import ProblemContext
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.proposals import ArchitectProposal, PragmaticProposal
from src.committee.agents import ArchitectAgent, PragmaticAgent
from src.committee.llm import MockLLMProvider
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.orchestration.parallel import (
    run_defenses_parallel,
    run_divergence_parallel,
)
from src.committee.orchestration.runner import AgentRunner
from src.committee.session import Session


def test_run_divergence_parallel_strict_blind_divergence() -> None:
    """Verify concurrent execution of Architect and Pragmatist with isolated contexts."""
    async def _test():
        provider = MockLLMProvider()
        runner = AgentRunner(provider)
        builder = ContextBuilder()

        session = Session(session_id=uuid4(), current_state=CommitteeState.DIVERGENCE)
        session.problem_context = provider._generate_default(ProblemContext, {})

        arch_prop, prag_prop = await run_divergence_parallel(
            runner=runner,
            architect_agent=ArchitectAgent(),
            pragmatic_agent=PragmaticAgent(),
            context_builder=builder,
            session=session,
        )

        assert isinstance(arch_prop, ArchitectProposal)
        assert isinstance(prag_prop, PragmaticProposal)
        assert len(provider.call_history) == 2

        # Verify contexts in call history
        arch_call = next(c for c in provider.call_history if c["output_schema"] == ArchitectProposal)
        prag_call = next(c for c in provider.call_history if c["output_schema"] == PragmaticProposal)

        assert "pragmatic_proposal" not in arch_call["input_context"]
        assert "architect_proposal" not in prag_call["input_context"]

    asyncio.run(_test())


def test_run_defenses_parallel() -> None:
    """Verify concurrent execution of Architect and Pragmatist defenses in Phase 3."""
    async def _test():
        provider = MockLLMProvider()
        runner = AgentRunner(provider)
        builder = ContextBuilder()

        session = Session(session_id=uuid4(), current_state=CommitteeState.DEFENSE)
        session.problem_context = provider._generate_default(ProblemContext, {})
        session.proposals[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectProposal, {})
        session.proposals[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticProposal, {})
        session.audit_report = provider._generate_default(AuditReport, {})

        arch_def, prag_def = await run_defenses_parallel(
            runner=runner,
            architect_agent=ArchitectAgent(),
            pragmatic_agent=PragmaticAgent(),
            context_builder=builder,
            session=session,
        )

        assert isinstance(arch_def, ArchitectDefense)
        assert isinstance(prag_def, PragmaticDefense)
        assert len(provider.call_history) == 2

        arch_call = next(c for c in provider.call_history if c["output_schema"] == ArchitectDefense)
        prag_call = next(c for c in provider.call_history if c["output_schema"] == PragmaticDefense)

        assert "pragmatic_defense" not in arch_call["input_context"]
        assert "architect_defense" not in prag_call["input_context"]

    asyncio.run(_test())
