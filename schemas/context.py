"""Context schemas separating facts, constraints, assumptions, unknowns, and contextual dimensions."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.common import BaseArtifact, CommitteeRole, Severity, ensure_timezone_aware


class ConstraintType(str, Enum):
    """Categorization of hard and soft constraints."""

    BUDGET = "BUDGET"
    DEADLINE = "DEADLINE"
    STACK = "STACK"
    REGULATORY = "REGULATORY"
    TEAM = "TEAM"
    OPERATIONAL = "OPERATIONAL"
    OTHER = "OTHER"


class Fact(BaseModel):
    """Objective, verified piece of information provided or validated by the user."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    source: Annotated[str, Field(min_length=1, description="Source of the verified fact")]
    verified_at: datetime | None = None

    @field_validator("verified_at")
    @classmethod
    def validate_verified_at(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return ensure_timezone_aware(v)
        return v


class Constraint(BaseModel):
    """Hard boundary or limitation that cannot be violated without formal approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    type: ConstraintType = ConstraintType.OTHER
    negotiable: bool = False


class Assumption(BaseModel):
    """Working hypothesis adopted provisionally to proceed with the analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    rationale: Annotated[str, Field(min_length=1)]
    risk_level: Severity = Severity.MEDIUM


class Unknown(BaseModel):
    """Critical information needed that is currently absent or unknowable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    impact_if_adverse: Severity = Severity.HIGH
    potential_resolution: str | None = None


class OpenQuestion(BaseModel):
    """Question directed to the user or an external source to clarify a missing requirement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1)]
    question: Annotated[str, Field(min_length=1)]
    target_role: CommitteeRole = CommitteeRole.HUMAN_USER
    why_critical: Annotated[str, Field(min_length=1)]
    answer: str | None = None
    answered_at: datetime | None = None

    @field_validator("answered_at")
    @classmethod
    def validate_answered_at(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return ensure_timezone_aware(v)
        return v


class TeamContext(BaseModel):
    """Information regarding the team composition and capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    team_size: Annotated[int, Field(ge=0)]
    skill_level: str | None = None
    constraints: list[str] = Field(default_factory=list)


class BudgetContext(BaseModel):
    """Budgetary bounds and infrastructure spending limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_monthly_budget: Annotated[float | None, Field(default=None, ge=0.0)]
    currency: str = "USD"
    description: str | None = None


class TimeContext(BaseModel):
    """Schedule and deadline parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deadline: datetime | None = None
    expected_duration: str | None = None
    milestone_notes: list[str] = Field(default_factory=list)

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return ensure_timezone_aware(v)
        return v


class OperationalContext(BaseModel):
    """Operational parameters, current infrastructure, and SLAs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    current_infrastructure: list[str] = Field(default_factory=list)
    sla_requirements: str | None = None
    peak_traffic: str | None = None


class ProblemContext(BaseArtifact):
    """Formal framing of the problem produced by the Facilitador in Phase 0.

    Strictly separates facts from premises and unknowns.
    """

    problem: Annotated[str, Field(min_length=5, description="High-level description of the problem")]
    facts: list[Fact] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    unknowns: list[Unknown] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    success_criteria: Annotated[list[str], Field(min_length=1)]
    team_context: TeamContext | None = None
    budget_context: BudgetContext | None = None
    time_context: TimeContext | None = None
    operational_context: OperationalContext | None = None

    def has_unanswered_questions(self) -> bool:
        """Check whether there are open questions awaiting answers."""
        return any(q.answer is None for q in self.open_questions)

    def unanswered_questions(self) -> list[OpenQuestion]:
        """Return the list of open questions that have not yet been answered."""
        return [q for q in self.open_questions if q.answer is None]

    def fact_ids(self) -> set[str]:
        """Return all declared Fact identifiers."""
        return {f.id for f in self.facts}

    def assumption_ids(self) -> set[str]:
        """Return all declared Assumption identifiers."""
        return {a.id for a in self.assumptions}

    def unknown_ids(self) -> set[str]:
        """Return all declared Unknown identifiers."""
        return {u.id for u in self.unknowns}

    def constraint_ids(self) -> set[str]:
        """Return all declared Constraint identifiers."""
        return {c.id for c in self.constraints}

    def get_fact(self, fact_id: str) -> Fact | None:
        """Look up a Fact by identifier."""
        return next((f for f in self.facts if f.id == fact_id), None)

    def get_assumption(self, assumption_id: str) -> Assumption | None:
        """Look up an Assumption by identifier."""
        return next((a for a in self.assumptions if a.id == assumption_id), None)

    def get_unknown(self, unknown_id: str) -> Unknown | None:
        """Look up an Unknown by identifier."""
        return next((u for u in self.unknowns if u.id == unknown_id), None)
