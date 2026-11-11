import React from 'react';
import { AuditDecision } from '../types';
import { formatRepair } from '../utils/copy';

interface AuditDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  auditLog: AuditDecision[];
  reviewerName: string;
  onEditReviewer: () => void;
  onClearAudit: () => void;
}

export const AuditDrawer: React.FC<AuditDrawerProps> = ({
  isOpen,
  onClose,
  auditLog,
  reviewerName,
  onEditReviewer,
  onClearAudit,
}) => {
  if (!isOpen) return null;

  const approvedCount = auditLog.filter((d) => d.action === 'approved').length;
  const editedCount = auditLog.filter((d) => d.action === 'edited').length;
  const rejectedCount = auditLog.filter((d) => d.action === 'rejected').length;

  const handleExportJson = () => {
    const exportBundle = {
      export_timestamp: new Date().toISOString(),
      reviewer: reviewerName,
      stats: {
        total_decisions: auditLog.length,
        approved: approvedCount,
        edited: editedCount,
        rejected: rejectedCount,
      },
      decisions: auditLog,
    };

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportBundle, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute(
      'download',
      `acadza_faculty_audit_log_${new Date().toISOString().slice(0, 10)}.json`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        backdropFilter: 'blur(2px)',
        zIndex: 100,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '520px',
          height: '100%',
          backgroundColor: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Drawer Header */}
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
              Audit log
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
              <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
                Reviewer: {reviewerName}
              </span>
              <button
                onClick={onEditReviewer}
                style={{
                  fontSize: '11px',
                  color: 'var(--accent)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
              >
                Change
              </button>
            </div>
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

        {/* Stats Row */}
        <div
          style={{
            padding: '12px 20px',
            borderBottom: '1px solid var(--border)',
            backgroundColor: 'var(--bg)',
            display: 'flex',
            gap: '24px',
            fontSize: '13px',
          }}
        >
          <div>
            <span style={{ color: 'var(--muted)' }}>Total </span>
            <strong>{auditLog.length}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--muted)' }}>Approved </span>
            <span style={{ color: 'var(--green)' }}>{approvedCount}</span>
          </div>
          <div>
            <span style={{ color: 'var(--muted)' }}>Edited </span>
            <span style={{ color: 'var(--amber)' }}>{editedCount}</span>
          </div>
          <div>
            <span style={{ color: 'var(--muted)' }}>Rejected </span>
            <span style={{ color: 'var(--red)' }}>{rejectedCount}</span>
          </div>
        </div>

        {/* Action Controls */}
        <div
          style={{
            padding: '10px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <button
            onClick={handleExportJson}
            disabled={auditLog.length === 0}
            style={{
              padding: '5px 12px',
              fontSize: '12px',
              fontWeight: 500,
              backgroundColor: 'var(--surface-hover)',
              color: 'var(--text)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              cursor: auditLog.length === 0 ? 'default' : 'pointer',
              opacity: auditLog.length === 0 ? 0.5 : 1,
            }}
          >
            Export audit log (JSON)
          </button>

          {auditLog.length > 0 && (
            <button
              onClick={() => {
                if (window.confirm('Reset all decisions in audit trail?')) {
                  onClearAudit();
                }
              }}
              style={{
                fontSize: '11px',
                color: 'var(--muted)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              Reset decisions
            </button>
          )}
        </div>

        {/* Chronological List of Decisions */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px' }}>
          {auditLog.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: '13px' }}>
              No decisions recorded yet.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {auditLog.map((item) => (
                <div
                  key={item.id}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 'var(--radius)',
                    backgroundColor: 'var(--bg)',
                    border: '1px solid var(--border)',
                    fontSize: '12.5px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '4px',
                    }}
                  >
                    <span className="mono-id">{item.caseId}</span>
                    <span
                      style={{
                        fontSize: '11px',
                        color:
                          item.action === 'approved'
                            ? 'var(--green)'
                            : item.action === 'edited'
                            ? 'var(--amber)'
                            : 'var(--red)',
                      }}
                    >
                      {item.action}
                    </span>
                  </div>

                  <div style={{ fontSize: '11.5px', color: 'var(--muted)', marginBottom: '3px' }}>
                    {item.timestamp} · {item.reviewer}
                  </div>

                  {item.topRepair && (
                    <div style={{ color: 'var(--text)' }}>
                      {formatRepair(item.topRepair)}
                    </div>
                  )}

                  {item.rejectReason && (
                    <div style={{ color: 'var(--red)', marginTop: '3px' }}>
                      Reason: {item.rejectReason}
                      {item.rejectNote && <span style={{ color: 'var(--muted)', display: 'block' }}>"{item.rejectNote}"</span>}
                    </div>
                  )}

                  {item.finalEdit && (
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11.5px', color: 'var(--accent)', marginTop: '3px' }}>
                      {item.finalEdit.field}: {String(item.finalEdit.replace)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

