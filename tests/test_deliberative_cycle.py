"""Deterministic tests for the enhanced deliberative cycle in the AI Committee."""

import asyncio
from uuid import uuid4

import pytest

from schemas.audit import AuditCategory, AuditFinding, AuditReport
from schemas.common import (
    CommitteeRole,
    CommitteeState,
    Confidence,
    DecisionStatus,
    EventType,
    Severity,
)
from schemas.context import (
    Constraint,
    ConstraintType,
    ContextDelta,
    Fact,
    OpenQuestion,
    ProblemContext,
    Unknown,
    apply_context_delta,
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
from schemas.events import EventEnvelope, QuestionRaisedPayload, UserRespondedPayload
from schemas.proposals import (
    ArchitectProposal,
    CostEstimate,
    EffortLevel,
    PragmaticProposal,
    ReversibilityAssessment,
    ReversibilityLevel,
)
from schemas.synthesis import DeliberationSynthesis, TradeOffDimension
from src.committee.event_store import EventStore
from src.committee.gates import gate_decision_exit
from src.committee.evaluation.evaluator import DeterministicEvaluator
from src.committee.evaluation.models import EpistemicCriterion, EvaluationCriterion, EvaluationMetadata
from src.committee.evaluation.scenarios import create_default_scenario_registry
from src.committee.llm.mock import MockLLMProvider
from src.committee.orchestration.orchestrator import CommitteeOrchestrator
from src.committee.session import Session


def _build_base_deliberation_session() -> Session:
    """Construct an active session ready for decision evaluation."""
    provider = MockLLMProvider()
    session = Session(session_id=uuid4(), problem_statement="Setor Azul lead ingestion.")
    session.problem_context = provider._generate_default(ProblemContext, {})
    session.proposals[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectProposal, {})
    session.proposals[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticProposal, {})
    session.audit_report = provider._generate_default(AuditReport, {})
    session.defenses[CommitteeRole.ARCHITECT] = provider._generate_default(ArchitectDefense, {})
    session.defenses[CommitteeRole.PRAGMATIST] = provider._generate_default(PragmaticDefense, {})
    session.deliberation_synthesis = provider._generate_default(DeliberationSynthesis, {})
    return session


def test_investigation_incorporates_user_answers_into_context() -> None:
    """1. User answers during investigation generate ContextDelta and update ProblemContext (v1 -> v2)."""
    initial_ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Integração de leads do Setor Azul",
        facts=[Fact(id="F1", description="PostgreSQL 15 ativo", source="initial")],
        open_questions=[
            OpenQuestion(
                id="Q-VOL",
                question="Qual é o volume de pico de leads?",
                why_critical="Dimensionamento da ingestão",
                dimension="volumetry",
                answer="O volume de pico é 500 requisições por segundo durante campanhas.",
            )
        ],
        success_criteria=["Zero perda de leads"],
    )

    provider = MockLLMProvider()
    input_context = {
        "phase": "PHASE_0_INVESTIGATION",
        "action": "INTERPRET_RESPONSE",
        "answered_questions": [
            {
                "question_id": "Q-VOL",
                "question": "Qual é o volume de pico de leads?",
                "answer": "O volume de pico é 500 requisições por segundo durante campanhas.",
            }
        ],
    }

    delta = provider._generate_default(ContextDelta, input_context)
    assert isinstance(delta, ContextDelta)
    assert "Q-VOL" in delta.source_question_ids
    assert len(delta.new_facts) == 1
    assert "500 requisições por segundo" in delta.new_facts[0].description

    updated_ctx = apply_context_delta(initial_ctx, delta)
    assert updated_ctx.version == 2
    assert any("500 requisições" in f.description for f in updated_ctx.facts)
    assert updated_ctx.open_questions[0].incorporated is True
    assert not updated_ctx.has_unincorporated_answers()


def test_unknown_infrastructure_categorized_as_unknown_not_fact() -> None:
    """2. User stating 'não temos fila / preciso criar' becomes a blocking Unknown, NEVER a fact of ready capacity."""
    provider = MockLLMProvider()
    input_context = {
        "phase": "PHASE_0_INVESTIGATION",
        "action": "INTERPRET_RESPONSE",
        "answered_questions": [
            {
                "question_id": "Q-QUEUE",
                "question": "Existe infraestrutura de mensageria disponível?",
                "answer": "Ainda não temos fila, preciso criar do zero.",
            }
        ],
    }

    delta = provider._generate_default(ContextDelta, input_context)
    assert len(delta.new_facts) == 0, "Absent infrastructure must not become a Fact."
    assert len(delta.new_unknowns) == 1, "Absent infrastructure must become an Unknown."

    unk = delta.new_unknowns[0]
    assert unk.blocking is True
    assert unk.could_change_selected_alternative is True
    assert unk.decision_relevance == Severity.HIGH
    assert "Ainda não temos fila" in unk.description


