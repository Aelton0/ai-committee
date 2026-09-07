"""Unit tests for deterministic Quality Gates."""

from uuid import uuid4

import pytest

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, CommitteeState, Confidence, DecisionStatus, EventType, Severity
from schemas.context import OpenQuestion, ProblemContext
from schemas.decision import DecisionRecord, RejectedAlternative, ReviewTrigger, TradeOffContract
from schemas.defense import ArchitectDefense, CritiqueResponse, DefenseStance, PragmaticDefense, ProposalAction
from schemas.events import CriticalErrorPayload, EventEnvelope, PhaseRollbackPayload, UserOverridePayload
from schemas.intervention import UserAbortCommand
from schemas.learning import LearningPathStep, LearningReference, LearningReport
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from schemas.synthesis import DeliberationSynthesis
from src.committee.gates import (
    gate_confrontation_exit,
    gate_convergence_exit,
    gate_critical_error,
    gate_decision_exit,
    gate_defense_submission,
    gate_divergence_proposal,
    gate_investigation_exit,
    gate_reflection_exit,
    gate_rollback,
    gate_user_override,
)
from src.committee.session import Session


@pytest.fixture
def session_id():
    return uuid4()


@pytest.fixture
def session(session_id):
    return Session(session_id=session_id)


def test_gate_investigation_exit_blocks_unanswered_questions(session, session_id) -> None:
    """Test Gate 0 blocks transition when open questions remain unanswered."""
    ctx_with_unanswered = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Test problem",
        success_criteria=["Success 1"],
        open_questions=[OpenQuestion(id="Q1", question="Missing requirement?", why_critical="Blocker")],
    )
    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=ctx_with_unanswered,
    )
    result = gate_investigation_exit(session, env)
    assert not result.passed
    assert "open question(s) remain unanswered" in (result.reason or "")

    # Now with questions answered
    ctx_answered = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Test problem",
        success_criteria=["Success 1"],
        open_questions=[OpenQuestion(id="Q1", question="Missing requirement?", why_critical="Blocker", answer="Resolved")],
    )
    env_answered = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=ctx_answered,
    )
    result_answered = gate_investigation_exit(session, env_answered)
    assert result_answered.passed


def test_gate_divergence_proposal_enforces_author_role(session, session_id) -> None:
    """Test Gate 1 verifies actor matches proposal proponent_role."""
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
    # Actor PRAGMATIST submitting ArchitectProposal must fail gate
    env_mismatch = EventEnvelope(
        session_id=session_id,
        event_type=EventType.PROPOSAL_CREATED,
        actor=CommitteeRole.PRAGMATIST,
        payload=prop,
    )
    res_mismatch = gate_divergence_proposal(session, env_mismatch)
    assert not res_mismatch.passed
    assert "does not match proposal proponent_role" in (res_mismatch.reason or "")


def test_gate_confrontation_exit_requires_both_proposals(session, session_id) -> None:
    """Test Gate 2 requires both proposals to have been registered before audit is accepted."""
    audit = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
    )
    env_audit = EventEnvelope(
        session_id=session_id,
        event_type=EventType.AUDIT_COMPLETED,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=audit,
    )
    # Fails because session does not have both proposals
    res = gate_confrontation_exit(session, env_audit)
    assert not res.passed
    assert "both Architect and Pragmatic proposals registered" in (res.reason or "")


def test_gate_decision_exit_requires_synthesis(session, session_id) -> None:
    """Test Gate 5 requires deliberation synthesis before decision can be recorded."""
    dec = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        rationale="Missing load test data.",
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Load tests"],
    )
    env_dec = EventEnvelope(
        session_id=session_id,
        event_type=EventType.DECISION_FAILED,
        actor=CommitteeRole.DECISOR,
        payload=dec,
    )
    # Fails because session.deliberation_synthesis is None
    res = gate_decision_exit(session, env_dec)
    assert not res.passed
    assert "before deliberation synthesis is established" in (res.reason or "")


