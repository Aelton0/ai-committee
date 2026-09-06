"""Unit tests for ArchitectDefense and PragmaticDefense models."""

from pydantic import ValidationError
import pytest

from schemas.common import CommitteeRole
from schemas.defense import (
    ArchitectDefense,
    CritiqueResponse,
    DefenseStance,
    PragmaticDefense,
    ProposalAction,
)


def test_valid_defense_with_modification() -> None:
    """Test defense that concedes critique and produces a revised version v2."""
    defense = ArchitectDefense(
        artifact_id="DEF-ARCH-001",
        version=1,
        original_proposal_id="PROP-ARCH-001",
        original_proposal_version=1,
        critique_responses=[
            CritiqueResponse(
                finding_id="AF-001",
                stance=DefenseStance.CONCEDED_WITH_REFINEMENT,
                response="Concede that Kafka is excessive for current scale.",
                rationale="Redis Streams satisfies throughput with much lower operational footprint.",
                proposed_modification="Replace Kafka brokers with managed Redis Streams cluster.",
            )
        ],
        proposal_action=ProposalAction.MODIFY,
        revised_proposal_id="PROP-ARCH-001",
        revised_proposal_version=2,
        persistent_disagreements=["Still reject synchronous RPC between billing and inventory."],
    )
    assert defense.proponent_role == CommitteeRole.ARCHITECT
    assert defense.proposal_action == ProposalAction.MODIFY
    assert defense.revised_proposal_version == 2


def test_valid_defense_maintaining_proposal() -> None:
    """Test defense that defends original proposal without creating a new version."""
    defense = PragmaticDefense(
        artifact_id="DEF-PRAG-001",
        version=1,
        original_proposal_id="PROP-PRAG-001",
        original_proposal_version=1,
        critique_responses=[
            CritiqueResponse(
                finding_id="AF-002",
                stance=DefenseStance.ACKNOWLEDGED_ACCEPTING_RISK,
                response="Acknowledge SPOF risk, but accepted as acceptable trade-off for MVP.",
                rationale="Automated daily backups and AWS RDS automated multi-AZ failover adequately mitigate total loss.",
            )
        ],
        proposal_action=ProposalAction.MAINTAIN,
    )
    assert defense.proponent_role == CommitteeRole.PRAGMATIST
    assert defense.proposal_action == ProposalAction.MAINTAIN
    assert defense.revised_proposal_version is None


def test_defense_modification_invariant_violation() -> None:
    """Test that MODIFY without revised version raises validation error."""
    with pytest.raises(ValidationError, match="revised_proposal_version"):
        ArchitectDefense(
            artifact_id="DEF-ARCH-002",
            version=1,
            original_proposal_id="PROP-ARCH-001",
            original_proposal_version=1,
            critique_responses=[
                CritiqueResponse(
                    finding_id="AF-001",
                    stance=DefenseStance.CONCEDED_WITH_REFINEMENT,
                    response="Concede critique.",
                    rationale="Valid points.",
                )
            ],
            proposal_action=ProposalAction.MODIFY,
            # Missing revised_proposal_version
        )


def test_defense_maintain_with_revised_version_fails() -> None:
    """Test that MAINTAIN with revised version raises validation error."""
    with pytest.raises(ValidationError, match="must not be set"):
        PragmaticDefense(
            artifact_id="DEF-PRAG-002",
            version=1,
            original_proposal_id="PROP-PRAG-001",
            original_proposal_version=1,
            critique_responses=[
                CritiqueResponse(
                    finding_id="AF-002",
                    stance=DefenseStance.CONTESTED,
                    response="Contesting finding.",
                    rationale="Evidence contradicts critique.",
                )
            ],
            proposal_action=ProposalAction.MAINTAIN,
            revised_proposal_version=2,  # Cannot specify revised version when MAINTAIN
        )
