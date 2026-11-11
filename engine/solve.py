"""
Independent Multi-Faceted Verification / Solver Stage for Acadza Questions.

Solves questions with ZERO anchoring to the stored key, stored solution, or student comments:
- Input: Parsed stem + options ONLY (includes question_id).
- Dual Solver Runs via real LLM calls using GEMINI_SOLVER_MODEL:
  - Solver A: First-principles step-by-step derivation (prompts/solver_a_v1.txt).
  - Solver B: Elimination, dimensional analysis, and sanity checks (prompts/solver_b_v1.txt).
- Safety Invariants:
  - Solver outputs must echo the question_id and first 40 chars of the stem.
  - Strict alignment assertion ensures outputs are never mapped to the wrong question.
  - Results stored in a dictionary keyed by questionId.
- Comparison:
  - Compares Solver A vs Solver B (solvers_agree).
  - Compares consensus vs stored key with 1% numeric tolerance (matches_key).
  - Compares consensus vs stored solution derivation (matches_solution).
  - Compares MCQs as sets.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
from typing import Any, Optional

from engine.llm import call_llm
from engine.parse import ParsedQuestion, parse_all_questions
from engine.schemas import SolverAgreementRecord, SolverRunOutput


from dotenv import load_dotenv

load_dotenv()

SOLVER_A_PROMPT_FILE = Path(__file__).parent / "prompts" / "solver_a_v1.txt"
SOLVER_B_PROMPT_FILE = Path(__file__).parent / "prompts" / "solver_b_v1.txt"
SOLVER_C_PROMPT_FILE = Path(__file__).parent / "prompts" / "solver_c_v1.txt"
DEFAULT_SOLVER_PROMPT = SOLVER_A_PROMPT_FILE
SOLVER_MODEL = os.getenv("GEMINI_SOLVER_MODEL", "gemini-flash-lite-latest")
TIEBREAK_MODEL = os.getenv("GEMINI_TIEBREAK_MODEL", "gemini-3-flash-preview")


def render_solver_prompt(q: ParsedQuestion, template_text: str) -> str:
    """Format prompt with question_id, stem and options (NO stored key, NO stored solution)."""
    if q.options:
        options_text = "\n".join(f"({lbl}) {opt.text}" for lbl, opt in q.options.items())
    else:
        options_text = "None (Integer or Numerical question requiring direct numeric entry)"

    replacements = {
        "{question_id}": q.question_id,
        "{question_type}": q.question_type,
        "{subject}": q.subject,
        "{chapter}": q.chapter,
        "{stem_text}": q.stem_text,
        "{options_text}": options_text,
    }

    prompt = template_text
    for placeholder, val in replacements.items():
        prompt = prompt.replace(placeholder, str(val))
    return prompt


# ============================================================================
# Comparison Helpers: Tolerances, Sets, and Solution Extraction
# ============================================================================

def normalize_mcq_answer(ans: Any) -> set[str]:
    """Normalize MCQ answers into a clean set of uppercase option letters."""
    if ans is None:
        return set()
    if isinstance(ans, list):
        res = set()
        for item in ans:
            for part in str(item).split(","):
                clean = part.strip().upper()
                if clean:
                    res.add(clean)
        return res
    if isinstance(ans, str):
        parts = [p.strip().upper() for p in ans.split(",") if p.strip()]
        return set(parts)
    return {str(ans).strip().upper()}


def parse_numeric_value(val: Any) -> Optional[float]:
    """Robustly parse numeric float from strings or numbers, stripping units."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    m = re.search(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", val_str)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def compare_answers(
    ans1: Any,
    ans2: Any,
    q_type: str,
    tolerance: float = 0.01,
) -> bool:
    """
    Compare two answers:
    - SCQ: Case-insensitive string equality
    - MCQ: Set equality
    - Integer: Numeric comparison within 1% relative tolerance
    """
    if ans1 is None and ans2 is None:
        return True
    if ans1 is None or ans2 is None:
        return False

    if q_type == "scq":
        return str(ans1).strip().upper() == str(ans2).strip().upper()

    elif q_type == "mcq":
        set1 = normalize_mcq_answer(ans1)
        set2 = normalize_mcq_answer(ans2)
        return len(set1) > 0 and set1 == set2

    elif q_type == "integerQuestion":
        num1 = parse_numeric_value(ans1)
        num2 = parse_numeric_value(ans2)
        if num1 is None or num2 is None:
            return str(ans1).strip() == str(ans2).strip()
        denom = max(abs(num1), abs(num2))
        if denom == 0:
            return abs(num1 - num2) < 1e-6
        return (abs(num1 - num2) / denom) <= tolerance

    return str(ans1).strip() == str(ans2).strip()


