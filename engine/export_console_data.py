"""
Data Exporter for the Acadza Faculty Review Console.

Compiles precomputed triage results, independent solver records, deterministic checks,
and question content into a unified, high-performance `cases.json` bundle.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from engine.checks import run_generic_checks
from engine.parse import parse_all_questions


ROOT_DIR = Path(__file__).parent.parent
QUESTIONS_FILE = ROOT_DIR / "data" / "questions.json"
REPORTS_FILE = ROOT_DIR / "data" / "reports.json"
RESULTS_FILE = ROOT_DIR / "results.json"
SOLVER_RESULTS_FILE = ROOT_DIR / "engine" / "out" / "solver_results.json"
AUDIT_RESULTS_FILE = ROOT_DIR / "engine" / "out" / "llm_audit.json"
TAXONOMY_FILE = ROOT_DIR / "data" / "taxonomy.json"

OUT_CASES_FILE = ROOT_DIR / "engine" / "out" / "cases.json"
CONSOLE_DATA_DIR = ROOT_DIR / "console" / "public" / "data"


SEVERITY_WEIGHTS = {
    "answer_key": 10.0,
    "stem_data": 10.0,
    "wrong_question": 10.0,
    "diagram": 7.0,
    "option_repair": 7.0,
    "identical_options": 7.0,
    "type_mismatch": 7.0,
    "solution_fix": 5.0,
    "solution_missing": 5.0,
    "wrong_chapter": 5.0,
    "markup_leak": 3.0,
    "spelling": 3.0,
    "notation": 3.0,
    "exam_reference": 3.0,
    "answer_form": 3.0,
    "noise": 2.0,
}


def calculate_urgency_score(
    repair: str | None,
    num_reports: int,
    confidence: float,
    route: str,
) -> float:
    """
    Urgency score = severity of repair (answer_key / missing data highest)
                    × number of reports × confidence it's a real defect × route priority.
    """
    severity = SEVERITY_WEIGHTS.get(repair or "", 1.0)
    route_multiplier = 3.0 if route == "faculty_review" else (1.5 if route == "auto_apply" else 0.2)
    return round(severity * num_reports * confidence * route_multiplier, 2)


def build_cases_bundle() -> dict[str, Any]:
    # 1. Load questions
    parsed_questions = {q.question_id: q for q in parse_all_questions()}
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        raw_questions = {q["_id"]: q for q in json.load(f)}

    # 2. Load reports metadata
    reports_meta = {}
    if REPORTS_FILE.exists():
        with open(REPORTS_FILE, "r", encoding="utf-8") as f:
            for rep in json.load(f):
                reports_meta[rep["reportId"]] = rep

    # 3. Load triage results
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)

    # 4. Load solver records
    solver_records = {}
    if SOLVER_RESULTS_FILE.exists():
        with open(SOLVER_RESULTS_FILE, "r", encoding="utf-8") as f:
            sol_data = json.load(f)
            for r in sol_data.get("results", []):
                solver_records[r["questionId"]] = r

    # 4. Load deterministic checks
    checks_by_qid: dict[str, list[dict[str, Any]]] = {}
    for c in run_generic_checks(list(parsed_questions.values())):
        checks_by_qid.setdefault(c.question_id, []).append(c.to_dict())

    # 5. Group results by questionId
    reports_by_qid: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        reports_by_qid.setdefault(r["questionId"], []).append(r)

    cases = []
    engine_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for qid, q_reports in reports_by_qid.items():
        parsed_q = parsed_questions.get(qid)
        raw_q = raw_questions.get(qid, {})
        solver_rec = dict(solver_records.get(qid, {}))
        if solver_rec:
            if solver_rec.get("solver_a") and isinstance(solver_rec["solver_a"], dict):
                solver_rec["solver_a"]["model"] = "Flash-Lite"
            if solver_rec.get("solver_b") and isinstance(solver_rec["solver_b"], dict):
                solver_rec["solver_b"]["model"] = "Flash-Lite"
            if solver_rec.get("solver_c") and isinstance(solver_rec["solver_c"], dict):
                solver_rec["solver_c"]["model"] = "Flash"
        q_checks = checks_by_qid.get(qid, [])

        # Representative adjudication for the question
        defect_reports = [r for r in q_reports if r["verdict"] == "defect"]
        rep_target = defect_reports[0] if defect_reports else q_reports[0]

        top_verdict = rep_target["verdict"]
        top_repair = rep_target["repair"]
        top_route = rep_target["route"]
        top_confidence = rep_target["confidence"]
        top_evidence = rep_target["evidence"]
        top_edit = rep_target["edit"]

        urgency = calculate_urgency_score(top_repair, len(q_reports), top_confidence, top_route)

        # Options dictionary
        options_dict = {}
        if parsed_q and parsed_q.options:
            for lbl, opt in parsed_q.options.items():
                options_dict[lbl] = {
                    "label": lbl,
                    "text": opt.text,
                    "html": opt.raw_html,
                    "is_blank": opt.is_blank,
                }

        enriched_reports = []
        for rep in q_reports:
            meta = reports_meta.get(rep["reportId"], {})
            e = dict(rep)
            e["student_comment"] = meta.get("comment", "")
            e["student_id"] = meta.get("studentId", "")
            e["source"] = meta.get("source", "")
            e["reported_at"] = meta.get("reportedAt", "")
            enriched_reports.append(e)

        case_item = {
            "questionId": qid,
            "subject": parsed_q.subject if parsed_q else raw_q.get("subject", "General"),
            "chapter": parsed_q.chapter if parsed_q else raw_q.get("chapter", "General"),
            "questionType": parsed_q.question_type if parsed_q else raw_q.get("questionType", "scq"),
            "stored_key": parsed_q.answer if parsed_q else raw_q.get("answer"),
            "stem_text": parsed_q.stem_text if parsed_q else "",
            "stem_html": parsed_q.stem_html if parsed_q else "",
            "solution_text": parsed_q.solution_text if parsed_q else "",
            "solution_html": parsed_q.solution_html if parsed_q else "",
            "options": options_dict,
            "top_verdict": top_verdict,
            "top_repair": top_repair,
            "route": top_route,
            "confidence": top_confidence,
            "evidence": top_evidence,
            "edit": top_edit,
            "urgency_score": urgency,
            "solver_record": solver_rec,
            "deterministic_checks": q_checks,
            "reports": enriched_reports,
        }
        cases.append(case_item)

    # Sort cases by urgency descending
    cases.sort(key=lambda c: c["urgency_score"], reverse=True)

    bundle = {
        "engine_run_timestamp": engine_timestamp,
        "summary": {
            "total_cases": len(cases),
            "total_reports": len(results),
            "faculty_review_count": len([c for c in cases if c["route"] == "faculty_review"]),
            "auto_apply_count": len([c for c in cases if c["route"] == "auto_apply"]),
            "no_change_count": len([c for c in cases if c["route"] == "no_change"]),
        },
        "cases": cases,
    }

    # Write output
    OUT_CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CASES_FILE, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    print(f"✓ Generated cases bundle at: {OUT_CASES_FILE.resolve()}")

    CONSOLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    console_cases_file = CONSOLE_DATA_DIR / "cases.json"
    with open(console_cases_file, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    print(f"✓ Copied cases bundle to: {console_cases_file.resolve()}")

    # Ensure questions.json and reports.json are also copied
    shutil.copyfile(QUESTIONS_FILE, CONSOLE_DATA_DIR / "questions.json")
    print(f"✓ Copied questions.json to: {(CONSOLE_DATA_DIR / 'questions.json').resolve()}")
    if REPORTS_FILE.exists():
        shutil.copyfile(REPORTS_FILE, CONSOLE_DATA_DIR / "reports.json")
        print(f"✓ Copied reports.json to: {(CONSOLE_DATA_DIR / 'reports.json').resolve()}")

    return bundle


if __name__ == "__main__":
    build_cases_bundle()
