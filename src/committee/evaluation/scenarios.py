"""Benchmark scenarios and scenario registry for deliberation evaluation."""

from typing import Any, Callable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, CommitteeState, Confidence, DecisionStatus, Severity
from schemas.context import Constraint, ConstraintType, Fact, OpenQuestion, ProblemContext, Unknown
from schemas.decision import (
    AcceptedRisk,
    DecisionRecord,
    RejectedAlternative,
    ReviewTrigger,
    TradeOffContract,
)
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.epistemic import (
    AssumptionItem,
    ConditionalRecommendation,
    FactItem,
    InferenceItem,
    RecommendationItem,
    UnknownItem,
)
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
from schemas.synthesis import DeliberationSynthesis, TradeOffDimension
from src.committee.evaluation.models import EpistemicCriterion, EvaluationCriterion
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


def _build_scenario_9(session_id: UUID) -> Session:
    """Scenario 9: Fato inventado (proposal invents 50k req/s not present in ProblemContext)."""
    session = _build_base_session(session_id)
    prop = session.proposals[CommitteeRole.ARCHITECT]
    new_facts = list(prop.epistemic_section.facts) + [
        FactItem(
            id="FACT-INV-1",
            statement="O sistema atual processa 50000 req/s em regime contínuo.",
            source="unverified",
            verified=False,
        )
    ]
    session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={
            "solution": "Arquitetura distribuída com cluster Kafka dimensionado para 50.000 req/s.",
            "epistemic_section": prop.epistemic_section.model_copy(update={"facts": new_facts}),
        }
    )
    return session


def _build_scenario_10(session_id: UUID) -> Session:
    """Scenario 10: Premissa oculta (proposal assumes 20% annual growth without declaring it in assumptions)."""
    session = _build_base_session(session_id)
    prop = session.proposals[CommitteeRole.ARCHITECT]
    session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={
            "solution": "Arquitetura dimensionada para suportar crescimento anual de 20% no tráfego.",
            "rationale": "A equipe aprenderá em 2 semanas a operar os novos serviços distribuídos.",
            "assumptions": [],
            "epistemic_section": prop.epistemic_section.model_copy(
                update={"assumptions": [], "inferences": []}
            ),
        }
    )
    return session


def _build_scenario_11(session_id: UUID) -> Session:
    """Scenario 11: Premissa explícita (same 20% growth declared with invalidation condition and impact)."""
    session = _build_base_session(session_id)
    prop = session.proposals[CommitteeRole.ARCHITECT]
    asm = [
        AssumptionItem(
            id="A1",
            statement="Crescimento anual de 20% no volume de dados",
            reason="Projeção baseada no histórico preliminar do negócio",
            confidence=Confidence.MEDIUM,
            invalidation_condition="Se o crescimento nos próximos 6 meses for menor que 5%",
            risk_level=Severity.MEDIUM,
        )
    ]
    session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={
            "solution": "Arquitetura modular projetada para absorver crescimento anual de 20% no tráfego.",
            "rationale": "Preparação para a escala projetada sob premissa técnica verificável.",
            "assumptions": ["Crescimento anual de 20% no volume de dados"],
            "epistemic_section": prop.epistemic_section.model_copy(update={"assumptions": asm}),
        }
    )
    return session


def _build_scenario_12(session_id: UUID) -> Session:
    """Scenario 12: Incógnita ignorada (context specifies unknown peak throughput, proposals ignore it)."""
    session = _build_base_session(session_id)
    session.problem_context = session.problem_context.model_copy(
        update={
            "unknowns": [
                Unknown(
                    id="UNK-PEAK-01",
                    description="Taxa de pico de requisições por segundo durante campanhas de marketing é desconhecida.",
                    impact_if_adverse=Severity.HIGH,
                )
            ]
        }
    )
    prop_a = session.proposals[CommitteeRole.ARCHITECT]
    prop_b = session.proposals[CommitteeRole.PRAGMATIST]
    session.proposals[CommitteeRole.ARCHITECT] = prop_a.model_copy(
        update={
            "solution": "Single deployable service on AWS ECS with PostgreSQL backend.",
            "rationale": "Standard service isolation pattern.",
            "risks": ["Database connection limits"],
            "epistemic_section": prop_a.epistemic_section.model_copy(
                update={"unknowns": [], "conditional_recommendations": []}
            ),
        }
    )
    session.proposals[CommitteeRole.PRAGMATIST] = prop_b.model_copy(
        update={
            "solution": "Modular monolith on basic virtual machine.",
            "rationale": "Simplest possible architecture.",
            "risks": ["Server downtime during updates"],
            "epistemic_section": prop_b.epistemic_section.model_copy(
                update={"unknowns": [], "conditional_recommendations": []}
            ),
        }
    )
    return session


