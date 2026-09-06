"""Mentor Agent connecting practical deliberation with computer science foundations."""

from typing import Any

from pydantic import BaseModel
from schemas.common import CommitteeRole
from schemas.learning import LearningReport
from src.committee.agents.base import BaseAgent


class MentorAgent(BaseAgent):
    """Pedagogical Mentor Agent formulating educational walkthroughs and knowledge gap analysis."""

    @property
    def role(self) -> CommitteeRole:
        return CommitteeRole.MENTOR

    @property
    def prompt_filename(self) -> str:
        return "mentor.md"

    @property
    def output_schema(self) -> type[BaseModel]:
        return LearningReport

    def validate_input_context(self, context: dict[str, Any]) -> None:
        pass