def test_gate_rollback_only_from_allowed_phases(session, session_id) -> None:
    """Test Gate Rollback only allows rollback from CONFRONTATION or DEFENSE."""
    session.current_state = CommitteeState.INVESTIGATION
    rollback_payload = PhaseRollbackPayload(
        from_phase="PHASE_2_CONFRONTATION",
        to_phase="PHASE_0_INVESTIGATION",
        reason="Baseline assumption flawed",
    )
    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.PHASE_ROLLBACK,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=rollback_payload,
    )
    res = gate_rollback(session, env)
    assert not res.passed

    # Allowed from CONFRONTATION
    session.current_state = CommitteeState.CONFRONTATION
    res_allowed = gate_rollback(session, env)
    assert res_allowed.passed


def test_gate_divergence_proposal_rejects_duplicate(session, session_id) -> None:
    """Test Gate 1 rejects duplicate proposals for the same role in the active round."""
    prop1 = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Initial Arch Proposal",
        solution="Solution detail.",
        rationale="Rationale detail.",
        benefits=["Benefit 1"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$10"),
        risks=["Risk 1"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="No future issues",
        assumptions=["Assumption 1"],
        invalidation_conditions=["Condition 1"],
    )
    session.proposals[CommitteeRole.ARCHITECT] = prop1

    prop2 = ArchitectProposal(
        artifact_id="PROP-ARCH-002",
        version=1,
        title="Duplicate Arch Proposal",
        solution="Alternative solution detail.",
        rationale="Alternative rationale detail.",
        benefits=["Benefit 2"],
        costs=CostEstimate(implementation_effort=EffortLevel.MEDIUM, infrastructure_cost_estimate="$20"),
        risks=["Risk 2"],
        complexity=Severity.MEDIUM,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.MEDIUM, rationale="Reversible"),
        future_implications="No future issues",
        assumptions=["Assumption 2"],
        invalidation_conditions=["Condition 2"],
    )
    env_duplicate = EventEnvelope(
        session_id=session_id,
        event_type=EventType.PROPOSAL_CREATED,
        actor=CommitteeRole.ARCHITECT,
        payload=prop2,
    )
    res = gate_divergence_proposal(session, env_duplicate)
    assert not res.passed
    assert "Duplicate proposal" in (res.reason or "")


