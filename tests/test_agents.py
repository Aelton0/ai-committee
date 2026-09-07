"""Unit tests verifying agent roles, system prompts, schemas, and immutability."""

import asyncio
import pytest

from schemas.audit import AuditReport
from schemas.common import CommitteeRole
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.learning import LearningReport
from schemas.proposals import ArchitectProposal, PragmaticProposal
from schemas.synthesis import DeliberationSynthesis
from src.committee.agents import (
    ArchitectAgent,
    AuditorAgent,
    BaseAgent,
    ContextIsolationError,
    DecisionMakerAgent,
    FacilitatorAgent,
    MentorAgent,
    PragmaticAgent,
)
from src.committee.llm import MockLLMProvider
from src.committee.orchestration.runner import AgentRunner


def test_agent_roles_and_system_prompts() -> None:
    """Verify that all 6 agents have the correct formal roles and non-empty prompts."""
    agents = [
        (ArchitectAgent(), CommitteeRole.ARCHITECT, ArchitectProposal),
        (PragmaticAgent(), CommitteeRole.PRAGMATIST, PragmaticProposal),
        (AuditorAgent(), CommitteeRole.AUDITOR_SRE, AuditReport),
        (FacilitatorAgent(), CommitteeRole.FACILITATOR, DeliberationSynthesis),
        (DecisionMakerAgent(), CommitteeRole.DECISOR, DecisionRecord),
        (MentorAgent(), CommitteeRole.MENTOR, LearningReport),
    ]

    for agent, expected_role, expected_schema in agents:
        assert agent.role == expected_role
        assert agent.output_schema == expected_schema
        assert len(agent.system_prompt.strip()) > 50
        assert "# " in agent.system_prompt


def test_agent_dynamic_phase_schemas() -> None:
    """Verify that multi-phase agents adapt their output schema appropriately."""
    arch = ArchitectAgent()
    assert arch.get_output_schema({"phase": "PHASE_1_DIVERGENCE"}) == ArchitectProposal
    assert arch.get_output_schema({"phase": "PHASE_3_DEFENSE"}) == ArchitectDefense
    assert arch.get_output_schema({"audit_report": {}}) == ArchitectDefense

    prag = PragmaticAgent()
    assert prag.get_output_schema({"phase": "PHASE_1_DIVERGENCE"}) == PragmaticProposal
    assert prag.get_output_schema({"phase": "PHASE_3_DEFENSE"}) == PragmaticDefense
    assert prag.get_output_schema({"audit_report": {}}) == PragmaticDefense

    fac = FacilitatorAgent()
    assert fac.get_output_schema({"phase": "PHASE_0_INVESTIGATION"}) == ProblemContext
    assert fac.get_output_schema({"phase": "PHASE_4_CONVERGENCE"}) == DeliberationSynthesis


def test_mock_provider_produces_valid_schemas_for_all_agents() -> None:
    """Verify that MockLLMProvider returns valid schema instances for all agent types."""
    async def _test():
        provider = MockLLMProvider()
        runner = AgentRunner(provider)

        div_context = {"phase": "PHASE_1_DIVERGENCE", "problem_statement": "Valid test problem."}
        aud_context = {"phase": "PHASE_2_CONFRONTATION", "architect_proposal": {"summary": "arch"}}
        def_context = {"phase": "PHASE_3_DEFENSE", "audit_report": {"summary": "audit"}}
        conv_context = {"phase": "PHASE_4_CONVERGENCE", "audit_report": {"summary": "audit"}}
        dec_context = {"phase": "PHASE_5_DECISION", "deliberation_synthesis": {"summary": "synth"}}
        ref_context = {"phase": "PHASE_6_REFLECTION", "decision_record": {"summary": "dec"}}

        # Architect
        arch_res = await runner.run(ArchitectAgent(), div_context, output_schema=ArchitectProposal)
        assert isinstance(arch_res, ArchitectProposal)

        # Pragmatic
        prag_res = await runner.run(PragmaticAgent(), div_context, output_schema=PragmaticProposal)
        assert isinstance(prag_res, PragmaticProposal)

        # Auditor
        aud_res = await runner.run(AuditorAgent(), aud_context, output_schema=AuditReport)
        assert isinstance(aud_res, AuditReport)

        # Architect Defense
        arch_def = await runner.run(ArchitectAgent(), def_context, output_schema=ArchitectDefense)
        assert isinstance(arch_def, ArchitectDefense)

        # Pragmatic Defense
        prag_def = await runner.run(PragmaticAgent(), def_context, output_schema=PragmaticDefense)
        assert isinstance(prag_def, PragmaticDefense)

        # Facilitator Synthesis
        fac_res = await runner.run(FacilitatorAgent(), conv_context, output_schema=DeliberationSynthesis)
        assert isinstance(fac_res, DeliberationSynthesis)

        # Decision Maker
        dec_res = await runner.run(DecisionMakerAgent(), dec_context, output_schema=DecisionRecord)
        assert isinstance(dec_res, DecisionRecord)

        # Mentor
        men_res = await runner.run(MentorAgent(), ref_context, output_schema=LearningReport)
        assert isinstance(men_res, LearningReport)

    asyncio.run(_test())


def test_facilitator_cannot_decide() -> None:
    """Verify that Facilitator Agent rejects decision context or attempts to decide."""
    fac = FacilitatorAgent()
    with pytest.raises(ContextIsolationError, match="Facilitator received DecisionRecord"):
        fac.validate_input_context({"decision_record": {"status": "RECOMMENDED"}})

    assert "chosen_alternative" not in DeliberationSynthesis.model_fields
    assert "recommendation" not in DeliberationSynthesis.model_fields


def test_agents_have_no_access_to_state_machine_or_event_store() -> None:
    """Verify that BaseAgent and subclasses do not hold references to StateMachine or EventStore."""
    agent_instances = [
        ArchitectAgent(),
        PragmaticAgent(),
        AuditorAgent(),
        FacilitatorAgent(),
        DecisionMakerAgent(),
        MentorAgent(),
    ]
    for agent in agent_instances:
        assert not hasattr(agent, "state_machine")
        assert not hasattr(agent, "event_store")
        assert not hasattr(agent, "session")
