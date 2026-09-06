"""Integration tests executing simulated end-to-end deliberation and negative tests."""

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
from schemas.context import ProblemContext
from schemas.decision import (
    AcceptedRisk,
    DecisionRecord,
    RejectedAlternative,
    ReviewTrigger,
    TradeOffContract,
)
from schemas.defense import (
    ArchitectDefense,
    CritiqueResponse,
    DefenseStance,
    PragmaticDefense,
    ProposalAction,
)
from schemas.events import EventEnvelope, PhaseRollbackPayload
from schemas.learning import (
    LearningPathStep,
    LearningReference,
    LearningReport,
    ObservedKnowledgeGap,
)
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from schemas.synthesis import DeliberationSynthesis, TradeOffDimension
from src.committee.event_store import DuplicateEventError, EventStore
from src.committee.replay import replay_session
from src.committee.session import Session
from src.committee.state_machine import (
    InvalidTransitionError,
    QualityGateFailedError,
    StateMachine,
)


@pytest.fixture
def event_store(tmp_path):
    store = EventStore(tmp_path / "test_integration.db")
    yield store
    store.close()


def test_full_simulated_deliberation_workflow(event_store) -> None:
    """End-to-end test walking through all 7 phases without any LLM calls."""
    sm = StateMachine(event_store)
    session_id = uuid4()

    # Step 1: SESSION_CREATED (DRAFT -> INVESTIGATION)
    session = sm.create_session(
        session_id=session_id,
        problem_statement="Determine cache invalidation architecture for high-volume portal.",
        user_id="lead_eng",
    )
    assert session.current_state == CommitteeState.INVESTIGATION

    # Step 2: CONTEXT_VALIDATED (INVESTIGATION -> DIVERGENCE)
    ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Determine cache invalidation architecture for high-volume portal.",
        success_criteria=["p95 latency < 30ms", "Zero stale data on article updates"],
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.CONTEXT_VALIDATED,
            actor=CommitteeRole.FACILITATOR,
            artifact_id="CTX-001",
            artifact_version="v1",
            payload=ctx,
        ),
    )
    assert session.current_state == CommitteeState.DIVERGENCE

    # Step 3: PROPOSAL_CREATED (Architect) -> remains in DIVERGENCE awaiting Pragmatic
    prop_arch = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Event-Driven Multi-AZ Redis Cluster",
        solution="Distributed cache invalidated by SNS/SQS event stream.",
        rationale="Guarantees immediate invalidation across multi-region read replicas.",
        benefits=["High cache consistency", "Scales to 10k req/s"],
        costs=CostEstimate(implementation_effort=EffortLevel.HIGH, infrastructure_cost_estimate="$300/mo"),
        risks=["Event consumer lag during burst traffic"],
        complexity=Severity.HIGH,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.MEDIUM, rationale="Decoupled events"),
        future_implications="Prepares platform for multi-region active-active deployment.",
        assumptions=["Cluster network latency < 2ms"],
        invalidation_conditions=["Read traffic drops under 100 req/s"],
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.PROPOSAL_CREATED,
            actor=CommitteeRole.ARCHITECT,
            artifact_id="PROP-ARCH-001",
            artifact_version="v1",
            payload=prop_arch,
        ),
    )
    assert session.current_state == CommitteeState.DIVERGENCE
    assert not session.has_both_proposals()

    # Step 4: PROPOSAL_CREATED (Pragmatist) -> transitions to CONFRONTATION (Gate 1 passed)
    prop_prag = PragmaticProposal(
        artifact_id="PROP-PRAG-001",
        version=1,
        title="Standalone Redis with Short TTLs",
        solution="Single Redis instance with 60-second TTL and background cache warming.",
        rationale="Eliminates cache invalidation code complexity entirely.",
        benefits=["Zero event plumbing", "Deployable in 2 days"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$40/mo"),
        risks=["60-second stale window for breaking news"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Easily swappable"),
        future_implications="May cause backend cache stampedes on article expiration.",
        assumptions=["Users tolerate up to 60s delay on updates"],
        invalidation_conditions=["Zero-stale SLA becomes strictly non-negotiable"],
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.PROPOSAL_CREATED,
            actor=CommitteeRole.PRAGMATIST,
            artifact_id="PROP-PRAG-001",
            artifact_version="v1",
            payload=prop_prag,
        ),
    )
    assert session.current_state == CommitteeState.CONFRONTATION
    assert session.has_both_proposals()

    # Step 5: AUDIT_COMPLETED (Auditor) -> transitions to DEFENSE (Gate 2 passed)
    audit = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[
            AuditFinding(
                id="F-01",
                target_proposal_id="PROP-ARCH-001",
                category=AuditCategory.OVERENGINEERING,
                severity=Severity.HIGH,
                title="Excessive broker infrastructure for single-region read cache",
                description="Managing SNS/SQS for invalidation creates unnecessary alert surfaces.",
                justification="Simple pub/sub on existing Redis solves this with zero extra cloud services.",
            )
        ],
        findings_proposal_b=[
            AuditFinding(
                id="F-02",
                target_proposal_id="PROP-PRAG-001",
                category=AuditCategory.RELIABILITY,
                severity=Severity.CRITICAL,
                title="Cache Stampede Risk on TTL Expiration",
                description="When popular article TTL expires, 5,000 concurrent req/s will hit DB.",
                justification="Known thundering herd vulnerability.",
            )
        ],
        single_points_of_failure=["Standalone Redis instance in Proposal B"],
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.AUDIT_COMPLETED,
            actor=CommitteeRole.AUDITOR_SRE,
            artifact_id="AUD-001",
            artifact_version="v1",
            payload=audit,
        ),
    )
    assert session.current_state == CommitteeState.DEFENSE

    # Step 6: DEFENSE_SUBMITTED (Architect) -> remains in DEFENSE awaiting Pragmatic
    def_arch = ArchitectDefense(
        artifact_id="DEF-ARCH-001",
        version=1,
        original_proposal_id="PROP-ARCH-001",
        original_proposal_version=1,
        critique_responses=[
            CritiqueResponse(
                finding_id="F-01",
                stance=DefenseStance.CONCEDED_WITH_REFINEMENT,
                response="Concede that SQS/SNS is excessive.",
                rationale="Adopt Redis native pub/sub for invalidation messages.",
                proposed_modification="Drop SQS/SNS in favor of Redis Pub/Sub.",
            )
        ],
        proposal_action=ProposalAction.MODIFY,
        revised_proposal_id="PROP-ARCH-001",
        revised_proposal_version=2,
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.DEFENSE_SUBMITTED,
            actor=CommitteeRole.ARCHITECT,
            artifact_id="DEF-ARCH-001",
            artifact_version="v1",
            payload=def_arch,
        ),
    )
    assert session.current_state == CommitteeState.DEFENSE
    assert not session.has_both_defenses()

    # Step 7: DEFENSE_SUBMITTED (Pragmatic) -> transitions to CONVERGENCE (Gate 3 passed)
    def_prag = PragmaticDefense(
        artifact_id="DEF-PRAG-001",
        version=1,
        original_proposal_id="PROP-PRAG-001",
        original_proposal_version=1,
        critique_responses=[
            CritiqueResponse(
                finding_id="F-02",
                stance=DefenseStance.CONCEDED_WITH_REFINEMENT,
                response="Concede cache stampede risk.",
                rationale="Add mutex locking (probabilistic early expiration) to prevent thundering herd.",
                proposed_modification="Use XFetch / probabilistic early refresh algorithm.",
            )
        ],
        proposal_action=ProposalAction.MODIFY,
        revised_proposal_id="PROP-PRAG-001",
        revised_proposal_version=2,
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.DEFENSE_SUBMITTED,
            actor=CommitteeRole.PRAGMATIST,
            artifact_id="DEF-PRAG-001",
            artifact_version="v1",
            payload=def_prag,
        ),
    )
    assert session.current_state == CommitteeState.CONVERGENCE
    assert session.has_both_defenses()

    # Step 8: SYNTHESIS_CREATED (Facilitator) -> transitions to DECISION (Gate 4 passed)
    synthesis = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consolidated_facts=["Redis cluster available", "Read volume 5,000 req/s"],
        consensus_points=["Both agree external queue brokers (SQS) are excessive"],
        divergence_points=["Active invalidation (Pub/Sub) vs Passive TTL with XFetch"],
        trade_offs=[
            TradeOffDimension(
                dimension="Complexity vs Stale Margin",
                option_a="Immediate invalidation with pub/sub event handling",
                option_b="60s TTL with XFetch avoiding stampedes, near zero complexity",
            )
        ],
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.SYNTHESIS_CREATED,
            actor=CommitteeRole.FACILITATOR,
            artifact_id="SYN-001",
            artifact_version="v1",
            payload=synthesis,
        ),
    )
    assert session.current_state == CommitteeState.DECISION

    # Step 9: DECISION_RECORDED (Decisor) -> transitions to REFLECTION (Gate 5 passed)
    decision = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        recommendation="Adopt Pragmatic Proposal v2 (Redis with 60s TTL and XFetch locking).",
        chosen_alternative="PROPOSAL_PRAG_V2",
        rejected_alternatives=[
            RejectedAlternative(
                name="PROPOSAL_ARCH_V2",
                rejection_reason="Active invalidation pub/sub introduces operational state for a problem that 60s TTL with XFetch solves adequately.",
            )
        ],
        rationale="Meets p95 SLA easily with negligible engineering effort. XFetch completely mitigates cache stampedes.",
        trade_offs=[
            TradeOffContract(
                gain="Deployable in 3 days with $40/mo infrastructure",
                sacrifice="Accepting up to 60-second delay for non-critical article updates",
            )
        ],
        accepted_risks=[
            AcceptedRisk(
                risk="Occasional delayed update during breaking news spikes",
                severity=Severity.LOW,
                mitigation="Provide manual cache purge API for editorial team",
            )
        ],
        review_triggers=[
            ReviewTrigger(
                condition="Editorial team reports stale content issues more than 3 times a week",
                trigger_type="EDITORIAL_ESCALATION",
            )
        ],
        confidence=Confidence.HIGH,
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.DECISION_RECORDED,
            actor=CommitteeRole.DECISOR,
            artifact_id="DEC-001",
            artifact_version="v1",
            payload=decision,
        ),
    )
    assert session.current_state == CommitteeState.REFLECTION

    # Step 10: LEARNING_REPORT_CREATED (Mentor) -> transitions to COMPLETED (Gate 6 passed)
    learning = LearningReport(
        artifact_id="LRN-001",
        version=1,
        concepts=["Cache Stampede / Thundering Herd", "XFetch Algorithm", "TTL vs Active Invalidation"],
        concepts_required_to_understand_decision=[
            "Probabilistic early expiration mechanics",
            "Trade-offs between cache consistency and read availability",
        ],
        observed_knowledge_gaps=[
            ObservedKnowledgeGap(
                observation="Initial requirements conflated real-time consistency with low latency.",
                context_evidence="Problem framing where user assumed caching requires microsecond synchronization.",
                recommended_topic="Consistency models in caching layers.",
            )
        ],
        study_questions=[
            "How does XFetch mathematically prevent all concurrent clients from hitting the database at once?"
        ],
        learning_path=[
            LearningPathStep(
                order=1,
                topic="Cache Engineering",
                description="Read Vattani et al. paper on Optimal Probabilistic Cache Invalidation.",
                reference=LearningReference(
                    title="Optimal Probabilistic Cache Invalidation",
                    url_or_citation="ACM Transactions, 2015",
                ),
            )
        ],
        theory_to_practice_connections=[
            "The committee chose TTL over active invalidation adhering to the KISS principle because the business SLA tolerated bounded eventual consistency."
        ],
        references=[
            LearningReference(
                title="Designing Data-Intensive Applications",
                url_or_citation="O'Reilly, Cap. 3",
            )
        ],
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.LEARNING_REPORT_CREATED,
            actor=CommitteeRole.MENTOR,
            artifact_id="LRN-001",
            artifact_version="v1",
            payload=learning,
        ),
    )
    assert session.current_state == CommitteeState.COMPLETED
    assert event_store.count_events(session_id) == 10

    # Step 11: Replay Verification
    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.COMPLETED
    assert replayed.decision_record is not None
    assert replayed.decision_record.chosen_alternative == "PROPOSAL_PRAG_V2"
    assert replayed.learning_report is not None


