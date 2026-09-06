"""Unit tests for DecisionRecord model and status invariants."""

from pydantic import ValidationError
import pytest

from schemas.common import CommitteeRole, Confidence, DecisionStatus, Severity
from schemas.decision import (
    AcceptedRisk,
    DecisionRecord,
    RejectedAlternative,
    ReviewTrigger,
    TradeOffContract,
)


def test_valid_decision_recommended() -> None:
    """Test valid DecisionRecord with RECOMMENDED status."""
    record = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        recommendation="Adopt Pragmatic Proposal (Celery worker) with connection pooling mitigations.",
        chosen_alternative="PROPOSAL_B_REFINED",
        rejected_alternatives=[
            RejectedAlternative(
                name="PROPOSAL_A",
                rejection_reason="Redis Streams adds unnecessary infrastructure given the 4-week deadline.",
            )
        ],
        rationale="Delivers the needed throughput within budget and deadline; SPOF risks are mitigated by AWS RDS multi-AZ.",
        trade_offs=[
            TradeOffContract(
                gain="Time to market in 10 days, $30/mo cost",
                sacrifice="Temporal coupling between tasks and database",
            )
        ],
        accepted_risks=[
            AcceptedRisk(
                risk="Worker restart drops in-flight memory state",
                severity=Severity.MEDIUM,
                mitigation="Celery task acknowledgment enabled",
            )
        ],
        technical_debt=["Eventual migration to dedicated queue if scale exceeds 1,000 req/s"],
        operational_debt=["Manual monitoring of Postgres connection pool utilization"],
        critical_assumptions=["Peak traffic remains under 500 req/s"],
        review_triggers=[
            ReviewTrigger(
                condition="Traffic sustained above 800 req/s for 3 consecutive days",
                metric_threshold="800 req/s",
                trigger_type="METRIC",
            )
        ],
        confidence=Confidence.HIGH,
        information_that_could_change_decision=["Third-party gateway announcing sub-10ms webhooks"],
    )

    assert record.decisor_role == CommitteeRole.DECISOR
    assert record.status == DecisionStatus.RECOMMENDED
    assert record.chosen_alternative == "PROPOSAL_B_REFINED"
    assert len(record.trade_offs) == 1
    assert len(record.review_triggers) == 1


def test_valid_decision_insufficient_evidence() -> None:
    """Test valid DecisionRecord when evidence is insufficient."""
    record = DecisionRecord(
        artifact_id="DEC-002",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        recommendation=None,
        chosen_alternative=None,
        rationale="Cannot recommend architecture because latency and reliability of third-party core banking API are completely unknown.",
        confidence=Confidence.LOW,
        information_that_could_change_decision=[
            "Load test results of third-party sandbox API",
            "Contractual SLA commitments from partner bank",
        ],
    )

    assert record.status == DecisionStatus.INSUFFICIENT_EVIDENCE
    assert record.chosen_alternative is None
    assert len(record.information_that_could_change_decision) == 2


def test_recommended_requires_chosen_alternative_and_tradeoffs() -> None:
    """Test that RECOMMENDED status enforces presence of alternative, trade-offs, and triggers."""
    with pytest.raises(ValidationError, match="chosen_alternative"):
        DecisionRecord(
            artifact_id="DEC-003",
            version=1,
            status=DecisionStatus.RECOMMENDED,
            chosen_alternative=None,  # Forbidden
            recommendation="Some recommendation",
            rationale="A sufficiently long rationale string.",
            confidence=Confidence.HIGH,
            trade_offs=[TradeOffContract(gain="gain speed", sacrifice="sacrifice coupling")],
            review_triggers=[ReviewTrigger(condition="condition 1")],
        )

    with pytest.raises(ValidationError, match="trade-off must be documented"):
        DecisionRecord(
            artifact_id="DEC-004",
            version=1,
            status=DecisionStatus.RECOMMENDED,
            chosen_alternative="ALT_A",
            recommendation="Some recommendation",
            rationale="A sufficiently long rationale string.",
            confidence=Confidence.HIGH,
            trade_offs=[],  # Forbidden: must have at least one trade-off (Principle 10)
            review_triggers=[ReviewTrigger(condition="condition 1")],
        )

    with pytest.raises(ValidationError, match="review trigger must be documented"):
        DecisionRecord(
            artifact_id="DEC-005",
            version=1,
            status=DecisionStatus.RECOMMENDED,
            chosen_alternative="ALT_A",
            recommendation="Some recommendation",
            rationale="A sufficiently long rationale string.",
            confidence=Confidence.HIGH,
            trade_offs=[TradeOffContract(gain="gain speed", sacrifice="sacrifice coupling")],
            review_triggers=[],  # Forbidden: must have review trigger (Principle 11)
        )


def test_insufficient_evidence_forbids_chosen_alternative() -> None:
    """Test that INSUFFICIENT_EVIDENCE forbids declaring a winning alternative."""
    with pytest.raises(ValidationError, match="must be None"):
        DecisionRecord(
            artifact_id="DEC-006",
            version=1,
            status=DecisionStatus.INSUFFICIENT_EVIDENCE,
            chosen_alternative="PROPOSAL_A",  # Forbidden: cannot have winner when evidence is insufficient
            rationale="A sufficiently long rationale string.",
            confidence=Confidence.LOW,
            information_that_could_change_decision=["Missing data points"],
        )


def test_insufficient_evidence_requires_missing_info() -> None:
    """Test that INSUFFICIENT_EVIDENCE requires declaring what information is missing."""
    with pytest.raises(ValidationError, match="must list the missing critical data"):
        DecisionRecord(
            artifact_id="DEC-007",
            version=1,
            status=DecisionStatus.INSUFFICIENT_EVIDENCE,
            chosen_alternative=None,
            rationale="A sufficiently long rationale string.",
            confidence=Confidence.LOW,
            information_that_could_change_decision=[],  # Forbidden
        )
