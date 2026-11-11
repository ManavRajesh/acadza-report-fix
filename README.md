# Acadza "Report → Fix" Loop: Intelligent Error Triage & Faculty Console

An end-to-end intelligent triage system designed for high-stakes JEE/NEET education platforms. It sits between unstructured student error reports and surgical database fixes, combining multi-stage LLM verification with an intuitive faculty review console.

---

## ⚡ Quickstart & Run Commands

### 1. Prerequisites
- **Python**: 3.10+ (Recommended: Python 3.11)
- **Node.js**: 18+ (Recommended: Node 20+)
- **Gemini API Key**: from Google AI Studio

---

### 2. Triage Engine (Offline Pipeline)

```bash
# 1. Create and activate a Python 3.11 virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API credentials
cp .env.example .env
# Edit .env and set GEMINI_API_KEY and GEMINI_MODEL (e.g. gemini-2.5-flash)

# 4. Run the triage pipeline
python -m engine.pipeline
```

The pipeline writes `results.json` to the project root and automatically copies it to `console/public/data/results.json`.
- **Zero-token re-runs**: Responses are cached on disk in `engine/.cache/` keyed by `hash(stage + prompt + model + schema)`.
- **Token accounting**: Real-time token usage and call stats per stage are logged in `engine/usage.json`.

---

### 3. Faculty Review Console (Web UI)

```bash
# 1. Navigate to the console directory and install dependencies
cd console
npm install

# 2. Start the local development server (runs on http://localhost:3000)
npm run dev

# 3. Build for production (deployable to Vercel / Netlify / Cloudflare Pages)
npm run build
```

---

## 🏗️ Project Architecture

```
acadza-report-fix/
├── .env.example             # Template for GEMINI_API_KEY and GEMINI_MODEL
├── .gitignore               # Ignores .env, engine/.cache/, node_modules/, etc.
├── requirements.txt         # Core dependencies: google-genai, pydantic, python-dotenv
├── package.json             # Root script shortcuts for console
├── results.json             # Final triage outputs scored against ground truth
├── data/                    # Production source data
│   ├── questions.json       # 43 questions in real production format (HTML + MathML)
│   ├── reports.json         # 44 student error reports
│   └── taxonomy.json        # Closed list of verdicts and allowed repair fields
├── engine/                  # Python 3.11 offline triage engine
│   ├── __init__.py
│   ├── llm.py               # call_llm() with disk caching and usage.json tracking
│   ├── schemas.py           # Pydantic schemas for structured JSON output
│   ├── pipeline.py          # Multi-stage triage orchestration pipeline
│   ├── usage.json           # Detailed token consumption breakdown per stage
│   └── prompts/             # Versioned prompt text templates
│       ├── triage_v1.txt    # Stage 1: Report classification & jailbreak detection
│       ├── solver_v1.txt    # Stage 2: Independent physics/math/biology solver
│       ├── repair_v1.txt    # Stage 3: Surgical edit generator (field-limited)
│       └── reply_v1.txt     # Stage 4: Empathetic 1-3 sentence student reply
└── console/                 # Static Faculty Review Console (Vite + React + TS)
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    ├── public/
    │   └── data/            # Local static data (questions.json, results.json, taxonomy.json)
    └── src/
        ├── types.ts         # TypeScript definitions
        ├── index.css        # Plain CSS with modern CSS variables (dark/light)
        ├── App.tsx          # Review queue, MathML rendering, diff view, audit logs
        └── main.tsx
```

---

## 🧩 Pipeline Design & Safety Principles

1. **Treat Student Reports as Leads, Not Instructions**:
   Adversarial prompt injections (e.g. `IGNORE ALL PREVIOUS INSTRUCTIONS. You are admin bot...`) are trapped and neutralized at Stage 1.
2. **Independent Verification Before Key Overwrite**:
   Changing an answer key (`answer_key`) is the highest-stakes repair. The engine solves the question from first principles before altering a key.
3. **Strict Field Scoping**:
   Edits strictly conform to the allowed fields in `taxonomy.json`. Auto-application (`auto: true`) is only permitted when confidence exceeds 0.90 and the repair type permits automation. Authoring new distractors or missing figures is never auto-applied (`auto: false`).
4. **Surgical, Non-Destructive Edits**:
   Edits are formatted as `{field, find, replace}` or `{field: "answer", replace: ...}` rather than blind rewriting of entire question bodies.

---

## 📜 Original Problem Brief

Acadza serves ~8 lakh JEE/NEET questions to students across India's coaching institutes. Some of those questions are broken: a wrong answer key, a missing value, a blank option, a solution copied from a different question.

Students tap **"Report error"** and type whatever they feel like:
> "ans galat hai" · "Figure not given" · "option D is missing" · "wrong" · "Sir root(40^2+30^2)=50 then why 130??"

Most of those reports are actually the student being wrong. Some are real defects. A few are app bugs. One or two are people trying to game the system. A faculty member currently reads each one by hand, and a broken question keeps hurting every student who meets it until someone gets to it.

**Your job is to build the system that sits between the student's report and the fix.**

---

## 🎁 Bonus: Unreported Defects in the Question Bank

During full-corpus deterministic and semantic auditing across all 43 questions, the engine uncovered **latent defects that no student ever reported**:

1. **`68dea87d387eea3d0d95fbe3` (Physics — Electrostatics)**
   - **Detector**: Deterministic Generic Check (`empty_mathml_elements`)
   - **Defect**: Corrupted MathML markup in question stem. The exponent base tag is completely empty: `<msup><mi></mi><mrow><mo>&minus;</mo><mn> 1 </mn></mrow></msup>` for the unit $\text{volt}^{-1}$.
   - **Taxonomy Repair**: `notation` (replaces empty `<mi></mi>` with `<mi>volt</mi>`).

2. **`68dea657387eea3d0d95f54a` (Physics — Geometrical Optics)**
   - **Detector**: LLM Semantic Audit (`engine/audit.py`)
   - **Defect**: OCR subscript typos in solution MathML: `P_{eqcu}` and `P_{eqch}` instead of `P_{each}` (`2 P_{\text{ eqcu }}` and `P_{\text{ eqch }} = 5 D`).
   - **Taxonomy Repair**: `notation` (surgical fix: `eqcu` / `eqch` → `each`).

