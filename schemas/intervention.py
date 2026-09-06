"""Human intervention commands allowing asynchronous human-in-the-loop control."""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal, Self, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.common import CommitteeRole, SessionId, ensure_timezone_aware


class InterventionType(str, Enum):
    """Catalog of valid human intervention commands."""

    USER_RESPOND = "USER_RESPOND"
    USER_CONTEST_ASSUMPTION = "USER_CONTEST_ASSUMPTION"
    USER_REQUEST_REVISION = "USER_REQUEST_REVISION"
    USER_ABORT = "USER_ABORT"


class AssumptionContestAction(str, Enum):
    """Action requested when contesting an assumption."""

    REJECT = "REJECT"
    MODIFY = "MODIFY"


class BaseHumanIntervention(BaseModel):
    """Base class for auditable human interventions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_id: UUID = Field(default_factory=uuid4)
    session_id: SessionId
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_role: Literal[CommitteeRole.HUMAN_USER] = CommitteeRole.HUMAN_USER
    intervention_type: InterventionType

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        return ensure_timezone_aware(v)


class UserRespondCommand(BaseHumanIntervention):
    """Human answers an open question during Phase 0."""

    intervention_type: Literal[InterventionType.USER_RESPOND] = InterventionType.USER_RESPOND
    question_id: Annotated[str, Field(min_length=1)]
    answer: Annotated[str, Field(min_length=1)]


class UserContestAssumptionCommand(BaseHumanIntervention):
    """Human contests or modifies a working assumption."""

    intervention_type: Literal[InterventionType.USER_CONTEST_ASSUMPTION] = (
        InterventionType.USER_CONTEST_ASSUMPTION
    )
    assumption_id: Annotated[str, Field(min_length=1)]
    action: AssumptionContestAction
    justification: Annotated[str, Field(min_length=5)]
    new_description: str | None = None

    @model_validator(mode="after")
    def validate_modify_action(self) -> Self:
        if self.action == AssumptionContestAction.MODIFY:
            if not self.new_description or not self.new_description.strip():
                raise ValueError("When action is 'MODIFY', 'new_description' must be provided.")
        return self


class UserRequestRevisionCommand(BaseHumanIntervention):
    """Human rejects a recommendation and requests a fresh deliberation with new constraints."""

    intervention_type: Literal[InterventionType.USER_REQUEST_REVISION] = (
        InterventionType.USER_REQUEST_REVISION
    )
    target_decision_id: Annotated[str, Field(min_length=1)]
    reason_for_rejection: Annotated[str, Field(min_length=5)]
    additional_constraints: Annotated[list[str], Field(min_length=1)]


class UserAbortCommand(BaseHumanIntervention):
    """Human aborts the deliberation immediately."""

    intervention_type: Literal[InterventionType.USER_ABORT] = InterventionType.USER_ABORT
    reason: Annotated[str, Field(min_length=3)]


HumanInterventionCommand = Annotated[
    Union[
        UserRespondCommand,
        UserContestAssumptionCommand,
        UserRequestRevisionCommand,
        UserAbortCommand,
    ],
    Field(discriminator="intervention_type"),
]
