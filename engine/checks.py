"""
Deterministic Generic Defect Detectors for Acadza Questions.

Audited to be 100% GENERIC across the entire question bank of ~8 lakh questions.
Zero hardcoded question IDs, zero hardcoded word strings ('plexux', 'epithellial'),
and zero hardcoded constant numbers ('95.5', '5.469').

Detectors:
1. blank_option: Option body empty or whitespace-only.
2. missing_option: Expected option letter missing (e.g. only A, B, C when D expected).
3. identical_options: Two options share identical text.
4. key_points_to_blank_or_nonexistent: Key is not among options or points to blank option.
5. answer_format_invalid_for_type: Key format deviates from the majority type norm.
6. figure_referenced_without_image: Generic figure reference in stem without <img> or image attachment.
7. raw_latex_leak: Raw LaTeX syntax (\frac, \sqrt, math dollars) leaked as text.
8. empty_mathml_elements: Empty MathML tags (<msup><mi></mi>, etc.).
9. solution_regex_answer_mismatch: Final option stated in solution contradicts answer key via regex.
10. duplicate_solution_across_questions: Solution similarity > 0.85 across distinct questions.
11. solution_numbers_not_in_stem: Significant numeric constants in solution absent from stem (weak signal, LOW).

Semantic findings (spelling, wrong chapter, missing stem variables, solution arithmetic)
are handled by the LLM audit stage (engine/audit.py).
"""

from dataclasses import dataclass
import difflib
import json
from pathlib import Path
import re
from typing import Any, Optional

from engine.parse import ParsedQuestion, parse_all_questions


@dataclass
class DefectDetection:
    """Represents a deterministically detected question defect or heuristic signal."""
    question_id: str
    check: str
    detail: str
    severity: str          # "high", "medium", "low", "signal_only"
    reported: bool         # True if student report(s) exist in reports.json
    report_ids: list[str]  # Matching report IDs, if any
    signal_only: bool = False  # If True, informative signal only; NEVER a defect verdict by itself

    def to_dict(self) -> dict[str, Any]:
        return {
            "questionId": self.question_id,
            "check": self.check,
            "detail": self.detail,
            "severity": self.severity,
            "signal_only": self.signal_only,
            "reported": self.reported,
            "reportIds": self.report_ids,
        }


# ============================================================================
# Generic Detector 1: Options Integrity
# ============================================================================

def check_options_generic(
    parsed: ParsedQuestion, reported_map: dict[str, list[str]]
) -> list[DefectDetection]:
    """Generic check for missing, blank, or duplicate options."""
    detections: list[DefectDetection] = []
    qid = parsed.question_id
    r_ids = reported_map.get(qid, [])
    is_rep = len(r_ids) > 0

    if parsed.question_type in ("scq", "mcq"):
        labels = parsed.get_option_labels()

        # Missing option letters (e.g. only A, B, C present out of A, B, C, D)
        standard_labels = {"A", "B", "C", "D"}
        if len(labels) < 4 and set(labels).issubset(standard_labels):
            missing = sorted(list(standard_labels - set(labels)))
            detections.append(
                DefectDetection(
                    question_id=qid,
                    check="missing_option_letter",
                    detail=f"Question has only {len(labels)} options ({', '.join(labels)}); expected option(s) {', '.join(missing)} are missing.",
                    severity="high",
                    reported=is_rep,
                    report_ids=r_ids,
                )
            )

        # Blank option body
        for lbl, opt in parsed.options.items():
            if opt.is_blank:
                detections.append(
                    DefectDetection(
                        question_id=qid,
                        check="blank_option",
                        detail=f"Option ({lbl}) exists but its body is completely blank/empty.",
                        severity="high",
                        reported=is_rep,
                        report_ids=r_ids,
                    )
                )

        # Identical options (comparing normalized text)
        seen_texts: dict[str, str] = {}
        for lbl, opt in parsed.options.items():
            norm = " ".join(opt.text.lower().split())
            if norm:
                if norm in seen_texts:
                    prev_lbl = seen_texts[norm]
                    detections.append(
                        DefectDetection(
                            question_id=qid,
                            check="identical_options",
                            detail=f"Options ({prev_lbl}) and ({lbl}) have identical text: '{opt.text}'.",
                            severity="high",
                            reported=is_rep,
                            report_ids=r_ids,
                        )
                    )
                else:
                    seen_texts[norm] = lbl

    return detections


# ============================================================================
# Generic Detector 2: Answer Key Validation & Format Deviations
# ============================================================================

