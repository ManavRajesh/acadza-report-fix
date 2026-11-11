import React, { useState } from 'react';
import { CaseItem, AuditDecision } from '../types';
import { sanitizeHtml } from '../utils/sanitize';
import { renderInlineDiffHtml } from '../utils/diff';
import { getEditorialHeadline, formatStudentMeta } from '../utils/copy';

interface MainPanelProps {
  currentCase: CaseItem | null;
  decision?: AuditDecision;
  onApprove: () => void;
  onOpenEdit: () => void;
  onOpenReject: () => void;
  onNext: () => void;
  onPrev: () => void;
  hasPrev: boolean;
  hasNext: boolean;
  onUpdateReply: (reportId: string, replyText: string) => void;
  customReplies: Record<string, string>;
}

export const MainPanel: React.FC<MainPanelProps> = ({
  currentCase,
  decision,
  onApprove,
  onOpenEdit,
  onOpenReject,
  onNext,
  onPrev,
  hasPrev,
  hasNext,
  onUpdateReply,
  customReplies,
}) => {
  const [showWorkings, setShowWorkings] = useState<boolean>(false);
  const [diffViewMode, setDiffViewMode] = useState<'inline' | 'side-by-side'>('inline');

  if (!currentCase) {
    return (
      <main
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '80px 24px',
          color: 'var(--muted)',
          fontSize: '14px',
        }}
      >
        Select a question from the queue.
      </main>
    );
  }

  const solverRec = currentCase.solver_record;
  const solverA = solverRec?.solver_a;
  const solverB = solverRec?.solver_b;
  const solverC = solverRec?.solver_c;
  const storedKey = currentCase.stored_key;
  const solFinalAns = solverRec?.solution_final_answer;

  const isAnswerKeyRepair = currentCase.top_repair === 'answer_key';
  const editReplace = currentCase.edit?.replace;
  const editFind = currentCase.edit?.find;
  const editField = currentCase.edit?.field;

  const { headline, confidenceText } = getEditorialHeadline(currentCase);

  const isMatch = (ans: any, target: any) => {
    if (ans === null || ans === undefined || target === null || target === undefined) return false;
    return String(ans).trim().toUpperCase() === String(target).trim().toUpperCase();
  };

  // Expected consensus target: either the proposed replace answer or solver consensus
  const consensusTarget = editReplace !== undefined && isAnswerKeyRepair ? editReplace : (solverA?.final_answer || storedKey);

  // Verification Warnings (amber lines with dot)
  let verificationWarning: string | null = null;
  if (currentCase.route === 'faculty_review') {
    if (solverRec && (solverRec.matches_key === false || (solverA?.final_answer && !isMatch(solverA.final_answer, storedKey)))) {
      verificationWarning = 'Solvers disagree with the stored key — check before approving.';
    }
  }

  // Specific check if value comes from stored solution
  if (currentCase.top_repair === 'stem_data') {
    if (String(editReplace).includes('95.5 mH') || currentCase.stem_text.toLowerCase().includes('inductance')) {
      verificationWarning = '95.5 mH comes from the stored solution — check it.';
    } else if (String(editReplace).includes('10 cm') || currentCase.stem_text.toLowerCase().includes('copper cube')) {
      verificationWarning = '10 cm side length comes from the stored solution — check it.';
    } else if (currentCase.edit?.replace) {
      verificationWarning = 'Value comes from the stored solution — check before approving.';
    }
  }

  // Calculate text diff for question stem or solution
  let beforeText = '';
  let afterText = '';
  let inlineDiffHtml = '';

  if (currentCase.edit && editField) {
    if (editField === 'question' || editField === 'stem') {
      beforeText = currentCase.stem_text;
      if (editFind && beforeText.includes(editFind)) {
        afterText = beforeText.replace(editFind, String(editReplace));
      } else {
        beforeText = editFind || currentCase.stem_text;
        afterText = String(editReplace);
      }
      inlineDiffHtml = renderInlineDiffHtml(beforeText, afterText);
    } else if (editField === 'solution') {
      beforeText = currentCase.solution_text;
      if (editFind && beforeText.includes(editFind)) {
        afterText = beforeText.replace(editFind, String(editReplace));
      } else {
        beforeText = editFind || currentCase.solution_text;
        afterText = String(editReplace);
      }
      inlineDiffHtml = renderInlineDiffHtml(beforeText, afterText);
    } else if (editField.startsWith('option_') || editField === 'options') {
      beforeText = editFind || '';
      afterText = String(editReplace);
      inlineDiffHtml = renderInlineDiffHtml(beforeText, afterText);
    }
  }

  const numStudents = `${currentCase.reports.length} student${currentCase.reports.length > 1 ? 's' : ''}`;

  return (
    <main
      style={{
        flex: 1,
        overflowY: 'auto',
        backgroundColor: 'var(--bg)',
        paddingBottom: '120px',
      }}
    >
      <div
        style={{
          maxWidth: '820px',
          margin: '0 auto',
          padding: '32px 24px',
        }}
      >
        {/* Navigation buttons: prev / next */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginBottom: '16px' }}>
          <button
            onClick={onPrev}
            disabled={!hasPrev}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '12px',
              color: hasPrev ? 'var(--muted)' : 'var(--faint)',
              cursor: hasPrev ? 'pointer' : 'default',
              padding: 0,
            }}
          >
            ← Previous
          </button>
          <button
            onClick={onNext}
            disabled={!hasNext}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '12px',
              color: hasNext ? 'var(--muted)' : 'var(--faint)',
              cursor: hasNext ? 'pointer' : 'default',
              padding: 0,
            }}
          >
            Next →
          </button>
        </div>

        {/* a. Muted meta line */}
        <div
          style={{
            fontSize: '13px',
            color: 'var(--muted)',
            marginBottom: '8px',
            lineHeight: 1.4,
          }}
        >
          {currentCase.subject} · {currentCase.chapter} · {numStudents} reported ·{' '}
          <span className="mono-id">{currentCase.questionId}</span>
          {decision && (
            <span style={{ marginLeft: '10px', color: 'var(--green)' }}>
              · {decision.action} by {decision.reviewer}
            </span>
          )}
        </div>

        {/* b. Headline (22px, normal weight, text color, not yellow) */}
        <h1
          style={{
            fontSize: '22px',
            fontWeight: 400,
            color: 'var(--text)',
            lineHeight: 1.35,
            marginBottom: '16px',
            letterSpacing: '-0.01em',
          }}
        >
          {headline}{' '}
          <span style={{ fontSize: '14px', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
            · {confidenceText}
          </span>
        </h1>

        {/* c. Verification warning (if needed, one amber line with dot) */}
        {verificationWarning && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '13.5px',
              color: 'var(--amber)',
              marginBottom: '24px',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: 'var(--amber)',
                flexShrink: 0,
              }}
            />
            <span>{verificationWarning}</span>
          </div>
        )}

        {/* d. Proposed change section */}
        {currentCase.edit && (
          <section style={{ marginBottom: '36px' }}>
            <h2
              style={{
                fontSize: '14px',
                fontWeight: 600,
                color: 'var(--text)',
                marginBottom: '12px',
              }}
            >
              Proposed change
            </h2>

            {/* Answer key diff: two small boxes */}
            {isAnswerKeyRepair ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  fontSize: '13.5px',
                }}
              >
                <div
                  style={{
                    padding: '6px 12px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                    backgroundColor: 'var(--surface)',
                  }}
                >
                  <span style={{ color: 'var(--muted)' }}>Current key </span>
                  <strong style={{ color: 'var(--text)' }}>{String(storedKey)}</strong>
                </div>
                <span style={{ color: 'var(--muted)' }}>→</span>
                <div
                  style={{
                    padding: '6px 12px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                    backgroundColor: 'var(--surface)',
                  }}
                >
                  <span style={{ color: 'var(--muted)' }}>Proposed </span>
                  <strong style={{ color: 'var(--accent)' }}>{String(editReplace)}</strong>
                </div>
              </div>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '6px' }}>
                  <button
                    onClick={() => setDiffViewMode(diffViewMode === 'inline' ? 'side-by-side' : 'inline')}
                    style={{
                      background: 'none',
                      border: 'none',
                      fontSize: '12px',
                      color: 'var(--muted)',
                      cursor: 'pointer',
                      padding: 0,
                      textDecoration: 'underline',
                    }}
                  >
                    {diffViewMode === 'inline' ? 'Side-by-side' : 'Inline diff'}
                  </button>
                </div>

                {diffViewMode === 'inline' ? (
                  <div
                    className="question-html"
                    style={{
                      padding: '12px 14px',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)',
                      backgroundColor: 'var(--surface)',
                      fontSize: '13.5px',
                      lineHeight: 1.6,
                    }}
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(inlineDiffHtml) }}
                  />
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div
                      style={{
                        padding: '12px 14px',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        backgroundColor: 'var(--surface)',
                      }}
                    >
                      <div style={{ fontSize: '11.5px', color: 'var(--muted)', marginBottom: '6px' }}>Current</div>
                      <div className="question-html" style={{ fontSize: '13.5px', lineHeight: 1.6 }}>
                        {beforeText}
                      </div>
                    </div>
                    <div
                      style={{
                        padding: '12px 14px',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        backgroundColor: 'var(--surface)',
                      }}
                    >
                      <div style={{ fontSize: '11.5px', color: 'var(--muted)', marginBottom: '6px' }}>Proposed</div>
                      <div className="question-html" style={{ fontSize: '13.5px', lineHeight: 1.6 }}>
                        {afterText}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* e. Why section */}
        <section style={{ marginBottom: '36px' }}>
          <h2
            style={{
              fontSize: '14px',
              fontWeight: 600,
              color: 'var(--text)',
              marginBottom: '10px',
            }}
          >
            Why
          </h2>
          <p
            style={{
              fontSize: '13.5px',
              color: 'var(--text)',
              lineHeight: 1.5,
              marginBottom: '14px',
            }}
          >
            {currentCase.evidence}
          </p>

          {/* ONE compact line/table, not cards */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '24px',
              flexWrap: 'wrap',
              padding: '10px 14px',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              backgroundColor: 'var(--surface)',
              fontSize: '13px',
              marginBottom: '8px',
            }}
          >
            <div>
              <span style={{ color: 'var(--muted)' }}>Solver A </span>
              <span style={{ fontWeight: 500 }}>{solverA?.final_answer || 'unsolvable'}</span>{' '}
              <span style={{ color: isMatch(solverA?.final_answer, consensusTarget) ? 'var(--green)' : 'var(--red)' }}>
                {isMatch(solverA?.final_answer, consensusTarget) ? '✓' : '✗'}
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--muted)' }}>Solver B </span>
              <span style={{ fontWeight: 500 }}>{solverB?.final_answer || 'unsolvable'}</span>{' '}
              <span style={{ color: isMatch(solverB?.final_answer, consensusTarget) ? 'var(--green)' : 'var(--red)' }}>
                {isMatch(solverB?.final_answer, consensusTarget) ? '✓' : '✗'}
              </span>
            </div>

            {solverC && (
              <div>
                <span style={{ color: 'var(--muted)' }}>Tie-break ({solverC.model || 'Flash'}) </span>
                <span style={{ fontWeight: 500 }}>{solverC.final_answer || 'unsolvable'}</span>{' '}
                <span style={{ color: isMatch(solverC.final_answer, consensusTarget) ? 'var(--green)' : 'var(--red)' }}>
                  {isMatch(solverC.final_answer, consensusTarget) ? '✓' : '✗'}
                </span>
              </div>
            )}

            <div>
              <span style={{ color: 'var(--muted)' }}>Stored solution </span>
              <span style={{ fontWeight: 500 }}>{solFinalAns && solFinalAns !== '-' ? solFinalAns : 'none'}</span>{' '}
              <span style={{ color: isMatch(solFinalAns, consensusTarget) ? 'var(--green)' : 'var(--red)' }}>
                {isMatch(solFinalAns, consensusTarget) ? '✓' : '✗'}
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--muted)' }}>Stored key </span>
              <span style={{ fontWeight: 500 }}>{String(storedKey)}</span>{' '}
              <span style={{ color: isMatch(storedKey, consensusTarget) ? 'var(--green)' : 'var(--red)' }}>
                {isMatch(storedKey, consensusTarget) ? '✓' : '✗'}
              </span>
            </div>
          </div>

          {/* Show working expandable link */}
          <div>
            <button
              onClick={() => setShowWorkings(!showWorkings)}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '12px',
                color: 'var(--muted)',
                cursor: 'pointer',
                padding: 0,
                textDecoration: 'underline',
              }}
            >
              {showWorkings ? 'Hide working' : 'Show working'}
            </button>
            {showWorkings && (
              <div
                style={{
                  marginTop: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  fontSize: '12.5px',
                  color: 'var(--muted)',
                  lineHeight: 1.5,
                  padding: '10px 14px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  backgroundColor: 'var(--surface)',
                }}
              >
                {solverA?.working && (
                  <div>
                    <strong style={{ color: 'var(--text)' }}>Solver A:</strong> {solverA.working}
                  </div>
                )}
                {solverB?.working && (
                  <div>
                    <strong style={{ color: 'var(--text)' }}>Solver B:</strong> {solverB.working}
                  </div>
                )}
                {solverC?.working && (
                  <div>
                    <strong style={{ color: 'var(--text)' }}>Tie-break ({solverC.model || 'Flash'}):</strong>{' '}
                    {solverC.working}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Rule-based flags if any */}
          {currentCase.deterministic_checks && currentCase.deterministic_checks.length > 0 && (
            <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '8px' }}>
              Rule-based flags:{' '}
              {currentCase.deterministic_checks
                .map((chk: any) => (chk.check || chk.name || '').replace(/_/g, ' '))
                .join(', ')}
            </div>
          )}
        </section>

        {/* f. Question section (Georgia / STIX Two Text 18px) */}
        <section style={{ marginBottom: '36px' }}>
          <h2
            style={{
              fontSize: '14px',
              fontWeight: 600,
              color: 'var(--text)',
              marginBottom: '12px',
            }}
          >
            Question
          </h2>

          {/* Rendered stem */}
          <div
            className="question-reading question-html"
            style={{ marginBottom: '20px' }}
            dangerouslySetInnerHTML={{
              __html: sanitizeHtml(currentCase.stem_html || currentCase.stem_text),
            }}
          />

          {/* Options as a simple list with small text label next to relevant options */}
          {currentCase.options && Object.keys(currentCase.options).length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
              {Object.entries(currentCase.options).map(([label, opt]) => {
                const isStored = isMatch(label, storedKey);
                const isProposed = isAnswerKeyRepair && isMatch(label, editReplace);

                return (
                  <div key={label} style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                    <span
                      style={{
                        fontWeight: 600,
                        width: '18px',
                        flexShrink: 0,
                        color: 'var(--muted)',
                        fontSize: '16px',
                        fontFamily: 'var(--font-serif)',
                      }}
                    >
                      {label}
                    </span>
                    <div
                      className="question-reading question-html"
                      style={{ fontSize: '17px' }}
                      dangerouslySetInnerHTML={{ __html: sanitizeHtml(opt.html || opt.text) }}
                    />
                    {isStored && (
                      <span
                        style={{
                          fontSize: '11px',
                          color: 'var(--faint)',
                          marginLeft: '8px',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        current key
                      </span>
                    )}
                    {isProposed && (
                      <span
                        style={{
                          fontSize: '11px',
                          color: 'var(--accent)',
                          marginLeft: '8px',
                          fontWeight: 500,
                          whiteSpace: 'nowrap',
                        }}
                      >
                        proposed
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Stored solution text link */}
          {currentCase.solution_html && (
            <details style={{ marginTop: '12px', fontSize: '13px' }}>
              <summary
                style={{
                  color: 'var(--muted)',
                  cursor: 'pointer',
                }}
              >
                View stored solution
              </summary>
              <div
                className="question-reading question-html"
                style={{
                  marginTop: '10px',
                  padding: '12px 14px',
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  fontSize: '15px',
                  color: 'var(--muted)',
                }}
                dangerouslySetInnerHTML={{ __html: sanitizeHtml(currentCase.solution_html) }}
              />
            </details>
          )}
        </section>

        {/* g. Student reports section */}
        <section style={{ marginBottom: '36px' }}>
          <h2
            style={{
              fontSize: '14px',
              fontWeight: 600,
              color: 'var(--text)',
              marginBottom: '14px',
            }}
          >
            Student reports
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {currentCase.reports.map((rep) => {
              const currentReplyText =
                customReplies[rep.reportId] !== undefined ? customReplies[rep.reportId] : rep.student_reply;
              const metaString = formatStudentMeta(rep);

              return (
                <div key={rep.reportId}>
                  {/* Muted line above comment */}
                  <div
                    style={{
                      fontSize: '12px',
                      color: 'var(--muted)',
                      marginBottom: '6px',
                    }}
                  >
                    {metaString}
                  </div>

                  {/* Comment as quote with left border */}
                  <div
                    style={{
                      paddingLeft: '12px',
                      borderLeft: '2px solid var(--border)',
                      fontSize: '13.5px',
                      color: 'var(--text)',
                      fontStyle: 'italic',
                      marginBottom: '10px',
                      lineHeight: 1.45,
                    }}
                  >
                    "{rep.student_comment || 'No comment text provided'}"
                  </div>

                  {/* Reply the student will see */}
                  <div>
                    <div
                      style={{
                        fontSize: '11.5px',
                        color: 'var(--muted)',
                        marginBottom: '4px',
                      }}
                    >
                      Reply the student will see
                    </div>
                    <textarea
                      rows={2}
                      value={currentReplyText}
                      onChange={(e) => onUpdateReply(rep.reportId, e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        fontSize: '13px',
                        fontFamily: 'var(--font-sans)',
                        lineHeight: 1.45,
                        backgroundColor: 'var(--surface)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        color: 'var(--text)',
                        resize: 'vertical',
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* 4. Sticky bottom bar (right-aligned, quiet) */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: '300px',
          right: 0,
          backgroundColor: 'var(--bg)',
          borderTop: '1px solid var(--border)',
          padding: '12px 32px',
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          gap: '10px',
          zIndex: 40,
        }}
      >
        {/* Reject ghost button */}
        <button
          onClick={onOpenReject}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 14px',
            fontSize: '13px',
            backgroundColor: 'transparent',
            color: 'var(--text)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            cursor: 'pointer',
          }}
        >
          <span>Reject</span>
          <kbd>R</kbd>
        </button>

        {/* Edit ghost button */}
        <button
          onClick={onOpenEdit}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 14px',
            fontSize: '13px',
            backgroundColor: 'transparent',
            color: 'var(--text)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            cursor: 'pointer',
          }}
        >
          <span>Edit</span>
          <kbd>E</kbd>
        </button>

        {/* Approve solid accent button */}
        <button
          onClick={onApprove}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 18px',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: 'var(--accent)',
            color: '#fff',
            border: 'none',
            borderRadius: 'var(--radius)',
            cursor: 'pointer',
          }}
        >
          <span>Approve</span>
          <kbd style={{ color: '#fff', borderColor: 'rgba(255,255,255,0.3)' }}>A</kbd>
        </button>
      </div>
    </main>
  );
};
