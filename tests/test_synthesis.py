"""Unit tests for DeliberationSynthesis model."""

from pydantic import ValidationError
import pytest

from schemas.common import CommitteeRole
from schemas.synthesis import DeliberationSynthesis, TradeOffDimension


def test_valid_synthesis() -> None:
    """Test valid DeliberationSynthesis mapping consensus, divergence, and trade-offs."""
    synthesis = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consolidated_facts=["Postgres 15 in use", "Team size is 4"],
        consolidated_constraints=["Budget < $200/mo", "Deadline in 4 weeks"],
        consolidated_assumptions=["Peak traffic under 500 req/s"],
        consolidated_unknowns=["Third-party gateway latency under load"],
        consensus_points=[
            "Both agree Kafka is excessive for current needs",
            "Both agree database should remain Postgres",
        ],
        divergence_points=[
            "Synchronous Celery vs Async Redis Streams for background jobs",
        ],
        arguments_by_alternative={
            "PROPOSAL_A": ["Higher decoupling", "Easier future extension"],
            "PROPOSAL_B": ["Lower complexity", "Deployment ready in 10 days"],
        },
        unresolved_risks=["Database connection saturation during marketing campaigns"],
        trade_offs=[
            TradeOffDimension(
                dimension="Time to Delivery",
                option_a="3-4 weeks (Redis Streams setup)",
                option_b="1-2 weeks (Celery on Postgres)",
                notes="Option B is 2x faster to market.",
            )
        ],
        open_questions=["Can marketing guarantee 48-hour notice before promotions?"],
    )

    assert synthesis.facilitator_role == CommitteeRole.FACILITATOR
    assert len(synthesis.consensus_points) == 2
    assert len(synthesis.trade_offs) == 1


def test_synthesis_forbids_recommended_solution() -> None:
    """Test Facilitador cannot decide: synthesis must strictly reject recommendation fields."""
    with pytest.raises(ValidationError):
        DeliberationSynthesis(
            artifact_id="SYN-002",
            version=1,
            consolidated_facts=["Fact 1"],
            recommended_solution="Option B",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        DeliberationSynthesis(
            artifact_id="SYN-003",
            version=1,
            winner="PROPOSAL_A",  # type: ignore[call-arg]
        )
