"""Comprehensive unit tests for Epistemic Discipline schemas and data models."""

import pytest
from pydantic import ValidationError

from schemas.audit import AuditCategory, AuditFinding
from schemas.common import Confidence, DecisionStatus, Severity
from schemas.context import Assumption, Constraint, ConstraintType, Fact, ProblemContext, Unknown
from schemas.decision import DecisionRecord, ReviewTrigger, TradeOffContract
from schemas.epistemic import (
    AssumptionItem,
    ConditionalRecommendation,
    EpistemicCategory,
    EpistemicSection,
    FactItem,
    InferenceItem,
    RecommendationItem,
    UnknownItem,
)
from schemas.learning import EpistemicLesson, LearningPathStep, LearningReference, LearningReport
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from schemas.synthesis import DeliberationSynthesis


def test_epistemic_category_values() -> None:
    expected = {"FACT", "ASSUMPTION", "INFERENCE", "UNKNOWN", "RECOMMENDATION"}
    actual = {c.value for c in EpistemicCategory}
    assert actual == expected


def test_fact_item_creation_and_immutability() -> None:
    fact = FactItem(
        id="F1",
        statement="PostgreSQL 15 is running on a single instance.",
        source="Infrastructure report",
        verified=True,
    )
    assert fact.id == "F1"
    assert fact.statement.startswith("PostgreSQL 15")
    assert fact.source == "Infrastructure report"
    assert fact.verified is True

    # Immutability
    with pytest.raises(ValidationError):
        fact.verified = False  # type: ignore


def test_assumption_item_validation() -> None:
    asm = AssumptionItem(
        id="A1",
        statement="Traffic will grow 20% in the next quarter.",
        reason="Commercial team projection",
        confidence=Confidence.MEDIUM,
        invalidation_condition="Quarterly growth remains below 5%",
        risk_level=Severity.MEDIUM,
    )
    assert asm.id == "A1"
    assert asm.confidence == Confidence.MEDIUM
    assert "below 5%" in asm.invalidation_condition


def test_inference_item_dependencies() -> None:
    inf = InferenceItem(
        id="I1",
        statement="Current database will experience connection saturation.",
        rationale="20% traffic increase exceeds the 100 max_connections setting without connection pooling.",
        depends_on=["F1", "A1"],
        confidence=Confidence.HIGH,
    )
    assert inf.id == "I1"
    assert inf.depends_on == ["F1", "A1"]


def test_unknown_item_creation() -> None:
    unk = UnknownItem(
        id="U1",
        statement="Actual peak queries per second during marketing campaigns.",
        impact_if_adverse=Severity.HIGH,
        how_to_resolve="Deploy APM metrics collector during next promotion.",
    )
    assert unk.id == "U1"
    assert unk.impact_if_adverse == Severity.HIGH
    assert unk.how_to_resolve is not None


def test_conditional_recommendation() -> None:
    cond_rec = ConditionalRecommendation(
        condition="IF sustained peak throughput exceeds 2,000 req/s",
        recommendation="THEN adopt Kafka event streaming with dedicated broker cluster",
        evidence=["F1", "A1", "I1"],
    )
    assert cond_rec.condition.startswith("IF")
    assert cond_rec.recommendation.startswith("THEN")
    assert cond_rec.evidence == ["F1", "A1", "I1"]


