import React, { useState } from 'react';
import { CaseItem, EditProposal } from '../types';

interface EditModalProps {
  currentCase: CaseItem;
  isOpen: boolean;
  onClose: () => void;
  onSaveAndApprove: (modifiedEdit: EditProposal, modifiedReplies: Record<string, string>) => void;
  initialReplies: Record<string, string>;
}

export const EditModal: React.FC<EditModalProps> = ({
  currentCase,
  isOpen,
  onClose,
  onSaveAndApprove,
  initialReplies,
}) => {
  if (!isOpen) return null;

  const originalEdit = currentCase.edit;
  const isAnswerKey = currentCase.top_repair === 'answer_key' || originalEdit?.field === 'answer';

  const [field, setField] = useState<string>(originalEdit?.field || (isAnswerKey ? 'answer' : 'question'));
  const [findText, setFindText] = useState<string>(originalEdit?.find || '');
  const [replaceText, setReplaceText] = useState<string>(
    originalEdit?.replace !== undefined ? String(originalEdit.replace) : ''
  );
  const [replies, setReplies] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const rep of currentCase.reports) {
      init[rep.reportId] = initialReplies[rep.reportId] !== undefined ? initialReplies[rep.reportId] : rep.student_reply;
    }
    return init;
  });

  const handleSave = () => {
    const modifiedEdit: EditProposal = {
      field,
      find: findText || null,
      replace: replaceText,
    };
    onSaveAndApprove(modifiedEdit, replies);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '20px',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '640px',
          backgroundColor: 'var(--surface)',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '90vh',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            backgroundColor: 'var(--bg)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text)' }}>
              Edit proposal & replies
            </h3>
            <span style={{ fontSize: '12px', color: 'var(--muted)' }} className="mono-id">
              {currentCase.questionId}
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '16px',
              color: 'var(--muted)',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
          {/* Target Field */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--muted)', marginBottom: '6px' }}>
              Target field
            </label>
            <input
              type="text"
              value={field}
              onChange={(e) => setField(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 10px',
                fontSize: '13px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                color: 'var(--text)',
              }}
            />
          </div>

          {/* Find */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--muted)', marginBottom: '6px' }}>
              Find string (exact text to replace)
            </label>
            <textarea
              rows={2}
              value={findText}
              onChange={(e) => setFindText(e.target.value)}
              placeholder="Leave blank for whole field or answer key..."
              style={{
                width: '100%',
                padding: '6px 10px',
                fontSize: '13px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                color: 'var(--text)',
              }}
            />
          </div>

          {/* Replace */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--muted)', marginBottom: '6px' }}>
              Replacement text / correct answer
            </label>
            <textarea
              rows={3}
              value={replaceText}
              onChange={(e) => setReplaceText(e.target.value)}
              placeholder="Exact replacement text..."
              style={{
                width: '100%',
                padding: '6px 10px',
                fontSize: '13px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                color: 'var(--text)',
              }}
            />
          </div>

          {/* Replies */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--muted)', marginBottom: '10px' }}>
              Replies ({currentCase.reports.length})
            </label>
            {currentCase.reports.map((rep) => (
              <div key={rep.reportId} style={{ marginBottom: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
                  Student {rep.student_id}:
                </span>
                <textarea
                  rows={2}
                  value={replies[rep.reportId] || ''}
                  onChange={(e) =>
                    setReplies({
                      ...replies,
                      [rep.reportId]: e.target.value,
                    })
                  }
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    fontSize: '13px',
                    backgroundColor: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                    color: 'var(--text)',
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid var(--border)',
            backgroundColor: 'var(--bg)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '10px',
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: '6px 14px',
              fontSize: '13px',
              backgroundColor: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              color: 'var(--text)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            style={{
              padding: '6px 16px',
              fontSize: '13px',
              fontWeight: 500,
              backgroundColor: 'var(--accent)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius)',
              cursor: 'pointer',
            }}
          >
            Save and approve
          </button>
        </div>
      </div>
    </div>
  );
};

