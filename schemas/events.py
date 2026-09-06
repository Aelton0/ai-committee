"""Canonical event envelope and typed payload models for the deliberation engine."""

from datetime import datetime, timezone
from typing import Annotated, Any, Self, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.audit import AuditReport
from schemas.common import (
    BaseArtifact,
    CommitteeRole,
    CorrelationId,
    DecisionStatus,
    EventId,
    EventType,
    Hash,
    SessionId,
    ensure_timezone_aware,
)
from schemas.context import OpenQuestion, ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.intervention import HumanInterventionCommand, UserRespondCommand
from schemas.learning import LearningReport
from schemas.proposals import ArchitectProposal, PragmaticProposal
from schemas.synthesis import DeliberationSynthesis


# --- Specific Non-Artifact Payloads ---
class SessionCreatedPayload(BaseModel):
    """Payload for SESSION_CREATED event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_statement: Annotated[str, Field(min_length=5)]
    initial_context: str | None = None
    user_id: str | None = None


class QuestionRaisedPayload(BaseModel):
    """Payload for QUESTION_RAISED event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: OpenQuestion


class UserRespondedPayload(BaseModel):
    """Payload for USER_RESPONDED event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: Annotated[str, Field(min_length=1)]
    answer: Annotated[str, Field(min_length=1)]


class PhaseRollbackPayload(BaseModel):
    """Payload for PHASE_ROLLBACK event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_phase: Annotated[str, Field(min_length=1)]
    to_phase: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=5)]
    superseded_artifacts: list[str] = Field(default_factory=list)


class UserOverridePayload(BaseModel):
    """Payload for USER_OVERRIDE event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention: HumanInterventionCommand


class SessionCancelledPayload(BaseModel):
    """Payload for SESSION_CANCELLED event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: Annotated[str, Field(min_length=3)]
    cancelled_by: CommitteeRole = CommitteeRole.HUMAN_USER


class CriticalErrorPayload(BaseModel):
    """Payload for CRITICAL_ERROR event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error_message: Annotated[str, Field(min_length=1)]
    error_code: str | None = None
    details: dict[str, str] = Field(default_factory=dict)


# Payload union type
EventPayload = Union[
    SessionCreatedPayload,
    QuestionRaisedPayload,
    UserRespondedPayload,
    ProblemContext,
    ArchitectProposal,
    PragmaticProposal,
    AuditReport,
    PhaseRollbackPayload,
    ArchitectDefense,
    PragmaticDefense,
    DeliberationSynthesis,
    DecisionRecord,
    LearningReport,
    UserOverridePayload,
    SessionCancelledPayload,
    CriticalErrorPayload,
]


EVENT_TYPE_PAYLOAD_MAP: dict[EventType, tuple[type[BaseModel], ...]] = {
    EventType.SESSION_CREATED: (SessionCreatedPayload,),
    EventType.QUESTION_RAISED: (QuestionRaisedPayload, OpenQuestion),
    EventType.USER_RESPONDED: (UserRespondedPayload, UserRespondCommand),
    EventType.CONTEXT_VALIDATED: (ProblemContext,),
    EventType.PROPOSAL_CREATED: (ArchitectProposal, PragmaticProposal),
    EventType.AUDIT_COMPLETED: (AuditReport,),
    EventType.PHASE_ROLLBACK: (PhaseRollbackPayload,),
    EventType.DEFENSE_SUBMITTED: (ArchitectDefense, PragmaticDefense),
    EventType.SYNTHESIS_CREATED: (DeliberationSynthesis,),
    EventType.DECISION_RECORDED: (DecisionRecord,),
    EventType.DECISION_FAILED: (DecisionRecord,),
    EventType.LEARNING_REPORT_CREATED: (LearningReport,),
    EventType.USER_OVERRIDE: (UserOverridePayload,),
    EventType.SESSION_CANCELLED: (SessionCancelledPayload,),
    EventType.CRITICAL_ERROR: (CriticalErrorPayload,),
}


class EventEnvelope(BaseModel):
    """Canonical message envelope for all events in the AI Committee deliberation engine."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: EventId = Field(default_factory=uuid4)
    event_type: EventType
    session_id: SessionId
    correlation_id: CorrelationId | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: CommitteeRole
    artifact_id: str | None = None
    artifact_version: Annotated[str | None, Field(pattern=r"^v[0-9]+$")] = None
    content_hash: Hash | None = None
    payload: Any

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        return ensure_timezone_aware(v)

    @model_validator(mode="after")
    def validate_payload_compatibility(self) -> Self:
        allowed_types = EVENT_TYPE_PAYLOAD_MAP.get(self.event_type)
        if not allowed_types:
            raise ValueError(f"No payload schema registered for event type {self.event_type}")

        # If payload is a dict, attempt to validate against one of the allowed types
        validated_payload = self.payload
        if isinstance(self.payload, dict):
            matched = False
            last_err: Exception | None = None
            for allowed_cls in allowed_types:
                try:
                    validated_payload = allowed_cls.model_validate(self.payload)
                    matched = True
                    break
                except Exception as e:
                    last_err = e
            if not matched:
                raise ValueError(
                    f"Payload dict incompatible with event {self.event_type}. "
                    f"Expected one of {[t.__name__ for t in allowed_types]}. Error: {last_err}"
                )
            object.__setattr__(self, "payload", validated_payload)
        elif not isinstance(self.payload, allowed_types):
            expected_names = [t.__name__ for t in allowed_types]
            actual_name = type(self.payload).__name__
            raise ValueError(
                f"Payload type '{actual_name}' is incompatible with event '{self.event_type}'. "
                f"Expected one of: {expected_names}"
            )

        # Specialized invariant checks
        if self.event_type == EventType.DECISION_RECORDED:
            if getattr(validated_payload, "status", None) != DecisionStatus.RECOMMENDED:
                raise ValueError(
                    f"Event {self.event_type.value} requires payload status to be "
                    f"'{DecisionStatus.RECOMMENDED.value}', got '{getattr(validated_payload, 'status', None)}'."
                )
        elif self.event_type == EventType.DECISION_FAILED:
            if getattr(validated_payload, "status", None) != DecisionStatus.INSUFFICIENT_EVIDENCE:
                raise ValueError(
                    f"Event {self.event_type.value} requires payload status to be "
                    f"'{DecisionStatus.INSUFFICIENT_EVIDENCE.value}', got '{getattr(validated_payload, 'status', None)}'."
                )

        # If payload is a BaseArtifact, verify consistency with envelope metadata
        if isinstance(validated_payload, BaseArtifact):
            if self.artifact_id is not None and self.artifact_id != validated_payload.artifact_id:
                raise ValueError(
                    f"Envelope artifact_id '{self.artifact_id}' does not match "
                    f"payload artifact_id '{validated_payload.artifact_id}'."
                )
            if (
                self.artifact_version is not None
                and self.artifact_version != validated_payload.formatted_version
            ):
                raise ValueError(
                    f"Envelope artifact_version '{self.artifact_version}' does not match "
                    f"payload version '{validated_payload.formatted_version}'."
                )

        return self
