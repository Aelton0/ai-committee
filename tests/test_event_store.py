"""Unit tests for the append-only, tamper-resistant EventStore."""

import sqlite3
from uuid import uuid4

import pytest

from schemas.common import CommitteeRole, EventType
from schemas.events import EventEnvelope, SessionCreatedPayload
from src.committee.event_store import (
    DuplicateEventError,
    EventStore,
    compute_canonical_hash,
)


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_committee.db"


@pytest.fixture
def event_store(temp_db_path):
    store = EventStore(temp_db_path)
    yield store
    store.close()


def test_append_and_retrieve_events(event_store) -> None:
    """Test appending events and retrieving them in sequence order."""
    session_id = uuid4()
    payload1 = SessionCreatedPayload(problem_statement="Initial Problem Description")
    env1 = EventEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_CREATED,
        actor=CommitteeRole.HUMAN_USER,
        payload=payload1,
    )
    event_store.append(env1)

    assert event_store.count_events(session_id) == 1
    events = event_store.get_events(session_id)
    assert len(events) == 1
    assert events[0].event_id == env1.event_id
    assert events[0].event_type == EventType.SESSION_CREATED
    assert events[0].content_hash is not None
    assert events[0].content_hash.startswith("sha256:")

    last = event_store.get_last_event(session_id)
    assert last is not None
    assert last.event_id == env1.event_id


def test_duplicate_event_id_rejected(event_store) -> None:
    """Test that duplicate event_id is rejected with DuplicateEventError."""
    session_id = uuid4()
    event_id = uuid4()
    payload = SessionCreatedPayload(problem_statement="Problem Statement")

    env1 = EventEnvelope(
        event_id=event_id,
        session_id=session_id,
        event_type=EventType.SESSION_CREATED,
        actor=CommitteeRole.HUMAN_USER,
        payload=payload,
    )
    event_store.append(env1)

    env2 = EventEnvelope(
        event_id=event_id,  # Same event_id
        session_id=session_id,
        event_type=EventType.SESSION_CREATED,
        actor=CommitteeRole.HUMAN_USER,
        payload=payload,
    )
    with pytest.raises(DuplicateEventError):
        event_store.append(env2)


def test_sqlite_trigger_prevents_update(temp_db_path, event_store) -> None:
    """Negative test: Attempting an UPDATE on events table must fail via SQLite trigger."""
    session_id = uuid4()
    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_CREATED,
        actor=CommitteeRole.HUMAN_USER,
        payload=SessionCreatedPayload(problem_statement="Original Text"),
    )
    event_store.append(env)

    # Attempt direct destructive UPDATE via raw SQL connection
    raw_conn = sqlite3.connect(temp_db_path)
    with pytest.raises(sqlite3.IntegrityError, match="UPDATE operations are forbidden"):
        raw_conn.execute(
            "UPDATE events SET payload_json = '{\"hacked\": true}' WHERE session_id = ?",
            (str(session_id),),
        )
    raw_conn.close()


def test_sqlite_trigger_prevents_delete(temp_db_path, event_store) -> None:
    """Negative test: Attempting a DELETE on events table must fail via SQLite trigger."""
    session_id = uuid4()
    env = EventEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_CREATED,
        actor=CommitteeRole.HUMAN_USER,
        payload=SessionCreatedPayload(problem_statement="Problem Text"),
    )
    event_store.append(env)

    # Attempt direct destructive DELETE via raw SQL connection
    raw_conn = sqlite3.connect(temp_db_path)
    with pytest.raises(sqlite3.IntegrityError, match="DELETE operations are forbidden"):
        raw_conn.execute("DELETE FROM events WHERE session_id = ?", (str(session_id),))
    raw_conn.close()


def test_canonical_hash_determinism() -> None:
    """Test that canonical hash is deterministic regardless of key order."""
    dict_a = {"b": 2, "a": 1, "nested": {"y": "val", "x": "val"}}
    dict_b = {"a": 1, "b": 2, "nested": {"x": "val", "y": "val"}}

    hash_a = compute_canonical_hash(dict_a)
    hash_b = compute_canonical_hash(dict_b)

    assert hash_a == hash_b
    assert hash_a.startswith("sha256:")
