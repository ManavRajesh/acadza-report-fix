"""
Deterministic HTML & MathML Parser for Acadza Questions.

Extracts question stem, options, solutions, and converts MathML into
a clean, readable linear text representation for LLM stages while preserving
the raw HTML intact for frontend console rendering. Pure code, no LLM.
"""

from dataclasses import dataclass, field
import html
import json
from pathlib import Path
import re
from typing import Any, Optional
import xml.etree.ElementTree as ET


@dataclass
class ParsedOption:
    """Structured representation of an extracted option."""
    label: str               # 'A', 'B', 'C', 'D'
    raw_html: str            # Untouched HTML for web console
    text: str                # Linear plain text with MathML linearized
    is_blank: bool           # True if option body is empty or whitespace-only


@dataclass
class ParsedQuestion:
    """Structured representation of a parsed question."""
    question_id: str
    question_type: str       # 'scq', 'mcq', 'integerQuestion'
    subject: str
    chapter: str
    concept: str
    sub_concept: str
    level: Optional[str]
    stem_html: str           # Raw HTML of stem (preserving MathML for console)
    stem_text: str           # Linearized text for LLM consumption
    options: dict[str, ParsedOption] = field(default_factory=dict)
    solution_html: str = ""  # Raw HTML of solution
    solution_text: str = ""  # Linearized text of solution
    answer: Any = None       # Raw answer: 'A', ['A', 'B'], or '20'
    ques_images: list[str] = field(default_factory=list)
    solution_images: list[str] = field(default_factory=list)
    has_images: bool = False

    def get_option_text(self, label: str) -> str:
        """Helper to get text of an option or empty string."""
        opt = self.options.get(label.upper())
        return opt.text if opt else ""

    def get_option_labels(self) -> list[str]:
        """Return sorted list of option labels present."""
        return sorted(list(self.options.keys()))


def _clean_mathml_for_xml_parser(mathml_str: str) -> str:
    """
    Sanitize MathML string for safe XML parsing via xml.etree.ElementTree.
    Protects XML-sensitive characters (<, >, &) that appear as entities or raw characters.
    """
    # Normalize hex entities for <, >, &
    s = re.sub(r"&#x0003[cC];|&lt;", "\x01", mathml_str)
    s = re.sub(r"&#x0003[eE];|&gt;", "\x02", s)
    s = re.sub(r"&#x00026;|&amp;", "\x03", s)

    # Unescape remaining HTML entities (e.g. &times; -> ×, &alpha; -> α)
    s = html.unescape(s)

    # Escape any bare & not part of a valid XML entity
    s = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+|#[xX][0-9a-fA-F]+);)", "&amp;", s)

    # Restore protected XML entities
    s = s.replace("\x01", "&lt;").replace("\x02", "&gt;").replace("\x03", "&amp;")

    # Strip xmlns declarations to avoid namespace prefix clutter in ElementTree
    s = re.sub(r"\s+xmlns(:\w+)?=\"[^\"]*\"", "", s)
    return s


def mathml_to_linear(mathml_str: str) -> str:
    """
    Convert a MathML XML fragment into a clean linear text representation.

    Examples:
        <mfrac><mn>1</mn><msqrt><mn>3</mn></msqrt></mfrac> -> (1)/(sqrt(3))
        <msup><mi>x</mi><mn>2</mn></msup>                   -> x^(2)
        <msub><mi>V</mi><mn>0</mn></msub>                   -> V_(0)
        <msubsup><mi>x</mi><mn>1</mn><mn>2</mn></msubsup>   -> x_(1)^(2)
    """
    clean_xml = _clean_mathml_for_xml_parser(mathml_str)

    try:
        root = ET.fromstring(clean_xml)
    except Exception:
        # Robust fallback: strip tags and unescape
        stripped = re.sub(r"<[^>]+>", " ", mathml_str)
        return " ".join(html.unescape(stripped).split())

    def _convert_node(elem: ET.Element) -> str:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        text = (elem.text or "").strip()
        tail = (elem.tail or "").strip()
        children = [_convert_node(c) for c in elem]

        if tag in ("math", "mrow", "mstyle"):
            res = " ".join(filter(None, [text] + children))
        elif tag == "mfrac":
            num = children[0] if len(children) > 0 else ""
            den = children[1] if len(children) > 1 else ""
            res = f"({num})/({den})"
        elif tag == "msqrt":
            inner = " ".join(filter(None, children))
            res = f"sqrt({inner})"
        elif tag == "msup":
            base = children[0] if len(children) > 0 else ""
            exp = children[1] if len(children) > 1 else ""
            res = f"{base}^({exp})"
        elif tag == "msub":
            base = children[0] if len(children) > 0 else ""
            sub = children[1] if len(children) > 1 else ""
            res = f"{base}_({sub})"
        elif tag == "msubsup":
            base = children[0] if len(children) > 0 else ""
            sub = children[1] if len(children) > 1 else ""
            exp = children[2] if len(children) > 2 else ""
            res = f"{base}_({sub})^({exp})"
        elif tag == "mover":
            base = children[0] if len(children) > 0 else ""
            res = f"{base}"
        elif tag in ("mi", "mn", "mo", "mtext"):
            res = text if text else " ".join(children)
        elif tag == "mspace":
            res = "\n" if "newline" in elem.attrib.get("linebreak", "") else " "
        elif tag in ("mtable", "mtr", "mtd"):
            res = " ".join(filter(None, [text] + children))
        else:
            res = " ".join(filter(None, [text] + children))

        if tail:
            res = f"{res} {tail}"
        return res.strip()

    linear = _convert_node(root)
    # Tidy up consecutive spaces while preserving linear structure
    return re.sub(r"[ \t]+", " ", linear).strip()


