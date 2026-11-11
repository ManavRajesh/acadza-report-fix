"""
LLM Semantic Audit Stage for Acadza Questions.

Audits ALL 43 questions for semantic, mathematical, pedagogical, and textual defects:
- Spelling and OCR errors
- Missing given data in question stem (assumed in solution)
- Solution arithmetic and derivation errors
- Solution foreign / alien snippets copied from other questions
- Wrong chapter / subject classifications
- Answer key disagreements where derivation proves key is wrong
- Missing answer forms / units in integer questions
- Leaked exam reference metadata

Rules:
1. Verbatim quote grounding: every reported issue MUST quote exact text from the question/solution.
2. Taxonomy mapping: every issue maps to one of the 18 keys in taxonomy.json or 'no_repair_in_taxonomy'.
3. Zero-token disk cache via call_llm (engine/.cache).
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any, Optional

from engine.llm import _get_cache_key, call_llm
from engine.parse import ParsedQuestion, parse_all_questions
from engine.schemas import QuestionAuditIssue, QuestionAuditResult


VALID_TAXONOMY_REPAIRS = {
    "spelling",
    "noise",
    "exam_reference",
    "markup_leak",
    "answer_form",
    "notation",
    "stem_data",
    "option_repair",
    "solution_fix",
    "solution_missing",
    "answer_key",
    "type_mismatch",
    "identical_options",
    "diagram",
    "wrong_question",
    "unsound",
    "wrong_chapter",
    "syllabus",
}

DEFAULT_PROMPT_TEMPLATE = Path(__file__).parent / "prompts" / "audit_v2.txt"
CACHE_DIR = Path(__file__).parent / ".cache"


def render_audit_prompt(q: ParsedQuestion, template_text: str) -> str:
    """Safely render prompt without str.format collisions on JSON schema curly braces."""
    if q.options:
        options_text = "\n".join(f"({lbl}) {opt.text}" for lbl, opt in q.options.items())
    else:
        options_text = "None (Integer or Numerical question)"

    replacements = {
        "{question_id}": q.question_id,
        "{subject}": q.subject,
        "{chapter}": q.chapter,
        "{question_type}": q.question_type,
        "{stem_text}": q.stem_text,
        "{options_text}": options_text,
        "{answer_key}": str(q.answer),
        "{solution_text}": q.solution_text,
    }

    prompt = template_text
    for placeholder, val in replacements.items():
        prompt = prompt.replace(placeholder, str(val))
    return prompt


def run_semantic_audit(
    questions: Optional[list[ParsedQuestion]] = None,
    reports_path: str = "data/reports.json",
    prompt_template_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Execute the LLM audit stage across all questions."""
    if questions is None:
        questions = parse_all_questions()

    template_file = Path(prompt_template_path) if prompt_template_path else DEFAULT_PROMPT_TEMPLATE
    template_text = template_file.read_text(encoding="utf-8")

    # Load reports map
    p_reports = Path(reports_path)
    if not p_reports.exists():
        p_reports = Path(__file__).parent.parent / "data" / "reports.json"

    with open(p_reports, "r", encoding="utf-8") as f:
        reports = json.load(f)

    reported_map: dict[str, list[str]] = {}
    for r in reports:
        reported_map.setdefault(r["questionId"], []).append(r["reportId"])

    solution_final_answers: dict[str, Optional[str]] = {}

    def _audit_single_q(q: ParsedQuestion) -> tuple[list[dict[str, Any]], str, Optional[str]]:
        prompt = render_audit_prompt(q, template_text)
        raw_output = call_llm(
            stage="audit",
            prompt=prompt,
            schema=QuestionAuditResult,
        )
        issues = raw_output.get("issues", [])
        sol_final = raw_output.get("solution_final_answer")
        r_ids = reported_map.get(q.question_id, [])
        is_rep = len(r_ids) > 0

        q_issues = []
        for issue in issues:
            repair_key = issue.get("taxonomy_repair", "no_repair_in_taxonomy")
            if repair_key not in VALID_TAXONOMY_REPAIRS:
                repair_key = "no_repair_in_taxonomy"

            audited_item = {
                "questionId": q.question_id,
                "type": issue.get("type", "unknown"),
                "taxonomy_repair": repair_key,
                "field": issue.get("field", "question"),
                "detail": issue.get("detail", ""),
                "evidence_quote": issue.get("evidence_quote", ""),
                "severity": issue.get("severity", "medium"),
                "confidence": issue.get("confidence", 1.0),
                "reported": is_rep,
                "reportIds": r_ids,
            }
            q_issues.append(audited_item)
        return q_issues, q.question_id, sol_final

    all_audited_issues: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for res_list, qid, sol_final in executor.map(_audit_single_q, questions):
            all_audited_issues.extend(res_list)
            solution_final_answers[qid] = sol_final

    return all_audited_issues, solution_final_answers


def export_llm_audit(
    issues: list[dict[str, Any]],
    solution_final_answers: Optional[dict[str, Optional[str]]] = None,
    output_path: str = "engine/out/llm_audit.json",
) -> None:
    """Export semantic audit findings to JSON."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "summary": {
            "total_issues_found": len(issues),
            "unique_questions_affected": len(set(i["questionId"] for i in issues)),
            "reported_issues": len([i for i in issues if i["reported"]]),
            "unreported_issues": len([i for i in issues if not i["reported"]]),
        },
        "solution_final_answers": solution_final_answers or {},
        "unreported_defects": [i for i in issues if not i["reported"]],
        "issues": issues,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Saved LLM semantic audit findings to: {out_file.resolve()}")


def print_audit_table(issues: list[dict[str, Any]]) -> None:
    """Print aligned table of LLM semantic audit issues."""
    print("=" * 125)
    print(f"{'#':<3} | {'QUESTION ID':<24} | {'SEV':<6} | {'REPAIR':<16} | {'STATUS':<11} | {'EVIDENCE QUOTE':<30} | {'DETAIL'}")
    print("=" * 125)

    for i, issue in enumerate(issues, 1):
        status = f"Reported ({','.join(issue['reportIds'])})" if issue["reported"] else "★ UNREPORTED"
        quote = issue["evidence_quote"]
        trunc_quote = quote if len(quote) <= 28 else quote[:25] + "..."
        detail = issue["detail"]
        trunc_detail = detail if len(detail) <= 32 else detail[:29] + "..."
        print(
            f"{i:<3} | {issue['questionId']:<24} | {issue['severity'].upper():<6} | "
            f"{issue['taxonomy_repair']:<16} | {status:<11} | {trunc_quote:<30} | {trunc_detail}"
        )

    print("=" * 125)
    unreported = [i for i in issues if not i["reported"]]
    print(f"Total SEMANTIC issues: {len(issues)} across {len(set(i['questionId'] for i in issues))} questions.")
    print(f"★ Unreported semantic defects found by LLM audit: {len(unreported)}.")
    print("=" * 125)


if __name__ == "__main__":
    issues, sol_finals = run_semantic_audit()
    print_audit_table(issues)
    export_llm_audit(issues, sol_finals)