def _build_scenario_13(session_id: UUID) -> Session:
    """Scenario 13: Recomendação condicional (proposal uses IF throughput > X THEN shard database)."""
    session = _build_base_session(session_id)
    prop_a = session.proposals[CommitteeRole.ARCHITECT]
    cr = [
        ConditionalRecommendation(
            condition="IF throughput ultrapassar 10000 req/s",
            recommendation="THEN particionar banco e adotar Kafka cluster",
            evidence=["F1"],
        )
    ]
    session.proposals[CommitteeRole.ARCHITECT] = prop_a.model_copy(
        update={
            "solution": "PostgreSQL com réplicas de leitura. IF throughput ultrapassar 10000 req/s THEN particionar banco e adotar Kafka cluster.",
            "epistemic_section": prop_a.epistemic_section.model_copy(
                update={"conditional_recommendations": cr}
            ),
        }
    )
    return session


def _build_scenario_14(session_id: UUID) -> Session:
    """Scenario 14: Incerteza honesta (decision record correctly emits INSUFFICIENT_EVIDENCE when context has critical unknowns)."""
    session = _build_base_session(session_id)
    session.problem_context = session.problem_context.model_copy(
        update={
            "unknowns": [
                Unknown(
                    id="UNK-SCALE-01",
                    description="Pico de carga e volume de transações por segundo desconhecidos.",
                    impact_if_adverse=Severity.HIGH,
                )
            ]
        }
    )
    unk_list = [
        UnknownItem(
            id="UNK-SCALE-01",
            statement="Pico de carga e volume de transações por segundo desconhecidos.",
            impact_if_adverse=Severity.HIGH,
        )
    ]
    prop_a = session.proposals[CommitteeRole.ARCHITECT]
    prop_b = session.proposals[CommitteeRole.PRAGMATIST]
    session.proposals[CommitteeRole.ARCHITECT] = prop_a.model_copy(
        update={"epistemic_section": prop_a.epistemic_section.model_copy(update={"unknowns": unk_list})}
    )
    session.proposals[CommitteeRole.PRAGMATIST] = prop_b.model_copy(
        update={"epistemic_section": prop_b.epistemic_section.model_copy(update={"unknowns": unk_list})}
    )
    session.decision_record = session.decision_record.model_copy(
        update={
            "status": DecisionStatus.INSUFFICIENT_EVIDENCE,
            "chosen_alternative": None,
            "rationale": "Impossível decidir arquitetura definitiva sem mensurar o pico de carga real.",
            "information_that_could_change_decision": ["Métricas de pico de carga"],
            "uncertainties": ["Pico de carga e volume de transações"],
            "confidence": Confidence.LOW,
        }
    )
    return session