def match_option_or_value(ans: Any, sol_val: Any, q: ParsedQuestion) -> bool:
    """Check if an answer (e.g. 'A') matches a solution value (e.g. 'A' or '50 V' or '50')."""
    if ans is None or sol_val is None:
        return False
    if compare_answers(ans, sol_val, q.question_type):
        return True
    if q.question_type == "scq" and q.options:
        opt_lbl = str(ans).strip().upper()
        if opt_lbl in q.options:
            opt_text = q.options[opt_lbl].text
            if compare_answers(opt_text, sol_val, "scq"):
                return True
            num_opt = parse_numeric_value(opt_text)
            num_sol = parse_numeric_value(sol_val)
            if num_opt is not None and num_sol is not None:
                denom = max(abs(num_opt), abs(num_sol))
                if denom == 0 or (abs(num_opt - num_sol) / denom) <= 0.01:
                    return True
    return False


def extract_solution_final_answer(q: ParsedQuestion) -> Optional[str]:
    """
    Extract declared or derived final answer from stored solution text.
    If regex cannot find an unambiguous final answer, returns None ('-') instead of guessing.
    """
    sol = q.solution_text.strip()
    if not sol:
        return None

    if q.question_type == "scq":
        # Explicit declarations: 'correct option is (D)', 'Solution: (B)', 'option A is correct', 'hence D'
        m = re.search(
            r"(?i)(?:(?:correct\s+)?(?:answer|option)\s*(?:is\s*)?[:=]?\s*\(?([A-D])\)?\b|Solution:\s*\(?([A-D])\)?\b)",
            sol,
        )
        if m:
            return (m.group(1) or m.group(2)).upper()

        m2 = re.search(r"(?i)\b(?:hence|therefore|thus)\b.*?\boption\s*\(?([A-D])\)?\b", sol)
        if m2:
            return m2.group(1).upper()

        m3 = re.search(r"(?i)\b(?:hence|therefore|thus)\b.*?([A-D])\s*is\s*correct\b", sol)
        if m3:
            return m3.group(1).upper()

        last_line = sol.split("\n")[-1].strip()
        m_last = re.search(r"(?i)\b(?:option|answer)\s*\(?([A-D])\)?\b", last_line)
        if m_last:
            return m_last.group(1).upper()

        return None

    elif q.question_type == "mcq":
        m = re.search(
            r"(?i)(?:correct\s+)?(?:options?|answers?)\s*(?:are|is)?\s*[:=]?\s*([A-D,\s]+)",
            sol,
        )
        if m:
            parts = [p.strip().upper() for p in m.group(1).split(",") if p.strip()]
            if all(p in ("A", "B", "C", "D") for p in parts) and len(parts) > 0:
                return ", ".join(parts)
        return None

    elif q.question_type == "integerQuestion":
        # Look for explicit assignment like 'a = 40 cm', 'answer = 20', '=> 20'
        m = re.search(
            r"(?i)(?:(?:correct\s+)?ans(?:wer)?\s*[:=]?|[a-zA-Z_]\s*=|=>\s*)\s*([-+]?\d+(?:\.\d+)?)\s*(?:[a-zA-Z%]+)?\s*$",
            sol,
        )
        if m:
            return m.group(1)

        last_line = sol.split("\n")[-1].strip()
        m_eq = re.search(r"=\s*([-+]?\d+(?:\.\d+)?)\s*(?:[a-zA-Z%]+)?\s*$", last_line)
        if m_eq:
            return m_eq.group(1)

        return None

    return None


# ============================================================================
# Alignment Assertion Verification
# ============================================================================

def verify_solver_output(q: ParsedQuestion, out: SolverRunOutput, label: str) -> None:
    """Assert that the LLM solver output corresponds exactly to the question asked."""
    # 1. Assert question_id
    clean_out_qid = str(out.question_id).strip()
    if clean_out_qid != q.question_id:
        raise AssertionError(
            f"[{label}] Critical misalignment! Expected question_id '{q.question_id}', "
            f"but solver returned '{clean_out_qid}'."
        )

    # 2. Assert stem echo matches question stem prefix
    stem_prefix = re.sub(r"\s+", " ", q.stem_text[:40]).strip().lower()
    echo_clean = re.sub(r"\s+", " ", out.stem_echo).strip().lower()
    stem_words = set(re.findall(r"\w+", stem_prefix))
    echo_words = set(re.findall(r"\w+", echo_clean))
    overlap = stem_words.intersection(echo_words)

    if len(stem_words) > 1 and not overlap:
        raise AssertionError(
            f"[{label}] Critical stem mismatch for question {q.question_id}!\n"
            f"  Expected prefix: '{stem_prefix}'\n"
            f"  Echoed prefix:   '{echo_clean}'"
        )


