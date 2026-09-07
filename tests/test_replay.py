"""Unit tests for deterministic session replay and reconstruction."""

from uuid import uuid4

import pytest

from schemas.audit import AuditReport
from schemas.common import CommitteeRole, CommitteeState, EventType
from schemas.context import ProblemContext
from schemas.events import EventEnvelope, PhaseRollbackPayload, SessionCreatedPayload, UserOverridePayload
from schemas.intervention import UserAbortCommand, UserRequestRevisionCommand
from schemas.proposals import ArchitectProposal, PragmaticProposal
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.synthesis import DeliberationSynthesis
from schemas.decision import DecisionRecord, DecisionStatus
from src.committee.event_store import EventStore
from src.committee.replay import replay_session
from src.committee.state_machine import SessionNotFoundError, StateMachine
from src.committee.llm.mock import MockLLMProvider


@pytest.fixture
def event_store(tmp_path):
    store = EventStore(tmp_path / "test_replay.db")
    yield store
    store.close()


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


def test_replay_session_matches_active_state(event_store) -> None:
    """Test replaying historical events yields exact same state projection."""
    sm = StateMachine(event_store)
    session_id = uuid4()

    session = sm.create_session(session_id, "Replay test problem.", user_id="user123")

    ctx = ProblemContext(
        artifact_id="CTX-001",
        version=1,
        problem="Replay test problem.",
        success_criteria=["Success 1"],
    )
    env_ctx = EventEnvelope(
        session_id=session_id,
        event_type=EventType.CONTEXT_VALIDATED,
        actor=CommitteeRole.FACILITATOR,
        payload=ctx,
    )
    sm.handle_event(session, env_ctx)
    assert session.current_state == CommitteeState.DIVERGENCE
    assert getattr(session, "problem_statement", None) == "Replay test problem."
    assert getattr(session, "user_id", None) == "user123"

    replayed = replay_session(session_id, event_store)

    assert replayed.session_id == session.session_id
    assert replayed.current_state == session.current_state
    assert replayed.current_phase == session.current_phase
    assert replayed.version == session.version
    assert replayed.problem_context is not None
    assert getattr(replayed, "problem_statement", None) == "Replay test problem."
    assert getattr(replayed, "user_id", None) == "user123"
    assert replayed.problem_context.artifact_id == "CTX-001"


def test_replay_nonexistent_session_fails(event_store) -> None:
    """Test replaying an unknown session raises SessionNotFoundError."""
    with pytest.raises(SessionNotFoundError):
        replay_session(uuid4(), event_store)


def test_replay_rollback_clears_artifacts(event_store, mock_llm) -> None:
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Problem Statement")
    
    ctx = mock_llm._generate_default(ProblemContext, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx))
    
    prop1 = mock_llm._generate_default(ArchitectProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop1))
    
    prop2 = mock_llm._generate_default(PragmaticProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.PRAGMATIST, payload=prop2))
    
    assert session.current_state == CommitteeState.CONFRONTATION
    assert len(session.proposals) == 2
    
    rollback_payload = PhaseRollbackPayload(reason="Testing rollback", from_phase="PHASE_2_CONFRONTATION", to_phase="PHASE_0_INVESTIGATION")
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PHASE_ROLLBACK, actor=CommitteeRole.AUDITOR_SRE, payload=rollback_payload))
    
    assert session.current_state == CommitteeState.INVESTIGATION
    assert len(session.proposals) == 0
    
    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.INVESTIGATION
    assert len(replayed.proposals) == 0
    assert len(replayed.rollback_history) == 1


def test_replay_cancellation(event_store) -> None:
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Problem Statement")
    
    cmd = UserAbortCommand(session_id=session_id, reason="Aborting test")
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.USER_OVERRIDE, actor=CommitteeRole.HUMAN_USER, payload=UserOverridePayload(intervention=cmd)))
    
    assert session.current_state == CommitteeState.CANCELLED
    
    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.CANCELLED


