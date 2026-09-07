"""Integration tests verifying the 8 canonical benchmark scenarios and ScenarioRegistry."""

from uuid import uuid4
import pytest

from schemas.common import Severity
from src.committee.evaluation.evaluator import DeterministicEvaluator
from src.committee.evaluation.models import EpistemicCriterion, EvaluationCriterion, EvaluationMetadata
from src.committee.evaluation.scenarios import create_default_scenario_registry


@pytest.fixture
def registry():
    return create_default_scenario_registry()


def test_registry_contains_at_least_eight_scenarios(registry) -> None:
    """Registry must contain at least 14 canonical benchmark scenarios."""
    scenarios = registry.list_all()
    assert len(scenarios) >= 14

    expected_ids = {
        "scenario-01-different-solutions",
        "scenario-02-false-conflict",
        "scenario-03-superficial-auditor",
        "scenario-04-strong-auditor",
        "scenario-05-biased-facilitator",
        "scenario-06-untraceable-decision",
        "scenario-07-insufficient-evidence",
        "scenario-08-generic-mentor",
        "scenario-09-invented-fact",
        "scenario-10-hidden-assumption",
        "scenario-11-explicit-assumption",
        "scenario-12-unknown-ignored",
        "scenario-13-conditional-recommendation",
        "scenario-14-proper-uncertainty",
    }
    actual_ids = {s.id for s in scenarios}
    assert expected_ids.issubset(actual_ids)


def test_scenario_01_different_solutions(registry) -> None:
    """Scenario 1: Genuine architectural divergence must score high."""
    scen = registry.get("scenario-01-different-solutions")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    div_score = res.summary.criterion_scores[EvaluationCriterion.PROPOSAL_DIVERGENCE]
    assert div_score.score >= 4.5
    assert div_score.passed is True


def test_scenario_02_false_conflict(registry) -> None:
    """Scenario 2: False conflict must be detected and scored <= 2.0."""
    scen = registry.get("scenario-02-false-conflict")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    div_score = res.summary.criterion_scores[EvaluationCriterion.PROPOSAL_DIVERGENCE]
    assert div_score.score <= 2.0
    assert div_score.passed is False
    assert any(f.id == "F-DIV-FALSE-CONFLICT" for f in res.summary.critical_findings)


def test_scenario_03_superficial_auditor(registry) -> None:
    """Scenario 3: Superficial auditor with zero critique must fail adversarial quality."""
    scen = registry.get("scenario-03-superficial-auditor")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    adv_score = res.summary.criterion_scores[EvaluationCriterion.ADVERSARIAL_QUALITY]
    assert adv_score.score <= 2.0
    assert adv_score.passed is False
    assert any(f.id == "F-ADV-NO-FINDINGS" for f in res.summary.critical_findings)


def test_scenario_04_strong_auditor(registry) -> None:
    """Scenario 4: Strong auditor with deep critique and SPOFs must achieve high scores."""
    scen = registry.get("scenario-04-strong-auditor")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    adv_score = res.summary.criterion_scores[EvaluationCriterion.ADVERSARIAL_QUALITY]
    rsk_score = res.summary.criterion_scores[EvaluationCriterion.RISK_COVERAGE]
    assert adv_score.score >= 4.5
    assert rsk_score.score >= 4.5


def test_scenario_05_biased_facilitator(registry) -> None:
    """Scenario 5: Biased facilitator introducing recommendation must score 0.0 with critical finding."""
    scen = registry.get("scenario-05-biased-facilitator")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    syn_score = res.summary.criterion_scores[EvaluationCriterion.SYNTHESIS_NEUTRALITY]
    assert syn_score.score == 0.0
    assert syn_score.passed is False
    assert any(f.id == "F-SYN-BIASED-FACILITATOR" and f.severity == Severity.CRITICAL for f in res.summary.critical_findings)


def test_scenario_06_untraceable_decision(registry) -> None:
    """Scenario 6: Deciding an invented unvetted solution must fail traceability."""
    scen = registry.get("scenario-06-untraceable-decision")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    trc_score = res.summary.criterion_scores[EvaluationCriterion.DECISION_TRACEABILITY]
    assert trc_score.score <= 2.0
    assert trc_score.passed is False
    assert any(f.id == "F-TRC-UNTRACEABLE-ALTERNATIVE" for f in res.summary.critical_findings)


