"""Unit tests verifying Epistemic Discipline evaluation functions and criteria."""

from uuid import uuid4
import pytest

from schemas.common import CommitteeRole, Confidence, DecisionStatus, Severity
from schemas.context import Fact, ProblemContext, Unknown
from schemas.decision import DecisionRecord
from schemas.epistemic import (
    AssumptionItem,
    ConditionalRecommendation,
    EpistemicSection,
    FactItem,
    InferenceItem,
    RecommendationItem,
    UnknownItem,
)
from schemas.proposals import ArchitectProposal, CostEstimate, EffortLevel, ReversibilityAssessment, ReversibilityLevel
from src.committee.evaluation.criteria import (
    evaluate_assumption_transparency,
    evaluate_epistemic_integrity,
    evaluate_fact_grounding,
    evaluate_inference_traceability,
    evaluate_recommendation_grounding,
    evaluate_unknown_visibility,
)
from src.committee.evaluation.models import EpistemicCriterion
from src.committee.evaluation.scenarios import _build_base_session
from src.committee.session import Session


@pytest.fixture
def base_session() -> Session:
    return _build_base_session(uuid4())


def test_fact_grounding_passes_when_all_facts_are_in_context(base_session: Session) -> None:
    """Proposals containing only grounded facts must score 5.0."""
    score_obj, findings = evaluate_fact_grounding(base_session)
    assert score_obj.criterion == EpistemicCriterion.FACT_GROUNDING
    assert score_obj.score == 5.0
    assert score_obj.passed is True
    assert len(findings) == 0


def test_fact_grounding_detects_invented_quantitative_claim_in_facts(base_session: Session) -> None:
    """Invented quantitative facts (>10) absent from context must be flagged."""
    prop = base_session.proposals[CommitteeRole.ARCHITECT]
    invented_fact = FactItem(
        id="FACT-INV",
        statement="O sistema atual possui 95000 usuários ativos diários.",
        source="unverified",
        verified=False,
    )
    new_facts = list(prop.epistemic_section.facts) + [invented_fact]
    base_session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={"epistemic_section": prop.epistemic_section.model_copy(update={"facts": new_facts})}
    )

    score_obj, findings = evaluate_fact_grounding(base_session)
    assert score_obj.score <= 2.0
    assert score_obj.passed is False
    assert any(f.id == "F-EPI-FACT-01" for f in findings)


def test_fact_grounding_detects_invented_throughput_in_text(base_session: Session) -> None:
    """Claims like '50000 req/s' in proposal text without assumption declaration must fail."""
    prop = base_session.proposals[CommitteeRole.ARCHITECT]
    base_session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={"solution": "Cluster processando 50000 req/s em produção."}
    )

    score_obj, findings = evaluate_fact_grounding(base_session)
    assert score_obj.score <= 2.0
    assert score_obj.passed is False
    assert any(f.id == "F-EPI-FACT-01" for f in findings)


def test_assumption_transparency_detects_hidden_growth_hypothesis(base_session: Session) -> None:
    """Hypotheses of volume growth or learning curve without declared assumptions must fail."""
    prop = base_session.proposals[CommitteeRole.ARCHITECT]
    base_session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={
            "solution": "Arquitetura dimensionada para crescimento contínuo de 20% no tráfego.",
            "rationale": "A equipe aprenderá em 2 semanas.",
            "assumptions": [],
            "epistemic_section": prop.epistemic_section.model_copy(update={"assumptions": []}),
        }
    )

    score_obj, findings = evaluate_assumption_transparency(base_session)
    assert score_obj.score <= 2.5
    assert score_obj.passed is False
    assert any(f.id == "F-EPI-ASM-01" for f in findings)


def test_assumption_transparency_passes_when_explicitly_declared(base_session: Session) -> None:
    """Hypotheses declared in assumptions with invalidation condition must pass."""
    prop = base_session.proposals[CommitteeRole.ARCHITECT]
    asm = AssumptionItem(
        id="A-GROWTH",
        statement="Crescimento de 20% no tráfego",
        reason="Projeção comercial",
        confidence=Confidence.MEDIUM,
        invalidation_condition="Se tráfego crescer menos de 5% no semestre",
    )
    base_session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={
            "solution": "Arquitetura dimensionada para crescimento de 20% no tráfego.",
            "assumptions": ["Crescimento de 20% no tráfego"],
            "epistemic_section": prop.epistemic_section.model_copy(update={"assumptions": [asm]}),
        }
    )

    score_obj, findings = evaluate_assumption_transparency(base_session)
    assert score_obj.score >= 4.5
    assert score_obj.passed is True