def test_replay_insufficient_evidence(event_store, mock_llm) -> None:
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Problem Statement")
    
    ctx = mock_llm._generate_default(ProblemContext, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx))
    
    prop1 = mock_llm._generate_default(ArchitectProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop1))
    
    prop2 = mock_llm._generate_default(PragmaticProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.PRAGMATIST, payload=prop2))
    
    audit = mock_llm._generate_default(AuditReport, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.AUDIT_COMPLETED, actor=CommitteeRole.AUDITOR_SRE, payload=audit))
    
    def1 = mock_llm._generate_default(ArchitectDefense, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DEFENSE_SUBMITTED, actor=CommitteeRole.ARCHITECT, payload=def1))
    
    def2 = mock_llm._generate_default(PragmaticDefense, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DEFENSE_SUBMITTED, actor=CommitteeRole.PRAGMATIST, payload=def2))
    
    synth = mock_llm._generate_default(DeliberationSynthesis, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.SYNTHESIS_CREATED, actor=CommitteeRole.FACILITATOR, payload=synth))
    
    dec = mock_llm._generate_default(DecisionRecord, input_context={})
    dec_dict = dec.model_dump()
    dec_dict["status"] = DecisionStatus.INSUFFICIENT_EVIDENCE
    dec_dict["chosen_alternative"] = None
    dec_dict["information_that_could_change_decision"] = ["Need more info"]
    dec2 = DecisionRecord(**dec_dict)
    
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DECISION_FAILED, actor=CommitteeRole.DECISOR, payload=dec2))
    
    assert session.current_state == CommitteeState.INSUFFICIENT_EVIDENCE
    
    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.INSUFFICIENT_EVIDENCE
    assert replayed.decision_record is not None
    assert replayed.decision_record.status == DecisionStatus.INSUFFICIENT_EVIDENCE

def test_replay_revision_clears_artifacts(event_store, mock_llm) -> None:
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Problem Statement")
    
    ctx = mock_llm._generate_default(ProblemContext, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx))
    
    prop1 = mock_llm._generate_default(ArchitectProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop1))
    
    prop2 = mock_llm._generate_default(PragmaticProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.PRAGMATIST, payload=prop2))
    
    audit = mock_llm._generate_default(AuditReport, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.AUDIT_COMPLETED, actor=CommitteeRole.AUDITOR_SRE, payload=audit))
    
    def1 = mock_llm._generate_default(ArchitectDefense, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DEFENSE_SUBMITTED, actor=CommitteeRole.ARCHITECT, payload=def1))
    
    def2 = mock_llm._generate_default(PragmaticDefense, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DEFENSE_SUBMITTED, actor=CommitteeRole.PRAGMATIST, payload=def2))
    
    synth = mock_llm._generate_default(DeliberationSynthesis, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.SYNTHESIS_CREATED, actor=CommitteeRole.FACILITATOR, payload=synth))
    
    dec = mock_llm._generate_default(DecisionRecord, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DECISION_RECORDED, actor=CommitteeRole.DECISOR, payload=dec))

    assert session.current_state == CommitteeState.REFLECTION

    cmd = UserRequestRevisionCommand(session_id=session_id, target_decision_id="DEC-001", reason_for_rejection="Testing", additional_constraints=["New constraint"])
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.USER_OVERRIDE, actor=CommitteeRole.HUMAN_USER, payload=UserOverridePayload(intervention=cmd)))
    
    assert session.current_state == CommitteeState.DIVERGENCE
    assert len(session.proposals) == 0
    assert len(session.historical_rounds) == 1
    
    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.DIVERGENCE
    assert len(replayed.proposals) == 0
    assert len(replayed.historical_rounds) == 1
    assert replayed.model_dump(mode="json") == session.model_dump(mode="json")


def test_replay_full_happy_path_to_completed(event_store, mock_llm) -> None:
    """Test full deliberation lifecycle from DRAFT to COMPLETED reproduces exact projection."""
    from schemas.learning import LearningReport
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "End to end problem statement", user_id="alice_dev", initial_context="Priority high")

    ctx = mock_llm._generate_default(ProblemContext, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx))

    prop1 = mock_llm._generate_default(ArchitectProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop1))

    prop2 = mock_llm._generate_default(PragmaticProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.PRAGMATIST, payload=prop2))

    audit = mock_llm._generate_default(AuditReport, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.AUDIT_COMPLETED, actor=CommitteeRole.AUDITOR_SRE, payload=audit))

    def1 = mock_llm._generate_default(ArchitectDefense, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DEFENSE_SUBMITTED, actor=CommitteeRole.ARCHITECT, payload=def1))

    def2 = mock_llm._generate_default(PragmaticDefense, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DEFENSE_SUBMITTED, actor=CommitteeRole.PRAGMATIST, payload=def2))

    synth = mock_llm._generate_default(DeliberationSynthesis, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.SYNTHESIS_CREATED, actor=CommitteeRole.FACILITATOR, payload=synth))

    dec = mock_llm._generate_default(DecisionRecord, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.DECISION_RECORDED, actor=CommitteeRole.DECISOR, payload=dec))

    learn = mock_llm._generate_default(LearningReport, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.LEARNING_REPORT_CREATED, actor=CommitteeRole.MENTOR, payload=learn))

    assert session.current_state == CommitteeState.COMPLETED
    assert session.learning_report is not None

    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.COMPLETED
    assert replayed.model_dump(mode="json") == session.model_dump(mode="json")


