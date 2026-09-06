"""JSON Schema generator exporting official schemas from Pydantic models."""

import json
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from schemas.audit import AuditReport
from schemas.context import ProblemContext
from schemas.decision import DecisionRecord
from schemas.defense import ArchitectDefense, PragmaticDefense
from schemas.events import EventEnvelope
from schemas.intervention import (
    UserAbortCommand,
    UserContestAssumptionCommand,
    UserRequestRevisionCommand,
    UserRespondCommand,
)
from schemas.learning import LearningReport
from schemas.proposals import ArchitectProposal, PragmaticProposal
from schemas.synthesis import DeliberationSynthesis

# Directory where generated schemas are persisted
OUTPUT_DIR = Path(__file__).resolve().parent / "generated"

MODELS_TO_EXPORT: dict[str, Type[BaseModel]] = {
    "problem_context": ProblemContext,
    "architect_proposal": ArchitectProposal,
    "pragmatic_proposal": PragmaticProposal,
    "audit_report": AuditReport,
    "architect_defense": ArchitectDefense,
    "pragmatic_defense": PragmaticDefense,
    "deliberation_synthesis": DeliberationSynthesis,
    "decision_record": DecisionRecord,
    "learning_report": LearningReport,
    "event_envelope": EventEnvelope,
    "user_respond_command": UserRespondCommand,
    "user_contest_assumption_command": UserContestAssumptionCommand,
    "user_request_revision_command": UserRequestRevisionCommand,
    "user_abort_command": UserAbortCommand,
}


def generate_json_schemas(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    """Generate and write JSON Schema files for all registered models.

    Pydantic is the single source of truth.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[Path] = []

    for schema_name, model_cls in MODELS_TO_EXPORT.items():
        schema_dict = model_cls.model_json_schema()
        file_path = output_dir / f"{schema_name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(schema_dict, f, indent=2, ensure_ascii=False)
            f.write("\n")
        generated_files.append(file_path)

    return generated_files


if __name__ == "__main__":
    files = generate_json_schemas()
    print(f"Successfully generated {len(files)} JSON Schemas in {OUTPUT_DIR}")
    for p in files:
        print(f" - {p.name}")
