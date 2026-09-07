"""Regression test suite for Quality Gates integrity (Gate 2 Confrontation and Gate 5 Decision).

Verifies strict enforcement of:
- Gate 2 (gate_confrontation_exit):
  * Audit with only Proposal A findings fails.
  * Audit with only Proposal B findings fails.
  * Audit with findings for both A and B passes.
  * Audit with completely empty findings fails.
  * Audit finding targeting an unknown/unregistered proposal fails.
  * Audit with A and B having different finding severities (e.g. HIGH vs LOW) passes.

- Gate 5 (gate_decision_exit):
  * Decision choosing an active round proposal passes.
  * Decision choosing a non-existent proposal fails.
  * Decision choosing a proposal from a superseded historical round fails.
  * Decision with status INSUFFICIENT_EVIDENCE without a winner (None) passes.
  * Decision with status INSUFFICIENT_EVIDENCE with a winner specified fails.
"""

from uuid import uuid4
import pytest

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import (
    CommitteeRole,
    CommitteeState,
    Confidence,
    DecisionStatus,
    EventType,
    Severity,
)
from schemas.decision import DecisionRecord, RejectedAlternative, ReviewTrigger, TradeOffContract
from schemas.events import EventEnvelope
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from schemas.synthesis import DeliberationSynthesis
from src.committee.gates import gate_confrontation_exit, gate_decision_exit
from src.committee.session import DeliberationRound, RoundStatus, Session


@pytest.fixture
def session_id():
    return uuid4()


@pytest.fixture
def session(session_id) -> Session:
    return Session(session_id=session_id, problem_statement="High throughput payment processing system")


