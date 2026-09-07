"""Common types, enums, and base models for the AI Committee system."""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

# --- Shared Identifiers and Type Aliases ---
SessionId = UUID
EventId = UUID
CorrelationId = UUID
ArtifactId = Annotated[str, Field(min_length=1, max_length=128)]
Version = PositiveInt
Timestamp = Annotated[datetime, Field(description="Timezone-aware datetime")]
Hash = Annotated[
    str,
    Field(
        pattern=r"^(sha256:)?[a-f0-9]{64}$",
        description="SHA-256 hash string optionally prefixed with sha256:",
    ),
]


def ensure_timezone_aware(dt: datetime) -> datetime:
    """Validate that a datetime instance is timezone-aware."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("Datetime must be timezone-aware (tzinfo is required).")
    return dt


# --- Core Enumerations ---
class CommitteeRole(str, Enum):
    """Roles participating in the AI Committee deliberation."""

    FACILITATOR = "FACILITATOR"
    ARCHITECT = "ARCHITECT"
    PRAGMATIST = "PRAGMATIST"
    AUDITOR_SRE = "AUDITOR_SRE"
    DECISOR = "DECISOR"
    MENTOR = "MENTOR"
    HUMAN_USER = "HUMAN_USER"
    SYSTEM = "SYSTEM"


class CommitteeState(str, Enum):
    """Lifecycle states of a deliberation session."""

    DRAFT = "DRAFT"
    INVESTIGATION = "INVESTIGATION"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    DIVERGENCE = "DIVERGENCE"
    CONFRONTATION = "CONFRONTATION"
    DEFENSE = "DEFENSE"
    CONVERGENCE = "CONVERGENCE"
    DECISION = "DECISION"
    REFLECTION = "REFLECTION"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CANCELLED = "CANCELLED"


class DecisionStatus(str, Enum):
    """Status outcomes for a DecisionRecord."""

    RECOMMENDED = "RECOMMENDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ACCEPTED_BY_USER = "ACCEPTED_BY_USER"
    REJECTED_BY_USER = "REJECTED_BY_USER"
    OBSOLETE = "OBSOLETE"


class Severity(str, Enum):
    """Severity classification for risks, vulnerabilities, and assumptions."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Confidence(str, Enum):
    """Confidence levels for assessments and recommendations."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EventType(str, Enum):
    """Catalog of formal events emitted within the deliberation engine."""

    SESSION_CREATED = "SESSION_CREATED"
    QUESTION_RAISED = "QUESTION_RAISED"
    USER_RESPONDED = "USER_RESPONDED"
    CONTEXT_VALIDATED = "CONTEXT_VALIDATED"
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    AUDIT_COMPLETED = "AUDIT_COMPLETED"
    PHASE_ROLLBACK = "PHASE_ROLLBACK"
    DEFENSE_SUBMITTED = "DEFENSE_SUBMITTED"
    SYNTHESIS_CREATED = "SYNTHESIS_CREATED"
    DECISION_RECORDED = "DECISION_RECORDED"
    DECISION_FAILED = "DECISION_FAILED"
    LEARNING_REPORT_CREATED = "LEARNING_REPORT_CREATED"
    USER_OVERRIDE = "USER_OVERRIDE"
    SESSION_CANCELLED = "SESSION_CANCELLED"
    CRITICAL_ERROR = "CRITICAL_ERROR"


# --- Base Immutable Artifact Model ---
class BaseArtifact(BaseModel):
    """Base class for all first-class artifacts produced by the committee.

    Enforces immutability (frozen), explicit versioning, and lineage tracking.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: ArtifactId
    version: PositiveInt = 1
    supersedes: str | None = None
    content_hash: Hash | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return ensure_timezone_aware(v)

    @field_validator("supersedes")
    @classmethod
    def validate_supersedes_format(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("supersedes cannot be an empty string.")
        return v

    @model_validator(mode="after")
    def validate_version_lineage(self) -> Self:
        if self.version > 1 and self.supersedes is None:
            raise ValueError(
                f"Artifact version {self.version} must specify 'supersedes' referencing the previous version."
            )
        if self.version == 1 and self.supersedes is not None:
            raise ValueError("Initial version (1) cannot specify 'supersedes'.")
        return self

    @property
    def formatted_version(self) -> str:
        """Return version formatted as 'vN'."""
        return f"v{self.version}"
