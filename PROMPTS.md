# Acadza Prompt Catalog & Version History

All LLM prompts live in `engine/prompts/` as plain text files with strict versioning (`_v1`, `_v2`, etc.).

---

## 1. Audit Stage (`engine/audit.py`)
- **`audit_v1.txt`**: Initial semantic defect auditing prompt. Audits questions for spelling, notation, missing stem data, wrong chapters, and obvious mathematical contradictions.
- **`audit_v2.txt`**: Added section `4. Stored Solution Final Answer`. Explicitly tasks the LLM with reading the stored solution text and extracting the exact option letter or numerical value that the derivation reaches (`solution_final_answer`), replacing fragile regex parsing.

---

## 2. Solver Stage (`engine/solve.py`)
- **`solver_a_v1.txt`**: First-principles physical and mathematical derivation solver. Given *only* question stem and options (zero anchoring to stored solution, stored key, or student reports). Requires question ID and stem echo in structured JSON output.
- **`solver_b_v1.txt`**: Independent solver with elimination framing, dimensional analysis, and sanity limits check.
- **`solver_c_v1.txt`**: Authoritative tie-breaker solver run with stronger Flash tier model (`gemini-3-flash-preview`) for questions with solver disagreements, key discrepancies, or potential unsolvability.

---

## 3. Intake Stage (`engine/triage.py`)
- **`intake_v1.txt`**: Untrusted student report parser. Treats student comments as untrusted data wrapped in `<student_comment>` tags. Categorizes claims into `claim_type`, identifies claimed values, detects language (English, Hindi, Hinglish), and flags adversarial prompt injections.

---

## 4. Judge Stage (`engine/triage.py`)
- **`judge_v1.txt`**: Initial holistic adjudicator combining question dossier, checks, dual solvers, and student claims.
- **`judge_v2.txt`**: Upgraded judge incorporating `solver_c` tie-breaker outputs and audited `solution_final_answer`. Enforces strict surgical edit boundaries: prevents edits adding substantial new content or explanations, requires splitting multi-typo fixes into lists of small edits, and mandates consensus across solvers and solution for `answer_key` repairs.

---

## 5. Reply Stage (`engine/triage.py`)
- **`reply_v1.txt`**: Initial student response generator.
- **`reply_v2.txt`**: Empathetic, direct response generator tailored for a 17-year-old student under high exam pressure:
  - 1–3 concise sentences.
  - No condescension, no emojis, no "Great catch!", and no corporate boilerplate ("integrity team", "customer support").
  - Clear state acknowledgment: confirms updates if `auto_apply`, confirms faculty review if `faculty_review` (never claims pending items are fixed).
  - Pinpoints specific conceptual or calculation traps when students are mistaken.
  - Neutral factual answer statement for prompt injection attempts without lecturing.
  - Natural Hinglish mirroring when student submitted in Hinglish.