def html_to_linear_text(html_str: str) -> str:
    """
    Convert HTML containing inline MathML into clean linear text for LLM consumption.
    Preserves structural line breaks for options and paragraphs.
    """
    if not html_str:
        return ""

    # 1. Convert MathML tags to linear text
    def _math_repl(m: re.Match) -> str:
        return f" {mathml_to_linear(m.group(0))} "

    s = re.sub(r"<math[\s\S]*?</math>", _math_repl, html_str)

    # 2. Convert standard HTML breaks / block tags to newlines
    s = re.sub(r"<br\s*/?>|</h\d>|</p>|</li>", "\n", s, flags=re.I)
    s = re.sub(r"<li>", "• ", s, flags=re.I)

    # 3. Strip all remaining HTML tags
    s = re.sub(r"<[^>]+>", " ", s)

    # 4. Unescape all remaining HTML entities
    s = html.unescape(s)

    # 5. Clean up multiple empty lines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in s.splitlines()]
    clean_lines = [line for line in lines if line]
    return "\n".join(clean_lines)


def _extract_options_from_html(html_str: str) -> tuple[str, dict[str, ParsedOption]]:
    """
    Split question HTML into stem HTML and a dictionary of extracted options.
    Handles standard markers: (A), (B), (C), (D) and MathML <mo>(A)</mo>.
    Guards against false positives like 'Assertion (A)'.
    """
    # Regex matches option markers
    pattern = re.compile(
        r"(?:<math[^>]*>)?\s*<mo>\s*\(([A-D])\)\s*</mo>\s*(?:</math>)?|\(([A-D])\)"
    )
    all_matches = list(pattern.finditer(html_str))

    # Filter out false positives like "Assertion (A)"
    valid_matches = []
    for m in all_matches:
        start = m.start()
        preceding = html_str[max(0, start - 20):start].lower()
        if "assertion" in preceding:
            continue
        label = m.group(1) or m.group(2)
        valid_matches.append((label, m.start(), m.end()))

    if not valid_matches:
        # No options found (or integer question)
        return html_str, {}

    # Stem is everything prior to the first option marker
    first_opt_start = valid_matches[0][1]
    stem_html = html_str[:first_opt_start].strip()

    options_dict: dict[str, ParsedOption] = {}
    for i in range(len(valid_matches)):
        label = valid_matches[i][0]
        content_start = valid_matches[i][2]
        content_end = (
            valid_matches[i + 1][1] if i + 1 < len(valid_matches) else len(html_str)
        )

        raw_opt_html = html_str[content_start:content_end]

        # Strip trailing enclosing block tags from the last option chunk
        trimmed_html = re.sub(r"</(h\d|p|span|div|ol|li)>\s*$", "", raw_opt_html.strip(), flags=re.I)
        trimmed_html = re.sub(r"<br\s*/?>\s*$", "", trimmed_html.strip(), flags=re.I)

        linear_text = html_to_linear_text(trimmed_html)
        is_blank = len(linear_text.strip()) == 0

        options_dict[label] = ParsedOption(
            label=label,
            raw_html=trimmed_html,
            text=linear_text,
            is_blank=is_blank,
        )

    return stem_html, options_dict


