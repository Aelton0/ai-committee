"""Unit tests for ArchitectProposal and PragmaticProposal models."""

from pydantic import ValidationError
import pytest

from schemas.common import CommitteeRole, Severity
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)


def test_valid_architect_proposal() -> None:
    """Test creating a valid ArchitectProposal with comparable fields."""
    prop = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Event-Driven Microservices Architecture",
        solution="Decouple payment and order domains using Apache Kafka event bus.",
        rationale="Maximizes modularity and allows independent horizontal scaling.",
        benefits=["High decoupling", "Fault isolation across services"],
        costs=CostEstimate(
            implementation_effort=EffortLevel.HIGH,
            infrastructure_cost_estimate="$150/mo",
            additional_costs=["Operational training"],
        ),
        risks=["Event schema drift", "Distributed tracing overhead"],
        complexity=Severity.HIGH,
        reversibility=ReversibilityAssessment(
            score=ReversibilityLevel.LOW,
            rationale="Contracts deeply embedded in consumers make rollback expensive.",
        ),
        future_implications="Enables rapid integration of third-party payment providers.",
        assumptions=["Team has capacity to learn Kafka basics."],
        invalidation_conditions=["Traffic drops below 1 event/min permanently."],
        modularity_strategy="Strict schema registry with Avro contracts.",
        evolution_path="Phase 1: Outbox pattern; Phase 2: Direct streaming.",
    )
    assert prop.proponent_role == CommitteeRole.ARCHITECT
    assert prop.artifact_id == "PROP-ARCH-001"
    assert prop.version == 1


def test_valid_pragmatic_proposal() -> None:
    """Test creating a valid PragmaticProposal with comparable fields."""
    prop = PragmaticProposal(
        artifact_id="PROP-PRAG-001",
        version=1,
        title="Modular Monolith with Background Workers",
        solution="Single deployable Python service with Postgres queue worker via Celery.",
        rationale="Delivers business value in 10 days with minimal operational complexity.",
        benefits=["Low infrastructure footprint", "Single codebase deployment"],
        costs=CostEstimate(
            implementation_effort=EffortLevel.LOW,
            infrastructure_cost_estimate="$30/mo",
        ),
        risks=["Shared database saturation", "Worker memory leaks"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(
            score=ReversibilityLevel.HIGH,
            rationale="Can easily swap Celery queue for external broker if traffic spikes.",
        ),
        future_implications="May require database connection pooling tuning at 1,000 req/s.",
        assumptions=["Postgres instance can handle queue poll I/O."],
        invalidation_conditions=["Peak transactions exceed 2,000 req/s."],
        time_to_value="2 weeks",
        simplifications_made=["No distributed transactions", "Synchronous HTTP for non-critical flows"],
    )
    assert prop.proponent_role == CommitteeRole.PRAGMATIST
    assert prop.artifact_id == "PROP-PRAG-001"
    assert prop.version == 1


def test_proposal_role_enforcement() -> None:
    """Test that each proposal subclass enforces its specific author role."""
    with pytest.raises(ValidationError):
        # Architect proposal cannot have PRAGMATIST role
        ArchitectProposal(
            artifact_id="PROP-ARCH-002",
            version=1,
            proponent_role=CommitteeRole.PRAGMATIST,  # type: ignore[arg-type]
            title="Invalid Role Proposal",
            solution="A solution string that is long enough.",
            rationale="A rationale string that is long enough.",
            benefits=["Benefit 1"],
            costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$10"),
            risks=["Risk 1"],
            complexity=Severity.LOW,
            reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Easy to revert"),
            future_implications="No future issues",
            assumptions=["Assumption 1"],
            invalidation_conditions=["Condition 1"],
        )


def test_proposal_immutability() -> None:
    """Test proposals cannot be mutated after creation."""
    prop = PragmaticProposal(
        artifact_id="PROP-PRAG-003",
        version=1,
        title="Valid Proposal",
        solution="A solution string that is long enough.",
        rationale="A rationale string that is long enough.",
        benefits=["Benefit 1"],
        costs=CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$10"),
        risks=["Risk 1"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Easy to revert"),
        future_implications="No future issues",
        assumptions=["Assumption 1"],
        invalidation_conditions=["Condition 1"],
    )
    with pytest.raises(ValidationError):
        prop.title = "Mutated Title"  # type: ignore[misc]
