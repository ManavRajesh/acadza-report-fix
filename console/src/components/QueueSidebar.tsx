import React, { useState } from 'react';
import { CaseItem, AuditDecision } from '../types';
import { formatRepair } from '../utils/copy';

interface QueueSidebarProps {
  cases: CaseItem[];
  selectedId: string | null;
  onSelectCase: (id: string) => void;
  decisions: Record<string, AuditDecision>;
  activeFilter: 'needs_review' | 'auto_apply' | 'no_change' | 'all';
}

export const QueueSidebar: React.FC<QueueSidebarProps> = ({
  cases,
  selectedId,
  onSelectCase,
  decisions,
  activeFilter,
}) => {
  const [collapsedNoChange, setCollapsedNoChange] = useState<boolean>(true);
  const [showOrderTooltip, setShowOrderTooltip] = useState<boolean>(false);

  // Group cases
  const needsReviewCases = cases.filter((c) => c.route === 'faculty_review');
  const autoApplyCases = cases.filter((c) => c.route === 'auto_apply');
  const noChangeCases = cases.filter((c) => c.route === 'no_change');

  const showNeedsReview = activeFilter === 'all' || activeFilter === 'needs_review';
  const showAutoApply = activeFilter === 'all' || activeFilter === 'auto_apply';
  const showNoChange = activeFilter === 'all' || activeFilter === 'no_change';

  const renderRow = (c: CaseItem) => {
    const isSelected = c.questionId === selectedId;
    const isReviewed = Boolean(decisions[c.questionId]);
    const repairLabel = formatRepair(c.top_repair);
    const numStudents = `${c.reports.length} student${c.reports.length > 1 ? 's' : ''}`;

    // 6px colored dot: red = defect, amber = verify, green = confirmed, gray = no change
    let dotColor = 'var(--gray)';
    if (c.top_verdict === 'defect') {
      dotColor = c.route === 'faculty_review' ? 'var(--red)' : 'var(--green)';
    } else if (c.route === 'no_change') {
      dotColor = 'var(--gray)';
    }

    return (
      <div
        key={c.questionId}
        onClick={() => onSelectCase(c.questionId)}
        style={{
          padding: '8px 16px',
          borderBottom: '1px solid var(--border)',
          borderLeft: isSelected ? '2px solid var(--accent)' : '2px solid transparent',
          backgroundColor: isSelected ? 'var(--surface)' : 'transparent',
          cursor: 'pointer',
          transition: 'background-color 0.1s ease',
        }}
      >
        {/* Line 1: stem truncated to one line */}
        <div
          style={{
            fontSize: '13px',
            color: 'var(--text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            lineHeight: 1.4,
          }}
        >
          {c.stem_text || 'Question content'}
        </div>

        {/* Line 2: small muted line with 6px dot */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--muted)',
            marginTop: '3px',
          }}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: dotColor,
              flexShrink: 0,
            }}
          />
          <span>
            {repairLabel} · {numStudents}
          </span>
          {isReviewed && (
            <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--faint)' }}>
              reviewed
            </span>
          )}
        </div>
      </div>
    );
  };

  return (
    <aside
      style={{
        width: '300px',
        flexShrink: 0,
        borderRight: '1px solid var(--border)',
        backgroundColor: 'var(--bg)',
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 52px)',
        position: 'sticky',
        top: '52px',
      }}
    >
      {/* Top line with "Why this order?" link */}
      <div
        style={{
          padding: '10px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '12px',
          color: 'var(--muted)',
        }}
      >
        <span>Questions</span>
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowOrderTooltip(!showOrderTooltip)}
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
            Why this order?
          </button>

          {showOrderTooltip && (
            <div
              style={{
                position: 'absolute',
                top: '20px',
                right: 0,
                width: '260px',
                padding: '12px',
                backgroundColor: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
                fontSize: '12px',
                color: 'var(--text)',
                lineHeight: 1.45,
                zIndex: 60,
              }}
            >
              Wrong answer keys and missing data come first — they mislead every student who attempts the question. Then more reports, then higher confidence.
            </div>
          )}
        </div>
      </div>

      {/* Rows Container */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {cases.length === 0 ? (
          <div style={{ padding: '32px 16px', color: 'var(--muted)', fontSize: '13px', textAlign: 'center' }}>
            No questions in this view.
          </div>
        ) : (
          <>
            {/* Needs review */}
            {showNeedsReview && needsReviewCases.length > 0 && (
              <div>
                <div
                  style={{
                    padding: '8px 16px 4px 16px',
                    fontSize: '12px',
                    color: 'var(--muted)',
                    fontWeight: 500,
                  }}
                >
                  Needs review ({needsReviewCases.length})
                </div>
                {needsReviewCases.map(renderRow)}
              </div>
            )}

            {/* Auto-applied — spot check */}
            {showAutoApply && autoApplyCases.length > 0 && (
              <div>
                <div
                  style={{
                    padding: '12px 16px 4px 16px',
                    fontSize: '12px',
                    color: 'var(--muted)',
                    fontWeight: 500,
                  }}
                >
                  Auto-applied — spot check ({autoApplyCases.length})
                </div>
                {autoApplyCases.map(renderRow)}
              </div>
            )}

            {/* No change (collapsible) */}
            {showNoChange && noChangeCases.length > 0 && (
              <div>
                <button
                  onClick={() => setCollapsedNoChange(!collapsedNoChange)}
                  style={{
                    width: '100%',
                    background: 'none',
                    border: 'none',
                    padding: '12px 16px 4px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '12px',
                    color: 'var(--muted)',
                    fontWeight: 500,
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <span>No change ({noChangeCases.length})</span>
                  <span style={{ fontSize: '10px' }}>{collapsedNoChange ? 'Show' : 'Hide'}</span>
                </button>
                {!collapsedNoChange && noChangeCases.map(renderRow)}
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
};