def test_replay_multi_round_rollback_preserves_historical_rounds(event_store, mock_llm) -> None:
    """Test multiple rollbacks archive rounds without losing any historical proposals or artifacts."""
    from src.committee.session import RoundStatus
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Multi rollback problem")

    # Round 1
    ctx1 = mock_llm._generate_default(ProblemContext, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx1))
    prop1_a = mock_llm._generate_default(ArchitectProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop1_a))
    prop1_p = mock_llm._generate_default(PragmaticProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.PRAGMATIST, payload=prop1_p))
    assert session.current_state == CommitteeState.CONFRONTATION

    # Rollback 1
    rollback1 = PhaseRollbackPayload(reason="Rollback 1 flaw", from_phase="PHASE_2_CONFRONTATION", to_phase="PHASE_0_INVESTIGATION")
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PHASE_ROLLBACK, actor=CommitteeRole.AUDITOR_SRE, payload=rollback1))
    assert session.current_state == CommitteeState.INVESTIGATION
    assert len(session.historical_rounds) == 1
    assert session.historical_rounds[0].status == RoundStatus.SUPERSEDED_BY_ROLLBACK

    # Round 2
    ctx2 = mock_llm._generate_default(ProblemContext, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx2))
    prop2_a = mock_llm._generate_default(ArchitectProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop2_a))
    prop2_p = mock_llm._generate_default(PragmaticProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.PRAGMATIST, payload=prop2_p))
    assert session.current_state == CommitteeState.CONFRONTATION

    # Rollback 2
    rollback2 = PhaseRollbackPayload(reason="Rollback 2 flaw", from_phase="PHASE_2_CONFRONTATION", to_phase="PHASE_0_INVESTIGATION")
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PHASE_ROLLBACK, actor=CommitteeRole.AUDITOR_SRE, payload=rollback2))
    assert session.current_state == CommitteeState.INVESTIGATION
    assert len(session.historical_rounds) == 2

    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.INVESTIGATION
    assert len(replayed.historical_rounds) == 2
    assert len(replayed.get_historical_proposals()) == 4
    assert replayed.model_dump(mode="json") == session.model_dump(mode="json")


def test_replay_critical_error_to_blocked(event_store, mock_llm) -> None:
    """Test replaying session that encountered CRITICAL_ERROR reproduces BLOCKED state."""
    from schemas.events import CriticalErrorPayload
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Fatal error test problem")

    ctx = mock_llm._generate_default(ProblemContext, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx))

    err_payload = CriticalErrorPayload(error_message="Critical disk IO failure", details={"device": "/dev/sda1"})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CRITICAL_ERROR, actor=CommitteeRole.FACILITATOR, payload=err_payload))

    assert session.current_state == CommitteeState.BLOCKED
    assert session.critical_error is not None
    assert session.critical_error.error_message == "Critical disk IO failure"

    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.BLOCKED
    assert replayed.critical_error is not None
    assert replayed.critical_error.error_message == "Critical disk IO failure"
    assert replayed.model_dump(mode="json") == session.model_dump(mode="json")


def test_replay_interrupted_mid_phase(event_store, mock_llm) -> None:
    """Test replaying a session that stopped mid-phase before all round events arrived."""
    sm = StateMachine(event_store)
    session_id = uuid4()
    session = sm.create_session(session_id, "Interrupted session problem")

    ctx = mock_llm._generate_default(ProblemContext, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.CONTEXT_VALIDATED, actor=CommitteeRole.FACILITATOR, payload=ctx))

    # Only 1 proposal submitted
    prop1 = mock_llm._generate_default(ArchitectProposal, input_context={})
    sm.handle_event(session, EventEnvelope(session_id=session_id, event_type=EventType.PROPOSAL_CREATED, actor=CommitteeRole.ARCHITECT, payload=prop1))

    assert session.current_state == CommitteeState.DIVERGENCE
    assert len(session.proposals) == 1

    replayed = replay_session(session_id, event_store)
    assert replayed.current_state == CommitteeState.DIVERGENCE
    assert len(replayed.proposals) == 1
    assert replayed.model_dump(mode="json") == session.model_dump(mode="json")