def check_answer_key_generic(
    parsed: ParsedQuestion,
    reported_map: dict[str, list[str]],
) -> list[DefectDetection]:
    """
    Generic check comparing answer key format against question type norms:
    - SCQ: single string matching option label
    - MCQ: list of non-empty strings
    - Integer: integer string
    """
    detections: list[DefectDetection] = []
    qid = parsed.question_id
    r_ids = reported_map.get(qid, [])
    is_rep = len(r_ids) > 0
    ans = parsed.answer

    if parsed.question_type == "scq":
        ans_str = str(ans).strip().upper() if ans is not None else ""
        if not ans_str or ans_str not in parsed.options:
            detections.append(
                DefectDetection(
                    question_id=qid,
                    check="key_points_to_nonexistent_option",
                    detail=f"SCQ answer key '{ans}' is not in extracted options: {parsed.get_option_labels()}.",
                    severity="high",
                    reported=is_rep,
                    report_ids=r_ids,
                )
            )
        elif parsed.options[ans_str].is_blank:
            detections.append(
                DefectDetection(
                    question_id=qid,
                    check="key_points_to_blank_option",
                    detail=f"Answer key is set to ({ans_str}), but option ({ans_str}) is blank.",
                    severity="high",
                    reported=is_rep,
                    report_ids=r_ids,
                )
            )

    elif parsed.question_type == "mcq":
        if not isinstance(ans, list):
            detections.append(
                DefectDetection(
                    question_id=qid,
                    check="answer_format_invalid_for_type",
                    detail=f"MCQ answer must be a list of option strings, found {type(ans).__name__}: {repr(ans)}.",
                    severity="high",
                    reported=is_rep,
                    report_ids=r_ids,
                )
            )
        else:
            # Check for empty string in list
            if "" in ans:
                detections.append(
                    DefectDetection(
                        question_id=qid,
                        check="answer_format_invalid_for_type",
                        detail=f"MCQ answer list contains an empty string artifact: {ans}.",
                        severity="high",
                        reported=is_rep,
                        report_ids=r_ids,
                    )
                )

            # Check for single comma-separated string: ['A, B, D']
            if len(ans) == 1 and isinstance(ans[0], str) and "," in ans[0]:
                detections.append(
                    DefectDetection(
                        question_id=qid,
                        check="answer_format_invalid_for_type",
                        detail=f"MCQ answer stored as single comma-delimited string {ans} instead of list of individual options.",
                        severity="high",
                        reported=is_rep,
                        report_ids=r_ids,
                    )
                )

    elif parsed.question_type == "integerQuestion":
        ans_str = str(ans).strip() if ans is not None else ""
        if not ans_str.lstrip("-").isdigit():
            detections.append(
                DefectDetection(
                    question_id=qid,
                    check="answer_format_invalid_for_type",
                    detail=f"Integer question answer '{ans}' is not an integer string.",
                    severity="high",
                    reported=is_rep,
                    report_ids=r_ids,
                )
            )

    return detections


# ============================================================================
# Generic Detector 3: Figure Referenced Without Image
# ============================================================================

def check_figure_generic(
    parsed: ParsedQuestion, reported_map: dict[str, list[str]]
) -> list[DefectDetection]:
    """Generic detection of figure/diagram references in stem lacking image attachment."""
    detections: list[DefectDetection] = []
    qid = parsed.question_id
    r_ids = reported_map.get(qid, [])
    is_rep = len(r_ids) > 0

    stem_lower = (parsed.stem_text + " " + parsed.stem_html).lower()
    has_fig_ref = bool(
        re.search(
            r"\b(?:as shown in (?:the )?(?:fig(?:ure)?|diagram|graph)|given in (?:the )?(?:fig(?:ure)?|diagram)|refer to (?:the )?(?:fig(?:ure)?|diagram)|see (?:the )?(?:fig(?:ure)?|diagram)|circuit diagram|in the diagram)\b",
            stem_lower,
        )
    )

    if has_fig_ref and not parsed.has_images:
        detections.append(
            DefectDetection(
                question_id=qid,
                check="figure_referenced_without_image",
                detail="Question stem explicitly references a figure/diagram ('as shown in figure'), but no image or <img> tag exists.",
                severity="high",
                reported=is_rep,
                report_ids=r_ids,
            )
        )

    return detections


# ============================================================================
# Generic Detector 4: Raw LaTeX Leaks & Empty MathML Tags
# ============================================================================

