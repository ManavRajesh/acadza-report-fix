import { CaseItem } from '../types';

export const REPAIR_LABELS: Record<string, string> = {
  answer_key: 'Wrong answer key',
  stem_data: 'Missing data in question',
  diagram: 'Missing figure',
  option_repair: 'Option problem',
  identical_options: 'Duplicate options',
  solution_fix: 'Solution error',
  solution_missing: 'Solution incomplete',
  spelling: 'Spelling',
  markup_leak: 'Formatting glitch',
  wrong_chapter: 'Wrong chapter',
  type_mismatch: 'Answer format',
  answer_form: 'Missing units',
  exam_reference: 'Exam reference',
  notation: 'Notation',
  noise: 'Noise',
};

export const ROUTE_LABELS: Record<string, string> = {
  auto_apply: 'Applied automatically',
  faculty_review: 'Needs your review',
  no_change: 'No change needed',
};

export function formatRepair(repair?: string | null): string {
  if (!repair) return 'No defect';
  return REPAIR_LABELS[repair] || repair.replace(/_/g, ' ');
}

export function formatConfidence(conf: number): string {
  if (conf >= 0.9) return 'high confidence';
  if (conf >= 0.7) return 'medium confidence';
  return 'low confidence';
}

/**
 * Editorial headline generator: plain English statement of the issue.
 */
export function getEditorialHeadline(c: CaseItem): { headline: string; confidenceText: string } {
  const confText = formatConfidence(c.confidence);

  if (c.top_verdict !== 'defect') {
    return {
      headline: 'The question and answer key look correct as stored.',
      confidenceText: confText,
    };
  }

  // Answer key error
  if (c.top_repair === 'answer_key') {
    const target = c.edit?.replace !== undefined ? String(c.edit.replace) : '?';
    return {
      headline: `The answer key says ${c.stored_key}, but the correct answer is ${target}.`,
      confidenceText: confText,
    };
  }

  // Missing stem data
  if (c.top_repair === 'stem_data') {
    const stemLower = c.stem_text.toLowerCase();
    if (stemLower.includes('inductance') || (c.edit && String(c.edit.replace).includes('95.5 mH'))) {
      return {
        headline: 'The question is missing the inductance value needed to calculate impedance.',
        confidenceText: confText,
      };
    }
    if (stemLower.includes('copper cube') || (c.edit && String(c.edit.replace).includes('10 cm'))) {
      return {
        headline: 'The question is missing the initial cube dimensions needed to calculate volume contraction.',
        confidenceText: confText,
      };
    }
    return {
      headline: 'The question is missing numeric data needed to solve it.',
      confidenceText: confText,
    };
  }

  // Missing figure / diagram
  if (c.top_repair === 'diagram') {
    return {
      headline: 'The question refers to a figure that is missing from the question bank.',
      confidenceText: confText,
    };
  }

  // Identical options
  if (c.top_repair === 'identical_options') {
    return {
      headline: 'Two options in this question are duplicates.',
      confidenceText: confText,
    };
  }

  // Option problem / missing option
  if (c.top_repair === 'option_repair') {
    if (c.deterministic_checks?.some((chk: any) => chk.check === 'blank_option')) {
      return {
        headline: 'An option is completely blank in the question.',
        confidenceText: confText,
      };
    }
    if (c.deterministic_checks?.some((chk: any) => chk.check === 'missing_option_letter')) {
      return {
        headline: 'Option D is missing from this single-choice question.',
        confidenceText: confText,
      };
    }
    return {
      headline: 'An option in this question is defective or incomplete.',
      confidenceText: confText,
    };
  }

  // Solution error
  if (c.top_repair === 'solution_fix') {
    return {
      headline: 'The answer key is correct, but the stored solution has an error in its derivation.',
      confidenceText: confText,
    };
  }

  // Solution incomplete
  if (c.top_repair === 'solution_missing') {
    return {
      headline: 'The stored solution is incomplete and lacks derivation.',
      confidenceText: confText,
    };
  }

  // Spelling
  if (c.top_repair === 'spelling') {
    return {
      headline: 'There is a spelling mistake in the question text.',
      confidenceText: confText,
    };
  }

  // Formatting glitch
  if (c.top_repair === 'markup_leak') {
    return {
      headline: 'Raw LaTeX markup is leaking as plain text in the question.',
      confidenceText: confText,
    };
  }

  // Missing units
  if (c.top_repair === 'answer_form') {
    return {
      headline: 'The integer question does not specify the required units in the stem.',
      confidenceText: confText,
    };
  }

  // Type mismatch
  if (c.top_repair === 'type_mismatch') {
    return {
      headline: 'The answer key data format does not match the question type.',
      confidenceText: confText,
    };
  }

  return {
    headline: `A ${formatRepair(c.top_repair).toLowerCase()} was reported in this question.`,
    confidenceText: confText,
  };
}

/**
 * Editorial student subtitle: e.g. "Student 6167 · Android · 2 days ago"
 */
export function formatStudentMeta(rep: { student_id?: string; source?: string; reported_at?: string }): string {
  const rawId = rep.student_id || 'student';
  const cleanId = rawId.startsWith('stu_') ? rawId.slice(4, 8) : rawId;
  const source = rep.source ? rep.source.charAt(0).toUpperCase() + rep.source.slice(1) : 'Web';

  let timeStr = 'recently';
  if (rep.reported_at) {
    try {
      const d = new Date(rep.reported_at);
      const diffMs = Date.now() - d.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      if (diffDays <= 0) timeStr = 'today';
      else if (diffDays === 1) timeStr = 'yesterday';
      else if (diffDays < 30) timeStr = `${diffDays} days ago`;
      else timeStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
      timeStr = 'recently';
    }
  }

  return `Student ${cleanId} · ${source} · ${timeStr}`;
}

