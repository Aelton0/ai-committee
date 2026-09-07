"""Regression tests for fail-closed input context validation across all 6 agents.

Verifies that agents fail closed when presented with:
1. Empty context ({})
2. Missing 'phase' key (e.g. {'foo': 'bar'}, {'problem_statement': '...'})
3. Invalid/unauthorized phase for the agent's role
4. Missing required keys/artifacts for the allowed phase
5. Forbidden keys violating isolation guarantees (e.g., blind divergence, defense isolation)
"""

import pytest

from src.committee.agents.base import ContextIsolationError
from src.committee.agents.architect import ArchitectAgent
from src.committee.agents.auditor import AuditorAgent
from src.committee.agents.decision_maker import DecisionMakerAgent
from src.committee.agents.facilitator import FacilitatorAgent
from src.committee.agents.mentor import MentorAgent
from src.committee.agents.pragmatic import PragmaticAgent

ALL_AGENTS = [
    ArchitectAgent(),
    PragmaticAgent(),
    AuditorAgent(),
    FacilitatorAgent(),
    DecisionMakerAgent(),
    MentorAgent(),
]


@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.role.value)
def test_empty_context_rejected_by_all_agents(agent) -> None:
    """Empty context dictionary must be rejected fail-closed by all agents."""
    with pytest.raises(ContextIsolationError, match="received empty input context"):
        agent.validate_input_context({})


@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.role.value)
def test_missing_phase_rejected_by_all_agents(agent) -> None:
    """Context without mandatory 'phase' key must be rejected by all agents."""
    # Arbitrary keys without phase
    with pytest.raises(ContextIsolationError, match="missing mandatory 'phase' key"):
        agent.validate_input_context({"problem_statement": "Valid statement without phase"})

    with pytest.raises(ContextIsolationError, match="missing mandatory 'phase' key"):
        agent.validate_input_context({"foo": "bar"})

    with pytest.raises(ContextIsolationError, match="missing mandatory 'phase' key"):
        agent.validate_input_context({"phase": ""})

    with pytest.raises(ContextIsolationError, match="missing mandatory 'phase' key"):
        agent.validate_input_context({"phase": "   "})


@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.role.value)
def test_invalid_phase_rejected_by_all_agents(agent) -> None:
    """Context with phase outside the agent's role mandate must be rejected."""
    with pytest.raises(ContextIsolationError, match="is invalid for"):
        agent.validate_input_context({"phase": "PHASE_NON_EXISTENT_999"})


# --- Individual Agent Tests ---


class TestArchitectValidation:
    @pytest.fixture
    def agent(self) -> ArchitectAgent:
        return ArchitectAgent()

    def test_forbidden_keys_blind_divergence(self, agent: ArchitectAgent) -> None:
        """Architect must reject pragmatic proposal and defense, even if valid phase is present."""
        with pytest.raises(ContextIsolationError, match="Blind divergence violated"):
            agent.validate_input_context({
                "phase": "PHASE_1_DIVERGENCE",
                "problem_statement": "Valid",
                "pragmatic_proposal": {"solution": "monolith"},
            })

        with pytest.raises(ContextIsolationError, match="Defense isolation violated"):
            agent.validate_input_context({
                "phase": "PHASE_3_DEFENSE",
                "audit_report": {"findings": []},
                "pragmatic_defense": {"response": "def"},
            })

    def test_missing_required_keys(self, agent: ArchitectAgent) -> None:
        with pytest.raises(ContextIsolationError, match="requires at least one of"):
            agent.validate_input_context({"phase": "PHASE_1_DIVERGENCE"})

        with pytest.raises(ContextIsolationError, match="requires 'audit_report'"):
            agent.validate_input_context({"phase": "PHASE_3_DEFENSE"})

    def test_valid_contexts(self, agent: ArchitectAgent) -> None:
        agent.validate_input_context({"phase": "PHASE_1_DIVERGENCE", "problem_statement": "Valid"})
        agent.validate_input_context({"phase": "PHASE_1_DIVERGENCE", "problem_context": {"foo": "bar"}})
        agent.validate_input_context({"phase": "PHASE_3_DEFENSE", "audit_report": {"findings": []}})


class TestPragmaticValidation:
    @pytest.fixture
    def agent(self) -> PragmaticAgent:
        return PragmaticAgent()

    def test_forbidden_keys_blind_divergence(self, agent: PragmaticAgent) -> None:
        """Pragmatic must reject architect proposal and defense."""
        with pytest.raises(ContextIsolationError, match="Blind divergence violated"):
            agent.validate_input_context({
                "phase": "PHASE_1_DIVERGENCE",
                "problem_statement": "Valid",
                "architect_proposal": {"solution": "microservices"},
            })

        with pytest.raises(ContextIsolationError, match="Defense isolation violated"):
            agent.validate_input_context({
                "phase": "PHASE_3_DEFENSE",
                "audit_report": {"findings": []},
                "architect_defense": {"response": "def"},
            })

    def test_missing_required_keys(self, agent: PragmaticAgent) -> None:
        with pytest.raises(ContextIsolationError, match="requires at least one of"):
            agent.validate_input_context({"phase": "PHASE_1_DIVERGENCE"})

        with pytest.raises(ContextIsolationError, match="requires 'audit_report'"):
            agent.validate_input_context({"phase": "PHASE_3_DEFENSE"})

    def test_valid_contexts(self, agent: PragmaticAgent) -> None:
        agent.validate_input_context({"phase": "PHASE_1_DIVERGENCE", "problem_statement": "Valid"})
        agent.validate_input_context({"phase": "PHASE_1_DIVERGENCE", "problem_context": {"foo": "bar"}})
        agent.validate_input_context({"phase": "PHASE_3_DEFENSE", "audit_report": {"findings": []}})