def test_blocking_unknown_prevents_unconditional_recommendation() -> None:
    """3. Gate 5 deterministically blocks RECOMMENDED status when unmitigated blocking unknowns exist."""
    session = _build_base_deliberation_session()
    session.problem_context = session.problem_context.model_copy(
        update={
            "unknowns": [
                Unknown(
                    id="UNK-BLOCK-01",
                    description="Tolerância a indisponibilidade do CRM desconhecida.",
                    impact_if_adverse=Severity.CRITICAL,
                    decision_relevance=Severity.CRITICAL,
                    could_change_selected_alternative=True,
                    blocking=True,
                )
            ]
        }
    )

    unconditional_record = DecisionRecord(
        artifact_id="DEC-001",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        chosen_alternative="PROPOSAL_PRAG_V2",
        recommendation="Adopt Pragmatic Proposal v2 unconditionally.",
        rejected_alternatives=[RejectedAlternative(name="PROPOSAL_ARCH_V2", rejection_reason="Too complex")],
        rationale="Adopt simple approach ignoring the blocking unknown.",
        trade_offs=[TradeOffContract(gain="Speed", sacrifice="Coupling")],
        review_triggers=[ReviewTrigger(condition="Scale exceeds 1k req/s", metric_threshold="1000 req/s")],
        confidence=Confidence.MEDIUM,
        conditional_recommendations=[],
        accepted_risks=[],
    )

    envelope = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.DECISION_RECORDED,
        actor=CommitteeRole.DECISOR,
        payload=unconditional_record,
    )

    result = gate_decision_exit(session, envelope)
    assert result.passed is False
    assert "Cannot issue RECOMMENDED decision while blocking or decision-changing unknowns remain unmitigated" in (result.reason or "")
    assert "UNK-BLOCK-01" in (result.reason or "")


def test_insufficient_evidence_emitted_when_critical_unknowns_remain() -> None:
    """4. Gate 5 accepts INSUFFICIENT_EVIDENCE when critical unknowns remain and no false winner is chosen."""
    session = _build_base_deliberation_session()
    session.problem_context = session.problem_context.model_copy(
        update={
            "unknowns": [
                Unknown(
                    id="UNK-BLOCK-01",
                    description="Tolerância a downtime do CRM desconhecida.",
                    impact_if_adverse=Severity.CRITICAL,
                    decision_relevance=Severity.CRITICAL,
                    could_change_selected_alternative=True,
                    blocking=True,
                )
            ]
        }
    )

    insufficient_record = DecisionRecord(
        artifact_id="DEC-002",
        version=1,
        status=DecisionStatus.INSUFFICIENT_EVIDENCE,
        chosen_alternative=None,
        recommendation=None,
        rejected_alternatives=[],
        rationale="Impossível emitir recomendação definitiva sem mensurar o SLA de downtime do CRM e o custo de perda de lead.",
        trade_offs=[],
        accepted_risks=[],
        review_triggers=[],
        confidence=Confidence.LOW,
        information_that_could_change_decision=["Mapeamento do SLA de downtime do CRM (UNK-BLOCK-01)"],
        uncertainties=["UNK-BLOCK-01"],
    )

    envelope = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.DECISION_FAILED,
        actor=CommitteeRole.DECISOR,
        payload=insufficient_record,
    )

    result = gate_decision_exit(session, envelope)
    assert result.passed is True


def test_conditional_recommendation_accepted_with_unknowns() -> None:
    """5. Guarded recommendation (IF ... THEN ... ELSE ...) is accepted by Gate 5 even with blocking unknowns."""
    session = _build_base_deliberation_session()
    session.problem_context = session.problem_context.model_copy(
        update={
            "unknowns": [
                Unknown(
                    id="UNK-BLOCK-01",
                    description="Pico de concorrência desconhecido.",
                    impact_if_adverse=Severity.HIGH,
                    decision_relevance=Severity.HIGH,
                    could_change_selected_alternative=True,
                    blocking=True,
                )
            ]
        }
    )

    conditional_record = DecisionRecord(
        artifact_id="DEC-003",
        version=1,
        status=DecisionStatus.RECOMMENDED,
        chosen_alternative="PROPOSAL_PRAG_V2",
        recommendation="Adopt Pragmatic Proposal v2 subject to conditional threshold.",
        rejected_alternatives=[RejectedAlternative(name="PROPOSAL_ARCH_V2", rejection_reason="Excessive cost")],
        rationale="Pragmatic approach is viable under baseline conditions.",
        trade_offs=[TradeOffContract(gain="Speed", sacrifice="Scalability")],
        review_triggers=[ReviewTrigger(condition="Pico > 1.000 req/s", metric_threshold="1000 req/s")],
        confidence=Confidence.MEDIUM,
        conditional_recommendations=[
            ConditionalRecommendation(
                condition="IF pico de concorrência exceder 1.000 req/s",
                recommendation="THEN migrar para Transactional Outbox com Redis Streams",
                evidence=["UNK-BLOCK-01"],
            )
        ],
    )

    envelope = EventEnvelope(
        session_id=session.session_id,
        event_type=EventType.DECISION_RECORDED,
        actor=CommitteeRole.DECISOR,
        payload=conditional_record,
    )

    result = gate_decision_exit(session, envelope)
    assert result.passed is True


