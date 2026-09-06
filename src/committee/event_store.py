"""Append-only, tamper-resistant Event Store backed by SQLite with WAL mode."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from schemas.events import EventEnvelope


class EventStoreError(Exception):
    """Base exception for Event Store errors."""


class DuplicateEventError(EventStoreError):
    """Raised when attempting to append an event with an existing event_id."""


class ImmutableEventStoreViolationError(EventStoreError):
    """Raised when an illegal mutation (UPDATE or DELETE) is attempted on the event store."""


def compute_canonical_hash(payload: Any) -> str:
    """Compute a deterministic, canonical SHA-256 hash for an event payload."""
    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        data = payload
    else:
        raise ValueError(f"Cannot compute canonical hash for type: {type(payload)}")

    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class EventStore:
    """SQLite-backed append-only event store.

    Enforces immutability at the schema and trigger levels.
    """

    def __init__(self, db_path: str | Path = "data/committee.db") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database settings, schema, and immutability triggers."""
        cursor = self._conn.cursor()
        if self.db_path != ":memory:":
            cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL,
                correlation_id TEXT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                artifact_id TEXT,
                artifact_version TEXT,
                content_hash TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_session ON events (session_id, sequence);"
        )

        # Triggers enforcing append-only immutability at the database engine level
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_event_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(FAIL, 'UPDATE operations are forbidden on append-only event store');
            END;
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_event_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(FAIL, 'DELETE operations are forbidden on append-only event store');
            END;
            """
        )
        self._conn.commit()

    def append(self, envelope: EventEnvelope) -> None:
        """Atomically persist a validated EventEnvelope into the append-only store."""
        # Calculate canonical hash if missing
        content_hash = envelope.content_hash
        if not content_hash and envelope.payload is not None:
            content_hash = compute_canonical_hash(envelope.payload)

        # Prepare payload json
        if isinstance(envelope.payload, BaseModel):
            payload_json = envelope.payload.model_dump_json()
        elif isinstance(envelope.payload, dict):
            payload_json = json.dumps(envelope.payload, ensure_ascii=False)
        else:
            payload_json = json.dumps(str(envelope.payload))

        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO events (
                        event_id,
                        session_id,
                        correlation_id,
                        event_type,
                        timestamp,
                        actor,
                        artifact_id,
                        artifact_version,
                        content_hash,
                        payload_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(envelope.event_id),
                        str(envelope.session_id),
                        str(envelope.correlation_id) if envelope.correlation_id else None,
                        envelope.event_type.value,
                        envelope.timestamp.isoformat(),
                        envelope.actor.value,
                        envelope.artifact_id,
                        envelope.artifact_version,
                        content_hash,
                        payload_json,
                        now_iso,
                    ),
                )
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: events.event_id" in str(e):
                raise DuplicateEventError(
                    f"Event with id '{envelope.event_id}' has already been persisted."
                ) from e
            raise EventStoreError(f"Database integrity error: {e}") from e

    def get_events(self, session_id: UUID) -> list[EventEnvelope]:
        """Retrieve all events belonging to a session in strict chronological sequence order."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT
                event_id,
                session_id,
                correlation_id,
                event_type,
                timestamp,
                actor,
                artifact_id,
                artifact_version,
                content_hash,
                payload_json
            FROM events
            WHERE session_id = ?
            ORDER BY sequence ASC
            """,
            (str(session_id),),
        )
        rows = cursor.fetchall()

        events: list[EventEnvelope] = []
        for row in rows:
            payload_dict = json.loads(row["payload_json"])
            envelope = EventEnvelope(
                event_id=UUID(row["event_id"]),
                session_id=UUID(row["session_id"]),
                correlation_id=UUID(row["correlation_id"]) if row["correlation_id"] else None,
                event_type=row["event_type"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                actor=row["actor"],
                artifact_id=row["artifact_id"],
                artifact_version=row["artifact_version"],
                content_hash=row["content_hash"],
                payload=payload_dict,
            )
            events.append(envelope)
        return events

    def get_last_event(self, session_id: UUID) -> EventEnvelope | None:
        """Retrieve the latest recorded event for a session, or None if session is empty."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT
                event_id,
                session_id,
                correlation_id,
                event_type,
                timestamp,
                actor,
                artifact_id,
                artifact_version,
                content_hash,
                payload_json
            FROM events
            WHERE session_id = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (str(session_id),),
        )
        row = cursor.fetchone()
        if not row:
            return None

        payload_dict = json.loads(row["payload_json"])
        return EventEnvelope(
            event_id=UUID(row["event_id"]),
            session_id=UUID(row["session_id"]),
            correlation_id=UUID(row["correlation_id"]) if row["correlation_id"] else None,
            event_type=row["event_type"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            actor=row["actor"],
            artifact_id=row["artifact_id"],
            artifact_version=row["artifact_version"],
            content_hash=row["content_hash"],
            payload=payload_dict,
        )

    def count_events(self, session_id: UUID) -> int:
        """Return the number of events recorded for a session."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ?",
            (str(session_id),),
        )
        return int(cursor.fetchone()[0])

    def get_all_session_ids(self) -> list[UUID]:
        """Return list of all distinct session UUIDs present in the store."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT DISTINCT session_id FROM events ORDER BY sequence ASC")
        return [UUID(row[0]) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close SQLite database connection."""
        self._conn.close()