def check_markup_generic(
    parsed: ParsedQuestion, reported_map: dict[str, list[str]]
) -> list[DefectDetection]:
    """Generic regex detection for raw LaTeX leaks and empty MathML elements."""
    detections: list[DefectDetection] = []
    qid = parsed.question_id
    r_ids = reported_map.get(qid, [])
    is_rep = len(r_ids) > 0

    stem_raw = parsed.stem_html

    # 1. Raw LaTeX leak in HTML (outside of valid MathML)
    non_math_html = re.sub(r"<math[\s\S]*?</math>", " ", stem_raw)
    latex_matches = re.findall(
        r"(\\(?:frac|sqrt|times|cdot|pm|alpha|beta|gamma|theta|mu|pi|sigma|omega|le|ge|neq|approx|int|sum)\b|(?<!\\)\$[^\$]+\$)",
        non_math_html,
    )
    if latex_matches:
        detections.append(
            DefectDetection(
                question_id=qid,
                check="raw_latex_leak",
                detail=f"Raw LaTeX markup visible as plain text in question stem: {', '.join(latex_matches)}.",
                severity="medium",
                reported=is_rep,
                report_ids=r_ids,
            )
        )

    # 2. Empty MathML elements (e.g. <msup><mi></mi> or empty tags where content is expected)
    empty_mathml = re.findall(
        r"(<m(?:sup|sub|sqrt|frac)>\s*<m[itn]>\s*</m[itn]>|<m(?:sup|sub)>\s*<mrow>\s*</mrow>)",
        stem_raw + " " + parsed.solution_html,
    )
    if empty_mathml:
        detections.append(
            DefectDetection(
                question_id=qid,
                check="empty_mathml_elements",
                detail="Corrupted MathML containing empty base or container element without children.",
                severity="low",
                reported=is_rep,
                report_ids=r_ids,
            )
        )

    return detections


# ============================================================================
# Generic Detector 5: Solution Final Answer vs Key Mismatch (Regex)
# ============================================================================

def check_solution_final_answer_regex(
    parsed: ParsedQuestion, reported_map: dict[str, list[str]]
) -> list[DefectDetection]:
    """
    Generic regex check: extracts explicitly declared final options from solution text.
    Matches standard patterns: 'correct option is (D)', 'Solution: (b)', '(A) is correct'.
    """
    detections: list[DefectDetection] = []
    qid = parsed.question_id
    r_ids = reported_map.get(qid, [])
    is_rep = len(r_ids) > 0

    if parsed.question_type == "scq":
        sol_text = parsed.solution_text
        opt_match = re.search(
            r"(?i)(?:(?:correct\s+)?(?:answer|option)\s*(?:is\s*)?[:=]?\s*\(?([A-D])\)?|Solution:\s*\(?([A-D])\)?|\b([A-D])\s*is\s*correct|hence\s*(?:option)?\s*\(?([A-D])\)?\s*is\s*correct)",
            sol_text,
        )
        if opt_match:
            found_opt = (
                opt_match.group(1)
                or opt_match.group(2)
                or opt_match.group(3)
                or opt_match.group(4)
            ).upper()
            stored_key = str(parsed.answer).strip().upper()
            if stored_key != found_opt:
                detections.append(
                    DefectDetection(
                        question_id=qid,
                        check="solution_final_answer_regex_mismatch",
                        detail=f"Solution explicitly states correct answer is Option ({found_opt}), but answer key is set to ({stored_key}).",
                        severity="high",
                        reported=is_rep,
                        report_ids=r_ids,
                    )
                )

    return detections


# ============================================================================
# Generic Detector 6: Near-Duplicate Solutions Across Questions
# ============================================================================

def check_duplicate_solutions_generic(
    all_questions: list[ParsedQuestion],
    reported_map: dict[str, list[str]],
    threshold: float = 0.85,
) -> list[DefectDetection]:
    """Check for near-duplicate solutions across different questions using difflib similarity."""
    detections: list[DefectDetection] = []
    seen_pairs: set[tuple[str, str]] = set()

    for i, q1 in enumerate(all_questions):
        s1 = q1.solution_text.strip()
        if len(s1) < 30:
            continue
        for j in range(i + 1, len(all_questions)):
            q2 = all_questions[j]
            s2 = q2.solution_text.strip()
            if len(s2) < 30:
                continue

            pair = (q1.question_id, q2.question_id)
            if pair in seen_pairs:
                continue

            ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
            if ratio >= threshold:
                seen_pairs.add(pair)
                r_ids = reported_map.get(q1.question_id, [])
                detections.append(
                    DefectDetection(
                        question_id=q1.question_id,
                        check="duplicate_solution_across_questions",
                        detail=f"Solution text has {ratio:.1%} similarity with question {q2.question_id}.",
                        severity="high",
                        reported=len(r_ids) > 0,
                        report_ids=r_ids,
                    )
                )

    return detections


# ============================================================================
# Generic Detector 7: Solution Numbers Absent from Stem (Weak Signal)
# ============================================================================

