"""Unit tests verifying ContextBuilder isolation, sanitization, and invariant checks."""

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
from src.committee.agents.base import ContextIsolationError
from src.committee.llm import MockLLMProvider
from src.committee.orchestration.context_builder import ContextBuilder
from src.committee.session import Session


@pytest.fixture
def populated_session() -> Session:
    """Fixture creating a session populated with artifacts up to Reflection."""
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


def test_blind_divergence_isolation_architect(populated_session: Session) -> None:
    """Architect context in Phase 1 must NEVER contain Pragmatic proposal or defense."""
    builder = ContextBuilder()
    context = builder.build_context(
        populated_session, CommitteeRole.ARCHITECT, phase="PHASE_1_DIVERGENCE"
    )

    assert "problem_context" in context
    assert "pragmatic_proposal" not in context
    assert "architect_proposal" not in context
    assert "pragmatic_defense" not in context
    assert "audit_report" not in context
    assert "decision_record" not in context


def test_blind_divergence_isolation_pragmatic(populated_session: Session) -> None:
    """Pragmatic context in Phase 1 must NEVER contain Architect proposal or defense."""
    builder = ContextBuilder()
    context = builder.build_context(
        populated_session, CommitteeRole.PRAGMATIST, phase="PHASE_1_DIVERGENCE"
    )

    assert "problem_context" in context
    assert "architect_proposal" not in context
    assert "pragmatic_proposal" not in context
    assert "architect_defense" not in context
    assert "audit_report" not in context
    assert "decision_record" not in context


def test_auditor_isolation(populated_session: Session) -> None:
    """Auditor context in Phase 2 receives both proposals but NEVER defenses."""
    builder = ContextBuilder()
    context = builder.build_context(
        populated_session, CommitteeRole.AUDITOR_SRE, phase="PHASE_2_CONFRONTATION"
    )

    assert "problem_context" in context
    assert "architect_proposal" in context
    assert "pragmatic_proposal" in context
    assert "architect_defense" not in context
    assert "pragmatic_defense" not in context
    assert "deliberation_synthesis" not in context
    assert "decision_record" not in context


def test_defense_isolation(populated_session: Session) -> None:
    """In Phase 3, each proponent receives their own proposal and audit report, but NOT opponent defense."""
    builder = ContextBuilder()

    arch_ctx = builder.build_context(
        populated_session, CommitteeRole.ARCHITECT, phase="PHASE_3_DEFENSE"
    )
    assert "architect_proposal" in arch_ctx
    assert "audit_report" in arch_ctx
    assert "pragmatic_defense" not in arch_ctx

    prag_ctx = builder.build_context(
        populated_session, CommitteeRole.PRAGMATIST, phase="PHASE_3_DEFENSE"
    )
    assert "pragmatic_proposal" in prag_ctx
    assert "audit_report" in prag_ctx
    assert "architect_defense" not in prag_ctx


def test_facilitator_isolation(populated_session: Session) -> None:
    """Facilitator context in Phase 4 receives all prior artifacts but NEVER DecisionRecord."""
    builder = ContextBuilder()
    context = builder.build_context(
        populated_session, CommitteeRole.FACILITATOR, phase="PHASE_4_CONVERGENCE"
    )

    assert "problem_context" in context
    assert "architect_proposal" in context
    assert "pragmatic_proposal" in context
    assert "audit_report" in context
    assert "architect_defense" in context
    assert "pragmatic_defense" in context
    assert "decision_record" not in context


def test_isolation_invariant_violation_raises() -> None:
    """Attempting to inject forbidden context data directly must raise ContextIsolationError."""
    builder = ContextBuilder()
    session = Session(session_id=uuid4(), current_state=CommitteeState.DIVERGENCE)

    with pytest.raises(ContextIsolationError, match="Blind divergence violated"):
        builder.build_context(
            session,
            CommitteeRole.ARCHITECT,
            phase="PHASE_1_DIVERGENCE",
            extra_data={"pragmatic_proposal": {"title": "Leaked"}},
        )

    with pytest.raises(ContextIsolationError, match="Auditor isolation violated"):
        builder.build_context(
            session,
            CommitteeRole.AUDITOR_SRE,
            phase="PHASE_2_CONFRONTATION",
            extra_data={"architect_defense": {"id": "Leaked"}},
        )
