export type QuestionType = 'scq' | 'mcq' | 'integerQuestion';

export interface SolverRun {
  question_id?: string;
  stem_echo?: string;
  final_answer: string | null;
  working: string;
  confidence: number;
  cannot_solve_reason?: string | null;
  model?: string;
}

export interface SolverRecord {
  questionId: string;
  questionType: QuestionType;
  stored_key: string | string[];
  solution_final_answer: string | null;
  solver_a?: SolverRun;
  solver_b?: SolverRun;
  solver_c?: SolverRun;
  solvers_agree?: boolean;
  matches_key?: boolean;
  matches_solution?: boolean;
  notes?: string;
}

export interface DeterministicCheck {
  name: string;
  status: 'pass' | 'fail' | 'warn';
  detail: string;
}

export interface OptionItem {
  label: string;
  text: string;
  html: string;
  is_blank?: boolean;
}

export interface EditProposal {
  field: string;
  find?: string | null;
  replace: string | string[];
}

export interface ReportItem {
  reportId: string;
  questionId: string;
  verdict: 'defect' | 'no_error' | 'display_issue' | 'app_issue' | 'language_mode' | 'already_fixed' | 'not_actionable';
  repair: string | null;
  edit?: EditProposal | null;
  route: 'auto_apply' | 'faculty_review' | 'no_change';
  confidence: number;
  evidence: string;
  student_reply: string;
  student_comment: string;
  student_id: string;
  source: string;
  reported_at: string;
}

export interface CaseItem {
  questionId: string;
  subject: string;
  chapter: string;
  questionType: QuestionType;
  stored_key: string | string[];
  stem_text: string;
  stem_html: string;
  solution_text: string;
  solution_html: string;
  options: Record<string, OptionItem>;
  top_verdict: string;
  top_repair: string | null;
  route: 'auto_apply' | 'faculty_review' | 'no_change';
  confidence: number;
  evidence: string;
  edit?: EditProposal | null;
  urgency_score: number;
  solver_record?: SolverRecord;
  deterministic_checks: DeterministicCheck[];
  reports: ReportItem[];
}

export interface CasesBundle {
  engine_run_timestamp: string;
  summary: {
    total_cases: number;
    total_reports: number;
    faculty_review_count: number;
    auto_apply_count: number;
    no_change_count: number;
  };
  cases: CaseItem[];
}

export interface AuditDecision {
  id: string;
  caseId: string;
  action: 'approved' | 'edited' | 'rejected';
  timestamp: string;
  reviewer: string;
  topRepair: string | null;
  originalEdit?: EditProposal | null;
  finalEdit?: EditProposal | null;
  replies: Record<string, string>; // reportId -> student_reply
  rejectReason?: string;
  rejectNote?: string;
}

export interface Taxonomy {
  verdicts: Record<string, string>;
  repairs: Record<
    string,
    {
      fields: string[];
      auto: boolean;
      label: string;
    }
  >;
}
