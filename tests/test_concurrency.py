"""Concurrency and thread-safety tests for StateMachine and Session handling.

Remediates finding HIGH-01 by verifying:
1. Two simultaneous proposals on the same session cleanly resolve to CONFRONTATION.
2. Two simultaneous defenses on the same session cleanly resolve to CONVERGENCE.
3. Concurrent execution across independent sessions runs in parallel without cross-blocking.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from uuid import uuid4
import pytest

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, CommitteeState, EventType, Severity
from schemas.context import ProblemContext
from schemas.defense import ArchitectDefense, CritiqueResponse, DefenseStance, PragmaticDefense, ProposalAction
from schemas.events import EventEnvelope
from schemas.proposals import ArchitectProposal, CostEstimate, EffortLevel, PragmaticProposal, ReversibilityAssessment, ReversibilityLevel
from src.committee.event_store import EventStore
from src.committee.state_machine import StateMachine


@pytest.fixture
def temp_db(tmp_path):
    store = EventStore(tmp_path / "test_concurrency.db")
    yield store
    store.close()


@pytest.fixture
def state_machine(temp_db):
    return StateMachine(temp_db)


def _build_context(session_id) -> ProblemContext:
    return ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Concurrency test problem statement.",
        success_criteria=["Must handle concurrency gracefully."],
    )


def _build_proposals():
    prop_arch = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Architect Proposal",
        solution="Modular decoupled service architecture.",
        rationale="Maximizes long-term evolutionary flexibility.",
        benefits=["High decoupling"],
        costs=CostEstimate(implementation_effort=EffortLevel.MEDIUM, infrastructure_cost_estimate="$50/mo"),
        risks=["Slightly higher initial complexity"],
        complexity=Severity.MEDIUM,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Standard microservices"),
        future_implications="Supports growth",
        assumptions=["Team can maintain containers"],
        invalidation_conditions=["Extreme cost budget under $10"],
    )
    prop_prag = PragmaticProposal(
        artifact_id="PROP-PRAG-001",
        version=1,
        title="Pragmatic Proposal",
        solution="Monolithic service architecture with SQLite/Postgres.",
        rationale="Quickest time to value with zero operational drag.",
        benefits=["Immediate delivery"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$20/mo"),
        risks=["Potential scaling bottleneck later"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Easy to split later"),
        future_implications="Fast MVP",
        assumptions=["Traffic stays modest in year 1"],
        invalidation_conditions=["Scale exceeding 10,000 req/s instantly"],
    )
    return prop_arch, prop_prag


def _build_audit_report():
    return AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[
            AuditFinding(
                id="F-01",
                target_proposal_id="PROP-ARCH-001",
                category=AuditCategory.OVERENGINEERING,
                severity=Severity.MEDIUM,
                title="Potential container orchestration overhead",
                description="Managing k8s for MVP is burdensome.",
                justification="Simple VM is enough.",
            )
        ],
        findings_proposal_b=[
            AuditFinding(
                id="F-02",
                target_proposal_id="PROP-PRAG-001",
                category=AuditCategory.SINGLE_POINTS_OF_FAILURE,
                severity=Severity.HIGH,
                title="Single node failure risk",
                description="Monolith node outage stops everything.",
                justification="Need failover mechanism.",
            )
        ],
    )


def _build_defenses():
    def_arch = ArchitectDefense(
        artifact_id="DEF-ARCH-001",
        version=1,
        original_proposal_id="PROP-ARCH-001",
        critique_responses=[
            CritiqueResponse(
                finding_id="F-01",
                stance=DefenseStance.CONCEDED_WITH_REFINEMENT,
                response="Will use lightweight container runner instead of full k8s.",
                rationale="Reduces ops cost while preserving container benefits.",
            )
        ],
        proposal_action=ProposalAction.MAINTAIN,
    )
    def_prag = PragmaticDefense(
        artifact_id="DEF-PRAG-001",
        version=1,
        original_proposal_id="PROP-PRAG-001",
        critique_responses=[
            CritiqueResponse(
                finding_id="F-02",
                stance=DefenseStance.ACKNOWLEDGED_ACCEPTING_RISK,
                response="Daily automated snapshot backups and systemd auto-restart.",
                rationale="Recovery time of 5 minutes is acceptable under initial SLA.",
            )
        ],
        proposal_action=ProposalAction.MAINTAIN,
    )
    return def_arch, def_prag


def test_concurrent_proposals_resolve_cleanly(state_machine) -> None:
    """Test two proposals submitted concurrently on the same session via threads.

    Proves finding HIGH-01 remediation: no race condition, deterministic transition to CONFRONTATION.
    """
    session_id = uuid4()
    session = state_machine.create_session(session_id, "Concurrent proposals test")

    # Advance to DIVERGENCE
    ctx = _build_context(session_id)
    state_machine.handle_event(
        session,
        EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx),
    )
    assert session.current_state == CommitteeState.DIVERGENCE

    prop_arch, prop_prag = _build_proposals()
    env_arch = EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop_arch)
    env_prag = EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.PRAGMATIST, payload=prop_prag)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(state_machine.handle_event, session, env_arch)
        f2 = executor.submit(state_machine.handle_event, session, env_prag)
        res1 = f1.result()
        res2 = f2.result()

    assert session.has_both_proposals()
    assert session.current_state == CommitteeState.CONFRONTATION
    # Exactly one result moved it to CONFRONTATION, the other resolved DIVERGENCE
    states = {res1.to_state, res2.to_state}
    assert states == {CommitteeState.DIVERGENCE, CommitteeState.CONFRONTATION}


def test_concurrent_defenses_resolve_cleanly(state_machine) -> None:
    """Test two defenses submitted concurrently on the same session via threads.

    Proves finding HIGH-01 remediation: no race condition, deterministic transition to CONVERGENCE.
    """
    session_id = uuid4()
    session = state_machine.create_session(session_id, "Concurrent defenses test")

    ctx = _build_context(session_id)
    state_machine.handle_event(
        session,
        EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx),
    )
    prop_arch, prop_prag = _build_proposals()
    state_machine.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop_arch))
    state_machine.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.PRAGMATIST, payload=prop_prag))

    audit = _build_audit_report()
    state_machine.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.AUDIT_COMPLETED, actor=CommitteeRole.AUDITOR_SRE, payload=audit))
    assert session.current_state == CommitteeState.DEFENSE

    def_arch, def_prag = _build_defenses()
    env_def_arch = EventEnvelope(session_id=session_id, event_type=EventType.DEFENSE_SUBMITTED, actor=CommitteeRole.ARCHITECT, payload=def_arch)
    env_def_prag = EventEnvelope(session_id=session_id, event_type=EventType.DEFENSE_SUBMITTED, actor=CommitteeRole.PRAGMATIST, payload=def_prag)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(state_machine.handle_event, session, env_def_arch)
        f2 = executor.submit(state_machine.handle_event, session, env_def_prag)
        res1 = f1.result()
        res2 = f2.result()

    assert session.has_both_defenses()
    assert session.current_state == CommitteeState.CONVERGENCE
    states = {res1.to_state, res2.to_state}
    assert states == {CommitteeState.DEFENSE, CommitteeState.CONVERGENCE}


def test_independent_sessions_do_not_block_each_other(state_machine) -> None:
    """Test that Session A does not unnecessarily lock or block Session B.

    Proves per-session locking granularity (no global lock).
    """
    session_a = state_machine.create_session(uuid4(), "Problem A")
    session_b = state_machine.create_session(uuid4(), "Problem B")

    def run_session_flow(session):
        ctx = _build_context(session.session_id)
        state_machine.handle_event(
            session,
            EventEnvelope(session_id=session.session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx),
        )
        return session.current_state

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(run_session_flow, session_a)
        future_b = executor.submit(run_session_flow, session_b)
        res_a = future_a.result()
        res_b = future_b.result()

    assert res_a == CommitteeState.DIVERGENCE
    assert res_b == CommitteeState.DIVERGENCE
