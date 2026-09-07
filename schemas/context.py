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
    decision_relevance: Severity = Severity.MEDIUM
    could_change_selected_alternative: bool = False
    blocking: bool = False
    mitigation: str | None = None


class OpenQuestion(BaseModel):
    """Question directed to the user or an external source to clarify a missing requirement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1)]
    question: Annotated[str, Field(min_length=1)]
    target_role: CommitteeRole = CommitteeRole.HUMAN_USER
    why_critical: Annotated[str, Field(min_length=1)]
    answer: str | None = None
    answered_at: datetime | None = None
    dimension: str | None = None
    incorporated: bool = False
    expected_value_of_information: str | None = None

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


class ContextDelta(BaseModel):
    """Incremental update to ProblemContext produced by Facilitator interpretation of user input.

    Separates LLM interpretation from deterministic state mutation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    delta_id: Annotated[str, Field(min_length=1)]
    source_question_ids: list[str] = Field(default_factory=list)
    classification_basis: str | None = None
    resolved_question_ids: list[str] = Field(default_factory=list)
    new_facts: list[Fact] = Field(default_factory=list)
    new_assumptions: list[Assumption] = Field(default_factory=list)
    new_unknowns: list[Unknown] = Field(default_factory=list)
    new_constraints: list[Constraint] = Field(default_factory=list)
    new_open_questions: list[OpenQuestion] = Field(default_factory=list)
    identified_conflicts: list[str] = Field(default_factory=list)


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
    conflicts: list[str] = Field(default_factory=list)
    business_value_chain: list[str] = Field(default_factory=list)
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

    def has_unincorporated_answers(self) -> bool:
        """Check whether there are answered questions not yet incorporated via ContextDelta."""
        return any(q.answer is not None and not q.incorporated for q in self.open_questions)

    def unincorporated_answers(self) -> list[OpenQuestion]:
        """Return questions with answers not yet incorporated via ContextDelta."""
        return [q for q in self.open_questions if q.answer is not None and not q.incorporated]

    def has_blocking_unknowns(self) -> bool:
        """Check whether there are blocking unknowns that impede a confident recommendation."""
        return any(u.blocking or (u.could_change_selected_alternative and u.impact_if_adverse in (Severity.HIGH, Severity.CRITICAL)) for u in self.unknowns)

    def blocking_unknowns(self) -> list[Unknown]:
        """Return critical unknowns that could materially alter architectural choice."""
        return [
            u for u in self.unknowns
            if u.blocking or (u.could_change_selected_alternative and u.impact_if_adverse in (Severity.HIGH, Severity.CRITICAL))
        ]

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


def apply_context_delta(current_ctx: ProblemContext, delta: ContextDelta) -> ProblemContext:
    """Deterministically apply a ContextDelta to produce an updated ProblemContext v(N+1).

    Preserves all existing facts, constraints, and assumptions without destructive replacement.
    """
    # 1. Update facts preserving existing
    existing_fact_ids = {f.id for f in current_ctx.facts}
    merged_facts = list(current_ctx.facts)
    for f in delta.new_facts:
        if f.id not in existing_fact_ids:
            merged_facts.append(f)
            existing_fact_ids.add(f.id)

    # 2. Update constraints preserving existing
    existing_constraint_ids = {c.id for c in current_ctx.constraints}
    merged_constraints = list(current_ctx.constraints)
    for c in delta.new_constraints:
        if c.id not in existing_constraint_ids:
            merged_constraints.append(c)
            existing_constraint_ids.add(c.id)

    # 3. Update assumptions preserving existing
    existing_assumption_ids = {a.id for a in current_ctx.assumptions}
    merged_assumptions = list(current_ctx.assumptions)
    for a in delta.new_assumptions:
        if a.id not in existing_assumption_ids:
            merged_assumptions.append(a)
            existing_assumption_ids.add(a.id)

    # 4. Update unknowns preserving existing
    existing_unknown_ids = {u.id for u in current_ctx.unknowns}
    merged_unknowns = list(current_ctx.unknowns)
    for u in delta.new_unknowns:
        if u.id not in existing_unknown_ids:
            merged_unknowns.append(u)
            existing_unknown_ids.add(u.id)

    # 5. Update open questions: mark resolved/source as incorporated, append new
    resolved_ids = set(delta.resolved_question_ids) | set(delta.source_question_ids)
    updated_questions: list[OpenQuestion] = []
    for q in current_ctx.open_questions:
        if q.id in resolved_ids or q.answer is not None:
            updated_questions.append(q.model_copy(update={"incorporated": True}))
        else:
            updated_questions.append(q)

    # Append new open questions that are not duplicates
    existing_q_ids = {q.id for q in updated_questions}
    for nq in delta.new_open_questions:
        if nq.id not in existing_q_ids:
            updated_questions.append(nq)
            existing_q_ids.add(nq.id)

    # 6. Merge conflicts
    merged_conflicts = list(current_ctx.conflicts)
    for conf in delta.identified_conflicts:
        if conf not in merged_conflicts:
            merged_conflicts.append(conf)

    new_version = current_ctx.version + 1

    return current_ctx.model_copy(
        update={
            "version": new_version,
            "facts": merged_facts,
            "constraints": merged_constraints,
            "assumptions": merged_assumptions,
            "unknowns": merged_unknowns,
            "open_questions": updated_questions,
            "conflicts": merged_conflicts,
        }
    )

