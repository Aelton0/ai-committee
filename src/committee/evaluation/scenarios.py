"""Benchmark scenarios and scenario registry for deliberation evaluation."""

from typing import Any, Callable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, CommitteeState, DecisionStatus, Severity
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.learning import (
    LearningPathStep,
    LearningReference,
    LearningReport,
    ObservedKnowledgeGap,
)
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from schemas.synthesis import DeliberationSynthesis
from src.committee.evaluation.models import EvaluationCriterion
from src.committee.llm.mock import MockLLMProvider
from src.committee.session import Session


class BenchmarkScenario(BaseModel):
    """A standardized benchmark scenario for evaluating deliberation engines."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    id: str
    description: str
    input_context: dict[str, Any] = Field(default_factory=dict)
    expected_properties: dict[str, Any] = Field(default_factory=dict)
    session_builder: Callable[[UUID], Session]


class ScenarioRegistry:
    """Registry maintaining canonical benchmark scenarios for model and prompt evaluation."""

    def __init__(self) -> None:
        self._scenarios: dict[str, BenchmarkScenario] = {}

    def register(self, scenario: BenchmarkScenario) -> None:
        self._scenarios[scenario.id] = scenario

    def get(self, scenario_id: str) -> BenchmarkScenario:
        if scenario_id not in self._scenarios:
            raise KeyError(f"Scenario '{scenario_id}' not found in registry.")
        return self._scenarios[scenario_id]

    def list_all(self) -> list[BenchmarkScenario]:
        return list(self._scenarios.values())


# --- Scenario Builders ---

def _build_base_session(session_id: UUID) -> Session:
    provider = MockLLMProvider()
    session = Session(session_id=session_id, current_state=CommitteeState.COMPLETED)
    session.problem_context = provider._generate_default(ProblemContext, {})
    session.proposals[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectProposal, {})
    session.proposals[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticProposal, {})
    session.audit_report = provider._generate_default(AuditReport, {})
    session.defenses[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectDefense, {})
    session.defenses[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticDefense, {})
    session.deliberation_synthesis = provider._generate_default(DeliberationSynthesis, {})
    session.decision_record = provider._generate_default(DecisionRecord, {})
    session.learning_report = provider._generate_default(LearningReport, {})
    return session


def _build_scenario_1(session_id: UUID) -> Session:
    """Scenario 1: Soluções claramente diferentes (high divergence)."""
    return _build_base_session(session_id)


def _build_scenario_2(session_id: UUID) -> Session:
    """Scenario 2: Falso conflito (both propose identical modular monoliths with different words)."""
    session = _build_base_session(session_id)
    session.proposals[CommitteeRole.ARCHITECT] = ArchitectProposal(
        artifact_id="PROP-ARCH-001",
        version=1,
        title="Modular Monolith with Background Workers and Celery",
        solution="Single deployable Python service using Postgres and Celery for async background processing.",
        rationale="Maximizes time to value by delivering in 10 days with minimal operational complexity.",
        benefits=["Immediate delivery", "Single codebase"],
        costs=CostEstimate(
            implementation_effort=EffortLevel.LOW,
            infrastructure_cost_estimate="$35/mo",
        ),
        risks=["Potential database connection pool saturation"],
        complexity=Severity.LOW,
        reversibility=ReversibilityAssessment(
            score=ReversibilityLevel.HIGH,
            rationale="Can easily replace Celery with broker if scale demands it.",
        ),
        future_implications="May require dedicated Redis broker later.",
        assumptions=["Existing Postgres instance handles queue I/O."],
        invalidation_conditions=["Peak transactions exceed 2,000 req/s."],
    )
    return session


def _build_scenario_3(session_id: UUID) -> Session:
    """Scenario 3: Auditor superficial (no high severity findings, just superficial summaries)."""
    session = _build_base_session(session_id)
    session.audit_report = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[],
        findings_proposal_b=[],
        single_points_of_failure=[],
        hidden_costs=[],
        fragile_assumptions=[],
        overengineering_risks=[],
        underengineering_risks=[],
        questions_for_proponents=[],
    )
    return session


def _build_scenario_4(session_id: UUID) -> Session:
    """Scenario 4: Auditor forte (deep adversarial critique with multiple high severity findings)."""
    session = _build_base_session(session_id)
    session.audit_report = AuditReport(
        artifact_id="AUD-001",
        version=1,
        target_proposal_a_id="PROP-ARCH-001",
        target_proposal_b_id="PROP-PRAG-001",
        findings_proposal_a=[
            AuditFinding(
                id="F-A1",
                target_proposal_id="PROP-ARCH-001",
                category=AuditCategory.OVERENGINEERING,
                severity=Severity.HIGH,
                title="Kafka cluster introduces unnecessary operational toil",
                description="Kafka cluster maintenance for 500 req/s creates extreme operational overhead.",
                justification="Throughput requirement of 500 req/s is easily met with Redis Streams or RabbitMQ.",
            )
        ],
        findings_proposal_b=[
            AuditFinding(
                id="F-B1",
                target_proposal_id="PROP-PRAG-001",
                category=AuditCategory.SINGLE_POINTS_OF_FAILURE,
                severity=Severity.CRITICAL,
                title="Postgres database without replication is single point of failure",
                description="Single Postgres node without automatic failover creates unmitigated downtime risk.",
                justification="Any host reboot or hardware crash will take down the entire core product.",
            )
        ],
        single_points_of_failure=["Single primary Postgres node without read replicas"],
        hidden_costs=["Kafka cluster monitoring and disk partitioning overhead"],
        fragile_assumptions=["Assumes Postgres can handle Celery queue polling without lock contention"],
        overengineering_risks=["Avro schema registry for small team"],
        underengineering_risks=["No circuit breaker pattern on synchronous HTTP calls"],
        questions_for_proponents=[
            "How does Proposal B guarantee 99.9% uptime with a single Postgres database node?",
            "What is the operational recovery procedure if Kafka broker runs out of disk?",
        ],
    )
    return session


def _build_scenario_5(session_id: UUID) -> Session:
    """Scenario 5: Facilitador enviesado (synthesis contains explicit recommendation)."""
    session = _build_base_session(session_id)
    session.deliberation_synthesis = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consolidated_facts=["Budget under $200/mo", "Single team of 3 developers"],
        consensus_points=[
            "Recomendo a proposta B como a melhor opção para a empresa",
        ],
        divergence_points=["Kafka vs Celery"],
        arguments_by_alternative={"PROPOSAL_B": ["Fast delivery"]},
    )
    return session


def _build_scenario_6(session_id: UUID) -> Session:
    """Scenario 6: Decisão não rastreável (decision recommends an invented unvetted solution)."""
    session = _build_base_session(session_id)
    session.decision_record = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        recommendation="Adopt Serverless DynamoDB with AWS Step Functions and Lambda.",
        chosen_alternative="PROPOSAL_SERVERLESS_LAMBDA_STEP_FUNCTIONS",
        rationale="Serverless eliminates server management completely.",
        trade_offs=session.decision_record.trade_offs,
        review_triggers=session.decision_record.review_triggers,
        confidence=session.decision_record.confidence,
    )
    return session


def _build_scenario_7(session_id: UUID) -> Session:
    """Scenario 7: Informação insuficiente (insufficient evidence properly recorded)."""
    session = _build_base_session(session_id)
    session.decision_record = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        chosen_alternative=None,
        rationale="Critical partner gateway latency and peak concurrency SLAs remain unknown.",
        information_that_could_change_decision=[
            "Partner payment gateway p99 latency SLA under load",
            "Target database write IOPS provisioned limit",
        ],
        critical_assumptions=["Third-party gateway handles 500 req/s"],
        confidence=session.decision_record.confidence,
    )
    return session


def _build_scenario_8(session_id: UUID) -> Session:
    """Scenario 8: Mentor genérico (learning report lists generic buzzwords with no contextual evidence)."""
    session = _build_base_session(session_id)
    session.learning_report = LearningReport(
        artifact_id="LRN-001",
        version=1,
        concepts=["Software Architecture", "Databases"],
        concepts_required_to_understand_decision=["General software concepts"],
        observed_knowledge_gaps=[
            ObservedKnowledgeGap(
                observation="Developer should learn distributed systems.",
                context_evidence="No specific evidence recorded in dialogue.",
                recommended_topic="Systems",
            )
        ],
        study_questions=["How does computing work?"],
        learning_path=[
            LearningPathStep(
                order=1,
                topic="Systems",
                description="Study computing systems in general.",
            )
        ],
        theory_to_practice_connections=["General connection text without mentioning any trade-off."],
        references=[
            LearningReference(title="Textbook", url_or_citation="Citation")
        ],
    )
    return session


def create_default_scenario_registry() -> ScenarioRegistry:
    """Create and populate the ScenarioRegistry with the 8 canonical benchmark scenarios."""
    reg = ScenarioRegistry()

    reg.register(
        BenchmarkScenario(
            id="scenario-01-different-solutions",
            description="Architect proposes distributed architecture; Pragmatic proposes modular monolith.",
            expected_properties={
                "min_score": {EvaluationCriterion.PROPOSAL_DIVERGENCE: 4.5},
                "passed": [EvaluationCriterion.PROPOSAL_DIVERGENCE],
            },
            session_builder=_build_scenario_1,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-02-false-conflict",
            description="Both proponents propose essentially the same modular monolith with minor phrasing differences.",
            expected_properties={
                "max_score": {EvaluationCriterion.PROPOSAL_DIVERGENCE: 2.0},
                "failed": [EvaluationCriterion.PROPOSAL_DIVERGENCE],
            },
            session_builder=_build_scenario_2,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-03-superficial-auditor",
            description="Auditor report contains zero findings or only superficial summaries without technical challenge.",
            expected_properties={
                "max_score": {EvaluationCriterion.ADVERSARIAL_QUALITY: 2.0},
                "failed": [EvaluationCriterion.ADVERSARIAL_QUALITY],
            },
            session_builder=_build_scenario_3,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-04-strong-auditor",
            description="Auditor identifies specific SPOFs, overengineering risks, and challenges both proposals with high severity.",
            expected_properties={
                "min_score": {
                    EvaluationCriterion.ADVERSARIAL_QUALITY: 4.5,
                    EvaluationCriterion.RISK_COVERAGE: 4.5,
                },
                "passed": [
                    EvaluationCriterion.ADVERSARIAL_QUALITY,
                    EvaluationCriterion.RISK_COVERAGE,
                ],
            },
            session_builder=_build_scenario_4,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-05-biased-facilitator",
            description="Facilitator violates neutrality by inserting explicit recommendations in the convergence synthesis.",
            expected_properties={
                "score": {EvaluationCriterion.SYNTHESIS_NEUTRALITY: 0.0},
                "failed": [EvaluationCriterion.SYNTHESIS_NEUTRALITY],
            },
            session_builder=_build_scenario_5,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-06-untraceable-decision",
            description="Decision Maker recommends an invented solution that was never proposed or debated.",
            expected_properties={
                "max_score": {EvaluationCriterion.DECISION_TRACEABILITY: 2.0},
                "failed": [EvaluationCriterion.DECISION_TRACEABILITY],
            },
            session_builder=_build_scenario_6,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-07-insufficient-evidence",
            description="Insufficient evidence correctly recorded with missing info identified and no false winner declared.",
            expected_properties={
                "min_score": {EvaluationCriterion.DECISION_TRACEABILITY: 4.5},
                "passed": [EvaluationCriterion.DECISION_TRACEABILITY],
            },
            session_builder=_build_scenario_7,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-08-generic-mentor",
            description="Mentor dossier lists generic buzzwords with no contextual evidence or grounded connections.",
            expected_properties={
                "max_score": {EvaluationCriterion.LEARNING_VALUE: 2.0},
                "failed": [EvaluationCriterion.LEARNING_VALUE],
            },
            session_builder=_build_scenario_8,
        )
    )

    return reg
