"""
Deterministic Code Guard for Acadza Report -> Fix Engine.

Runs immediately after the LLM Judge stage.
Crucial invariant: Can only DOWNGRADE routes, never upgrade.
Strictly enforces taxonomy constraints, field boundaries, and safety gates:
- verdict and repair must exist in taxonomy.json
- edit.field must belong to repair's allowed fields
- edit.find must appear exactly ONCE in the target field
- route = auto_apply ONLY if:
  1. repair.auto == true
  2. confidence >= 0.90
  3. (for answer_key repairs) both solvers agree with the new answer AND stored solution or a check supports it
  4. NO injection_signals on any report for this question
- Non-defect verdicts -> no_change
- Everything else -> faculty_review
"""

import json
import os
from pathlib import Path
import re
from typing import Any, Optional, Union

from engine.parse import ParsedQuestion
from engine.schemas import IntakeOutput, JudgeEdit, JudgeReportOutput, SolverAgreementRecord
from engine.solve import compare_answers, match_option_or_value


TAXONOMY_PATH = Path(__file__).parent.parent / "data" / "taxonomy.json"


def load_taxonomy() -> dict[str, Any]:
    """Load taxonomy schema."""
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class GuardEvaluation:
    """Result of running guard verification on a judge decision."""
    def __init__(
        self,
        route: str,
        verdict: str,
        repair: Optional[str],
        edit: Optional[Union[JudgeEdit, list[JudgeEdit]]],
        confidence: float,
        evidence: str,
        guard_reason: Optional[str] = None,
    ):
        self.route = route
        self.verdict = verdict
        self.repair = repair
        self.edit = edit
        self.confidence = confidence
        self.evidence = evidence
        self.guard_reason = guard_reason