def test_contradictory_user_answers_detected_as_conflicts() -> None:
    """6. Contradictory user answers are captured in conflicts rather than silently chosen."""
    provider = MockLLMProvider()
    input_context = {
        "phase": "PHASE_0_INVESTIGATION",
        "action": "INTERPRET_RESPONSE",
        "answered_questions": [
            {
                "question_id": "Q-SLA",
                "question": "Qual o requisito de throughput?",
                "answer": "Existe um conflito: exigem 50.000 req/s mas é incompatível com o orçamento de $50/mês.",
            }
        ],
    }

    delta = provider._generate_default(ContextDelta, input_context)
    assert len(delta.identified_conflicts) > 0
    assert any("conflito" in c.lower() for c in delta.identified_conflicts)

    base_ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Setor Azul",
        success_criteria=["Success"],
    )
    updated_ctx = apply_context_delta(base_ctx, delta)
    assert len(updated_ctx.conflicts) > 0


def test_architect_proposal_grounded_in_actual_context() -> None:
    """7. Architect cannot treat invented capacities as facts; unproven proposals fail fact grounding."""
    registry = create_default_scenario_registry()
    evaluator = DeterministicEvaluator()

    # Scenario 9 tests invented facts
    scen_invented = registry.get("scenario-09-invented-fact")
    session_invented = scen_invented.session_builder(uuid4())
    res_invented = evaluator.evaluate_session(session_invented, metadata=EvaluationMetadata(scenario_id=scen_invented.id))
    score_invented = res_invented.summary.epistemic_scores[EpistemicCriterion.FACT_GROUNDING]
    assert score_invented.score <= 2.5
    assert score_invented.passed is False

    # Scenario 13 tests proper conditional recommendations
    scen_grounded = registry.get("scenario-13-conditional-recommendation")
    session_grounded = scen_grounded.session_builder(uuid4())
    res_grounded = evaluator.evaluate_session(session_grounded, metadata=EvaluationMetadata(scenario_id=scen_grounded.id))
    score_grounded = res_grounded.summary.epistemic_scores[EpistemicCriterion.RECOMMENDATION_GROUNDING]
    assert score_grounded.score >= 4.5
    assert score_grounded.passed is True


def test_auditor_flags_presumed_capabilities() -> None:
    """8. Auditor actively audits and penalizes presumed capabilities via EPISTEMIC_RISK."""
    session = _build_base_deliberation_session()
    finding = AuditFinding(
        id="F-EPI-01",
        target_proposal_id=session.proposals[CommitteeRole.ARCHITECT].artifact_id,
        severity=Severity.HIGH,
        category=AuditCategory.EPISTEMIC_RISK,
        title="Capacidade presumida como fato pronto",
        description="A proposta do Arquiteto assume cluster Kafka com TLS existente, mas a infraestrutura não consta no ProblemContext.",
        justification="A infraestrutura existente possui apenas PostgreSQL; Kafka exigiria custo de provisionamento e equipe especializada.",
        impact="Custo operacional não orçado e risco de atraso na entrega",
    )

    session.audit_report = session.audit_report.model_copy(
        update={
            "findings_proposal_a": [finding],
        }
    )

    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id="test-auditor-flags"))
    adv_score = res.summary.criterion_scores[EvaluationCriterion.ADVERSARIAL_QUALITY]
    assert adv_score.score >= 4.0
    assert any(f.category == AuditCategory.EPISTEMIC_RISK for f in session.audit_report.all_findings())


def test_review_triggers_contain_measurable_metrics() -> None:
    """9. DecisionRecord review triggers require measurable thresholds and score high on reviewability."""
    registry = create_default_scenario_registry()
    evaluator = DeterministicEvaluator()

    scen = registry.get("scenario-16-setor-azul-informed")
    session = scen.session_builder(uuid4())
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    rev_score = res.summary.criterion_scores[EvaluationCriterion.REVIEWABILITY]
    assert rev_score.score >= 4.0
    assert rev_score.passed is True

    for trigger in session.decision_record.review_triggers:
        assert trigger.metric_threshold is not None
        assert len(trigger.metric_threshold) > 0


def test_full_setor_azul_informed_deliberation() -> None:
    """10. Full Setor Azul informed deliberation achieves divergence, explicit trade-offs and decision traceability."""
    registry = create_default_scenario_registry()
    scen = registry.get("scenario-16-setor-azul-informed")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    assert session.decision_record.status == DecisionStatus.RECOMMENDED
    assert session.decision_record.chosen_alternative == "PROP-ARCH-001"
    assert "Transactional Outbox" in session.decision_record.recommendation

    div_score = res.summary.criterion_scores[EvaluationCriterion.PROPOSAL_DIVERGENCE]
    tro_score = res.summary.criterion_scores[EvaluationCriterion.TRADE_OFF_EXPLICITNESS]
    dec_score = res.summary.criterion_scores[EvaluationCriterion.DECISION_TRACEABILITY]

    assert div_score.score >= 4.0
    assert tro_score.score >= 4.0
    assert dec_score.score >= 4.0
    assert div_score.passed is True
    assert tro_score.passed is True
    assert dec_score.passed is True
