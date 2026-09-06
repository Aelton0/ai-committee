"""Unit tests for AuditReport and AuditFinding models."""

from pydantic import ValidationError
import pytest

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, Severity


def test_valid_audit_report() -> None:
    """Test creating a comprehensive AuditReport covering required critique categories."""
    finding1 = AuditFinding(
        id="AF-001",
        target_proposal_id="PROP-ARCH-001",
        category=AuditCategory.OVERENGINEERING,
        severity=Severity.HIGH,
        title="Kafka overkill for 500 req/s",
        description="Deploying multi-broker Kafka introduces substantial operational burden.",
        justification="Postgres listen/notify or Redis Streams achieves equivalent throughput with 10x lower overhead.",
        impact="Increases AWS monthly bill by $120.",
    )
    finding2 = AuditFinding(
        id="AF-002",
        target_proposal_id="PROP-PRAG-001",
        category=AuditCategory.SINGLE_POINTS_OF_FAILURE,
        severity=Severity.CRITICAL,
        title="Single Postgres instance SPOF",
        description="Monolith proposal relies on single Postgres instance without read replicas or failover.",
        justification="Disk failure or network partition causes total system outage.",
        impact="Downtime exceeding SLA limits.",
    )

    report = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[finding1],
        findings_proposal_b=[finding2],
        single_points_of_failure=["Standalone database in Proposal B"],
        hidden_costs=["Kafka ZooKeeper / KRaft maintenance overhead in Proposal A"],
        fragile_assumptions=["Assumes Celery worker does not leak memory under burst load"],
        overengineering_risks=["Avro schema registry for small team in Proposal A"],
        underengineering_risks=["No circuit breaker for synchronous HTTP calls in Proposal B"],
        questions_for_proponents=["How does Proposal B handle DB restarts without dropping tasks?"],
    )

    assert report.auditor_role == CommitteeRole.AUDITOR_SRE
    assert len(report.all_findings()) == 2
    assert len(report.findings_by_category(AuditCategory.OVERENGINEERING)) == 1
    assert len(report.findings_by_category(AuditCategory.SECURITY)) == 0
    assert len(report.critical_findings()) == 2  # HIGH and CRITICAL


def test_finding_requires_severity_and_justification() -> None:
    """Test that each critique must have a valid severity and justification."""
    with pytest.raises(ValidationError):
        # Missing justification
        AuditFinding(
            id="AF-003",
            target_proposal_id="PROP-PRAG-001",
            category=AuditCategory.SECURITY,
            severity=Severity.HIGH,
            title="Missing Auth",
            description="Endpoints are unauthenticated",
            justification="",  # Empty justification rejected
        )


def test_audit_report_role_enforcement() -> None:
    """Test that AuditReport enforces AUDITOR_SRE role."""
    with pytest.raises(ValidationError):
        AuditReport(
            artifact_id="AUD-002",
            version=1,
            auditor_role=CommitteeRole.ARCHITECT,  # type: ignore[arg-type]
            target_proposal_a_id="PROP-ARCH-001",
            target_proposal_b_id="PROP-PRAG-001",
        )
