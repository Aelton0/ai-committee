"""Audit schemas covering adversarial critique, vulnerabilities, SPOFs, and risk vectors."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import BaseArtifact, CommitteeRole, Severity


class AuditCategory(str, Enum):
    """Specific categories evaluated by the Auditor/SRE."""

    SECURITY = "security"
    RELIABILITY = "reliability"
    OPERATIONS = "operations"
    SCALABILITY = "scalability"
    COST = "cost"
    COMPLEXITY = "complexity"
    SINGLE_POINTS_OF_FAILURE = "single_points_of_failure"
    HIDDEN_COSTS = "hidden_costs"
    FRAGILE_ASSUMPTIONS = "fragile_assumptions"
    OVERENGINEERING = "overengineering"
    UNDERENGINEERING = "underengineering"


class AuditFinding(BaseModel):
    """Individual critique identified during adversarial audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(min_length=1)]
    target_proposal_id: Annotated[str, Field(min_length=1)]
    category: AuditCategory
    severity: Severity
    title: Annotated[str, Field(min_length=3)]
    description: Annotated[str, Field(min_length=5)]
    justification: Annotated[str, Field(min_length=5)]
    impact: str | None = None


class AuditReport(BaseArtifact):
    """Comprehensive adversarial audit attacking both proposals independently."""

    auditor_role: Literal[CommitteeRole.AUDITOR_SRE] = CommitteeRole.AUDITOR_SRE
    target_proposal_a_id: Annotated[str, Field(min_length=1)]
    target_proposal_b_id: Annotated[str, Field(min_length=1)]
    findings_proposal_a: list[AuditFinding] = Field(default_factory=list)
    findings_proposal_b: list[AuditFinding] = Field(default_factory=list)
    single_points_of_failure: list[str] = Field(default_factory=list)
    hidden_costs: list[str] = Field(default_factory=list)
    fragile_assumptions: list[str] = Field(default_factory=list)
    overengineering_risks: list[str] = Field(default_factory=list)
    underengineering_risks: list[str] = Field(default_factory=list)
    questions_for_proponents: list[str] = Field(default_factory=list)

    def all_findings(self) -> list[AuditFinding]:
        """Return all findings across both evaluated proposals."""
        return self.findings_proposal_a + self.findings_proposal_b

    def findings_by_category(self, category: AuditCategory) -> list[AuditFinding]:
        """Filter findings by specific audit category."""
        return [f for f in self.all_findings() if f.category == category]

    def critical_findings(self) -> list[AuditFinding]:
        """Return all findings classified as HIGH or CRITICAL severity."""
        return [f for f in self.all_findings() if f.severity in (Severity.HIGH, Severity.CRITICAL)]