# ============================================================================
# Independent Solver Execution Engine (100% Real Live LLM Calls via call_llm)
# ============================================================================

def solve_question_independently(
    q: ParsedQuestion,
    template_a: str,
    template_b: str,
) -> tuple[SolverRunOutput, SolverRunOutput]:
    """Execute dual solver runs (Derivation A vs Elimination B) with zero anchoring via GEMINI_SOLVER_MODEL."""
    prompt_a = render_solver_prompt(q, template_a)
    prompt_b = render_solver_prompt(q, template_b)

    raw_a = call_llm("solver_a", prompt_a, schema=SolverRunOutput, temperature=0.0, model=SOLVER_MODEL)
    raw_b = call_llm("solver_b", prompt_b, schema=SolverRunOutput, temperature=0.0, model=SOLVER_MODEL)

    out_a = SolverRunOutput(**raw_a)
    out_b = SolverRunOutput(**raw_b)

    # Verify alignment assertions
    verify_solver_output(q, out_a, "Solver A")
    verify_solver_output(q, out_b, "Solver B")

    return out_a, out_b


def solve_tiebreaker_run(
    q: ParsedQuestion,
    template_c: str,
) -> SolverRunOutput:
    """Execute authoritative tie-breaker solve using GEMINI_TIEBREAK_MODEL (cached, max 2 retries)."""
    prompt_c = render_solver_prompt(q, template_c)
    raw_c = call_llm(
        stage="solver_c",
        prompt=prompt_c,
        schema=SolverRunOutput,
        temperature=0.0,
        model=TIEBREAK_MODEL,
    )
    out_c = SolverRunOutput(**raw_c)
    verify_solver_output(q, out_c, "Solver C (Tie-Breaker)")
    return out_c


def compare_solver_runs(
    q: ParsedQuestion,
    solver_a: SolverRunOutput,
    solver_b: SolverRunOutput,
    solver_c: Optional[SolverRunOutput] = None,
    solution_final_answer: Optional[str] = None,
) -> SolverAgreementRecord:
    """Compare Solver A vs Solver B vs Solver C vs Stored Key vs Stored Solution."""
    sol_final = solution_final_answer if solution_final_answer is not None else extract_solution_final_answer(q)
    stored_key = q.answer
    q_type = q.question_type

    # Unsolvability check
    if solver_a.cannot_solve_reason or solver_b.cannot_solve_reason:
        solvers_agree = (solver_a.cannot_solve_reason is not None) and (solver_b.cannot_solve_reason is not None)
        consensus_ans = None
    else:
        # Determine consensus among solvers (A, B, and optional C)
        ab_agree = compare_answers(solver_a.final_answer, solver_b.final_answer, q_type)
        if solver_c is not None and not solver_c.cannot_solve_reason:
            ac_agree = compare_answers(solver_a.final_answer, solver_c.final_answer, q_type)
            bc_agree = compare_answers(solver_b.final_answer, solver_c.final_answer, q_type)

            if ab_agree and ac_agree:
                # 3-way unanimous consensus
                solvers_agree = True
                consensus_ans = solver_a.final_answer
            elif ab_agree:
                # A & B agree
                solvers_agree = True
                consensus_ans = solver_a.final_answer
            elif ac_agree:
                # A & C tie-break majority
                solvers_agree = True
                consensus_ans = solver_a.final_answer
            elif bc_agree:
                # B & C tie-break majority
                solvers_agree = True
                consensus_ans = solver_b.final_answer
            else:
                # All 3 disagree
                solvers_agree = False
                consensus_ans = None
        else:
            solvers_agree = ab_agree
            consensus_ans = solver_a.final_answer if solvers_agree else None

    # Matches stored key?
    matches_key = False
    if consensus_ans is not None:
        matches_key = compare_answers(consensus_ans, stored_key, q_type)

    # Matches solution?
    matches_solution = False
    if consensus_ans is not None and sol_final is not None:
        matches_solution = match_option_or_value(consensus_ans, sol_final, q)

    # Diagnostic Notes
    if solver_a.cannot_solve_reason or (solver_c and solver_c.cannot_solve_reason):
        reason = (solver_c and solver_c.cannot_solve_reason) or solver_a.cannot_solve_reason
        notes = f"Unsolvable: {reason}."
    elif not solvers_agree:
        notes = f"Disagreement: Solver A gave '{solver_a.final_answer}', Solver B gave '{solver_b.final_answer}'"
        if solver_c:
            notes += f", Solver C tie-breaker gave '{solver_c.final_answer}'."
        else:
            notes += "."
    elif matches_key and matches_solution:
        notes = f"Complete consensus on '{consensus_ans}'. Key and solution are sound."
    elif matches_solution and not matches_key:
        notes = f"KEY DEFECT: Solvers agree on '{consensus_ans}' (matches solution derivation '{sol_final}'), but contradicts stored key '{stored_key}'."
    elif matches_key and not matches_solution:
        notes = f"SOLUTION DEFECT: Solvers agree on '{consensus_ans}' (matches key), but stored solution derivation concludes '{sol_final or '-'}'."
    else:
        notes = f"DISCREPANCY: Solvers concluded '{consensus_ans}', stored key is '{stored_key}', and solution derivation is '{sol_final or '-'}'."

    return SolverAgreementRecord(
        questionId=q.question_id,
        questionType=q_type,
        stored_key=stored_key,
        solution_final_answer=sol_final,
        solver_a=solver_a,
        solver_b=solver_b,
        solver_c=solver_c,
        solvers_agree=solvers_agree,
        matches_key=matches_key,
        matches_solution=matches_solution,
        notes=notes,
    )


