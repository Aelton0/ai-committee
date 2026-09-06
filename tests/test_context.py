"""Unit tests for ProblemContext and context submodels."""

from datetime import datetime, timezone

from pydantic import ValidationError
import pytest

from schemas.common import CommitteeRole, Severity
from schemas.context import (
    Assumption,
    BudgetContext,
    Constraint,
    ConstraintType,
    Fact,
    OpenQuestion,
    OperationalContext,
    ProblemContext,
    TeamContext,
    TimeContext,
    Unknown,
)


def test_valid_problem_context() -> None:
    """Test valid construction of ProblemContext with all dimensions."""
    now = datetime.now(timezone.utc)
    ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        created_at=now,
        problem="Migrate monolith payment service to scalable event-driven architecture.",
        facts=[
            Fact(id="F1", description="PostgreSQL 15 single node", source="Telemetry", verified_at=now)
        ],
        constraints=[
            Constraint(id="C1", description="Budget under $200/mo", type=ConstraintType.BUDGET, negotiable=False)
        ],
        assumptions=[
            Assumption(id="A1", description="Peak traffic stays under 500 req/s", rationale="Historical data", risk_level=Severity.MEDIUM)
        ],
        unknowns=[
            Unknown(id="U1", description="Third-party gateway latency", impact_if_adverse=Severity.HIGH)
        ],
        open_questions=[
            OpenQuestion(id="Q1", question="What is the SLA requirement?", why_critical="Influences redundancy choices", answer="p99 < 150ms")
        ],
        success_criteria=["Latency p99 < 150ms", "Zero data loss during failover"],
        team_context=TeamContext(team_size=4, skill_level="Senior Python/Go"),
        budget_context=BudgetContext(max_monthly_budget=200.0, currency="USD"),
        time_context=TimeContext(expected_duration="4 weeks"),
        operational_context=OperationalContext(current_infrastructure=["AWS ECS", "RDS Postgres"]),
    )

    assert ctx.artifact_id == "CTX-001"
    assert ctx.version == 1
    assert ctx.formatted_version == "v1"
    assert not ctx.has_unanswered_questions()
    assert len(ctx.unanswered_questions()) == 0


def test_problem_context_unanswered_questions() -> None:
    """Test question status tracking."""
    ctx = ProblemContext(
        artifact_id="CTX-002",
        version=1,
        problem="Need caching layer evaluation.",
        success_criteria=["p95 < 50ms"],
        open_questions=[
            OpenQuestion(id="Q1", question="Expected cache hit ratio?", why_critical="Sizing requirement")
        ],
    )
    assert ctx.has_unanswered_questions()
    assert len(ctx.unanswered_questions()) == 1
    assert ctx.unanswered_questions()[0].id == "Q1"


def test_problem_context_missing_required_fields() -> None:
    """Test validation fails when mandatory fields are missing."""
    with pytest.raises(ValidationError):
        # Missing 'problem' and 'success_criteria'
        ProblemContext(artifact_id="CTX-003", version=1)  # type: ignore[call-arg]


def test_problem_context_rejects_extra_fields() -> None:
    """Test that unknown fields are strictly rejected."""
    with pytest.raises(ValidationError):
        ProblemContext(
            artifact_id="CTX-004",
            version=1,
            problem="Valid problem description.",
            success_criteria=["p99 < 100ms"],
            unexpected_field="should fail",  # type: ignore[call-arg]
        )


def test_problem_context_immutable() -> None:
    """Test that ProblemContext is frozen against in-place mutation."""
    ctx = ProblemContext(
        artifact_id="CTX-005",
        version=1,
        problem="Original problem description.",
        success_criteria=["Criteria 1"],
    )
    with pytest.raises(ValidationError):
        ctx.problem = "Mutated problem"  # type: ignore[misc]


def test_problem_context_version_lineage() -> None:
    """Test version 2 requires supersedes, while version 1 forbids it."""
    # Version 2 without supersedes must fail
    with pytest.raises(ValidationError, match="must specify 'supersedes'"):
        ProblemContext(
            artifact_id="CTX-006",
            version=2,
            problem="Valid problem description.",
            success_criteria=["Criteria 1"],
        )

    # Version 1 with supersedes must fail
    with pytest.raises(ValidationError, match="Initial version .* cannot specify 'supersedes'"):
        ProblemContext(
            artifact_id="CTX-006",
            version=1,
            supersedes="CTX-005:v1",
            problem="Valid problem description.",
            success_criteria=["Criteria 1"],
        )

    # Version 2 with valid supersedes succeeds
    v2 = ProblemContext(
        artifact_id="CTX-006",
        version=2,
        supersedes="CTX-006:v1",
        problem="Updated problem description.",
        success_criteria=["Criteria 1"],
    )
    assert v2.version == 2
    assert v2.supersedes == "CTX-006:v1"


def test_timezone_awareness_enforced() -> None:
    """Test naive datetimes are rejected."""
    naive_now = datetime.now()  # no tzinfo
    with pytest.raises(ValidationError, match="timezone-aware"):
        ProblemContext(
            artifact_id="CTX-007",
            version=1,
            created_at=naive_now,
            problem="Valid problem description.",
            success_criteria=["Criteria 1"],
        )