def parse_question(raw_question: dict) -> ParsedQuestion:
    """
    Parse a raw question object from questions.json into a structured ParsedQuestion.
    """
    qid = raw_question["_id"]
    qtype = raw_question.get("questionType", "scq")
    payload = raw_question.get(qtype, {})

    raw_q_html = payload.get("question", "")
    raw_sol_html = payload.get("solution", "")
    answer = payload.get("answer")

    ques_images = list(payload.get("quesImages", []))
    solution_images = list(payload.get("solutionImages", []))

    # Also detect inline <img src="..."> tags
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_q_html, re.I):
        if src not in ques_images:
            ques_images.append(src)
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_sol_html, re.I):
        if src not in solution_images:
            solution_images.append(src)

    has_images = len(ques_images) > 0 or "<img" in raw_q_html.lower()

    if qtype in ("scq", "mcq"):
        stem_html, options = _extract_options_from_html(raw_q_html)
    else:
        # integerQuestion has no options
        stem_html = raw_q_html
        options = {}

    stem_text = html_to_linear_text(stem_html)
    solution_text = html_to_linear_text(raw_sol_html)

    return ParsedQuestion(
        question_id=qid,
        question_type=qtype,
        subject=raw_question.get("subject", ""),
        chapter=raw_question.get("chapter", ""),
        concept=raw_question.get("concept", ""),
        sub_concept=raw_question.get("subConcept", ""),
        level=raw_question.get("level"),
        stem_html=stem_html,
        stem_text=stem_text,
        options=options,
        solution_html=raw_sol_html,
        solution_text=solution_text,
        answer=answer,
        ques_images=ques_images,
        solution_images=solution_images,
        has_images=has_images,
    )


def parse_all_questions(data_path: str = "data/questions.json") -> list[ParsedQuestion]:
    """Parse all questions from questions.json."""
    with open(data_path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)
    return [parse_question(q) for q in raw_list]


# ============================================================================
# Unit Tests with 3 Real Questions from data/
# ============================================================================

def test_parse_samples():
    """Unit test with 3 real questions from data/ showing raw -> parsed."""
    data_file = Path("data/questions.json")
    if not data_file.exists():
        data_file = Path(__file__).parent.parent / "data" / "questions.json"

    with open(data_file, "r", encoding="utf-8") as f:
        questions = {q["_id"]: q for q in json.load(f)}

    # 1. Real SCQ: 60ca4feb6420652745f55522
    scq_id = "60ca4feb6420652745f55522"
    parsed_scq = parse_question(questions[scq_id])

    print("=" * 60)
    print(f"SAMPLE 1: SCQ [{scq_id}]")
    print("=" * 60)
    print("RAW QUESTION HTML:")
    print(questions[scq_id]["scq"]["question"])
    print("\n--> PARSED STEM TEXT:")
    print(parsed_scq.stem_text)
    print("\n--> PARSED OPTIONS:")
    for lbl, opt in parsed_scq.options.items():
        print(f"  ({lbl}) [blank={opt.is_blank}]: {opt.text}")
    print("\n--> PARSED SOLUTION TEXT:")
    print(parsed_scq.solution_text)
    print(f"--> ANSWER: {parsed_scq.answer}")

    assert len(parsed_scq.options) == 4, f"Expected 4 options, got {len(parsed_scq.options)}"
    assert parsed_scq.options["A"].text == "100 N"
    assert parsed_scq.options["C"].text == "99 N"
    assert parsed_scq.answer == "C"

    # 2. Real MCQ: 68c8153cfb6b2f16e2d3ceaf
    mcq_id = "68c8153cfb6b2f16e2d3ceaf"
    parsed_mcq = parse_question(questions[mcq_id])

    print("\n" + "=" * 60)
    print(f"SAMPLE 2: MCQ [{mcq_id}]")
    print("=" * 60)
    print("RAW QUESTION HTML:")
    print(questions[mcq_id]["mcq"]["question"])
    print("\n--> PARSED STEM TEXT:")
    print(parsed_mcq.stem_text)
    print("\n--> PARSED OPTIONS:")
    for lbl, opt in parsed_mcq.options.items():
        print(f"  ({lbl}) [blank={opt.is_blank}]: {opt.text}")
    print(f"--> ANSWER: {parsed_mcq.answer}")

    assert len(parsed_mcq.options) == 4
    assert parsed_mcq.options["B"].text.startswith("perpendicular to the uniform electrostatic field")

    # 3. Real integerQuestion: 68dea616d0cda73d07e93ae6
    int_id = "68dea616d0cda73d07e93ae6"
    parsed_int = parse_question(questions[int_id])

    print("\n" + "=" * 60)
    print(f"SAMPLE 3: integerQuestion [{int_id}]")
    print("=" * 60)
    print("RAW QUESTION HTML:")
    print(questions[int_id]["integerQuestion"]["question"])
    print("\n--> PARSED STEM TEXT (MathML converted to linear):")
    print(parsed_int.stem_text)
    print("\n--> PARSED SOLUTION TEXT (MathML converted to linear):")
    print(parsed_int.solution_text)
    print(f"--> ANSWER: {parsed_int.answer}")

    assert len(parsed_int.options) == 0, "Integer question must have 0 options"
    assert "(q)/(2)" in parsed_int.stem_text, "Expected (q)/(2) in linearized math"
    assert "(n q)/(2 ε_(0))" in parsed_int.stem_text, "Expected linearized flux formula"
    assert parsed_int.answer == "2"

    print("\n✅ All 3 real question parse unit tests passed successfully!")


if __name__ == "__main__":
    test_parse_samples()