def _build_scenario_15(session_id: UUID) -> Session:
    """Scenario 15 (Setor Azul - Subinformed): Missing critical volume, SLA, and queue info forces INSUFFICIENT_EVIDENCE."""
    session = _build_base_session(session_id)
    session.problem_statement = "Integração Setor Azul: captura de leads para CRM sem dados de volumetria, sem SLA de perda e sem mensageria confirmada."
    session.problem_context = session.problem_context.model_copy(
        update={
            "problem": session.problem_statement,
            "business_value_chain": [
                "landing_page_lead",
                "webhook_capture",
                "persistence",
                "crm_deal_creation",
                "sales_revenue_attribution",
            ],
            "facts": [
                Fact(id="F1", description="PostgreSQL 15 em produção para banco transacional", source="user_input"),
            ],
            "unknowns": [
                Unknown(
                    id="UNK-VOL-01",
                    description="Volumetria de pico de leads por segundo desconhecida.",
                    impact_if_adverse=Severity.CRITICAL,
                    decision_relevance=Severity.CRITICAL,
                    could_change_selected_alternative=True,
                    blocking=True,
                ),
                Unknown(
                    id="UNK-SLA-01",
                    description="SLA de tolerância a indisponibilidade do CRM de destino desconhecido.",
                    impact_if_adverse=Severity.HIGH,
                    decision_relevance=Severity.HIGH,
                    could_change_selected_alternative=True,
                    blocking=True,
                ),
            ],
        }
    )
    unk_items = [
        UnknownItem(id="UNK-VOL-01", statement="Volumetria de pico de leads por segundo desconhecida.", impact_if_adverse=Severity.CRITICAL),
        UnknownItem(id="UNK-SLA-01", statement="SLA de tolerância a indisponibilidade do CRM de destino desconhecido.", impact_if_adverse=Severity.HIGH),
    ]
    prop_a = session.proposals[CommitteeRole.ARCHITECT]
    prop_b = session.proposals[CommitteeRole.PRAGMATIST]
    session.proposals[CommitteeRole.ARCHITECT] = prop_a.model_copy(
        update={"epistemic_section": prop_a.epistemic_section.model_copy(update={"unknowns": unk_items})}
    )
    session.proposals[CommitteeRole.PRAGMATIST] = prop_b.model_copy(
        update={"epistemic_section": prop_b.epistemic_section.model_copy(update={"unknowns": unk_items})}
    )
    session.decision_record = session.decision_record.model_copy(
        update={
            "status": DecisionStatus.INSUFFICIENT_EVIDENCE,
            "chosen_alternative": None,
            "recommendation": None,
            "rationale": "Evidência insuficiente: impossível recomendar entre Store-and-Forward e integração direta sem conhecer a volumetria de pico e o SLA de downtime do CRM.",
            "information_that_could_change_decision": [
                "Pico de volumetria de requisições por segundo (UNK-VOL-01)",
                "Tolerância a indisponibilidade e SLA do CRM (UNK-SLA-01)",
            ],
            "uncertainties": ["UNK-VOL-01", "UNK-SLA-01"],
            "confidence": Confidence.LOW,
        }
    )
    return session