def test_gate_confrontation_exit_validation(session, session_id) -> None:
    """Test Gate 2 enforces target proposal match, non-empty findings, and valid finding targets."""
    prop_a = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Arch Proposal",
        solution="Detailed architectural solution proposal.",
        rationale="Detailed architectural rationale explanation.",
        benefits=["B1"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$1"),
        risks=["R1"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="No future issues",
        assumptions=["A1"],
        invalidation_conditions=["C1"],
    )
    prop_b = PragmaticProposal(
        artifact_id="PROP-PRAG-001",
        version=1,
        title="Prag Proposal",
        solution="Detailed pragmatic solution proposal.",
        rationale="Detailed pragmatic rationale explanation.",
        benefits=["B1"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$1"),
        risks=["R1"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="No future issues",
        assumptions=["A1"],
        invalidation_conditions=["C1"],
    )
    session.proposals[CommitteeRole.ARCHITECT] = prop_a
    session.proposals[CommitteeRole.PRAGMATIST] = prop_b

    # Case 1: Target proposal IDs don't match registered
    bad_targets_audit = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-UNKNOWN-999",
        findings_proposal_a=[
            AuditFinding(
                id="F1",
                category=AuditCategory.OPERATIONS,
                severity=Severity.HIGH,
                target_proposal_id="PROP-ARCH-001",
                title="Risk",
                description="Risk description",
                justification="Risk justification",
            )
        ],
    )
    env_bad_targets = EventEnvelope(
        session_id=session_id,
        event_type=EventType.AUDIT_COMPLETED,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=bad_targets_audit,
    )
    res = gate_confrontation_exit(session, env_bad_targets)
    assert not res.passed
    assert "do not match registered proposal IDs" in (res.reason or "")

    # Case 2: Empty findings
    empty_findings_audit = AuditReport(
        artifact_id="AUD-002",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[],
        findings_proposal_b=[],
    )
    env_empty = EventEnvelope(
        session_id=session_id,
        event_type=EventType.AUDIT_COMPLETED,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=empty_findings_audit,
    )
    res_empty = gate_confrontation_exit(session, env_empty)
    assert not res_empty.passed
    assert "at least one finding" in (res_empty.reason or "")

    # Case 3: Finding targets unknown proposal
    unknown_target_finding_audit = AuditReport(
        artifact_id="AUD-003",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[
            AuditFinding(
                id="F1",
                category=AuditCategory.SECURITY,
                severity=Severity.HIGH,
                target_proposal_id="PROP-SOME-OTHER",
                title="Sec",
                description="Security description",
                justification="Security justification",
            )
        ],
    )
    env_unknown_f = EventEnvelope(
        session_id=session_id,
        event_type=EventType.AUDIT_COMPLETED,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=unknown_target_finding_audit,
    )
    res_unknown_f = gate_confrontation_exit(session, env_unknown_f)
    assert not res_unknown_f.passed
    assert "targets unknown proposal" in (res_unknown_f.reason or "")

    # Case 4: Valid audit report
    valid_audit = AuditReport(
        artifact_id="AUD-004",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[
            AuditFinding(
                id="F1",
                category=AuditCategory.OPERATIONS,
                severity=Severity.MEDIUM,
                target_proposal_id="PROP-ARCH-001",
                title="Operational risk",
                description="Risk description",
                justification="Risk justification",
            )
        ],
        findings_proposal_b=[
            AuditFinding(
                id="F2",
                category=AuditCategory.RELIABILITY,
                severity=Severity.LOW,
                target_proposal_id="PROP-PRAG-001",
                title="Reliability note",
                description="Risk description",
                justification="Risk justification",
            )
        ],
    )
    env_valid = EventEnvelope(
        session_id=session_id,
        event_type=EventType.AUDIT_COMPLETED,
        actor=CommitteeRole.AUDITOR_SRE,
        payload=valid_audit,
    )
    assert gate_confrontation_exit(session, env_valid).passed


def test_gate_defense_submission_validation(session, session_id) -> None:
    """Test Gate 3 verifies defense author, duplicate check, proposal link, and valid finding IDs."""
    prop_arch = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Arch Proposal",
        solution="Detailed architectural solution proposal.",
        rationale="Detailed architectural rationale explanation.",
        benefits=["B1"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$1"),
        risks=["R1"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="No future issues",
        assumptions=["A1"],
        invalidation_conditions=["C1"],
    )
    session.proposals[CommitteeRole.ARCHITECT] = prop_arch
    session.audit_report = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[
            AuditFinding(
                id="FIND-001",
                category=AuditCategory.OPERATIONS,
                severity=Severity.HIGH,
                target_proposal_id="PROP-ARCH-001",
                title="Risk 1",
                description="Risk description",
                justification="Risk justification",
            )
        ],
    )

    valid_defense = ArchitectDefense(
        artifact_id="DEF-ARCH-001",
        version=1,
        original_proposal_id="PROP-ARCH-001",
        proposal_action=ProposalAction.MAINTAIN,
        critique_responses=[
            CritiqueResponse(
                finding_id="FIND-001",
                stance=DefenseStance.CONTESTED,
                response="Circuit breaker pattern mitigates this risk.",
                rationale="Proven pattern in production systems.",
            )
        ],
    )
    env_valid = EventEnvelope(
        session_id=session_id,
        event_type=EventType.DEFENSE_SUBMITTED,
        actor=CommitteeRole.ARCHITECT,
        payload=valid_defense,
    )
    assert gate_defense_submission(session, env_valid).passed

    # Case 1: Mismatched proposal ID
    defense_bad_prop = ArchitectDefense(
        artifact_id="DEF-ARCH-002",
        version=1,
        original_proposal_id="PROP-WRONG-001",
        proposal_action=ProposalAction.MAINTAIN,
        critique_responses=[
            CritiqueResponse(
                finding_id="FIND-001",
                stance=DefenseStance.CONTESTED,
                response="Circuit breaker pattern mitigates this risk.",
                rationale="Proven pattern in production systems.",
            )
        ],
    )
    env_bad_prop = EventEnvelope(
        session_id=session_id,
        event_type=EventType.DEFENSE_SUBMITTED,
        actor=CommitteeRole.ARCHITECT,
        payload=defense_bad_prop,
    )
    res_bad_prop = gate_defense_submission(session, env_bad_prop)
    assert not res_bad_prop.passed
    assert "does not match active proposal" in (res_bad_prop.reason or "")

    # Case 2: Response targets unknown finding
    defense_bad_finding = ArchitectDefense(
        artifact_id="DEF-ARCH-003",
        version=1,
        original_proposal_id="PROP-ARCH-001",
        proposal_action=ProposalAction.MAINTAIN,
        critique_responses=[
            CritiqueResponse(
                finding_id="FIND-UNKNOWN-999",
                stance=DefenseStance.CONTESTED,
                response="Invalid finding response.",
                rationale="Invalid finding rationale.",
            )
        ],
    )
    env_bad_finding = EventEnvelope(
        session_id=session_id,
        event_type=EventType.DEFENSE_SUBMITTED,
        actor=CommitteeRole.ARCHITECT,
        payload=defense_bad_finding,
    )
    res_bad_finding = gate_defense_submission(session, env_bad_finding)
    assert not res_bad_finding.passed
    assert "unknown audit finding 'FIND-UNKNOWN-999'" in (res_bad_finding.reason or "")

    # Case 3: Duplicate defense for same role
    session.defenses[CommitteeRole.ARCHITECT] = valid_defense
    res_dup = gate_defense_submission(session, env_valid)
    assert not res_dup.passed
    assert "Duplicate defense" in (res_dup.reason or "")


def test_gate_decision_exit_recommended_and_insufficient_evidence(session, session_id) -> None:
    """Test Gate 5 enforces invariants for RECOMMENDED and INSUFFICIENT_EVIDENCE decisions."""
    session.proposals[CommitteeRole.ARCHITECT] = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Arch Proposal",
        solution="Detailed architectural solution proposal.",
        rationale="Detailed architectural rationale explanation.",
        benefits=["B1"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$1"),
        risks=["R1"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Reversible"),
        future_implications="No future issues",
        assumptions=["A1"],
        invalidation_conditions=["C1"],
    )
    session.deliberation_synthesis = DeliberationSynthesis(
        artifact_id="SYNTH-001",
        version=1,
        consensus_points=["Point 1"],
        divergence_points=["Diff 1"],
    )

    # Missing chosen_alternative for RECOMMENDED
    bad_rec_no_choice = DecisionRecord.model_construct(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        chosen_alternative=None,
        recommendation="Use Arch",
        rationale="Best available architectural rationale.",
        confidence=Confidence.HIGH,
        trade_offs=[TradeOffContract(gain="Scalability", sacrifice="Simplicity")],
        review_triggers=[ReviewTrigger(condition="Requests exceed 10k req/sec")],
        rejected_alternatives=[RejectedAlternative(name="Pragmatic", rejection_reason="Too simple for long term")],
    )
    env = EventEnvelope(session_id=session_id, event_type=EventType.DECISION_RECORDED, actor=CommitteeRole.DECISOR, payload=bad_rec_no_choice)
    res = gate_decision_exit(session, env)
    assert not res.passed
    assert "must specify a non-empty chosen_alternative" in (res.reason or "")

    # Missing trade_offs for RECOMMENDED
    bad_rec_no_tradeoffs = DecisionRecord.model_construct(
        artifact_id="DEC-002",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        chosen_alternative="PROP-ARCH-001",
        recommendation="Use Arch",
        rationale="Best available architectural rationale.",
        confidence=Confidence.HIGH,
        trade_offs=[],
        review_triggers=[ReviewTrigger(condition="Requests exceed 10k req/sec")],
        rejected_alternatives=[RejectedAlternative(name="Pragmatic", rejection_reason="Too simple for long term")],
    )
    env = EventEnvelope(session_id=session_id, event_type=EventType.DECISION_RECORDED, actor=CommitteeRole.DECISOR, payload=bad_rec_no_tradeoffs)
    res = gate_decision_exit(session, env)
    assert not res.passed
    assert "must specify at least one trade-off contract" in (res.reason or "")

    # Valid RECOMMENDED
    valid_rec = DecisionRecord(
        artifact_id="DEC-003",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        chosen_alternative="PROP-ARCH-001",
        recommendation="Use Arch",
        rationale="Best available architectural rationale.",
        confidence=Confidence.HIGH,
        trade_offs=[TradeOffContract(gain="Scalability", sacrifice="Simplicity")],
        review_triggers=[ReviewTrigger(condition="Requests exceed 10k req/sec")],
        rejected_alternatives=[RejectedAlternative(name="Pragmatic", rejection_reason="Too simple for long term")],
    )
    env_valid_rec = EventEnvelope(session_id=session_id, event_type=EventType.DECISION_RECORDED, actor=CommitteeRole.DECISOR, payload=valid_rec)
    assert gate_decision_exit(session, env_valid_rec).passed

    # INSUFFICIENT_EVIDENCE with chosen_alternative set must fail
    bad_insufficient = DecisionRecord.model_construct(
        artifact_id="DEC-004",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        chosen_alternative="PROP-ARCH-001",
        rationale="Not enough data",
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Load test results"],
    )
    env_bad_insuf = EventEnvelope(session_id=session_id, event_type=EventType.DECISION_FAILED, actor=CommitteeRole.DECISOR, payload=bad_insufficient)
    res_bad_insuf = gate_decision_exit(session, env_bad_insuf)
    assert not res_bad_insuf.passed
    assert "must not choose any alternative" in (res_bad_insuf.reason or "")

    # Valid INSUFFICIENT_EVIDENCE
    valid_insufficient = DecisionRecord(
        artifact_id="DEC-005",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        chosen_alternative=None,
        rationale="Not enough data",
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Load test results"],
    )
    env_valid_insuf = EventEnvelope(session_id=session_id, event_type=EventType.DECISION_FAILED, actor=CommitteeRole.DECISOR, payload=valid_insufficient)
    assert gate_decision_exit(session, env_valid_insuf).passed


def test_gate_critical_error_validation(session, session_id) -> None:
    """Test Gate CriticalError validates payload type."""
    bad_env = EventEnvelope.model_construct(
        session_id=session_id,
        event_type=EventType.CRITICAL_ERROR,
        actor=CommitteeRole.FACILITATOR,
        payload="Invalid non-CriticalErrorPayload string",
    )
    res_bad = gate_critical_error(session, bad_env)
    assert not res_bad.passed
    assert "must be a CriticalErrorPayload" in (res_bad.reason or "")

    good_env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CRITICAL_ERROR,
        actor=CommitteeRole.FACILITATOR,
        payload=CriticalErrorPayload(
            error_message="Fatal unrecoverable error",
            details={"phase": "PHASE_1_DIVERGENCE"},
        ),
    )
    res_good = gate_critical_error(session, good_env)
    assert res_good.passed
