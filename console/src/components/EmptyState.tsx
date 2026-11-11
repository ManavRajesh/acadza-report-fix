import React from 'react';

interface EmptyStateProps {
  totalReviewed: number;
  totalCases: number;
  onOpenAudit: () => void;
  onResetFilter: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  totalReviewed,
  totalCases,
  onOpenAudit,
  onResetFilter,
}) => {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 20px',
        textAlign: 'center',
        color: 'var(--text)',
      }}
    >
      <h2 style={{ fontSize: '18px', fontWeight: 500, color: 'var(--text)', marginBottom: '8px' }}>
        All caught up. {totalReviewed} of {totalCases} reviewed.
      </h2>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '13px', marginTop: '12px' }}>
        <button
          onClick={onOpenAudit}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--accent)',
            cursor: 'pointer',
            padding: 0,
            fontSize: '13px',
            textDecoration: 'underline',
          }}
        >
          Export audit log
        </button>

        <span style={{ color: 'var(--border)' }}>·</span>

        <button
          onClick={onResetFilter}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--muted)',
            cursor: 'pointer',
            padding: 0,
            fontSize: '13px',
          }}
        >
          View all questions
        </button>
      </div>
    </div>
  );
};