def _build_scenario_16(session_id: UUID) -> Session:
    """Scenario 16 (Setor Azul - Informed): Complete requirements enable genuine divergence, trade-off contract and traceable decision."""
    session = _build_base_session(session_id)
    session.problem_statement = "Integração Setor Azul: 200 leads/dia (pico 15 req/s), CRM com 2h downtime semanal, perda de lead = $500 CAC, prazo 4 semanas, budget $300/mês."
    session.problem_context = session.problem_context.model_copy(
        update={
            "problem": session.problem_statement,
            "business_value_chain": [
                "landing_page_lead",
                "webhook_capture",
                "transactional_buffer",
                "crm_deal_creation",
                "sales_revenue_attribution",
            ],
            "facts": [
                Fact(id="F1", description="PostgreSQL 15 single instance 16GB", source="User input"),
                Fact(id="F2", description="Volume de 200 leads/dia com pico de 15 req/s em campanhas", source="user_response"),
                Fact(id="F3", description="CRM de terceiros sofre indisponibilidade de até 2 horas semanais", source="user_response"),
                Fact(id="F4", description="Perda de um único lead custa $500 de CAC para o negócio", source="user_response"),
            ],
            "constraints": [
                Constraint(id="C1", description="Monthly budget under $300", type=ConstraintType.BUDGET, negotiable=False),
                Constraint(id="C2", description="Delivery in 4 weeks", type=ConstraintType.DEADLINE, negotiable=False),
            ],
            "unknowns": [],
        }
    )
    prop_a = session.proposals[CommitteeRole.ARCHITECT].model_copy(
        update={
            "artifact_id": "PROP-ARCH-001",
            "title": "Transactional Outbox on Existing PostgreSQL with Asynchronous Worker",
            "solution": "Persist incoming leads immediately into an outbox table in Postgres within the ingestion transaction, processed by an async worker with exponential backoff.",
            "rationale": "Guarantees zero lead loss ($500 CAC risk) even during 2-hour CRM downtime by decoupling ingestion from external delivery.",
            "benefits": ["Zero data loss for high-value leads", "No additional messaging infrastructure needed"],
            "costs": CostEstimate(implementation_effort=EffortLevel.MEDIUM, infrastructure_cost_estimate="$0"),
            "risks": ["Outbox table polling load on Postgres if index unoptimized"],
            "complexity": Severity.MEDIUM,
            "reversibility": ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Table schema easily retired"),
            "future_implications": "Can upgrade to Debezium CDC if write throughput exceeds 1,000 req/s.",
            "assumptions": ["Postgres transaction throughput handles 15 req/s easily"],
            "invalidation_conditions": ["Postgres CPU reaches 85% utilization"],
        }
    )
    prop_b = session.proposals[CommitteeRole.PRAGMATIST].model_copy(
        update={
            "artifact_id": "PROP-PRAG-001",
            "title": "Direct FastAPI Webhook with In-Memory Retries and SQLite Fallback",
            "solution": "FastAPI endpoint that attempts direct HTTP call to CRM, falling back to local SQLite buffer if CRM returns 5xx error.",
            "rationale": "Delivers working MVP in 5 days with minimal boilerplate and near-zero ongoing operational overhead.",
            "benefits": ["Ultra-fast time to market", "Minimal moving parts and no background daemon"],
            "costs": CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$0"),
            "risks": ["Process crash before SQLite flush loses active leads in memory"],
            "complexity": Severity.LOW,
            "reversibility": ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Simple endpoint"),
            "future_implications": "Replace SQLite fallback with outbox when scale grows.",
            "assumptions": ["CRM downtime is usually under 10 minutes, rarely 2 hours"],
            "invalidation_conditions": ["Lead loss exceeds 1 lead per month"],
        }
    )
    session.proposals[CommitteeRole.ARCHITECT] = prop_a
    session.proposals[CommitteeRole.PRAGMATIST] = prop_b

    finding_b = AuditFinding(
        id="F-AUD-01",
        target_proposal_id=prop_b.artifact_id,
        severity=Severity.HIGH,
        category=AuditCategory.RELIABILITY,
        title="In-memory buffer risks lead loss",
        description="In-memory buffer before SQLite flush risks losing $500 leads during unexpected worker restart.",
        justification="Process crash during 2-hour CRM downtime empties volatile queue before persistence.",
        impact="Direct financial loss of $500 CAC per dropped lead",
    )
    finding_a = AuditFinding(
        id="F-AUD-02",
        target_proposal_id=prop_a.artifact_id,
        severity=Severity.MEDIUM,
        category=AuditCategory.OPERATIONS,
        title="Worker polling table lock contention",
        description="Worker polling table without SKIP LOCKED can cause concurrency locks.",
        justification="Multiple workers query outbox table concurrently causing deadlocks under high write load.",
        impact="Temporary latency increase on database transactions",
    )
    session.audit_report = session.audit_report.model_copy(
        update={
            "target_proposal_a_id": prop_a.artifact_id,
            "target_proposal_b_id": prop_b.artifact_id,
            "findings_proposal_a": [finding_a],
            "findings_proposal_b": [finding_b],
        }
    )

    session.deliberation_synthesis = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consensus_points=[
            "Both agree existing PostgreSQL is sufficient without dedicated Kafka/RabbitMQ broker",
            "Both acknowledge $500 CAC makes unbuffered lead drops unacceptable",
        ],
        divergence_points=[
            "Transactional Outbox (guaranteed delivery) vs Direct HTTP with local fallback (fast time-to-market)",
        ],
        arguments_by_alternative={
            "PROP-ARCH-001": ["Guaranteed zero data loss", "Resilient to 2h CRM downtime"],
            "PROP-PRAG-001": ["5-day delivery", "Extremely simple codebase"],
        },
        trade_offs=[
            TradeOffDimension(
                dimension="Lead Preservation vs Time to Market",
                option_a="Guaranteed lead persistence ($0 loss risk) with 2-3 weeks implementation",
                option_b="5-day launch with non-zero loss risk if process dies during CRM downtime",
                notes="Option A protects the core business revenue attribution chain.",
            )
        ],
    )

    session.decision_record = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        chosen_alternative="PROP-ARCH-001",
        recommendation="Adopt Transactional Outbox pattern on PostgreSQL with SKIP LOCKED polling worker.",
        rejected_alternatives=[
            RejectedAlternative(
                name="PROP-PRAG-001",
                rejection_reason="In-memory buffering poses unacceptable financial risk ($500 per lost lead) during CRM 2-hour outages.",
            )
        ],
        rationale="The financial impact of lost leads ($500 CAC) and 2-hour CRM outages justifies the moderate effort of the Transactional Outbox over direct HTTP.",
        trade_offs=[
            TradeOffContract(
                gain="Guaranteed zero lead loss and resilience against 2h CRM outages",
                sacrifice="2 additional weeks of initial engineering effort",
            )
        ],
        accepted_risks=[
            AcceptedRisk(
                risk="Outbox table growth during prolonged CRM outage",
                severity=Severity.LOW,
                mitigation="Worker cleanup cron purging dispatched events older than 7 days",
            )
        ],
        review_triggers=[
            ReviewTrigger(
                condition="Throughput exceeds 500 leads/sec or Postgres CPU > 75%",
                metric_threshold="500 leads/sec",
                trigger_type="METRIC",
            )
        ],
        confidence=Confidence.HIGH,
        supported_by=["F1", "F2", "F3", "F4"],
        depends_on=["C1", "C2"],
    )
    return session


