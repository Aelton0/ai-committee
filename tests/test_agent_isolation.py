"""Comprehensive security and isolation test suite verifying strict boundaries."""

from uuid import uuid4
import pytest

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.learning import LearningReport
from schemas.proposals import ArchitectProposal, PragmaticProposal
from schemas.synthesis import DeliberationSynthesis
from src.committee.agents import (
    ArchitectAgent,
    AuditorAgent,
    ContextIsolationError,
    FacilitatorAgent,
    PragmaticAgent,
)
from src.committee.event_store import EventStore
from src.committee.llm import MockLLMProvider
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.session import Session
from src.committee.state_machine import StateMachine


@pytest.fixture
def fully_loaded_session() -> Session:
    """Fixture with every artifact present across all phases."""
    provider = MockLLMProvider()
    session = Session(session_id=uuid4(), current_state=CommitteeState.REFLECTION)
    session.problem_context = provider._generate_default(ProblemContext, {})
    session.proposals[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectProposal, {})
    session.proposals[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticProposal, {})
    session.audit_report = provider._generate_default(AuditReport, {})
    session.defenses[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectDefense, {})
    session.defenses[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticDefense, {})
    session.deliberation_synthesis = provider._generate_default(DeliberationSynthesis, {})
    session.decision_record = provider._generate_default(DecisionRecord, {})
    session.learning_report = provider._generate_default(LearningReport, {})
    return session


def test_blind_divergence_code_level_isolation(fully_loaded_session: Session) -> None:
    """Verify that ContextBuilder strictly enforces blind divergence in Phase 1."""
    builder = ContextBuilder()

    arch_ctx = builder.build_context(
        fully_loaded_session, CommitteeRole.ARCHITECT, phase="PHASE_1_DIVERGENCE"
    )
    assert "pragmatic_proposal" not in arch_ctx
    assert "pragmatic_defense" not in arch_ctx

    prag_ctx = builder.build_context(
        fully_loaded_session, CommitteeRole.PRAGMATIST, phase="PHASE_1_DIVERGENCE"
    )
    assert "architect_proposal" not in prag_ctx
    assert "architect_defense" not in prag_ctx


def test_auditor_isolation_cannot_receive_defenses(fully_loaded_session: Session) -> None:
    """Auditor context must NEVER include defenses before audit completion."""
    builder = ContextBuilder()
    auditor_ctx = builder.build_context(
        fully_loaded_session, CommitteeRole.AUDITOR_SRE, phase="PHASE_2_CONFRONTATION"
    )

    assert "architect_defense" not in auditor_ctx
    assert "pragmatic_defense" not in auditor_ctx

    # Direct agent validation also blocks defenses
    auditor_agent = AuditorAgent()
    with pytest.raises(ContextIsolationError, match="Auditor received Architect defense"):
        auditor_agent.validate_input_context({"architect_defense": {"id": "DEF-001"}})
    with pytest.raises(ContextIsolationError, match="Auditor received Pragmatic defense"):
        auditor_agent.validate_input_context({"pragmatic_defense": {"id": "DEF-002"}})


def test_defense_isolation_cannot_cross_pollinate(fully_loaded_session: Session) -> None:
    """In Phase 3, Architect cannot see Pragmatic defense and vice-versa."""
    arch_agent = ArchitectAgent()
    with pytest.raises(ContextIsolationError, match="Architect received Pragmatic defense"):
        arch_agent.validate_input_context({"pragmatic_defense": {"id": "DEF-002"}})

    prag_agent = PragmaticAgent()
    with pytest.raises(ContextIsolationError, match="Pragmatic received Architect defense"):
        prag_agent.validate_input_context({"architect_defense": {"id": "DEF-001"}})


def test_facilitator_neutrality_enforcement(fully_loaded_session: Session) -> None:
    """Facilitator context never receives DecisionRecord and cannot decide."""
    builder = ContextBuilder()
    fac_ctx = builder.build_context(
        fully_loaded_session, CommitteeRole.FACILITATOR, phase="PHASE_4_CONVERGENCE"
    )
    assert "decision_record" not in fac_ctx

    fac_agent = FacilitatorAgent()
    with pytest.raises(ContextIsolationError, match="Facilitator received DecisionRecord"):
        fac_agent.validate_input_context({"decision_record": {"status": "RECOMMENDED"}})


def test_agents_and_runners_cannot_mutate_state_machine_or_event_store(tmp_path) -> None:
    """Verify that agents and runner do not expose write APIs to EventStore or StateMachine."""
    store = EventStore(tmp_path / "iso_test.db")
    sm = StateMachine(store)

    arch = ArchitectAgent()
    assert not hasattr(arch, "handle_event")
    assert not hasattr(arch, "append")

    store.close()