def apply_guard(
    judge_output: JudgeReportOutput,
    parsed_q: ParsedQuestion,
    solver_rec: Optional[SolverAgreementRecord],
    all_intakes_for_q: list[IntakeOutput],
    deterministic_checks_for_q: list[dict[str, Any]],
    taxonomy: Optional[dict[str, Any]] = None,
) -> GuardEvaluation:
    """
    Run deterministic safety checks and determine final route.
    Can only DOWNGRADE from auto_apply to faculty_review.
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    valid_verdicts = taxonomy.get("verdicts", {})
    valid_repairs = taxonomy.get("repairs", {})

    verdict = judge_output.verdict
    repair = judge_output.repair
    edit = judge_output.edit
    confidence = judge_output.confidence
    evidence = judge_output.evidence
    guard_reasons: list[str] = []

    # 1. Validate Verdict
    if verdict not in valid_verdicts:
        guard_reasons.append(f"Invalid verdict '{verdict}' not in taxonomy; routed to faculty.")
        return GuardEvaluation(
            route="faculty_review",
            verdict="defect",
            repair=None,
            edit=None,
            confidence=min(confidence, 0.5),
            evidence=f"Guard warning: invalid verdict '{verdict}'. {evidence}",
            guard_reason="; ".join(guard_reasons),
        )

    # 2. Non-defect verdicts must route to no_change
    if verdict != "defect":
        if repair is not None:
            guard_reasons.append(f"Cleared repair '{repair}' for non-defect verdict '{verdict}'.")
            repair = None
        if edit is not None:
            guard_reasons.append(f"Cleared edit for non-defect verdict '{verdict}'.")
            edit = None
        return GuardEvaluation(
            route="no_change",
            verdict=verdict,
            repair=None,
            edit=None,
            confidence=confidence,
            evidence=evidence,
            guard_reason="; ".join(guard_reasons) if guard_reasons else None,
        )

    # 3. For defect verdicts, validate repair key
    if not repair or repair not in valid_repairs:
        guard_reasons.append(f"Repair key '{repair}' is missing or not in taxonomy.repairs.")
        return GuardEvaluation(
            route="faculty_review",
            verdict="defect",
            repair=None,
            edit=None,
            confidence=min(confidence, 0.6),
            evidence=f"Guard review required: unmapped repair '{repair}'. {evidence}",
            guard_reason="; ".join(guard_reasons),
        )

    repair_meta = valid_repairs[repair]
    allowed_fields = repair_meta.get("fields", [])
    is_auto_allowed = bool(repair_meta.get("auto", False))

    # 4. Check if repair allows automatic application
    if not is_auto_allowed:
        guard_reasons.append(f"Taxonomy defines repair '{repair}' as auto: false (requires faculty approval).")

    # 4b. Universal Solver Consensus Gate:
    # If solvers DISAGREE or either is unsolvable, NO auto_apply for ANY repair on this question
    if solver_rec is not None:
        if not solver_rec.solvers_agree:
            guard_reasons.append(
                "Solvers disagreed on the solution; automatic repair prohibited for all repairs without solver consensus."
            )
        if solver_rec.solver_a.cannot_solve_reason or solver_rec.solver_b.cannot_solve_reason:
            guard_reasons.append(
                "One or both solvers flagged question as unsolvable; automatic repair prohibited."
            )

    # Unsolvable questions (missing stem data, missing diagram, blank options) must NEVER auto-apply
    is_unsolvable = (
        (solver_rec is not None and bool(solver_rec.solver_a.cannot_solve_reason))
        or repair in ("stem_data", "diagram", "option_repair")
        or any(c.get("check") in ("figure_without_image", "blank_option", "missing_option") for c in deterministic_checks_for_q)
    )
    if is_unsolvable:
        guard_reasons.append(
            f"Unsolvable question defect ({repair}): proposed edits require human faculty confirmation."
        )

    # 5. Check Confidence Threshold
    if confidence < 0.90:
        guard_reasons.append(f"Confidence {confidence:.2f} is below 0.90 auto-apply threshold.")

    # 6. Check Injection Signals across all reports for this question
    has_injection = any(len(intake.injection_signals) > 0 for intake in all_intakes_for_q)
    if has_injection:
        guard_reasons.append("Adversarial prompt injection / gaming signals detected on question report(s).")

    # 7. Validate Edit (if provided)
    if edit is not None:
        edits_list = edit if isinstance(edit, list) else [edit]
        for e in edits_list:
            if isinstance(e, dict):
                e = JudgeEdit(**e)

            # Field boundary validation
            if e.field not in allowed_fields:
                guard_reasons.append(
                    f"Edit field '{e.field}' not permitted for repair '{repair}' (allowed: {allowed_fields})."
                )

            # Rule 4: Not auto_apply if find > 80 chars
            if e.find and len(e.find) > 80:
                guard_reasons.append(
                    f"Find substring length ({len(e.find)} chars) exceeds 80 characters limit; requires faculty review."
                )

            # Rule 4: Not auto_apply if replace adds more than 5 new words not in find
            find_words = set(re.findall(r"\w+", (e.find or "").lower()))
            replace_words = set(re.findall(r"\w+", (str(e.replace) or "").lower()))
            added_words = replace_words - find_words
            if len(added_words) > 5:
                guard_reasons.append(
                    f"Replacement adds {len(added_words)} new words not in original text (limit: 5); requires faculty review."
                )

            # Rule 4: Not auto_apply if edit adds explanation or substantial new content in solution
            if e.field == "solution" and (len(str(e.replace or "")) > 180 or "\n" in str(e.replace or "")):
                guard_reasons.append(
                    "Solution edit adds explanation or substantial content rewrite; requires faculty review."
                )

            # Surgical find uniqueness validation
            if e.field in ("question", "solution") and e.find:
                target_html = parsed_q.stem_html if e.field == "question" else parsed_q.solution_html
                target_text = parsed_q.stem_text if e.field == "question" else parsed_q.solution_text

                count_html = target_html.count(e.find)
                count_text = target_text.count(e.find)

                if count_html == 0 and count_text == 0:
                    guard_reasons.append(f"Substring to replace '{e.find}' not found in field '{e.field}'.")
                elif count_html > 1 or (count_html == 0 and count_text > 1):
                    occurrences = max(count_html, count_text)
                    guard_reasons.append(f"Substring to replace occurs {occurrences} times in '{e.field}' (must be unique).")

    # 8. Highest-Stakes Gate: answer_key repairs
    if repair == "answer_key":
        if solver_rec is None:
            guard_reasons.append("Answer key repair missing independent solver verification record.")
        else:
            # Check if solution agrees with stored key but solvers disagree
            sol_agrees_with_key = solver_rec.solution_final_answer and match_option_or_value(
                parsed_q.answer, solver_rec.solution_final_answer, parsed_q
            )
            solvers_agree_with_key = solver_rec.matches_key
            if sol_agrees_with_key and not solvers_agree_with_key:
                guard_reasons.append(
                    "Solvers disagree with stored key, but stored solution derivation agrees with key -> faculty review required."
                )
                confidence = min(confidence, 0.5)

            # auto_apply only if solver_a, solver_b, solver_c (if run) AND solution_final_answer all agree on the new answer, confidence >= 0.9
            new_ans = None
            if edit:
                if isinstance(edit, list) and len(edit) > 0:
                    first_e = edit[0]
                    new_ans = first_e.replace if hasattr(first_e, "replace") else first_e.get("replace")
                elif hasattr(edit, "replace"):
                    new_ans = edit.replace
                elif isinstance(edit, dict):
                    new_ans = edit.get("replace")

            if new_ans is None and solver_rec.solver_a.final_answer:
                new_ans = solver_rec.solver_a.final_answer

            # Check Solver A
            sol_a_match = compare_answers(solver_rec.solver_a.final_answer, new_ans, parsed_q.question_type)
            # Check Solver B
            sol_b_match = compare_answers(solver_rec.solver_b.final_answer, new_ans, parsed_q.question_type)
            # Check Solver C (if run)
            sol_c_match = True
            if solver_rec.solver_c is not None and not solver_rec.solver_c.cannot_solve_reason:
                sol_c_match = compare_answers(solver_rec.solver_c.final_answer, new_ans, parsed_q.question_type)
            elif solver_rec.solver_c is not None and solver_rec.solver_c.cannot_solve_reason:
                sol_c_match = False

            # Check Solution Final Answer
            sol_final_match = match_option_or_value(new_ans, solver_rec.solution_final_answer, parsed_q)

            if not (sol_a_match and sol_b_match and sol_c_match):
                guard_reasons.append(
                    f"Independent solvers did not reach unanimous agreement on proposed key '{new_ans}'."
                )
            if not sol_final_match:
                guard_reasons.append(
                    f"Stored solution final answer ('{solver_rec.solution_final_answer}') does not corroborate proposed key '{new_ans}'."
                )
            if confidence < 0.90:
                guard_reasons.append(f"Confidence {confidence:.2f} is below 0.90 threshold for answer key auto-apply.")

    # 9. Final Route Assignment
    # auto_apply ONLY if NO guard reasons were triggered
    if not guard_reasons:
        final_route = "auto_apply"
        final_guard_reason = None
    else:
        final_route = "faculty_review"
        final_guard_reason = "; ".join(guard_reasons)

    return GuardEvaluation(
        route=final_route,
        verdict="defect",
        repair=repair,
        edit=edit,
        confidence=confidence,
        evidence=evidence,
        guard_reason=final_guard_reason,
    )