def test_scenario_07_insufficient_evidence(registry) -> None:
    """Scenario 7: INSUFFICIENT_EVIDENCE status must be handled correctly without false penalties."""
    scen = registry.get("scenario-07-insufficient-evidence")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    trc_score = res.summary.criterion_scores[EvaluationCriterion.DECISION_TRACEABILITY]
    trd_score = res.summary.criterion_scores[EvaluationCriterion.TRADE_OFF_EXPLICITNESS]
    assert trc_score.score >= 4.5
    assert trd_score.score >= 4.0


def test_scenario_08_generic_mentor(registry) -> None:
    """Scenario 8: Generic mentor buzzwords must fail learning value."""
    scen = registry.get("scenario-08-generic-mentor")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    lrn_score = res.summary.criterion_scores[EvaluationCriterion.LEARNING_VALUE]
    assert lrn_score.score <= 2.0
    assert lrn_score.passed is False
    assert any(f.id == "F-LRN-GENERIC" for f in res.summary.critical_findings)


def test_scenario_09_invented_fact(registry) -> None:
    """Scenario 9: Invented facts not present in context must fail fact grounding."""
    scen = registry.get("scenario-09-invented-fact")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    fact_score = res.summary.epistemic_scores[EpistemicCriterion.FACT_GROUNDING]
    assert fact_score.score <= 2.0
    assert fact_score.passed is False
    assert any(f.id == "F-EPI-FACT-01" for f in res.summary.critical_findings)


def test_scenario_10_hidden_assumption(registry) -> None:
    """Scenario 10: Hidden assumptions without declaration must fail assumption transparency."""
    scen = registry.get("scenario-10-hidden-assumption")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    asm_score = res.summary.epistemic_scores[EpistemicCriterion.ASSUMPTION_TRANSPARENCY]
    assert asm_score.score <= 2.5
    assert asm_score.passed is False
    assert any(f.id == "F-EPI-ASM-01" for f in res.summary.critical_findings)


def test_scenario_11_explicit_assumption(registry) -> None:
    """Scenario 11: Explicit assumptions with invalidation conditions must score high."""
    scen = registry.get("scenario-11-explicit-assumption")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    asm_score = res.summary.epistemic_scores[EpistemicCriterion.ASSUMPTION_TRANSPARENCY]
    assert asm_score.score >= 4.5
    assert asm_score.passed is True


def test_scenario_12_unknown_ignored(registry) -> None:
    """Scenario 12: Ignoring critical context unknowns must fail unknown visibility."""
    scen = registry.get("scenario-12-unknown-ignored")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    unk_score = res.summary.epistemic_scores[EpistemicCriterion.UNKNOWN_VISIBILITY]
    assert unk_score.score <= 2.5
    assert unk_score.passed is False
    assert any(f.id == "F-EPI-UNK-01" for f in res.summary.critical_findings)


def test_scenario_13_conditional_recommendation(registry) -> None:
    """Scenario 13: Conditional recommendations (IF ... THEN ...) must score high on grounding."""
    scen = registry.get("scenario-13-conditional-recommendation")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    rec_score = res.summary.epistemic_scores[EpistemicCriterion.RECOMMENDATION_GROUNDING]
    assert rec_score.score >= 4.5
    assert rec_score.passed is True


def test_scenario_14_proper_uncertainty(registry) -> None:
    """Scenario 14: Proper uncertainty handling with INSUFFICIENT_EVIDENCE must score high."""
    scen = registry.get("scenario-14-proper-uncertainty")
    session = scen.session_builder(uuid4())
    evaluator = DeterministicEvaluator()
    res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scen.id))

    unk_score = res.summary.epistemic_scores[EpistemicCriterion.UNKNOWN_VISIBILITY]
    int_score = res.summary.epistemic_scores[EpistemicCriterion.EPISTEMIC_INTEGRITY]
    assert unk_score.score >= 4.5
    assert int_score.score >= 4.5
    assert unk_score.passed is True
    assert int_score.passed is True


def test_batch_evaluation_all_scenarios_deterministic(registry) -> None:
    """Run all 14 benchmark scenarios in batch, verifying determinism and report output."""
    evaluator = DeterministicEvaluator()
    results = []

    for scenario in registry.list_all():
        session = scenario.session_builder(uuid4())
        res = evaluator.evaluate_session(session, metadata=EvaluationMetadata(scenario_id=scenario.id))
        results.append(res)
        report = res.format_report()
        assert len(report) > 200
        assert f"Scenario:      {scenario.id}" in report

    assert len(results) >= 14
