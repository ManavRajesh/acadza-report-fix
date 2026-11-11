import React, { useEffect, useState } from 'react';
import { AuditDecision } from '../types';

interface UndoToastProps {
  decision: AuditDecision | null;
  onUndo: () => void;
  onDismiss: () => void;
}

export const UndoToast: React.FC<UndoToastProps> = ({ decision, onUndo, onDismiss }) => {
  const [secondsLeft, setSecondsLeft] = useState<number>(5);

  useEffect(() => {
    if (!decision) return;
    setSecondsLeft(5);

    const interval = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          onDismiss();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [decision, onDismiss]);

  if (!decision) return null;

  return (
    <div
      className="animate-toast"
      style={{
        position: 'fixed',
        bottom: '80px',
        left: '50%',
        transform: 'translateX(-50%)',
        backgroundColor: 'var(--bg-surface-elevated)',
        border: '1px solid var(--border-strong)',
        boxShadow: 'var(--shadow-lg)',
        borderRadius: 'var(--radius-md)',
        padding: '10px 18px',
        display: 'flex',
        alignItems: 'center',
        gap: '14px',
        zIndex: 90,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
        <span
          style={{
            fontSize: '10px',
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: 'var(--radius-xs)',
            backgroundColor:
              decision.action === 'approved'
                ? 'var(--color-green-bg)'
                : decision.action === 'edited'
                ? 'var(--color-amber-bg)'
                : 'var(--color-red-bg)',
            color:
              decision.action === 'approved'
                ? 'var(--color-green-text)'
                : decision.action === 'edited'
                ? 'var(--color-amber-text)'
                : 'var(--color-red-text)',
            border: `1px solid ${
              decision.action === 'approved'
                ? 'var(--color-green-border)'
                : decision.action === 'edited'
                ? 'var(--color-amber-border)'
                : 'var(--color-red-border)'
            }`,
          }}
        >
          {decision.action.toUpperCase()}
        </span>
        <span>
          Recorded decision for{' '}
          <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)' }}>
            {decision.caseId.slice(0, 10)}...
          </code>
        </span>
      </div>

      <button
        onClick={onUndo}
        style={{
          padding: '4px 12px',
          fontSize: '12px',
          fontWeight: 700,
          backgroundColor: 'var(--accent-primary)',
          color: '#000',
          border: 'none',
          borderRadius: 'var(--radius-xs)',
          cursor: 'pointer',
        }}
      >
        Undo ({secondsLeft}s)
      </button>

      <button
        onClick={onDismiss}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          fontSize: '14px',
          padding: '2px',
        }}
      >
        ✕
      </button>
    </div>
  );
};

