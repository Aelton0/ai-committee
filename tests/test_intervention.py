"""Unit tests for human intervention commands."""

from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
import pytest

from schemas.common import CommitteeRole
from schemas.intervention import (
    AssumptionContestAction,
    HumanInterventionCommand,
    InterventionType,
    UserAbortCommand,
    UserContestAssumptionCommand,
    UserRequestRevisionCommand,
    UserRespondCommand,
)


def test_valid_user_respond_command() -> None:
    """Test user responding to an open question."""
    session_id = uuid4()
    cmd = UserRespondCommand(
        session_id=session_id,
        question_id="Q1",
        answer="Max budget is $300/mo and SLA p99 must be under 100ms.",
    )
    assert cmd.intervention_type == InterventionType.USER_RESPOND
    assert cmd.actor_role == CommitteeRole.HUMAN_USER
    assert cmd.question_id == "Q1"


def test_valid_user_contest_assumption_modify() -> None:
    """Test user modifying an assumption with new text."""
    session_id = uuid4()
    cmd = UserContestAssumptionCommand(
        session_id=session_id,
        assumption_id="A1",
        action=AssumptionContestAction.MODIFY,
        justification="Traffic is expected to grow by 5x next month due to product launch.",
        new_description="Peak traffic will reach 2,500 req/s rather than 500 req/s.",
    )
    assert cmd.action == AssumptionContestAction.MODIFY
    assert cmd.new_description is not None


def test_contest_assumption_modify_requires_new_description() -> None:
    """Test that action MODIFY requires new_description."""
    session_id = uuid4()
    with pytest.raises(ValidationError, match="new_description"):
        UserContestAssumptionCommand(
            session_id=session_id,
            assumption_id="A1",
            action=AssumptionContestAction.MODIFY,
            justification="Valid justification string.",
            new_description=None,  # Missing
        )


def test_valid_user_request_revision() -> None:
    """Test user requesting a fresh round of deliberation with new constraints."""
    session_id = uuid4()
    cmd = UserRequestRevisionCommand(
        session_id=session_id,
        target_decision_id="DEC-001",
        reason_for_rejection="Cannot accept Celery queue due to audit compliance requirement for zero-loss events.",
        additional_constraints=["Must use durable, multi-AZ message broker with at-least-once guarantee"],
    )
    assert cmd.intervention_type == InterventionType.USER_REQUEST_REVISION
    assert len(cmd.additional_constraints) == 1


def test_valid_user_abort_command() -> None:
    """Test user aborting deliberation."""
    session_id = uuid4()
    cmd = UserAbortCommand(
        session_id=session_id,
        reason="Project requirements cancelled by business stakeholder.",
    )
    assert cmd.intervention_type == InterventionType.USER_ABORT
    assert cmd.actor_role == CommitteeRole.HUMAN_USER


def test_human_intervention_discriminated_union() -> None:
    """Test parsing arbitrary human intervention command via discriminated union."""
    adapter = TypeAdapter(HumanInterventionCommand)
    session_id = str(uuid4())

    data = {
        "session_id": session_id,
        "intervention_type": "USER_ABORT",
        "reason": "Test abort",
    }
    parsed = adapter.validate_python(data)
    assert isinstance(parsed, UserAbortCommand)
    assert parsed.reason == "Test abort"