def test_negative_decision_before_audit(event_store) -> None:
    """Negative test: Attempting to record a decision before audit must be rejected."""
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Problem description.")

    dec = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        rationale="Premature decision attempt.",
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Everything"],
    )
    with pytest.raises(InvalidTransitionError):
        sm.handle_event(
            session,
            EventEnvelope(
                session_id=session_id,
                event_type=EventType.DECISION_FAILED,
                actor=CommitteeRole.DECISOR,
                payload=dec,
            ),
        )


def test_negative_synthesis_before_defenses(event_store) -> None:
    """Negative test: Attempting to create synthesis before defenses must be rejected."""
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Problem description.")

    synth = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consolidated_facts=["Fact"],
    )
    with pytest.raises(InvalidTransitionError):
        sm.handle_event(
            session,
            EventEnvelope(
                session_id=session_id,
                event_type=EventType.SYNTHESIS_CREATED,
                actor=CommitteeRole.FACILITATOR,
                payload=synth,
            ),
        )


def test_negative_rollback_preserves_history(event_store) -> None:
    """Negative/Rollback test: Rollback does not erase events, appending a rollback record."""
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "IoT factory telemetry problem.")

    # Validate Context
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.CONTEXT_VALIDATED,
            actor=CommitteeRole.FACILITATOR,
            payload=ProblemContext(
                artifact_id="CTX-001",
                version=1,
                problem="IoT factory problem.",
                success_criteria=["S1"],
            ),
        ),
    )

    # Submit Proposal A & B
    prop_a = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Streaming proposal",
        solution="WebSocket streaming",
        rationale="Real-time streaming meets requirements",
        benefits=["Realtime"],
        costs=CostEstimate(implementation_effort=EffortLevel.MEDIUM, infrastructure_cost_estimate="$100"),
        risks=["Network drop"],
        complexity=Severity.MEDIUM,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="Scalable",
        assumptions=["Continuous internet"],
        invalidation_conditions=["No internet"],
    )
    prop_b = PragmaticProposal(
        artifact_id="PROP-PRAG-001",
        version=1,
        title="Polling proposal",
        solution="HTTP polling",
        rationale="Simple HTTP polling meets initial needs.",
        benefits=["Simple"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$20"),
        risks=["Load"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="Limited",
        assumptions=["Continuous internet"],
        invalidation_conditions=["No internet"],
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.PROPOSAL_CREATED,
            actor=CommitteeRole.ARCHITECT,
            payload=prop_a,
        ),
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.PROPOSAL_CREATED,
            actor=CommitteeRole.PRAGMATIST,
            payload=prop_b,
        ),
    )
    assert session.current_state == CommitteeState.CONFRONTATION
    count_before_rollback = event_store.count_events(session_id)

    # Trigger Rollback from CONFRONTATION to INVESTIGATION
    rollback_payload = PhaseRollbackPayload(
        from_phase="PHASE_2_CONFRONTATION",
        to_phase="PHASE_0_INVESTIGATION",
        reason="Auditor found factory has 72h offline periods, invalidating continuous internet assumption.",
        superseded_artifacts=["PROP-ARCH-001:v1", "PROP-PRAG-001:v1"],
    )
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.PHASE_ROLLBACK,
            actor=CommitteeRole.AUDITOR_SRE,
            payload=rollback_payload,
        ),
    )

    assert session.current_state == CommitteeState.INVESTIGATION
    # History was preserved and grown append-only, NOT erased!
    assert event_store.count_events(session_id) == count_before_rollback + 1
    events = event_store.get_events(session_id)
    assert any(e.event_type == EventType.PHASE_ROLLBACK for e in events)
    assert any(e.event_type == EventType.PROPOSAL_CREATED for e in events)


