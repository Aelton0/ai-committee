"""Learning report schemas produced by the Mentor in Phase 6."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import BaseArtifact, CommitteeRole


class LearningReference(BaseModel):
    """Academic, industry, or textbook reference supporting study."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: Annotated[str, Field(min_length=1)]
    author: str | None = None
    url_or_citation: Annotated[str, Field(min_length=1)]
    relevance_notes: str | None = None


class LearningPathStep(BaseModel):
    """Structured step in the recommended self-study progression."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    order: Annotated[int, Field(ge=1)]
    topic: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=5)]
    reference: LearningReference | None = None


class ObservedKnowledgeGap(BaseModel):
    """Knowledge gap grounded objectively on content observed during deliberation.

    Explicitly avoids psychological inferences or absolute assumptions about user capability.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation: Annotated[
        str,
        Field(
            min_length=5,
            description="Objective observation grounded strictly on the content presented by the user",
        ),
    ]
    context_evidence: Annotated[
        str,
        Field(
            min_length=5,
            description="Specific interaction or question from which the observation was derived",
        ),
    ]
    recommended_topic: Annotated[str, Field(min_length=1)]


class EpistemicLesson(BaseModel):
    """Pedagogical lesson highlighting epistemological clarity and trade-offs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept: Annotated[str, Field(min_length=3, description="Underlying theoretical concept")]
    debate_example: Annotated[str, Field(min_length=5, description="Specific occurrence in the deliberation")]
    epistemic_confusion: Annotated[
        str,
        Field(
            min_length=5,
            description="Observed confusion, e.g. treating an assumption as an established fact",
        ),
    ]
    study_topic: Annotated[str, Field(min_length=3, description="Recommended theory/practice topic to explore")]


class LearningReport(BaseArtifact):
    """Pedagogical synthesis connecting practical choices with core computer science theory."""

    mentor_role: Literal[CommitteeRole.MENTOR] = CommitteeRole.MENTOR
    concepts: Annotated[list[str], Field(min_length=1)]
    concepts_required_to_understand_decision: Annotated[list[str], Field(min_length=1)]
    observed_knowledge_gaps: list[ObservedKnowledgeGap] = Field(default_factory=list)
    epistemic_lessons: list[EpistemicLesson] = Field(default_factory=list)
    study_questions: Annotated[list[str], Field(min_length=1)]
    learning_path: Annotated[list[LearningPathStep], Field(min_length=1)]
    theory_to_practice_connections: Annotated[list[str], Field(min_length=1)]
    references: Annotated[list[LearningReference], Field(min_length=1)]