def test_epistemic_section_validation_and_methods() -> None:
    fact = FactItem(id="F1", statement="Existing database is MySQL", source="User input")
    asm = AssumptionItem(
        id="A1",
        statement="Budget will remain flexible",
        reason="Initial guidance",
        invalidation_condition="Budget capped at $100/mo",
    )
    inf = InferenceItem(
        id="I1",
        statement="Refactoring will require 2 sprints",
        rationale="Derived from team size",
        depends_on=["F1", "A1"],
    )
    unk = UnknownItem(id="U1", statement="Third party API rate limits")
    cond_rec = ConditionalRecommendation(
        condition="IF rate limit is strict",
        recommendation="THEN implement client side token bucket",
    )

    section = EpistemicSection(
        facts=[fact],
        assumptions=[asm],
        inferences=[inf],
        unknowns=[unk],
        conditional_recommendations=[cond_rec],
    )

    assert section.fact_ids() == {"F1"}
    assert section.assumption_ids() == {"A1"}
    assert section.inference_ids() == {"I1"}
    assert section.unknown_ids() == {"U1"}
    assert section.validate_dependency_references() == []

    # Test broken dependency reference
    broken_inf = InferenceItem(
        id="I2",
        statement="Broken inference",
        rationale="Derivation",
        depends_on=["F_NONEXISTENT", "A1"],
    )
    broken_section = EpistemicSection(
        facts=[fact],
        assumptions=[asm],
        inferences=[broken_inf],
    )
    missing = broken_section.validate_dependency_references()
    assert len(missing) == 1
    assert "F_NONEXISTENT" in missing[0]


def test_proposal_backward_compatibility_with_default_epistemic_section() -> None:
    # Creating an ArchitectProposal without epistemic_section works seamlessly
    proposal = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Decoupled Architecture",
        solution="Event streaming via Kafka with schema registry.",
        rationale="Enables independent service evolution and fault isolation.",
        benefits=["Domain decoupling"],
        costs=CostEstimate(
            implementation_effort=EffortLevel.HIGH,
            infrastructure_cost_estimate="$200/mo",
        ),
        risks=["Tracing complexity"],
        complexity=Severity.HIGH,
        reversibility=ReversibilityAssessment(
            score=ReversibilityLevel.LOW,
            rationale="Schema migration needed to roll back.",
        ),
        future_implications="Multi-region ready.",
        assumptions=["Team learns Kafka."],
        invalidation_conditions=["Throughput drops below 10 req/s."],
    )
    assert isinstance(proposal.epistemic_section, EpistemicSection)
    assert len(proposal.epistemic_section.facts) == 0


def test_proposal_with_explicit_epistemic_section() -> None:
    section = EpistemicSection(
        facts=[FactItem(id="F1", statement="Single Postgres instance", source="User input")],
        assumptions=[
            AssumptionItem(
                id="A1",
                statement="Volume grows 20%",
                reason="Commercial estimate",
                invalidation_condition="Volume drops",
            )
        ],
        unknowns=[UnknownItem(id="U1", statement="Peak concurrent checkout sessions")],
        conditional_recommendations=[
            ConditionalRecommendation(
                condition="IF checkout sessions > 5,000",
                recommendation="THEN provision dedicated redis cache",
            )
        ],
    )

    proposal = PragmaticProposal(
        artifact_id="PROP-PRAG-001",
        version=1,
        title="Monolith with Celery",
        solution="Single Python service with async background tasks.",
        rationale="KISS and rapid delivery.",
        benefits=["Low cost"],
        costs=CostEstimate(
            implementation_effort=EffortLevel.LOW,
            infrastructure_cost_estimate="$30/mo",
        ),
        risks=["Single database SPOF"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(
            score=ReversibilityLevel.HIGH,
            rationale="Standard celery worker.",
        ),
        future_implications="Scale when needed.",
        assumptions=["Existing database holds queue load."],
        invalidation_conditions=["Database connection pool saturated."],
        epistemic_section=section,
    )
    assert len(proposal.epistemic_section.facts) == 1
    assert len(proposal.epistemic_section.conditional_recommendations) == 1


def test_audit_category_epistemic_risk() -> None:
    finding = AuditFinding(
        id="AUD-EPI-01",
        target_proposal_id="PROP-ARCH-001",
        category=AuditCategory.EPISTEMIC_RISK,
        severity=Severity.HIGH,
        title="Unsubstantiated 100k req/s traffic assumption",
        description="Proposal assumes 100k req/s to justify Kafka cluster, but ProblemContext has no traffic metrics.",
        justification="Violates Epistemic Discipline Principle 5: ungrounded assumptions disguised as facts.",
    )
    assert finding.category == AuditCategory.EPISTEMIC_RISK


def test_synthesis_consolidated_inferences() -> None:
    syn = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consolidated_facts=["Single RDS Postgres"],
        consolidated_assumptions=["20% annual growth"],
        consolidated_inferences=["Database connection limits will be reached during Q4 peak"],
        consolidated_unknowns=["Peak checkout concurrency"],
    )
    assert "Database connection limits" in syn.consolidated_inferences[0]


