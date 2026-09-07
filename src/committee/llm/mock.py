"""Deterministic Mock LLM Provider producing schema-valid artifacts for testing."""

from typing import Any, Callable

from pydantic import BaseModel

from src.committee.llm.provider import LLMCallMetadata

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import CommitteeRole, Confidence, DecisionStatus, Severity
from schemas.context import (
    Assumption,
    BudgetContext,
    Constraint,
    ConstraintType,
    ContextDelta,
    Fact,
    OpenQuestion,
    OperationalContext,
    ProblemContext,
    TeamContext,
    TimeContext,
    Unknown,
)
from schemas.decision import (
    AcceptedRisk,
    DecisionRecord,
    RejectedAlternative,
    ReviewTrigger,
    TradeOffContract,
)
from schemas.defense import (
    ArchitectDefense,
    CritiqueResponse,
    DefenseStance,
    PragmaticDefense,
    ProposalAction,
)
from schemas.epistemic import (
    AssumptionItem,
    ConditionalRecommendation,
    EpistemicSection,
    FactItem,
    InferenceItem,
    RecommendationItem,
    UnknownItem,
)
from schemas.learning import (
    EpistemicLesson,
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


class MockLLMProvider:
    """Mock implementation of LLMProvider producing deterministic, schema-valid artifacts.

    Allows unit and integration testing without external LLM calls.
    """

    def __init__(
        self,
        custom_generators: dict[type[BaseModel], Callable[[dict[str, Any]], BaseModel]] | None = None,
        failure_counts: dict[type[BaseModel], int] | None = None,
    ) -> None:
        self.custom_generators = custom_generators or {}
        self.failure_counts = failure_counts or {}
        self.call_history: list[dict[str, Any]] = []
        self.last_metadata: LLMCallMetadata | None = None
        self.metadata_history: list[LLMCallMetadata] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        input_context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Generate a valid mock instance matching the requested output_schema."""
        self.call_history.append(
            {
                "system_prompt": system_prompt,
                "input_context": input_context,
                "output_schema": output_schema,
            }
        )

        self.last_metadata = LLMCallMetadata(
            model="mock-deterministic",
            latency_seconds=0.001,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )
        self.metadata_history.append(self.last_metadata)

        # Handle programmed failure count (for testing retries)
        if output_schema in self.failure_counts and self.failure_counts[output_schema] > 0:
            self.failure_counts[output_schema] -= 1
            raise ValueError(
                f"Simulated LLM generation failure for schema {output_schema.__name__}."
            )

        # Check for custom generator
        if output_schema in self.custom_generators:
            return self.custom_generators[output_schema](input_context)

        # Default deterministic generator by schema
        return self._generate_default(output_schema, input_context)

    def _generate_default(
        self, output_schema: type[BaseModel], input_context: dict[str, Any]
    ) -> BaseModel:
        problem_text = input_context.get("problem_statement") or "Deliberation problem statement."

        if output_schema == ProblemContext:
            return ProblemContext(
                artifact_id="CTX-001",
                version=1,
                problem=problem_text,
                facts=[
                    Fact(id="F1", description="PostgreSQL 15 single instance 16GB", source="User input")
                ],
                constraints=[
                    Constraint(id="C1", description="Monthly budget under $200", type=ConstraintType.BUDGET, negotiable=False),
                    Constraint(id="C2", description="Delivery in 4 weeks", type=ConstraintType.DEADLINE, negotiable=False),
                ],
                assumptions=[
                    Assumption(id="A1", description="Traffic stays under 500 req/s in Q1", rationale="User projection", risk_level=Severity.MEDIUM)
                ],
                unknowns=[
                    Unknown(id="U1", description="Third-party gateway latency under load", impact_if_adverse=Severity.HIGH)
                ],
                open_questions=[],
                success_criteria=["Latency p95 < 50ms", "Deployment within 4 weeks"],
                team_context=TeamContext(team_size=3, skill_level="Intermediate"),
                budget_context=BudgetContext(max_monthly_budget=200.0),
                time_context=TimeContext(expected_duration="4 weeks"),
                operational_context=OperationalContext(current_infrastructure=["AWS ECS", "RDS"]),
            )

        elif output_schema == ArchitectProposal:
            return ArchitectProposal(
                artifact_id="PROP-ARCH-001",
                version=1,
                title="Event-Driven Microservices Architecture",
                solution="Decouple domain services with durable Kafka streaming and schema registry.",
                rationale="Ensures long-term modularity and independent service evolution without structural debt.",
                benefits=["High domain decoupling", "Independent horizontal scalability"],
                costs=CostEstimate(
                    implementation_effort=EffortLevel.HIGH,
                    infrastructure_cost_estimate="$180/mo",
                    additional_costs=["Schema governance overhead"],
                ),
                risks=["Distributed tracing overhead", "Event schema drift"],
                complexity=Severity.HIGH,
                reversibility=ReversibilityAssessment(
                    score=ReversibilityLevel.LOW,
                    rationale="Event contracts deeply embedded in services make rollback expensive.",
                ),
                future_implications="Prepares platform for multi-region active-active deployment.",
                assumptions=["Team acquires event streaming competencies in 2 weeks."],
                invalidation_conditions=["Sustained traffic drops below 10 req/s permanently."],
                modularity_strategy="Strict schema contracts enforced via CI/CD.",
                evolution_path="Phase 1: Outbox pattern; Phase 2: Native streaming.",
                epistemic_section=EpistemicSection(
                    facts=[
                        FactItem(id="F1", statement="PostgreSQL 15 single instance 16GB", source="User input"),
                    ],
                    assumptions=[
                        AssumptionItem(
                            id="A1",
                            statement="Traffic will reach 1,500 req/s during peak sales",
                            reason="Anticipated product campaign growth",
                            confidence=Confidence.MEDIUM,
                            invalidation_condition="Throughput remains below 50 req/s permanently",
                        ),
                    ],
                    inferences=[
                        InferenceItem(
                            id="I1",
                            statement="Direct synchronous database writes will bottleneck during marketing spikes",
                            rationale="Single instance connection pool will saturate without asynchronous buffering",
                            depends_on=["F1", "A1"],
                            confidence=Confidence.HIGH,
                        ),
                    ],
                    unknowns=[
                        UnknownItem(
                            id="U1",
                            statement="Third-party payment gateway latency and concurrency limits under heavy load",
                            impact_if_adverse=Severity.HIGH,
                        ),
                    ],
                    conditional_recommendations=[
                        ConditionalRecommendation(
                            condition="IF sustained event volume exceeds 2,000 events/s",
                            recommendation="THEN upgrade from Redis Streams to multi-broker Kafka cluster",
                            evidence=["F1", "A1", "I1"],
                        ),
                    ],
                    recommendations=[
                        RecommendationItem(
                            id="R1",
                            statement="Decouple domain services using asynchronous message streaming",
                            rationale="Ensures transactional isolation and prevents cascade failures",
                            depends_on=["I1"],
                        ),
                    ],
                ),
            )

        elif output_schema == PragmaticProposal:
            return PragmaticProposal(
                artifact_id="PROP-PRAG-001",
                version=1,
                title="Modular Monolith with Background Workers",
                solution="Single deployable Python service using Postgres and Celery for async processing.",
                rationale="Maximizes time-to-value by delivering in 10 days with minimal operational complexity.",
                benefits=["Immediate delivery", "Single codebase and low maintenance cost"],
                costs=CostEstimate(
                    implementation_effort=EffortLevel.LOW,
                    infrastructure_cost_estimate="$35/mo",
                ),
                risks=["Potential database connection pool saturation under bursts"],
                complexity=Severity.LOW,
                reversibility=ReversibilityAssessment(
                    score=ReversibilityLevel.HIGH,
                    rationale="Can easily replace Celery with external broker if scale demands it.",
                ),
                future_implications="May require dedicated Redis broker when traffic grows 10x.",
                assumptions=["Existing Postgres instance handles queue I/O."],
                invalidation_conditions=["Peak transactions exceed 2,000 req/s."],
                time_to_value="10 business days",
                simplifications_made=["No distributed event broker", "Synchronous HTTP for internal flows"],
                epistemic_section=EpistemicSection(
                    facts=[
                        FactItem(id="F1", statement="PostgreSQL 15 single instance 16GB", source="User input"),
                    ],
                    assumptions=[
                        AssumptionItem(
                            id="A1",
                            statement="Existing Postgres instance handles queue I/O comfortably",
                            reason="Traffic projections for Q1 remain moderate",
                            confidence=Confidence.HIGH,
                            invalidation_condition="Peak transactions exceed 2,000 req/s",
                        ),
                    ],
                    inferences=[
                        InferenceItem(
                            id="I1",
                            statement="Celery workers on Postgres deliver required functionality with zero added infra",
                            rationale="Existing RDS instance handles background tasks without extra services",
                            depends_on=["F1", "A1"],
                            confidence=Confidence.HIGH,
                        ),
                    ],
                    unknowns=[
                        UnknownItem(
                            id="U1",
                            statement="Sustained transaction throughput capacity of Postgres queue under surge",
                            impact_if_adverse=Severity.HIGH,
                        ),
                    ],
                    conditional_recommendations=[
                        ConditionalRecommendation(
                            condition="IF database connection pool saturation exceeds 80%",
                            recommendation="THEN provision dedicated Redis instance for background queues",
                            evidence=["F1", "A1"],
                        ),
                    ],
                    recommendations=[
                        RecommendationItem(
                            id="R1",
                            statement="Modular monolith with Celery background workers",
                            rationale="Maximizes time to value and keeps operational cost at $35/mo",
                            depends_on=["I1"],
                        ),
                    ],
                ),
            )

        elif output_schema == AuditReport:
            return AuditReport(
                artifact_id="AUD-001",
                version=1,
                target_proposal_a_id="PROP-ARCH-001",
                target_proposal_b_id="PROP-PRAG-001",
                findings_proposal_a=[
                    AuditFinding(
                        id="F-01",
                        target_proposal_id="PROP-ARCH-001",
                        category=AuditCategory.OVERENGINEERING,
                        severity=Severity.HIGH,
                        title="Excessive Kafka broker infrastructure for 500 req/s",
                        description="Managing Kafka clusters for 500 req/s introduces disproportionate ops burden.",
                        justification="Redis Streams or lightweight pub/sub satisfies throughput with 80% less effort.",
                    )
                ],
                findings_proposal_b=[
                    AuditFinding(
                        id="F-02",
                        target_proposal_id="PROP-PRAG-001",
                        category=AuditCategory.SINGLE_POINTS_OF_FAILURE,
                        severity=Severity.HIGH,
                        title="Single database instance SPOF",
                        description="Monolith proposal relies on single Postgres node without automatic failover.",
                        justification="Disk failure or host outage causes total downtime.",
                    )
                ],
                single_points_of_failure=["Standalone database in Proposal B"],
                hidden_costs=["Kafka maintenance and ZooKeeper/KRaft monitoring overhead in A"],
                fragile_assumptions=["Assumes team can learn Kafka in 2 weeks"],
                overengineering_risks=["Avro schema registry for small team in A"],
                underengineering_risks=["No circuit breaker on internal HTTP calls in B"],
                questions_for_proponents=["How does Proposal B mitigate connection pool exhaustion?"],
            )

        elif output_schema == ArchitectDefense:
            return ArchitectDefense(
                artifact_id="DEF-ARCH-001",
                version=1,
                original_proposal_id="PROP-ARCH-001",
                original_proposal_version=1,
                critique_responses=[
                    CritiqueResponse(
                        finding_id="F-01",
                        stance=DefenseStance.CONCEDED_WITH_REFINEMENT,
                        response="Concede that full Kafka cluster is excessive for initial launch.",
                        rationale="Redis Streams provides required async semantics with 90% lower operational footprint.",
                        proposed_modification="Replace Kafka brokers with managed Redis Streams cluster.",
                    )
                ],
                proposal_action=ProposalAction.MODIFY,
                revised_proposal_id="PROP-ARCH-001",
                revised_proposal_version=2,
                persistent_disagreements=["Still reject synchronous RPC calls between core domains."],
            )

        elif output_schema == PragmaticDefense:
            return PragmaticDefense(
                artifact_id="DEF-PRAG-001",
                version=1,
                original_proposal_id="PROP-PRAG-001",
                original_proposal_version=1,
                critique_responses=[
                    CritiqueResponse(
                        finding_id="F-02",
                        stance=DefenseStance.CONCEDED_WITH_REFINEMENT,
                        response="Concede the single-point-of-failure risk.",
                        rationale="Enable AWS RDS Multi-AZ automated failover and PgBouncer connection pooling.",
                        proposed_modification="Add PgBouncer and RDS Multi-AZ replication.",
                    )
                ],
                proposal_action=ProposalAction.MODIFY,
                revised_proposal_id="PROP-PRAG-001",
                revised_proposal_version=2,
            )

        elif output_schema == DeliberationSynthesis:
            return DeliberationSynthesis(
                artifact_id="SYN-001",
                version=1,
                consolidated_facts=["Existing Postgres database", "Budget under $200/mo", "Deadline in 4 weeks"],
                consolidated_assumptions=["Traffic grows moderately in Q1"],
                consolidated_inferences=["Synchronous direct writes cause connection pool bottleneck; Celery on Postgres is viable short-term, Redis Streams is future upgrade path"],
                consolidated_unknowns=["Peak payment gateway concurrency under load"],
                consensus_points=[
                    "Both agree Kafka is excessive for current needs",
                    "Both agree on Postgres relational persistence",
                ],
                divergence_points=[
                    "Lightweight Redis Streams (Architect) vs Celery on Postgres (Pragmatist)",
                ],
                arguments_by_alternative={
                    "PROPOSAL_A": ["Higher decoupling", "Easier future extension"],
                    "PROPOSAL_B": ["Lower complexity", "Deployment ready in 10 days"],
                },
                unresolved_risks=["Database connection saturation during marketing spikes"],
                trade_offs=[
                    TradeOffDimension(
                        dimension="Time to Market",
                        option_a="3-4 weeks (Redis Streams setup)",
                        option_b="10 days (Celery on Postgres)",
                        notes="Option B is 2x faster to deploy.",
                    )
                ],
                open_questions=["Can marketing guarantee 48-hour advance notice before campaigns?"],
            )

        elif output_schema == DecisionRecord:
            return DecisionRecord(
                artifact_id="DEC-001",
                version=1,
                status=DecisionStatus.RECOMMENDED,
                recommendation="Adopt Pragmatic Proposal v2 (Celery on Postgres with PgBouncer connection pool).",
                chosen_alternative="PROPOSAL_PRAG_V2",
                rejected_alternatives=[
                    RejectedAlternative(
                        name="PROPOSAL_ARCH_V2",
                        rejection_reason="Redis Streams adds extra operational surface when 4-week deadline is non-negotiable.",
                    )
                ],
                rationale="Meets all throughput and budget requirements within the 4-week deadline. PgBouncer mitigates connection exhaustion.",
                trade_offs=[
                    TradeOffContract(
                        gain="Time to market in 10 days and $35/mo infrastructure cost",
                        sacrifice="Temporal coupling between tasks and relational database",
                    )
                ],
                accepted_risks=[
                    AcceptedRisk(
                        risk="Worker restart drops in-flight memory state",
                        severity=Severity.LOW,
                        mitigation="Celery task acknowledgment enabled",
                    )
                ],
                technical_debt=["Eventual migration to dedicated queue if scale exceeds 1,000 req/s"],
                operational_debt=["Monitoring PgBouncer pool utilization"],
                critical_assumptions=["Peak traffic remains under 500 req/s in Q1"],
                review_triggers=[
                    ReviewTrigger(
                        condition="Traffic sustained above 800 req/s for 3 consecutive days",
                        metric_threshold="800 req/s",
                        trigger_type="METRIC",
                    )
                ],
                confidence=Confidence.HIGH,
                supported_by=["F1"],
                depends_on=["A1"],
                uncertainties=["U1"],
                conditional_recommendations=[
                    ConditionalRecommendation(
                        condition="IF traffic sustained above 800 req/s for 3 consecutive days",
                        recommendation="THEN migrate from Postgres queue to dedicated Redis queue",
                        evidence=["F1", "A1"],
                    )
                ],
            )

        elif output_schema == LearningReport:
            return LearningReport(
                artifact_id="LRN-001",
                version=1,
                concepts=["CAP Theorem", "Connection Pool Sizing", "Thundering Herd Problem"],
                concepts_required_to_understand_decision=[
                    "Differences between synchronous RPC and background task queues",
                    "Impact of database connection saturation under concurrency",
                ],
                observed_knowledge_gaps=[
                    ObservedKnowledgeGap(
                        observation="Initial requirements assumed queueing automatically solves database saturation.",
                        context_evidence="Problem framing where user assumed Celery eliminates backend load.",
                        recommended_topic="Queue backpressure and rate limiting.",
                    )
                ],
                epistemic_lessons=[
                    EpistemicLesson(
                        concept="Trade-off between Scalability and Operational Simplicity",
                        debate_example="Architect proposed Kafka cluster based on projected traffic growth",
                        epistemic_confusion="Projected growth was an assumption, not an established fact",
                        study_topic="Architectural assumptions, capacity planning, and YAGNI principle",
                    )
                ],
                study_questions=[
                    "Why does placing a queue in front of a slow database only buffer latency rather than solve throughput?"
                ],
                learning_path=[
                    LearningPathStep(
                        order=1,
                        topic="Database Reliability",
                        description="Read chapters on connection management and connection pools.",
                        reference=LearningReference(
                            title="Designing Data-Intensive Applications",
                            url_or_citation="O'Reilly, Cap. 7",
                        ),
                    )
                ],
                theory_to_practice_connections=[
                    "The committee chose KISS over event-driven architecture because the current scale did not justify distributed event broker operational overhead."
                ],
                references=[
                    LearningReference(
                        title="Release It! Second Edition",
                        author="Michael Nygard",
                        url_or_citation="Pragmatic Bookshelf",
                    )
                ],
            )

        elif output_schema == ContextDelta:
            answered_questions = input_context.get("answered_questions", [])
            new_facts: list[Fact] = []
            new_assumptions: list[Assumption] = []
            new_unknowns: list[Unknown] = []
            new_constraints: list[Constraint] = []
            new_open_questions: list[OpenQuestion] = []
            identified_conflicts: list[str] = []
            source_q_ids: list[str] = []
            resolved_q_ids: list[str] = []

            for idx, item in enumerate(answered_questions, start=1):
                if isinstance(item, dict):
                    q_id = item.get("question_id", f"Q-{idx}")
                    ans = str(item.get("answer", "")).strip()
                    q_text = item.get("question", "")
                else:
                    q_id = getattr(item, "id", f"Q-{idx}")
                    ans = str(getattr(item, "answer", "")).strip()
                    q_text = getattr(item, "question", "")

                source_q_ids.append(q_id)
                ans_lower = ans.lower()

                unknown_signals = [
                    "não existe",
                    "preciso criar",
                    "desconhecido",
                    "ainda não temos",
                    "não temos",
                    "ainda não foi definido",
                    "não foi definido",
                    "a definir",
                    "tbd",
                    "unknown",
                ]
                conflict_signals = [
                    "conflito",
                    "contraditório",
                    "contradição",
                    "incompatível",
                ]

                if any(sig in ans_lower for sig in unknown_signals):
                    new_unknowns.append(
                        Unknown(
                            id=f"UNK-{len(new_unknowns) + 1:03d}",
                            description=f"Capacidade ausente ou requisito indefinido ({q_id}): {ans}",
                            impact_if_adverse=Severity.HIGH,
                            potential_resolution="Prover alternativa que dispense o componente ou prever esforço de provisionamento.",
                            decision_relevance=Severity.HIGH,
                            could_change_selected_alternative=True,
                            blocking=True,
                            mitigation="Prover alternativa que dispense o componente ou prever esforço de provisionamento.",
                        )
                    )
                    resolved_q_ids.append(q_id)
                elif any(sig in ans_lower for sig in conflict_signals):
                    identified_conflicts.append(
                        f"Conflito identificado na resposta à pergunta {q_id} ('{q_text}'): '{ans}' contradiz restrições ou premissas anteriores."
                    )
                    resolved_q_ids.append(q_id)
                elif ans:
                    new_facts.append(
                        Fact(
                            id=f"FACT-{len(new_facts) + 1:03d}",
                            description=f"Confirmado pelo usuário ({q_id}): {ans}",
                            source="user_response",
                        )
                    )
                    resolved_q_ids.append(q_id)

            return ContextDelta(
                delta_id=f"DELTA-{(len(resolved_q_ids) or 1):03d}",
                source_question_ids=source_q_ids,
                classification_basis="Classificação epistêmica determinística das respostas do usuário.",
                resolved_question_ids=resolved_q_ids,
                new_facts=new_facts,
                new_assumptions=new_assumptions,
                new_unknowns=new_unknowns,
                new_constraints=new_constraints,
                new_open_questions=new_open_questions,
                identified_conflicts=identified_conflicts,
            )

        raise ValueError(f"MockLLMProvider does not have default generator for {output_schema.__name__}")