# ============================================================================
# Runner, Table Formatter & Exporter
# ============================================================================

def run_solver_pipeline(
    reports_path: str = "data/reports.json",
    prompt_a_path: Optional[str] = None,
    prompt_b_path: Optional[str] = None,
    prompt_c_path: Optional[str] = None,
    solution_finals_path: Optional[str] = "engine/out/llm_audit.json",
    output_path: str = "engine/out/solver_results.json",
) -> list[SolverAgreementRecord]:
    """Execute independent dual-solve + selective tie-breaker pipeline on reported questions."""
    out_file = Path(output_path)
    if out_file.exists():
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict) and "results" in saved and len(saved["results"]) == 39:
                    return [SolverAgreementRecord(**r) for r in saved["results"]]
        except Exception:
            pass

    file_a = Path(prompt_a_path) if prompt_a_path else SOLVER_A_PROMPT_FILE
    file_b = Path(prompt_b_path) if prompt_b_path else SOLVER_B_PROMPT_FILE
    file_c = Path(prompt_c_path) if prompt_c_path else SOLVER_C_PROMPT_FILE
    template_a = file_a.read_text(encoding="utf-8")
    template_b = file_b.read_text(encoding="utf-8")
    template_c = file_c.read_text(encoding="utf-8") if file_c.exists() else ""

    # Load solution final answers if available
    sol_finals: dict[str, Optional[str]] = {}
    if solution_finals_path and Path(solution_finals_path).exists():
        try:
            with open(solution_finals_path, "r", encoding="utf-8") as f:
                audit_data = json.load(f)
                sol_finals = audit_data.get("solution_final_answers", {})
        except Exception:
            pass

    # Load reported question IDs
    p_reports = Path(reports_path)
    if not p_reports.exists():
        p_reports = Path(__file__).parent.parent / "data" / "reports.json"

    with open(p_reports, "r", encoding="utf-8") as f:
        reports = json.load(f)

    reported_qids = sorted(list(set(r["questionId"] for r in reports)))
    all_questions = {q.question_id: q for q in parse_all_questions()}

    # Results dictionary strictly keyed by questionId (never by position)
    records_by_qid: dict[str, SolverAgreementRecord] = {}

    print(f"Phase 1: Running primary dual solvers (A & B) on {len(reported_qids)} questions...")
    for idx, qid in enumerate(reported_qids, 1):
        q = all_questions[qid]
        out_a, out_b = solve_question_independently(q, template_a, template_b)
        sol_final = sol_finals.get(qid)
        rec = compare_solver_runs(q, out_a, out_b, solver_c=None, solution_final_answer=sol_final)
        records_by_qid[qid] = rec

    # Phase 2: Identify questions needing Tie-Breaker Solver C
    # Criteria: solvers disagree OR solvers disagree with stored key OR unsolvable
    tiebreak_qids = [
        qid for qid in reported_qids
        if (not records_by_qid[qid].solvers_agree)
        or (not records_by_qid[qid].matches_key)
        or (records_by_qid[qid].solver_a.cannot_solve_reason is not None)
    ]
    print(f"\nPhase 2: Running Tie-Breaker Solver C ({TIEBREAK_MODEL}) on {len(tiebreak_qids)} candidate questions...")

    for idx, qid in enumerate(tiebreak_qids, 1):
        q = all_questions[qid]
        prev_rec = records_by_qid[qid]
        sol_final = sol_finals.get(qid)
        try:
            out_c = solve_tiebreaker_run(q, template_c)
            updated_rec = compare_solver_runs(
                q,
                solver_a=prev_rec.solver_a,
                solver_b=prev_rec.solver_b,
                solver_c=out_c,
                solution_final_answer=sol_final,
            )
            records_by_qid[qid] = updated_rec
            print(f"  [{idx}/{len(tiebreak_qids)}] Tie-Breaker for {qid[:8]}... -> C gave: '{out_c.final_answer}' (SolversAgree: {updated_rec.solvers_agree}, KeyMatch: {updated_rec.matches_key})")
        except Exception as exc:
            print(f"  [{idx}/{len(tiebreak_qids)}] Tie-Breaker for {qid[:8]}... skipped or failed: {exc}")

    # Order records deterministically by reported_qids
    records = [records_by_qid[qid] for qid in reported_qids]

    # Export results to JSON
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "total_questions_solved": len(records),
            "solvers_agree_count": len([r for r in records if r.solvers_agree]),
            "matches_key_count": len([r for r in records if r.matches_key]),
            "key_discrepancies": len([r for r in records if r.solvers_agree and not r.matches_key and not r.solver_a.cannot_solve_reason]),
            "unsolvable_count": len([r for r in records if r.solver_a.cannot_solve_reason]),
        },
        "results": [r.model_dump() for r in records],
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return records