def _build_scenario_17(session_id: UUID) -> Session:
    """Scenario 17 (Setor Azul - Contradictory): Conflicting user statements are recorded in conflicts rather than silently chosen."""
    session = _build_base_session(session_id)
    session.problem_statement = "Integração Setor Azul com premissas mutuamente excludentes: throughput de 50.000 req/s vs orçamento máximo de $50/mês."
    session.problem_context = session.problem_context.model_copy(
        update={
            "problem": session.problem_statement,
            "conflicts": [
                "Conflito identificado: throughput de 50.000 req/s exige infraestrutura distribuída horizontalmente, incompatível com teto orçamentário de $50/mês.",
            ],
            "open_questions": [
                OpenQuestion(
                    id="Q-CONFLICT-01",
                    question="Inconsistência entre throughput de 50.000 req/s e orçamento de $50/mês. Qual restrição deve ser ajustada?",
                    why_critical="Conflitos entre requisitos inegociáveis devem ser formalmente resolvidos antes de liberar a divergência.",
                    incorporated=False,
                )
            ],
        }
    )
    return session


def _build_scenario_18(session_id: UUID) -> Session:
    """Scenario 18 (Legitimate Consensus): Minimal workload (10 events/day) where both agents legitimately agree on simple solution without artificial conflict."""
    session = _build_base_session(session_id)
    session.problem_statement = "Geração de relatório diário interno: 10 eventos por dia, 1 único consumidor, sem projeção de crescimento."
    session.problem_context = session.problem_context.model_copy(
        update={
            "problem": session.problem_statement,
            "facts": [
                Fact(id="F1", description="10 eventos por dia no total", source="user_input"),
                Fact(id="F2", description="Apenas 1 consumidor interno sem requisitos de concorrência", source="user_input"),
            ],
            "unknowns": [],
        }
    )
    prop_a = session.proposals[CommitteeRole.ARCHITECT].model_copy(
        update={
            "artifact_id": "PROP-ARCH-001",
            "title": "Modular Scheduled Batch Service",
            "solution": "Isolated Python module with single responsibility separation between extraction and rendering, scheduled via system cron.",
            "rationale": "Structural modularity ensures code clarity and low maintenance overhead while avoiding distributed complexity for 10 events/day.",
            "benefits": ["Clean boundaries", "Easy local testing", "Zero operational overhead"],
            "costs": CostEstimate(implementation_effort=EffortLevel.MEDIUM, infrastructure_cost_estimate="$0"),
            "risks": ["Cron execution silently failing if logging is not configured"],
            "complexity": Severity.LOW,
            "reversibility": ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Single module"),
            "future_implications": "Can wrap in Docker container if environment changes.",
            "assumptions": ["Volume remains under 100 events/day"],
            "invalidation_conditions": ["Multiple consumers require push notifications"],
        }
    )
    prop_b = session.proposals[CommitteeRole.PRAGMATIST].model_copy(
        update={
            "artifact_id": "PROP-PRAG-001",
            "title": "Single-File Python Script on System Crontab",
            "solution": "Standalone Python script executed once daily by Linux crontab writing directly to shared storage.",
            "rationale": "YAGNI and KISS: 10 events per day does not justify any queue, framework, or container orchestration.",
            "benefits": ["1 day implementation", "Zero infrastructure cost", "Zero dependencies"],
            "costs": CostEstimate(implementation_effort=EffortLevel.LOW, infrastructure_cost_estimate="$0"),
            "risks": ["No automatic retry on transient error"],
            "complexity": Severity.LOW,
            "reversibility": ReversibilityAssessment(score=ReversibilityLevel.HIGH, rationale="Trivial to replace"),
            "future_implications": "Add retry wrapper if network is unstable.",
            "assumptions": ["Local machine has 99% uptime during cron trigger window"],
            "invalidation_conditions": ["Report needed in real-time"],
        }
    )
    session.proposals[CommitteeRole.ARCHITECT] = prop_a
    session.proposals[CommitteeRole.PRAGMATIST] = prop_b

    session.deliberation_synthesis = DeliberationSynthesis(
        artifact_id="SYN-001",
        version=1,
        consensus_points=[
            "Both agree 10 events/day does not justify any message broker, queue, or cloud service",
            "Both agree on scheduled Python script running via cron as the right architectural choice",
        ],
        divergence_points=[
            "Architect emphasizes modular internal layers for testability vs Pragmatist emphasizes single-file script for speed",
        ],
        arguments_by_alternative={
            "PROP-ARCH-001": ["Clean testability", "Modular extraction/rendering separation"],
            "PROP-PRAG-001": ["1 day delivery", "Zero overhead"],
        },
        trade_offs=[
            TradeOffDimension(
                dimension="Modularity vs Implementation Hours",
                option_a="Separate extractor/renderer modules (1-2 days)",
                option_b="Single script (half day)",
                notes="Both options are highly simple and cost $0.",
            )
        ],
    )

    session.decision_record = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        chosen_alternative="PROP-ARCH-001",
        recommendation="Adopt modular Python script scheduled via cron with structured logging.",
        rejected_alternatives=[
            RejectedAlternative(
                name="PROP-PRAG-001",
                rejection_reason="Single-file script without modular separation makes automated unit testing harder, even though it is slightly faster to write.",
            )
        ],
        rationale="For 10 events/day, a simple modular script scheduled via cron provides the best balance of simplicity ($0 infra) and maintainability without overengineering.",
        trade_offs=[
            TradeOffContract(
                gain="Simplicity, $0 infrastructure cost, and clean maintainability",
                sacrifice="Manual execution setup without distributed scheduler",
            )
        ],
        accepted_risks=[
            AcceptedRisk(
                risk="Cron failure on host machine reboot",
                severity=Severity.LOW,
                mitigation="Add @reboot cron check and failure alert email",
            )
        ],
        review_triggers=[
            ReviewTrigger(
                condition="Volume exceeds 1,000 events/day or multiple real-time consumers required",
                metric_threshold="1000 events/day",
                trigger_type="METRIC",
            )
        ],
        confidence=Confidence.HIGH,
        supported_by=["F1", "F2"],
    )
    return session