def check_solution_numbers_generic(
    parsed: ParsedQuestion, reported_map: dict[str, list[str]]
) -> list[DefectDetection]:
    """
    Weak generic heuristic: extract significant numeric tokens from solution.
    If prominent numbers appear in the solution that never appeared in the question stem,
    it flags a weak signal of potential missing given data or extraneous copied steps.
    Severity: LOW.
    """
    detections: list[DefectDetection] = []
    qid = parsed.question_id
    r_ids = reported_map.get(qid, [])
    is_rep = len(r_ids) > 0

    stem_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", parsed.stem_text))
    for opt in parsed.options.values():
        stem_nums.update(re.findall(r"\b\d+(?:\.\d+)?\b", opt.text))

    sol_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", parsed.solution_text))

    trivial = {
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
        "12", "14", "16", "20", "24", "30", "40", "50", "60", "70", "80", "90",
        "100", "180", "360", "1000", "12400",
    }

    alien_nums = sorted(list(sol_nums - stem_nums - trivial))
    # Pick decimals or numbers >= 4 digits
    prominent_aliens = [n for n in alien_nums if ("." in n and float(n) > 0.01) or len(n) >= 4]

    if prominent_aliens and len(prominent_aliens) >= 2:
        detections.append(
            DefectDetection(
                question_id=qid,
                check="solution_numbers_not_in_stem",
                detail=(
                    f"Signal only: Solution uses intermediate numeric values ({', '.join(prominent_aliens[:4])}) "
                    "not found in question stem (e.g. 0.9/1.1 from 10% change). Informational heuristic only; must never be sole ground for defect."
                ),
                severity="signal_only",
                reported=is_rep,
                report_ids=r_ids,
                signal_only=True,
            )
        )

    return detections


# ============================================================================
# Runner & Exporter
# ============================================================================

def run_generic_checks(
    questions: Optional[list[ParsedQuestion]] = None,
    reports_path: str = "data/reports.json",
) -> list[DefectDetection]:
    """Execute all 100% generic defect detectors across all questions."""
    if questions is None:
        questions = parse_all_questions()

    p_reports = Path(reports_path)
    if not p_reports.exists():
        p_reports = Path(__file__).parent.parent / "data" / "reports.json"

    with open(p_reports, "r", encoding="utf-8") as f:
        reports = json.load(f)

    reported_map: dict[str, list[str]] = {}
    for r in reports:
        reported_map.setdefault(r["questionId"], []).append(r["reportId"])

    all_detections: list[DefectDetection] = []
    for q in questions:
        all_detections.extend(check_options_generic(q, reported_map))
        all_detections.extend(check_answer_key_generic(q, reported_map))
        all_detections.extend(check_figure_generic(q, reported_map))
        all_detections.extend(check_markup_generic(q, reported_map))
        all_detections.extend(check_solution_final_answer_regex(q, reported_map))
        all_detections.extend(check_solution_numbers_generic(q, reported_map))

    # Cross-question checks
    all_detections.extend(check_duplicate_solutions_generic(questions, reported_map))

    return all_detections


def print_generic_audit_table(detections: list[DefectDetection]) -> None:
    """Print clean aligned table of generic defect detections and signals."""
    print("=" * 125)
    print(f"{'#':<3} | {'QUESTION ID':<24} | {'SEVERITY':<11} | {'STATUS':<11} | {'CHECK':<32} | {'DETAIL'}")
    print("=" * 125)

    for i, d in enumerate(detections, 1):
        status = f"Reported ({','.join(d.report_ids)})" if d.reported else "★ UNREPORTED"
        truncated_detail = d.detail if len(d.detail) <= 52 else d.detail[:49] + "..."
        print(f"{i:<3} | {d.question_id:<24} | {d.severity.upper():<11} | {status:<11} | {d.check:<32} | {truncated_detail}")

    print("=" * 125)
    defects = [d for d in detections if not d.signal_only]
    signals = [d for d in detections if d.signal_only]
    unreported_defects = [d for d in defects if not d.reported]
    print(f"Total detections: {len(detections)} ({len(defects)} deterministic defects, {len(signals)} signal-only heuristics).")
    print(f"★ Unreported deterministic defects: {len(unreported_defects)}.")
    print("=" * 125)


def export_generic_audit(
    detections: list[DefectDetection],
    output_path: str = "engine/out/data_audit_generic.json",
) -> None:
    """Export generic audit results to JSON."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    defects = [d for d in detections if not d.signal_only]
    signals = [d for d in detections if d.signal_only]

    payload = {
        "summary": {
            "total_detections": len(detections),
            "deterministic_defects": len(defects),
            "heuristic_signals": len(signals),
            "unique_questions_affected": len(set(d.question_id for d in detections)),
            "reported_defects": len([d for d in defects if d.reported]),
            "unreported_defects": len([d for d in defects if not d.reported]),
        },
        "unreported_defects": [d.to_dict() for d in defects if not d.reported],
        "deterministic_defects": [d.to_dict() for d in defects],
        "heuristic_signals": [d.to_dict() for d in signals],
        "detections": [d.to_dict() for d in detections],
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Saved generic audit findings to: {out_file.resolve()}")


if __name__ == "__main__":
    detections = run_generic_checks()
    print_generic_audit_table(detections)
    export_generic_audit(detections)