@pytest.fixture
def proposals(session) -> tuple[ArchitectProposal, PragmaticProposal]:
    prop_a = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Event-Driven Microservices",
        solution="Distributed event-driven architecture using Kafka.",
        rationale="High decouple and horizontal scale.",
        benefits=["Extensibility"],
        costs=CostEstimate(implementation_effort=EffortLevel.HIGH, infrastructure_cost_estimate="$5000/mo"),
        risks=["Complexity"],
        complexity=Severity.HIGH,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.LOW, rationale="Hard to rollback"),
        future_implications="Requires Kubernetes cluster",
        assumptions=["Kafka expertise"],
        invalidation_conditions=["Volume < 10 req/s"],
    )
    prop_b = PragmaticProposal(
        artifact_id="PROP-PRAG-001",
        version=1,
        title="Modular Monolith",
        solution="Single deployable unit with modular boundaries.",
        rationale="Simplicity and immediate delivery.",
        benefits=["Low cost"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$50/mo"),
        risks=["Scaling bottlenecks"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Easy to extract"),
        future_implications="Might require sharding later",
        assumptions=["Single database suffices"],
        invalidation_conditions=["Volume > 100k req/s"],
    )
    session.proposals[CommitteeRole.ARCHITECT] = prop_a
    session.proposals[CommitteeRole.PRAGMATIST] = prop_b
    return prop_a, prop_b


# ==============================================================================
# Gate 2: Confrontation Exit Integrity Tests
# ==============================================================================


class TestGate2ConfrontationIntegrity:
    def test_audit_only_proposal_a_fails(self, session, session_id, proposals) -> None:
        """Audit that only reviews Proposal A and omits Proposal B must fail Gate 2."""
        audit = AuditReport(
            artifact_id="AUD-001",
            version=1,
            target_proposal_a_id="PROP-ARCH-001",
            target_proposal_b_id="PROP-PRAG-001",
            findings_proposal_a=[
                AuditFinding(
                    id="F-ARCH-1",
                    category=AuditCategory.OPERATIONS,
                    severity=Severity.HIGH,
                    target_proposal_id="PROP-ARCH-001",
                    title="High operational overhead",
                    description="Kafka ops require dedicated team.",
                    justification="Industry operational baselines.",
                )
            ],
            findings_proposal_b=[],  # Proposal B omitted
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.AUDIT_COMPLETED,
            actor=CommitteeRole.AUDITOR_SRE,
            payload=audit,
        )
        result = gate_confrontation_exit(session, env)
        assert not result.passed
        assert "must cover both proposals with at least one finding each" in (result.reason or "")
        assert "found 1 for proposal A, 0 for proposal B" in (result.reason or "")

    def test_audit_only_proposal_b_fails(self, session, session_id, proposals) -> None:
        """Audit that only reviews Proposal B and omits Proposal A must fail Gate 2."""
        audit = AuditReport(
            artifact_id="AUD-002",
            version=1,
            target_proposal_a_id="PROP-ARCH-001",
            target_proposal_b_id="PROP-PRAG-001",
            findings_proposal_a=[],  # Proposal A omitted
            findings_proposal_b=[
                AuditFinding(
                    id="F-PRAG-1",
                    category=AuditCategory.SCALABILITY,
                    severity=Severity.MEDIUM,
                    target_proposal_id="PROP-PRAG-001",
                    title="Single point of failure in shared DB",
                    description="Shared DB can bottleneck.",
                    justification="Relational DB connection limits.",
                )
            ],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.AUDIT_COMPLETED,
            actor=CommitteeRole.AUDITOR_SRE,
            payload=audit,
        )
        result = gate_confrontation_exit(session, env)
        assert not result.passed
        assert "must cover both proposals with at least one finding each" in (result.reason or "")
        assert "found 0 for proposal A, 1 for proposal B" in (result.reason or "")

    def test_audit_both_proposals_passes(self, session, session_id, proposals) -> None:
        """Audit that covers both Proposal A and B passes Gate 2."""
        audit = AuditReport(
            artifact_id="AUD-003",
            version=1,
            target_proposal_a_id="PROP-ARCH-001",
            target_proposal_b_id="PROP-PRAG-001",
            findings_proposal_a=[
                AuditFinding(
                    id="F-ARCH-1",
                    category=AuditCategory.OPERATIONS,
                    severity=Severity.HIGH,
                    target_proposal_id="PROP-ARCH-001",
                    title="Kafka ops complexity",
                    description="Kafka ops require dedicated team.",
                    justification="Ops burden.",
                )
            ],
            findings_proposal_b=[
                AuditFinding(
                    id="F-PRAG-1",
                    category=AuditCategory.SCALABILITY,
                    severity=Severity.MEDIUM,
                    target_proposal_id="PROP-PRAG-001",
                    title="Shared DB limit",
                    description="Shared DB connection pool contention.",
                    justification="Connection limits.",
                )
            ],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.AUDIT_COMPLETED,
            actor=CommitteeRole.AUDITOR_SRE,
            payload=audit,
        )
        result = gate_confrontation_exit(session, env)
        assert result.passed

    def test_audit_empty_findings_fails(self, session, session_id, proposals) -> None:
        """Audit with no findings for either proposal must fail Gate 2."""
        audit = AuditReport(
            artifact_id="AUD-004",
            version=1,
            target_proposal_a_id="PROP-ARCH-001",
            target_proposal_b_id="PROP-PRAG-001",
            findings_proposal_a=[],
            findings_proposal_b=[],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.AUDIT_COMPLETED,
            actor=CommitteeRole.AUDITOR_SRE,
            payload=audit,
        )
        result = gate_confrontation_exit(session, env)
        assert not result.passed
        assert "Audit report must contain at least one finding" in (result.reason or "")

    def test_unknown_proposal_finding_fails(self, session, session_id, proposals) -> None:
        """Audit finding that targets an unknown proposal ID must fail Gate 2."""
        audit = AuditReport(
            artifact_id="AUD-005",
            version=1,
            target_proposal_a_id="PROP-ARCH-001",
            target_proposal_b_id="PROP-PRAG-001",
            findings_proposal_a=[
                AuditFinding(
                    id="F-ARCH-1",
                    category=AuditCategory.OPERATIONS,
                    severity=Severity.HIGH,
                    target_proposal_id="PROP-UNKNOWN-999",  # Invalid target
                    title="Unknown target",
                    description="Detailed description of the issue.",
                    justification="Industry standard rationale.",
                )
            ],
            findings_proposal_b=[
                AuditFinding(
                    id="F-PRAG-1",
                    category=AuditCategory.SCALABILITY,
                    severity=Severity.LOW,
                    target_proposal_id="PROP-PRAG-001",
                    title="Prag finding",
                    description="Detailed description of the issue.",
                    justification="Industry standard rationale.",
                )
            ],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.AUDIT_COMPLETED,
            actor=CommitteeRole.AUDITOR_SRE,
            payload=audit,
        )
        result = gate_confrontation_exit(session, env)
        assert not result.passed
        assert "targets unknown proposal 'PROP-UNKNOWN-999'" in (result.reason or "")

    def test_audit_different_severities_passes(self, session, session_id, proposals) -> None:
        """Audit with Proposal A having CRITICAL/HIGH findings and Proposal B having LOW passes."""
        audit = AuditReport(
            artifact_id="AUD-006",
            version=1,
            target_proposal_a_id="PROP-ARCH-001",
            target_proposal_b_id="PROP-PRAG-001",
            findings_proposal_a=[
                AuditFinding(
                    id="F-ARCH-CRIT",
                    category=AuditCategory.RELIABILITY,
                    severity=Severity.CRITICAL,
                    target_proposal_id="PROP-ARCH-001",
                    title="Split-brain risk in Kafka cluster",
                    description="Potential loss of transactional semantics during partition.",
                    justification="CAP theorem tradeoff.",
                )
            ],
            findings_proposal_b=[
                AuditFinding(
                    id="F-PRAG-LOW",
                    category=AuditCategory.COST,
                    severity=Severity.LOW,
                    target_proposal_id="PROP-PRAG-001",
                    title="Minor telemetry omission",
                    description="Structured log format could use trace context.",
                    justification="Standard observability practice.",
                )
            ],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.AUDIT_COMPLETED,
            actor=CommitteeRole.AUDITOR_SRE,
            payload=audit,
        )
        result = gate_confrontation_exit(session, env)
        assert result.passed


# ==============================================================================
# Gate 5: Decision Exit Integrity Tests
# ==============================================================================


class TestGate5DecisionIntegrity:
    @pytest.fixture(autouse=True)
    def setup_session_for_decision(self, session, proposals) -> None:
        session.current_state = CommitteeState.DECISION
        session.deliberation_synthesis = DeliberationSynthesis(
            artifact_id="SYN-001",
            version=1,
            consensus_points=["Both agree on PostgreSQL for storage"],
            divergence_points=["Microservices vs Monolith"],
        )

    def test_active_round_proposal_passes(self, session, session_id) -> None:
        """Decision choosing an active proposal from the current round passes Gate 5."""
        decision = DecisionRecord(
            artifact_id="DEC-001",
            version=1,
            status=DecisionStatus.RECOMMENDED,
            chosen_alternative="PROP-ARCH-001",
            recommendation="Adopt event-driven architecture.",
            rationale="Best alignment with anticipated 10x traffic growth.",
            confidence=Confidence.HIGH,
            trade_offs=[TradeOffContract(gain="Scalability", sacrifice="Operational simplicity")],
            review_triggers=[ReviewTrigger(condition="Monthly infra cost exceeds $10,000")],
            rejected_alternatives=[
                RejectedAlternative(name="Modular Monolith", rejection_reason="Cannot sustain long-term scale")
            ],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.DECISION_RECORDED,
            actor=CommitteeRole.DECISOR,
            payload=decision,
        )
        result = gate_decision_exit(session, env)
        assert result.passed

    def test_non_existent_alternative_fails(self, session, session_id) -> None:
        """Decision choosing an arbitrary or non-existent alternative fails Gate 5."""
        decision = DecisionRecord(
            artifact_id="DEC-002",
            version=1,
            status=DecisionStatus.RECOMMENDED,
            chosen_alternative="NON_EXISTENT_PROPOSAL_999",
            recommendation="Use non-existent proposal.",
            rationale="Invented rationale.",
            confidence=Confidence.MEDIUM,
            trade_offs=[TradeOffContract(gain="Magic", sacrifice="Reality")],
            review_triggers=[ReviewTrigger(condition="Never")],
            rejected_alternatives=[
                RejectedAlternative(name="Pragmatic", rejection_reason="Discarded")
            ],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.DECISION_RECORDED,
            actor=CommitteeRole.DECISOR,
            payload=decision,
        )
        result = gate_decision_exit(session, env)
        assert not result.passed
        assert "does not reference an active proposal in the current round" in (result.reason or "")

    def test_historical_round_alternative_fails(self, session, session_id) -> None:
        """Decision choosing a proposal from an archived/superseded round fails Gate 5."""
        # Archive a round with an old proposal
        hist_prop = ArchitectProposal(
            artifact_id="PROP-ARCH-HIST-000",
            version=1,
            title="Old Discarded Arch",
            solution="Streaming WebSocket without local buffer.",
            rationale="Assumed continuous connectivity.",
            benefits=["Real-time"],
            costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$100"),
            risks=["Offline failure"],
            complexity=Severity.MEDIUM,
            reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Easy to replace"),
            future_implications="No significant implications.",
            assumptions=["Always online"],
            invalidation_conditions=["Offline > 1s"],
        )
        session.historical_rounds.append(
            DeliberationRound(
                round_number=0,
                status=RoundStatus.SUPERSEDED_BY_ROLLBACK,
                proposals={CommitteeRole.ARCHITECT: hist_prop},
            )
        )

        decision = DecisionRecord(
            artifact_id="DEC-003",
            version=1,
            status=DecisionStatus.RECOMMENDED,
            chosen_alternative="PROP-ARCH-HIST-000",  # From historical round
            recommendation="Adopt old discarded architecture.",
            rationale="Incorrectly reviving superseded proposal.",
            confidence=Confidence.HIGH,
            trade_offs=[TradeOffContract(gain="Real-time", sacrifice="Offline resilience")],
            review_triggers=[ReviewTrigger(condition="Always")],
            rejected_alternatives=[
                RejectedAlternative(name="Pragmatic", rejection_reason="Discarded")
            ],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.DECISION_RECORDED,
            actor=CommitteeRole.DECISOR,
            payload=decision,
        )
        result = gate_decision_exit(session, env)
        assert not result.passed
        assert "references a proposal from a superseded historical round" in (result.reason or "")

    def test_insufficient_evidence_without_winner_passes(self, session, session_id) -> None:
        """Decision with INSUFFICIENT_EVIDENCE and no chosen alternative passes Gate 5."""
        decision = DecisionRecord(
            artifact_id="DEC-004",
            version=1,
            status=DecisionStatus.INSUFFICIENT_EVIDENCE,
            chosen_alternative=None,
            rationale="Critical SLA throughput metrics are missing to determine if Kafka is required.",
            confidence=Confidence.LOW,
            information_that_could_change_decision=[
                "Peak requests/sec measurement from current production telemetry."
            ],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.DECISION_FAILED,
            actor=CommitteeRole.DECISOR,
            payload=decision,
        )
        result = gate_decision_exit(session, env)
        assert result.passed

    def test_insufficient_evidence_with_winner_fails(self, session, session_id) -> None:
        """Decision with INSUFFICIENT_EVIDENCE that still names a chosen alternative must fail Gate 5."""
        decision = DecisionRecord.model_construct(
            artifact_id="DEC-005",
            version=1,
            status=DecisionStatus.INSUFFICIENT_EVIDENCE,
            chosen_alternative="PROP-ARCH-001",  # Illegal for INSUFFICIENT_EVIDENCE
            rationale="Insufficient evidence, but recommending Arch anyway.",
            confidence=Confidence.LOW,
            information_that_could_change_decision=["More data"],
        )
        env = EventEnvelope(
            session_id=session_id,
            event_type=EventType.DECISION_FAILED,
            actor=CommitteeRole.DECISOR,
            payload=decision,
        )
        result = gate_decision_exit(session, env)
        assert not result.passed
        assert "must not choose any alternative" in (result.reason or "")
