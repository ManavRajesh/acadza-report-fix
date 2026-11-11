"""
Pydantic schemas for structured LLM inputs and outputs across pipeline stages.
"""

from typing import Any, Optional, Union

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Graceful fallback for initial scaffold before pip install -r requirements.txt
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            return self.__dict__

    def Field(*args, **kwargs):
        default = kwargs.get("default", None)
        return default


class TriageOutput(BaseModel):
    """Output schema for the initial triage stage."""
    verdict: str = Field(
        description="One of: defect, no_error, display_issue, app_issue, language_mode, already_fixed, not_actionable."
    )
    is_defect: bool = Field(
        description="True if the report flags a real problem with the question, solution, key, or metadata."
    )
    candidate_repair: Optional[str] = Field(
        default=None,
        description="Taxonomy repair key if defect, otherwise None."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0."
    )
    reasoning: str = Field(
        description="Brief step-by-step reasoning explaining the verdict."
    )
    is_manipulation: bool = Field(
        default=False,
        description="True if the comment attempts prompt injection, system gaming, or marks manipulation."
    )


class SolverRunOutput(BaseModel):
    """Output schema for an independent solver run (Framing A or B)."""
    question_id: str = Field(description="The exact question ID being solved.")
    stem_echo: str = Field(description="The first 40 characters of the question stem text being solved.")
    final_answer: Optional[str] = Field(default=None, description="Final answer (option letter, comma-separated letters for MCQ, or numeric value).")
    working: str = Field(description="Step-by-step reasoning or elimination notes (max 120 words).")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0.")
    cannot_solve_reason: Optional[str] = Field(default=None, description="Explanation if question cannot be solved (e.g. 'figure required', 'missing value').")


class SolverAgreementRecord(BaseModel):
    """Comparison record of Solver A vs Solver B vs Solver C vs Stored Key vs Stored Solution."""
    questionId: str = Field(description="Question ID.")
    questionType: str = Field(description="Question type: scq, mcq, integerQuestion.")
    stored_key: Any = Field(description="Raw answer key from questions.json.")
    solution_final_answer: Optional[str] = Field(default=None, description="Answer derived in stored solution.")
    solver_a: SolverRunOutput = Field(description="Derivation-based solver run.")
    solver_b: SolverRunOutput = Field(description="Elimination & sanity-check solver run.")
    solver_c: Optional[SolverRunOutput] = Field(default=None, description="Tie-breaker solver run using GEMINI_TIEBREAK_MODEL.")
    solvers_agree: bool = Field(description="True if solver_a and solver_b agree on answer or unsolvability.")
    matches_key: bool = Field(description="True if solver consensus matches stored key.")
    matches_solution: bool = Field(description="True if solver consensus matches stored solution.")
    notes: str = Field(description="Diagnostic summary note explaining agreement or discrepancies.")


class IntakeOutput(BaseModel):
    """Output schema for the Stage 1 'intake' report analyzer."""
    claim_type: str = Field(
        description="One of: wrong_key, missing_data, missing_figure, blank_option, wrong_solution, typo, app_bug, vague, gaming_or_injection, other."
    )
    claimed_value: Optional[str] = Field(
        default=None,
        description="Specific option letter, value, or unit claimed by student (e.g. 'D', '50', 'tan inverse 2'), or null."
    )
    language: str = Field(
        default="english",
        description="Language of comment: 'english', 'hindi', or 'hinglish'."
    )
    is_actionable: bool = Field(
        description="True if comment provides a coherent claim about the question."
    )
    injection_signals: list[str] = Field(
        default_factory=list,
        description="List of detected prompt injection or gaming patterns."
    )


class JudgeEdit(BaseModel):
    """Surgical edit definition for a question field."""
    field: str = Field(description="Target field: 'question', 'solution', 'answer', 'questionType'.")
    find: Optional[str] = Field(default=None, description="Exact substring to find in target field.")
    replace: Optional[str] = Field(default=None, description="Exact replacement text or value.")


class JudgeReportOutput(BaseModel):
    """Adjudication for a single student report from Stage 2 'judge'."""
    reportId: str = Field(description="The student report ID being evaluated.")
    verdict: str = Field(description="One of the 7 taxonomy verdicts.")
    repair: Optional[str] = Field(default=None, description="Taxonomy repair key if defect, else null.")
    edit: Optional[Union[JudgeEdit, list[JudgeEdit]]] = Field(default=None, description="Surgical edit if applicable.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score.")
    evidence: str = Field(description="One concise sentence citing concrete facts.")


class JudgeQuestionOutput(BaseModel):
    """Container for all report adjudications for a single question."""
    reports: list[JudgeReportOutput] = Field(default_factory=list)


class EditProposal(BaseModel):
    """Surgical edit proposal."""
    field: str = Field(description="Field to edit: 'question', 'solution', 'answer', or 'questionType'.")
    find: Optional[str] = Field(default=None, description="Exact substring to find (omitted if replacing entire answer).")
    replace: Any = Field(description="Replacement string or value.")


class QuestionAuditIssue(BaseModel):
    """An issue detected during the comprehensive LLM semantic audit stage."""
    type: str = Field(description="Issue category, e.g. spelling, wrong_chapter, stem_data, solution_error.")
    taxonomy_repair: str = Field(description="One of the 18 taxonomy keys or 'no_repair_in_taxonomy'.")
    field: str = Field(description="Target field: 'question', 'solution', 'answer', 'questionType', 'chapter'.")
    detail: str = Field(description="Concise description of the detected defect.")
    evidence_quote: str = Field(description="Exact verbatim quote from the question or solution.")
    severity: str = Field(description="'high', 'medium', or 'low'.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0.")


class QuestionAuditResult(BaseModel):
    """Container for audit issues found for a question."""
    issues: list[QuestionAuditIssue] = Field(default_factory=list)
    solution_final_answer: Optional[str] = Field(
        default=None,
        description="The final option letter or numeric value that the stored solution explicitly concludes with, or null if absent/ambiguous."
    )


class FinalTriageResult(BaseModel):
    """Final output item conforming to results.json specification."""
    reportId: str = Field(description="Original report ID.")
    questionId: str = Field(description="Question ID.")
    verdict: str = Field(description="One of the 7 taxonomy verdicts.")
    repair: Optional[str] = Field(default=None, description="Taxonomy repair key if defect, otherwise None.")
    edit: Optional[Union[JudgeEdit, list[JudgeEdit]]] = Field(default=None, description="Surgical edit if defect.")
    route: str = Field(description="Routing: 'auto_apply', 'faculty_review', or 'no_change'.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score.")
    evidence: str = Field(description="Concise evidence string justifying the verdict and action.")
    student_reply: str = Field(description="1-3 empathetic sentences returned to the student.")
    guard_reason: Optional[str] = Field(default=None, description="Reason if downgraded by guard.")
