"""Unit tests for LearningReport and educational submodels."""

from pydantic import ValidationError
import pytest

from schemas.common import CommitteeRole
from schemas.learning import (
    LearningPathStep,
    LearningReference,
    LearningReport,
    ObservedKnowledgeGap,
)


def test_valid_learning_report() -> None:
    """Test valid LearningReport linking decision to computing principles."""
    report = LearningReport(
        artifact_id="LRN-001",
        version=1,
        concepts=["Eventual Consistency", "Circuit Breaker Pattern", "Outbox Pattern"],
        concepts_required_to_understand_decision=[
            "Difference between at-least-once and exactly-once message delivery semantics",
            "Impact of database connection exhaustion under synchronous cascades",
        ],
        observed_knowledge_gaps=[
            ObservedKnowledgeGap(
                observation="User treated Redis cache as a durable message queue during initial framing.",
                context_evidence="Question Q1 interaction where user proposed writing financial transactions directly to volatile Redis keys.",
                recommended_topic="Message durability and WAL principles in distributed queues.",
            )
        ],
        study_questions=[
            "Why is a volatile in-memory cache unsuitable as an authoritative event log for financial ledgers?",
            "How does an exponential backoff circuit breaker prevent a thundering herd failure?",
        ],
        learning_path=[
            LearningPathStep(
                order=1,
                topic="Reliability Patterns",
                description="Study timeout, retry with jitter, and circuit breaker patterns.",
                reference=LearningReference(
                    title="Release It! Second Edition",
                    author="Michael T. Nygard",
                    url_or_citation="Pragmatic Bookshelf, 2018",
                ),
            ),
            LearningPathStep(
                order=2,
                topic="Data-Intensive Architectures",
                description="Review transactions, isolation levels, and replication topologies.",
                reference=LearningReference(
                    title="Designing Data-Intensive Applications",
                    author="Martin Kleppmann",
                    url_or_citation="O'Reilly Media, 2017",
                ),
            ),
        ],
        theory_to_practice_connections=[
            "The committee accepted synchronous HTTP over Kafka because the CAP theorem availability penalty was deemed acceptable within the single datacenter boundary."
        ],
        references=[
            LearningReference(
                title="Building Microservices",
                author="Sam Newman",
                url_or_citation="O'Reilly Media, 2021",
                relevance_notes="Chapters on asynchronous messaging and service boundaries.",
            )
        ],
    )

    assert report.mentor_role == CommitteeRole.MENTOR
    assert len(report.concepts) == 3
    assert len(report.observed_knowledge_gaps) == 1
    assert len(report.learning_path) == 2


def test_learning_report_role_enforcement() -> None:
    """Test that LearningReport enforces MENTOR role."""
    with pytest.raises(ValidationError):
        LearningReport(
            artifact_id="LRN-002",
            version=1,
            mentor_role=CommitteeRole.ARCHITECT,  # type: ignore[arg-type]
            concepts=["Concept 1"],
            concepts_required_to_understand_decision=["Concept 2"],
            study_questions=["Question 1"],
            learning_path=[LearningPathStep(order=1, topic="Topic", description="Desc sufficiently long")],
            theory_to_practice_connections=["Connection 1"],
            references=[LearningReference(title="Title", url_or_citation="Citation")],
        )
