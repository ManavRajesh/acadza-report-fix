"""
Acadza Report -> Fix Pipeline.

Orchestrates multi-stage offline triage:
1. Load and group reports by questionId to consolidate duplicate reports.
2. Stage 1 (Triage): Classify report into taxonomy verdict; detect adversarial prompts.
3. Stage 2 (Solver / Verification): Independently solve questions for candidate defects.
4. Stage 3 (Surgical Repair & Routing): Propose minimal edit strictly within taxonomy field limits.
5. Stage 4 (Student Reply): Generate reassuring 1-3 sentence response.
6. Export: Write results.json and mirror to console/public/data/results.json.
"""

import json
from pathlib import Path
from typing import Any, Optional

from engine.llm import call_llm
from engine.schemas import (
    EditProposal,
    FinalTriageResult,
    SolverOutput,
    TriageOutput,
)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt_template(stage: str, version: str = "v1") -> str:
    """
    Load a versioned prompt template from engine/prompts/<stage>_<version>.txt.

    Args:
        stage: Stage name (e.g. 'triage', 'solver', 'repair', 'reply').
        version: Version string (defaults to 'v1').

    Returns:
        str: Raw prompt template with format placeholders.
    """
    filepath = PROMPTS_DIR / f"{stage}_{version}.txt"
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def load_dataset(data_dir: str = "data") -> tuple[dict[str, Any], list[dict], dict]:
    """
    Load questions.json, reports.json, and taxonomy.json from data directory.

    Returns:
        tuple containing:
            - questions_by_id: dict mapping questionId (_id) to question object.
            - reports: list of student report dicts.
            - taxonomy: dict of verdicts and repairs taxonomy.
    """
    base_path = Path(data_dir)
    with open(base_path / "questions.json", "r", encoding="utf-8") as f:
        questions_raw = json.load(f)
    with open(base_path / "reports.json", "r", encoding="utf-8") as f:
        reports = json.load(f)
    with open(base_path / "taxonomy.json", "r", encoding="utf-8") as f:
        taxonomy = json.load(f)

    questions_by_id = {q["_id"]: q for q in questions_raw}
    return questions_by_id, reports, taxonomy


def group_reports_by_question(reports: list[dict]) -> dict[str, list[dict]]:
    """
    Group reports by questionId to allow multi-report awareness and context aggregation.

    Args:
        reports: Raw list of reports from reports.json.

    Returns:
        dict: Mapping of questionId -> list of reports for that question.
    """
    grouped: dict[str, list[dict]] = {}
    for r in reports:
        qid = r["questionId"]
        grouped.setdefault(qid, []).append(r)
    return grouped


def stage_triage(
    report: dict,
    question: dict,
    related_reports: list[dict],
    taxonomy: dict,
    prompt_version: str = "v1",
) -> TriageOutput:
    """
    Stage 1: Evaluate a report against a question to assign a preliminary verdict.

    - Classifies into one of the 7 taxonomy verdicts.
    - Flags adversarial jailbreaks / manipulation attempts (e.g. R027).
    - Checks related reports on the same question to strengthen or corroborate evidence.

    [Stub implementation: To be connected to call_llm]
    """
    raise NotImplementedError("Stage 1 triage will be implemented in the next phase.")


def stage_solver(
    question: dict,
    lead_comment: str,
    prompt_version: str = "v1",
) -> SolverOutput:
    """
    Stage 2: Independently solve and verify the physics/chemistry/biology problem.

    - Verifies mathematical soundness and numerical values.
    - Checks if the question stem omits essential variables.
    - Detects whether stored solution has calculation flaws or belongs to another question.

    [Stub implementation: To be connected to call_llm]
    """
    raise NotImplementedError("Stage 2 solver will be implemented in the next phase.")


def stage_repair_and_route(
    triage_result: TriageOutput,
    solver_result: Optional[SolverOutput],
    question: dict,
    taxonomy: dict,
    prompt_version: str = "v1",
) -> tuple[Optional[str], Optional[EditProposal], str, str]:
    """
    Stage 3: Propose a surgical edit and determine routing based on taxonomy permissions.

    - Validates that edit touches ONLY allowed fields in taxonomy.repairs[repair_key].
    - Adheres to auto: true vs auto: false (must route auto:false to faculty_review).
    - Ensures non-destructive, surgical edits (find-and-replace, not full question rewrites).

    Returns:
        tuple of (repair_key, edit_proposal, route, evidence)

    [Stub implementation: To be connected to call_llm]
    """
    raise NotImplementedError("Stage 3 repair will be implemented in the next phase.")


def stage_student_reply(
    report: dict,
    verdict: str,
    repair: Optional[str],
    evidence: str,
    prompt_version: str = "v1",
) -> str:
    """
    Stage 4: Generate an empathetic 1-3 sentence response addressed to the student.

    - Tailored for a stressed 17-year-old JEE/NEET aspirant.
    - Validates student if right; kindly explains traps if wrong; neutral if hostile.

    [Stub implementation: To be connected to call_llm]
    """
    raise NotImplementedError("Stage 4 reply will be implemented in the next phase.")


def run_pipeline(
    data_dir: str = "data",
    output_path: str = "results.json",
    console_data_dir: str = "console/public/data",
) -> list[dict]:
    """
    Execute the end-to-end triage pipeline on all reports and write results.json.

    Args:
        data_dir: Path to directory containing raw data files.
        output_path: Destination path for root results.json.
        console_data_dir: Destination directory for console public data.

    Returns:
        list[dict]: Array of 44 result items conforming to the Part 3 specification.

    [Stub implementation: Orchestration loop to be implemented]
    """
    raise NotImplementedError("Pipeline orchestration will be implemented in the next phase.")


if __name__ == "__main__":
    print("Acadza Triage Engine Pipeline Stubs Loaded.")