def test_decision_record_epistemic_fields() -> None:
    decision = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        recommendation="Adopt Pragmatic Proposal v2 (Celery on Postgres with PgBouncer).",
        chosen_alternative="PROPOSAL_PRAG_V2",
        rationale="Meets deadline and budget while mitigating connection pool exhaustion.",
        trade_offs=[TradeOffContract(gain="Fast delivery", sacrifice="Coupled queue")],
        review_triggers=[ReviewTrigger(condition="Sustained throughput > 800 req/s")],
        confidence=Confidence.HIGH,
        supported_by=["F1", "F2"],
        depends_on=["A1"],
        uncertainties=["U1"],
        conditional_recommendations=[
            ConditionalRecommendation(
                condition="IF peak throughput exceeds 1,000 req/s",
                recommendation="THEN migrate from Celery DB queue to Redis broker",
            )
        ],
    )
    assert decision.supported_by == ["F1", "F2"]
    assert decision.depends_on == ["A1"]
    assert decision.uncertainties == ["U1"]
    assert len(decision.conditional_recommendations) == 1


def test_learning_report_epistemic_lessons() -> None:
    lesson = EpistemicLesson(
        concept="Trade-off between scalability and operational complexity",
        debate_example="Architect suggested Kafka and Kubernetes based on projected traffic growth.",
        epistemic_confusion="Projected growth was an assumption, not an established fact.",
        study_topic="Capacity planning, architectural assumptions, and YAGNI.",
    )
    report = LearningReport(
        artifact_id="LRN-001",
        version=1,
        concepts=["CAP Theorem"],
        concepts_required_to_understand_decision=["RPC vs Async queues"],
        study_questions=["Why does queuing not increase database write throughput?"],
        learning_path=[
            LearningPathStep(
                order=1,
                topic="Reliability",
                description="Study connection pools.",
                reference=LearningReference(title="DDIA", url_or_citation="O'Reilly"),
            )
        ],
        theory_to_practice_connections=["KISS chosen because volume does not justify Kafka ops."],
        references=[LearningReference(title="Release It!", url_or_citation="Pragmatic Bookshelf")],
        epistemic_lessons=[lesson],
    )
    assert len(report.epistemic_lessons) == 1
    assert "projected growth was an assumption" in report.epistemic_lessons[0].epistemic_confusion.lower()


def test_problem_context_helper_methods() -> None:
    ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Monolith experiencing database latency spikes under load.",
        facts=[
            Fact(id="F1", description="Postgres 15 on single node", source="Infra config"),
            Fact(id="F2", description="Latency p95 is 400ms", source="Datadog APM"),
        ],
        constraints=[
            Constraint(id="C1", description="Budget under $300/mo", type=ConstraintType.BUDGET),
        ],
        assumptions=[
            Assumption(id="A1", description="Traffic will grow 15% in Q2", rationale="Commercial lead"),
        ],
        unknowns=[
            Unknown(id="U1", description="Maximum database connection capacity under burst load"),
        ],
        success_criteria=["Latency p95 < 100ms"],
    )

    assert ctx.fact_ids() == {"F1", "F2"}
    assert ctx.assumption_ids() == {"A1"}
    assert ctx.unknown_ids() == {"U1"}
    assert ctx.constraint_ids() == {"C1"}

    assert ctx.get_fact("F1") is not None
    assert ctx.get_fact("F_NONEXISTENT") is None
    assert ctx.get_assumption("A1") is not None
    assert ctx.get_unknown("U1") is not None