def test_negative_proponent_role_mismatch(event_store) -> None:
    """Negative test: Attempting to submit Architect proposal under Pragmatist actor role."""
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Problem description.")
    sm.handle_event(
        session,
        EventEnvelope(
            session_id=session_id,
            event_type=EventType.CONTEXT_VALIDATED,
            actor=CommitteeRole.FACILITATOR,
            payload=ProblemContext(
                artifact_id="CTX-001",
                version=1,
                problem="Problem description.",
                success_criteria=["Success 1"],
            ),
        ),
    )
    # ArchitectProposal with actor PRAGMATIST must be rejected by Gate 1
    prop = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Valid Proposal",
        solution="Solution string long enough.",
        rationale="Rationale string long enough.",
        benefits=["Benefit 1"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$10"),
        risks=["Risk 1"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="No future issues",
        assumptions=["Assumption 1"],
        invalidation_conditions=["Condition 1"],
    )
    with pytest.raises(QualityGateFailedError, match="does not match proposal proponent_role"):
        sm.handle_event(
            session,
            EventEnvelope(
                session_id=session_id,
                event_type=EventType.PROPOSAL_CREATED,
                actor=CommitteeRole.PRAGMATIST,
                payload=prop,
            ),
        )


def test_negative_duplicate_event_id(event_store) -> None:
    """Negative test: Appending two events with the same event_id fails."""
    session_id = uuid4()
    shared_event_id = uuid4()
    sm = StateMachine(event_store)
    session = sm.create_session(session_id, "Problem description.")

    env1 = EventEnvelope(
        event_id=shared_event_id,
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=ProblemContext(
            artifact_id="CTX-001",
            version=1,
            problem="Problem description.",
            success_criteria=["Success 1"],
        ),
    )
    sm.handle_event(session, env1)

    # Attempt to submit another event with the exact same event_id
    env2 = EventEnvelope(
        event_id=shared_event_id,
        session_id=session_id,
        event_type=EventType.PROPOSAL_CREATED,
        actor=CommitteeRole.ARCHITECT,
        payload=ArchitectProposal(
            artifact_id="PROP-ARCH-001",
            version=1,
            title="Valid Proposal",
            solution="Solution string long enough.",
            rationale="Rationale string long enough.",
            benefits=["Benefit 1"],
            costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$10"),
            risks=["Risk 1"],
            complexity=Severity.LOW,
            reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
            future_implications="No future issues",
            assumptions=["Assumption 1"],
            invalidation_conditions=["Condition 1"],
        ),
    )
    with pytest.raises(DuplicateEventError):
        sm.handle_event(session, env2)


def test_negative_skip_investigation_to_decision(event_store) -> None:
    """Negative test: Skipping from INVESTIGATION directly to DECISION is strictly rejected."""
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Problem description.")

    dec = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        rationale="Skipping phases attempt.",
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Everything"],
    )
    with pytest.raises(InvalidTransitionError):
        sm.handle_event(
            session,
            EventEnvelope(
                session_id=session_id,
                event_type=EventType.DECISION_FAILED,
                actor=CommitteeRole.DECISOR,
                payload=dec,
            ),
        )


def test_negative_complete_without_learning_report(event_store) -> None:
    """Negative test: Transitioning to COMPLETED without LearningReport is rejected."""
    session = Session(session_id=uuid4(), current_state=CommitteeState.REFLECTION)
    sm = StateMachine(event_store)

    # Attempt to emit something other than LEARNING_REPORT_CREATED while in REFLECTION
    ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Problem description.",
        success_criteria=["Success 1"],
    )
    with pytest.raises(InvalidTransitionError):
        sm.handle_event(
            session,
            EventEnvelope(
                session_id=session.session_id,
                event_type=EventType.CONTEXT_VALIDATED,
                actor=CommitteeRole.FACILITATOR,
                payload=ctx,
            ),
        )
