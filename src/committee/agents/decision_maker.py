"""Decision Maker Agent formulating the final balanced recommendation or declaring insufficient evidence."""

from typing import Any

from pydantic import BaseModel
from schemas.common import CommitteeRole
from schemas.decision import DecisionRecord
from src.committee.agents.base import BaseAgent


class DecisionMakerAgent(BaseAgent):
    """Decision Maker Agent synthesizing debate and formulating formal recommendations."""

    @property
    def role(self) -> CommitteeRole:
        return CommitteeRole.DECISOR

    @property
    def prompt_filename(self) -> str:
        return "decision-maker.md"

    @property
    def output_schema(self) -> type[BaseModel]:
        return DecisionRecord

    def validate_input_context(self, context: dict[str, Any]) -> None:
        # Decision Maker needs synthesis or minimum context
        pass