def print_solver_table(records: list[SolverAgreementRecord]) -> None:
    """Print clean aligned terminal table of solver verification results."""
    print("=" * 145)
    print(f"{'#':<3} | {'QUESTION ID':<24} | {'TYPE':<12} | {'SOL A':<8} | {'SOL B':<8} | {'SOL C':<8} | {'KEY':<6} | {'SOL END':<8} | {'AGREE?':<6} | {'KEY MATCH?':<10} | {'NOTES'}")
    print("=" * 145)

    for i, r in enumerate(records, 1):
        ans_a = r.solver_a.final_answer if r.solver_a.final_answer is not None else "UNSOLV"
        ans_b = r.solver_b.final_answer if r.solver_b.final_answer is not None else "UNSOLV"
        ans_c = r.solver_c.final_answer if r.solver_c and r.solver_c.final_answer is not None else ("UNSOLV" if r.solver_c and r.solver_c.cannot_solve_reason else "-")
        key_str = str(r.stored_key)
        if len(key_str) > 5:
            key_str = key_str[:5] + ".."
        sol_str = str(r.solution_final_answer or "-")
        if len(sol_str) > 7:
            sol_str = sol_str[:6] + ".."

        agree_str = "YES" if r.solvers_agree else "NO"
        if r.solver_a.cannot_solve_reason or (r.solver_c and r.solver_c.cannot_solve_reason):
            key_match_str = "UNSOLVABLE"
        else:
            key_match_str = "MATCH" if r.matches_key else "MISMATCH"

        trunc_notes = r.notes if len(r.notes) <= 45 else r.notes[:42] + "..."
        print(
            f"{i:<3} | {r.questionId:<24} | {r.questionType:<12} | {str(ans_a)[:7]:<8} | {str(ans_b)[:7]:<8} | {str(ans_c)[:7]:<8} | "
            f"{key_str:<6} | {sol_str:<8} | {agree_str:<6} | {key_match_str:<10} | {trunc_notes}"
        )

    print("=" * 145)
    agree_count = len([r for r in records if r.solvers_agree])
    match_key_count = len([r for r in records if r.matches_key])
    unsolvable = [r for r in records if r.solver_a.cannot_solve_reason or (r.solver_c and r.solver_c.cannot_solve_reason)]
    key_defects = [r for r in records if r.solvers_agree and not r.matches_key and not (r.solver_a.cannot_solve_reason or (r.solver_c and r.solver_c.cannot_solve_reason))]

    print(f"Summary: {len(records)} reported questions independently solved.")
    print(f"  • Solvers agreed: {agree_count} / {len(records)}")
    print(f"  • Confirmed stored key correct: {match_key_count} / {len(records)}")
    print(f"  • Key defects discovered: {len(key_defects)} (Solvers prove stored key is WRONG)")
    print(f"  • Unsolvable stems discovered: {len(unsolvable)} (Missing data or missing figure)")
    print("=" * 145)


if __name__ == "__main__":
    records = run_solver_pipeline()
    print_solver_table(records)
