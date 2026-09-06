"""Concurrent execution utilities for independent agent phases enforcing blind divergence."""

import asyncio

from schemas.common import CommitteeRole
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.proposals import ArchitectProposal, PragmaticProposal
from src.committee.agents.architect import ArchitectAgent
from src.committee.agents.pragmatic import PragmaticAgent
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.orchestration.runner import AgentRunner
from src.committee.session import Session


async def run_divergence_parallel(
    runner: AgentRunner,
    architect_agent: ArchitectAgent,
    pragmatic_agent: PragmaticAgent,
    context_builder: ContextBuilder,
    session: Session,
) -> tuple[ArchitectProposal, PragmaticProposal]:
    """Execute Architect and Pragmatist concurrently in Phase 1 with strict Blind Divergence.

    CRITICAL: Contexts are built independently before any agent execution begins,
    preventing any potential cross-contamination or causal ordering leak.
    """
    # 1. Independently pre-build contexts
    context_architect = context_builder.build_context(
        session, CommitteeRole.ARCHITECT, phase="PHASE_1_DIVERGENCE"
    )
    context_pragmatic = context_builder.build_context(
        session, CommitteeRole.PRAGMATIST, phase="PHASE_1_DIVERGENCE"
    )

    # 2. Concurrently execute both agents
    arch_res, prag_res = await asyncio.gather(
        runner.run(architect_agent, context_architect, output_schema=ArchitectProposal),
        runner.run(pragmatic_agent, context_pragmatic, output_schema=PragmaticProposal),
    )

    return arch_res, prag_res


async def run_defenses_parallel(
    runner: AgentRunner,
    architect_agent: ArchitectAgent,
    pragmatic_agent: PragmaticAgent,
    context_builder: ContextBuilder,
    session: Session,
) -> tuple[ArchitectDefense, PragmaticDefense]:
    """Execute Architect and Pragmatist defenses concurrently in Phase 3.

    Contexts are pre-built independently so neither sees the other's defense.
    """
    context_architect = context_builder.build_context(
        session, CommitteeRole.ARCHITECT, phase="PHASE_3_DEFENSE"
    )
    context_pragmatic = context_builder.build_context(
        session, CommitteeRole.PRAGMATIST, phase="PHASE_3_DEFENSE"
    )

    arch_defense, prag_defense = await asyncio.gather(
        runner.run(architect_agent, context_architect, output_schema=ArchitectDefense),
        runner.run(pragmatic_agent, context_pragmatic, output_schema=PragmaticDefense),
    )

    return arch_defense, prag_defense