class TestAuditorValidation:
    @pytest.fixture
    def agent(self) -> AuditorAgent:
        return AuditorAgent()

    def test_forbidden_keys_defense_leakage(self, agent: AuditorAgent) -> None:
        """Auditor must not receive defenses during confrontation phase."""
        with pytest.raises(ContextIsolationError, match="Auditor isolation violated"):
            agent.validate_input_context({
                "phase": "PHASE_2_CONFRONTATION",
                "architect_proposal": {"title": "A"},
                "architect_defense": {"text": "def"},
            })

        with pytest.raises(ContextIsolationError, match="Auditor isolation violated"):
            agent.validate_input_context({
                "phase": "PHASE_2_CONFRONTATION",
                "pragmatic_proposal": {"title": "P"},
                "pragmatic_defense": {"text": "def"},
            })

    def test_missing_required_keys(self, agent: AuditorAgent) -> None:
        with pytest.raises(ContextIsolationError, match="requires at least one of"):
            agent.validate_input_context({"phase": "PHASE_2_CONFRONTATION"})

    def test_valid_contexts(self, agent: AuditorAgent) -> None:
        agent.validate_input_context({
            "phase": "PHASE_2_CONFRONTATION",
            "architect_proposal": {"title": "Arch"},
        })
        agent.validate_input_context({
            "phase": "PHASE_2_CONFRONTATION",
            "pragmatic_proposal": {"title": "Prag"},
        })


class TestFacilitatorValidation:
    @pytest.fixture
    def agent(self) -> FacilitatorAgent:
        return FacilitatorAgent()

    def test_forbidden_keys_decision_record(self, agent: FacilitatorAgent) -> None:
        """Facilitator must not receive DecisionRecord in any phase."""
        with pytest.raises(ContextIsolationError, match="Facilitator isolation violated"):
            agent.validate_input_context({
                "phase": "PHASE_4_CONVERGENCE",
                "problem_context": {},
                "decision_record": {"status": "RECOMMENDED"},
            })

    def test_missing_required_keys(self, agent: FacilitatorAgent) -> None:
        with pytest.raises(ContextIsolationError, match="requires at least one of"):
            agent.validate_input_context({"phase": "PHASE_0_INVESTIGATION"})

        with pytest.raises(ContextIsolationError, match="requires at least one of"):
            agent.validate_input_context({"phase": "PHASE_4_CONVERGENCE"})

    def test_valid_contexts(self, agent: FacilitatorAgent) -> None:
        agent.validate_input_context({"phase": "PHASE_0_INVESTIGATION", "problem_statement": "Valid"})
        agent.validate_input_context({"phase": "PHASE_0_INVESTIGATION", "problem_context": {"statement": "Valid"}})
        agent.validate_input_context({"phase": "PHASE_4_CONVERGENCE", "problem_context": {"statement": "Valid"}})
        agent.validate_input_context({"phase": "PHASE_4_CONVERGENCE", "audit_report": {"findings": []}})


class TestDecisionMakerValidation:
    @pytest.fixture
    def agent(self) -> DecisionMakerAgent:
        return DecisionMakerAgent()

    def test_missing_required_keys(self, agent: DecisionMakerAgent) -> None:
        with pytest.raises(ContextIsolationError, match="requires at least one of"):
            agent.validate_input_context({"phase": "PHASE_5_DECISION"})

    def test_valid_contexts(self, agent: DecisionMakerAgent) -> None:
        agent.validate_input_context({
            "phase": "PHASE_5_DECISION",
            "deliberation_synthesis": {"consensus": []},
        })
        agent.validate_input_context({
            "phase": "PHASE_5_DECISION",
            "problem_context": {"statement": "P"},
        })


class TestMentorValidation:
    @pytest.fixture
    def agent(self) -> MentorAgent:
        return MentorAgent()

    def test_missing_required_keys(self, agent: MentorAgent) -> None:
        with pytest.raises(ContextIsolationError, match="requires at least one of"):
            agent.validate_input_context({"phase": "PHASE_6_REFLECTION"})

    def test_valid_contexts(self, agent: MentorAgent) -> None:
        agent.validate_input_context({
            "phase": "PHASE_6_REFLECTION",
            "decision_record": {"status": "RECOMMENDED"},
        })
        agent.validate_input_context({
            "phase": "PHASE_6_REFLECTION",
            "problem_context": {"statement": "P"},
        })