def create_default_scenario_registry() -> ScenarioRegistry:
    """Create and populate the ScenarioRegistry with canonical benchmark scenarios."""
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

    reg.register(
        BenchmarkScenario(
            id="scenario-09-invented-fact",
            description="Proposal invents 50k req/s metric not provided in ProblemContext.",
            expected_properties={
                "max_score": {EpistemicCriterion.FACT_GROUNDING: 2.0},
                "failed": [EpistemicCriterion.FACT_GROUNDING],
            },
            session_builder=_build_scenario_9,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-10-hidden-assumption",
            description="Proposal assumes 20% annual volume growth and 2-week team learning curve without declaring them as assumptions.",
            expected_properties={
                "max_score": {EpistemicCriterion.ASSUMPTION_TRANSPARENCY: 2.5},
                "failed": [EpistemicCriterion.ASSUMPTION_TRANSPARENCY],
            },
            session_builder=_build_scenario_10,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-11-explicit-assumption",
            description="Proposal explicitly declares 20% volume growth with rationale and invalidation condition.",
            expected_properties={
                "min_score": {EpistemicCriterion.ASSUMPTION_TRANSPARENCY: 4.5},
                "passed": [EpistemicCriterion.ASSUMPTION_TRANSPARENCY],
            },
            session_builder=_build_scenario_11,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-12-unknown-ignored",
            description="Problem context specifies critical unknown peak throughput, but proposals ignore it completely.",
            expected_properties={
                "max_score": {EpistemicCriterion.UNKNOWN_VISIBILITY: 2.5},
                "failed": [EpistemicCriterion.UNKNOWN_VISIBILITY],
            },
            session_builder=_build_scenario_12,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-13-conditional-recommendation",
            description="Proposal formulates guarded conditional recommendations (IF throughput > X THEN shard database).",
            expected_properties={
                "min_score": {EpistemicCriterion.RECOMMENDATION_GROUNDING: 4.5},
                "passed": [EpistemicCriterion.RECOMMENDATION_GROUNDING],
            },
            session_builder=_build_scenario_13,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-14-proper-uncertainty",
            description="Decision record emits INSUFFICIENT_EVIDENCE and acknowledges critical unknown metrics.",
            expected_properties={
                "min_score": {
                    EpistemicCriterion.UNKNOWN_VISIBILITY: 4.5,
                    EpistemicCriterion.EPISTEMIC_INTEGRITY: 4.5,
                },
                "passed": [
                    EpistemicCriterion.UNKNOWN_VISIBILITY,
                    EpistemicCriterion.EPISTEMIC_INTEGRITY,
                ],
            },
            session_builder=_build_scenario_14,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-15-setor-azul-subinformed",
            description="Subinformed deliberation where critical unknowns must force INSUFFICIENT_EVIDENCE.",
            expected_properties={
                "min_score": {
                    EpistemicCriterion.UNKNOWN_VISIBILITY: 4.5,
                    EpistemicCriterion.EPISTEMIC_INTEGRITY: 4.5,
                },
                "passed": [
                    EpistemicCriterion.UNKNOWN_VISIBILITY,
                    EpistemicCriterion.EPISTEMIC_INTEGRITY,
                ],
            },
            session_builder=_build_scenario_15,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-16-setor-azul-informed",
            description="Informed deliberation with genuine divergence, explicit trade-off contract and traceable decision.",
            expected_properties={
                "min_score": {
                    EvaluationCriterion.PROPOSAL_DIVERGENCE: 4.0,
                    EvaluationCriterion.TRADE_OFF_EXPLICITNESS: 4.0,
                    EvaluationCriterion.DECISION_TRACEABILITY: 4.0,
                },
                "passed": [
                    EvaluationCriterion.PROPOSAL_DIVERGENCE,
                    EvaluationCriterion.TRADE_OFF_EXPLICITNESS,
                    EvaluationCriterion.DECISION_TRACEABILITY,
                ],
            },
            session_builder=_build_scenario_16,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-17-setor-azul-contradictory",
            description="Contradictory user input registered in conflicts rather than silently resolved.",
            expected_properties={
                "has_conflicts": True,
            },
            session_builder=_build_scenario_17,
        )
    )

    reg.register(
        BenchmarkScenario(
            id="scenario-18-legitimate-consensus",
            description="Minimal workload where both agents legitimately converge on simple solution without artificial conflict.",
            expected_properties={
                "min_score": {
                    EvaluationCriterion.DECISION_TRACEABILITY: 4.0,
                    EvaluationCriterion.HUMAN_SOVEREIGNTY: 4.0,
                },
                "passed": [
                    EvaluationCriterion.DECISION_TRACEABILITY,
                    EvaluationCriterion.HUMAN_SOVEREIGNTY,
                ],
            },
            session_builder=_build_scenario_18,
        )
    )

    return reg