def test_unknown_visibility_flags_ignored_context_unknowns(base_session: Session) -> None:
    """Critical unknowns in ProblemContext that are ignored by proposals must be flagged."""
    base_session.problem_context = base_session.problem_context.model_copy(
        update={
            "unknowns": [
                Unknown(
                    id="U-PEAK",
                    description="Taxa de pico de requisições por segundo durante campanhas é desconhecida.",
                    impact_if_adverse=Severity.HIGH,
                )
            ]
        }
    )
    prop_a = base_session.proposals[CommitteeRole.ARCHITECT]
    prop_b = base_session.proposals[CommitteeRole.PRAGMATIST]
    base_session.proposals[CommitteeRole.ARCHITECT] = prop_a.model_copy(
        update={
            "solution": "Standalone microservice.",
            "rationale": "Simple service architecture.",
            "epistemic_section": prop_a.epistemic_section.model_copy(
                update={"unknowns": [], "conditional_recommendations": []}
            ),
        }
    )
    base_session.proposals[CommitteeRole.PRAGMATIST] = prop_b.model_copy(
        update={
            "solution": "Basic monolith.",
            "rationale": "Simple monolith architecture.",
            "epistemic_section": prop_b.epistemic_section.model_copy(
                update={"unknowns": [], "conditional_recommendations": []}
            ),
        }
    )

    score_obj, findings = evaluate_unknown_visibility(base_session)
    assert score_obj.score <= 2.5
    assert score_obj.passed is False
    assert any(f.id == "F-EPI-UNK-01" for f in findings)


def test_inference_traceability_detects_broken_dependencies(base_session: Session) -> None:
    """Inferences referencing non-existent Fact or Assumption IDs must fail."""
    prop = base_session.proposals[CommitteeRole.ARCHITECT]
    inf = InferenceItem(
        id="I-BROKEN",
        statement="Database connection saturation is imminent",
        rationale="Connection pools will deplete under load",
        depends_on=["F-NON-EXISTENT", "A-GHOST"],
    )
    base_session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={"epistemic_section": prop.epistemic_section.model_copy(update={"inferences": [inf]})}
    )

    score_obj, findings = evaluate_inference_traceability(base_session)
    assert score_obj.score <= 2.0
    assert score_obj.passed is False
    assert any(f.id == "F-EPI-INF-01" for f in findings)


def test_recommendation_grounding_detects_ungrounded_heavy_infrastructure(base_session: Session) -> None:
    """Recommending heavy tools like Kafka/sharding without factual throughput or IF condition must fail."""
    prop = base_session.proposals[CommitteeRole.ARCHITECT]
    base_session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={
            "solution": "Adotar cluster Kafka multi-region com sharding de banco de dados distribuído.",
            "rationale": "Para garantir alta escalabilidade futura.",
            "epistemic_section": prop.epistemic_section.model_copy(update={"conditional_recommendations": []}),
        }
    )

    score_obj, findings = evaluate_recommendation_grounding(base_session)
    assert score_obj.score <= 2.0
    assert score_obj.passed is False
    assert any(f.id == "F-EPI-REC-01" for f in findings)


def test_recommendation_grounding_passes_with_conditional_guardrails(base_session: Session) -> None:
    """Heavy tools guarded by conditional recommendations (IF ... THEN ...) must pass."""
    prop = base_session.proposals[CommitteeRole.ARCHITECT]
    cr = ConditionalRecommendation(
        condition="IF pico de requisições ultrapassar 5.000 req/s",
        recommendation="THEN provisionar cluster Kafka e particionar o banco",
        evidence=["F1"],
    )
    base_session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={
            "solution": "Manter PostgreSQL. IF pico de requisições ultrapassar 5.000 req/s THEN provisionar cluster Kafka.",
            "epistemic_section": prop.epistemic_section.model_copy(update={"conditional_recommendations": [cr]}),
        }
    )

    score_obj, findings = evaluate_recommendation_grounding(base_session)
    assert score_obj.score >= 4.5
    assert score_obj.passed is True


def test_epistemic_integrity_composite_penalizes_critical_epistemic_failure(base_session: Session) -> None:
    """A critical failure in any epistemic dimension must cap epistemic integrity at <= 2.0."""
    prop = base_session.proposals[CommitteeRole.ARCHITECT]
    new_facts = list(prop.epistemic_section.facts) + [
        FactItem(
            id="FACT-INV",
            statement="O sistema atual processa 80000 transações por segundo.",
            source="unverified",
            verified=False,
        )
    ]
    base_session.proposals[CommitteeRole.ARCHITECT] = prop.model_copy(
        update={"epistemic_section": prop.epistemic_section.model_copy(update={"facts": new_facts})}
    )

    score_obj, findings = evaluate_epistemic_integrity(base_session)
    assert score_obj.criterion == EpistemicCriterion.EPISTEMIC_INTEGRITY
    assert score_obj.score <= 2.0
    assert score_obj.passed is False
    assert any(f.id == "F-EPI-INT-01" for f in findings)
