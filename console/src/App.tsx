import { useState, useEffect, useMemo, useCallback } from 'react';
import { CasesBundle, AuditDecision, EditProposal } from './types';
import { Navbar } from './components/Navbar';
import { QueueSidebar } from './components/QueueSidebar';
import { MainPanel } from './components/MainPanel';
import { EditModal } from './components/EditModal';
import { RejectModal } from './components/RejectModal';
import { AuditDrawer } from './components/AuditDrawer';
import { ShortcutsModal } from './components/ShortcutsModal';
import { ReviewerModal } from './components/ReviewerModal';
import { UndoToast } from './components/UndoToast';
import { EmptyState } from './components/EmptyState';

const LOCAL_STORAGE_KEY_DECISIONS = 'acadza_decisions_v2';
const LOCAL_STORAGE_KEY_LOG = 'acadza_audit_log_v2';
const LOCAL_STORAGE_KEY_REVIEWER = 'acadza_reviewer_name_v2';
const LOCAL_STORAGE_KEY_THEME = 'acadza_theme_v2';

export default function App() {
  const [bundle, setBundle] = useState<CasesBundle | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Core application state
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<'needs_review' | 'auto_apply' | 'no_change' | 'all'>('needs_review');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Custom in-memory replies modified in the main view
  const [customReplies, setCustomReplies] = useState<Record<string, string>>({});

  // LocalStorage state: Decisions & Audit Log
  const [decisions, setDecisions] = useState<Record<string, AuditDecision>>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY_DECISIONS);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const [auditLog, setAuditLog] = useState<AuditDecision[]>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY_LOG);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [reviewerName, setReviewerName] = useState<string>(() => {
    return localStorage.getItem(LOCAL_STORAGE_KEY_REVIEWER) || 'Faculty Reviewer';
  });

  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem(LOCAL_STORAGE_KEY_THEME) as 'dark' | 'light') || 'dark';
  });

  // Modals & Drawers
  const [showEditModal, setShowEditModal] = useState<boolean>(false);
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [showAuditDrawer, setShowAuditDrawer] = useState<boolean>(false);
  const [showShortcutsModal, setShowShortcutsModal] = useState<boolean>(false);
  const [showReviewerModal, setShowReviewerModal] = useState<boolean>(false);

  // Undo Toast state
  const [undoItem, setUndoItem] = useState<AuditDecision | null>(null);

  // Set Theme attribute on root element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(LOCAL_STORAGE_KEY_THEME, theme);
  }, [theme]);

  // Save decisions to localStorage
  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEY_DECISIONS, JSON.stringify(decisions));
  }, [decisions]);

  // Save auditLog to localStorage
  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEY_LOG, JSON.stringify(auditLog));
  }, [auditLog]);

  // Load data bundle
  useEffect(() => {
    async function loadCases() {
      try {
        setLoading(true);
        const res = await fetch('/data/cases.json');
        if (!res.ok) {
          throw new Error(`Failed to load /data/cases.json (${res.status})`);
        }
        const data: CasesBundle = await res.json();
        setBundle(data);

        // Find initial selected question: first unreviewed question in needs_review, or first item
        const firstUnreviewed = data.cases.find(
          (c) => c.route === 'faculty_review' && !decisions[c.questionId]
        );
        setSelectedId(firstUnreviewed ? firstUnreviewed.questionId : data.cases[0]?.questionId || null);
      } catch (err: any) {
        setError(err.message || 'Error loading cases');
      } finally {
        setLoading(false);
      }
    }

    loadCases();
  }, []);

  const allCases = useMemo(() => bundle?.cases || [], [bundle]);

  // Filter and search logic
  const filteredCases = useMemo(() => {
    return allCases.filter((c) => {
      // Filter by route category
      if (activeFilter === 'needs_review' && c.route !== 'faculty_review') return false;
      if (activeFilter === 'auto_apply' && c.route !== 'auto_apply') return false;
      if (activeFilter === 'no_change' && c.route !== 'no_change') return false;

      // Filter by search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const inId = c.questionId.toLowerCase().includes(q);
        const inStem = (c.stem_text || '').toLowerCase().includes(q);
        const inSubject = (c.subject || '').toLowerCase().includes(q);
        const inChapter = (c.chapter || '').toLowerCase().includes(q);
        const inReports = c.reports.some(
          (r) =>
            (r.student_comment || '').toLowerCase().includes(q) ||
            (r.student_id || '').toLowerCase().includes(q)
        );
        return inId || inStem || inSubject || inChapter || inReports;
      }

      return true;
    });
  }, [allCases, activeFilter, searchQuery]);

  // Filter counts
  const filterCounts = useMemo(() => {
    return {
      needs_review: allCases.filter((c) => c.route === 'faculty_review').length,
      auto_apply: allCases.filter((c) => c.route === 'auto_apply').length,
      no_change: allCases.filter((c) => c.route === 'no_change').length,
      all: allCases.length,
    };
  }, [allCases]);

  // Selected Case Object
  const currentCase = useMemo(() => {
    if (!selectedId) return null;
    return allCases.find((c) => c.questionId === selectedId) || null;
  }, [allCases, selectedId]);

  // Index navigation
  const currentIndex = useMemo(() => {
    return filteredCases.findIndex((c) => c.questionId === selectedId);
  }, [filteredCases, selectedId]);

  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex >= 0 && currentIndex < filteredCases.length - 1;

  const handleNext = useCallback(() => {
    if (hasNext) {
      setSelectedId(filteredCases[currentIndex + 1].questionId);
    }
  }, [hasNext, currentIndex, filteredCases]);

  const handlePrev = useCallback(() => {
    if (hasPrev) {
      setSelectedId(filteredCases[currentIndex - 1].questionId);
    }
  }, [hasPrev, currentIndex, filteredCases]);

  // Auto-advance to next unreviewed case after action
  const autoAdvance = useCallback(() => {
    // Find next unreviewed item in current filtered list
    const nextUnreviewed = filteredCases.find(
      (c, idx) => idx > currentIndex && !decisions[c.questionId]
    );
    if (nextUnreviewed) {
      setSelectedId(nextUnreviewed.questionId);
      return;
    }
    // Or find any unreviewed in filtered list
    const anyUnreviewed = filteredCases.find((c) => !decisions[c.questionId]);
    if (anyUnreviewed && anyUnreviewed.questionId !== selectedId) {
      setSelectedId(anyUnreviewed.questionId);
      return;
    }
    // Otherwise regular next
    if (hasNext) {
      handleNext();
    }
  }, [filteredCases, currentIndex, decisions, selectedId, hasNext, handleNext]);

  // Decision actions
  const handleApprove = useCallback(() => {
    if (!currentCase) return;

    // Collect final replies
    const repliesMap: Record<string, string> = {};
    for (const r of currentCase.reports) {
      repliesMap[r.reportId] =
        customReplies[r.reportId] !== undefined ? customReplies[r.reportId] : r.student_reply;
    }

    const newDecision: AuditDecision = {
      id: `dec_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
      caseId: currentCase.questionId,
      action: 'approved',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      reviewer: reviewerName,
      topRepair: currentCase.top_repair,
      originalEdit: currentCase.edit || null,
      finalEdit: currentCase.edit || null,
      replies: repliesMap,
    };

    setDecisions((prev) => ({ ...prev, [currentCase.questionId]: newDecision }));
    setAuditLog((prev) => [newDecision, ...prev]);
    setUndoItem(newDecision);
    autoAdvance();
  }, [currentCase, customReplies, reviewerName, autoAdvance]);

  const handleSaveEditAndApprove = useCallback(
    (modifiedEdit: EditProposal, modifiedReplies: Record<string, string>) => {
      if (!currentCase) return;

      const newDecision: AuditDecision = {
        id: `dec_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        caseId: currentCase.questionId,
        action: 'edited',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        reviewer: reviewerName,
        topRepair: currentCase.top_repair,
        originalEdit: currentCase.edit || null,
        finalEdit: modifiedEdit,
        replies: modifiedReplies,
      };

      setDecisions((prev) => ({ ...prev, [currentCase.questionId]: newDecision }));
      setAuditLog((prev) => [newDecision, ...prev]);
      setUndoItem(newDecision);
      setShowEditModal(false);
      autoAdvance();
    },
    [currentCase, reviewerName, autoAdvance]
  );

  const handleConfirmReject = useCallback(
    (reason: string, note: string) => {
      if (!currentCase) return;

      const newDecision: AuditDecision = {
        id: `dec_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        caseId: currentCase.questionId,
        action: 'rejected',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        reviewer: reviewerName,
        topRepair: currentCase.top_repair,
        originalEdit: currentCase.edit || null,
        replies: {},
        rejectReason: reason,
        rejectNote: note,
      };

      setDecisions((prev) => ({ ...prev, [currentCase.questionId]: newDecision }));
      setAuditLog((prev) => [newDecision, ...prev]);
      setUndoItem(newDecision);
      setShowRejectModal(false);
      autoAdvance();
    },
    [currentCase, reviewerName, autoAdvance]
  );

  const handleUndo = useCallback(() => {
    if (!undoItem) return;
    const targetCaseId = undoItem.caseId;

    // Remove from decisions and audit log
    setDecisions((prev) => {
      const copy = { ...prev };
      delete copy[targetCaseId];
      return copy;
    });

    setAuditLog((prev) => prev.filter((d) => d.id !== undoItem.id));
    setUndoItem(null);
    setSelectedId(targetCaseId);
  }, [undoItem]);

  // Global Keyboard Shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept if user is typing inside an input, textarea, or select
      const target = e.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      ) {
        if (e.key === 'Escape') {
          target.blur();
        }
        return;
      }

      // Escape closes any modal or drawer
      if (e.key === 'Escape') {
        setShowEditModal(false);
        setShowRejectModal(false);
        setShowAuditDrawer(false);
        setShowShortcutsModal(false);
        setShowReviewerModal(false);
        return;
      }

      // Help
      if (e.key === '?') {
        e.preventDefault();
        setShowShortcutsModal((prev) => !prev);
        return;
      }

      // Navigation
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        handleNext();
        return;
      }
      if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        handlePrev();
        return;
      }

      // Action: Approve
      if (e.key === 'a' || e.key === 'A') {
        e.preventDefault();
        handleApprove();
        return;
      }

      // Action: Edit
      if (e.key === 'e' || e.key === 'E') {
        e.preventDefault();
        setShowEditModal(true);
        return;
      }

      // Action: Reject
      if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        setShowRejectModal(true);
        return;
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleNext, handlePrev, handleApprove]);

  // Reviewer name persistence
  const handleSaveReviewer = (name: string) => {
    setReviewerName(name);
    localStorage.setItem(LOCAL_STORAGE_KEY_REVIEWER, name);
    setShowReviewerModal(false);
  };

  const handleClearAudit = () => {
    setDecisions({});
    setAuditLog([]);
    localStorage.removeItem(LOCAL_STORAGE_KEY_DECISIONS);
    localStorage.removeItem(LOCAL_STORAGE_KEY_LOG);
  };

  const handleUpdateReply = (reportId: string, replyText: string) => {
    setCustomReplies((prev) => ({
      ...prev,
      [reportId]: replyText,
    }));
  };

  const reviewedCount = Object.keys(decisions).length;
  const isAllReviewed = allCases.length > 0 && reviewedCount === allCases.length;
  const isFilterEmpty = filteredCases.length === 0;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-app)' }}>
      {/* Top Navbar */}
      <Navbar
        engineTimestamp={bundle?.engine_run_timestamp || ''}
        totalCases={allCases.length}
        reviewedCount={reviewedCount}
        activeFilter={activeFilter}
        filterCounts={filterCounts}
        onFilterChange={setActiveFilter}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        reviewerName={reviewerName}
        onEditReviewer={() => setShowReviewerModal(true)}
        onOpenAuditDrawer={() => setShowAuditDrawer(true)}
        auditCount={auditLog.length}
        onOpenShortcuts={() => setShowShortcutsModal(true)}
      />

      {/* Main Workspace Layout */}
      <div style={{ flex: 1, display: 'flex', position: 'relative' }}>
        {loading ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '100px 0',
              color: 'var(--text-muted)',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                border: '3px solid var(--border-subtle)',
                borderTopColor: 'var(--accent-primary)',
                animation: 'spin 1s linear infinite',
                marginBottom: '16px',
              }}
            />
            <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', marginBottom: '6px' }}>
              Loading Precomputed Cases Bundle...
            </h3>
            <p style={{ fontSize: '13px' }}>Parsing MathML stems, solver outputs & deterministic checks</p>
          </div>
        ) : error ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '100px 20px',
              color: 'var(--color-red-text)',
            }}
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: 'var(--color-red-bg)',
                border: '1px solid var(--color-red-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                marginBottom: '14px',
              }}
            >
              !
            </div>
            <h3 style={{ fontSize: '16px', marginBottom: '6px' }}>Error Loading Console Data</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '480px', textAlign: 'center' }}>
              {error}
            </p>
          </div>
        ) : (
          <>
            {/* Left Queue Sidebar */}
            <QueueSidebar
              cases={filteredCases}
              selectedId={selectedId}
              onSelectCase={setSelectedId}
              decisions={decisions}
              activeFilter={activeFilter}
            />

            {/* Main Inspection Panel or Empty State */}
            {isAllReviewed ? (
              <EmptyState
                totalReviewed={reviewedCount}
                totalCases={allCases.length}
                onOpenAudit={() => setShowAuditDrawer(true)}
                onResetFilter={() => setActiveFilter('all')}
              />
            ) : isFilterEmpty ? (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '60px 20px',
                  color: 'var(--text-muted)',
                }}
              >
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    border: '2px solid var(--border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '12px',
                    fontWeight: 700,
                  }}
                >
                  Ø
                </div>
                <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', marginBottom: '6px' }}>
                  No cases found in "{activeFilter.replace('_', ' ')}"
                </h3>
                <p style={{ fontSize: '13px', marginBottom: '16px' }}>
                  Try switching to another tab or clearing your search query.
                </p>
                <button
                  onClick={() => {
                    setActiveFilter('all');
                    setSearchQuery('');
                  }}
                  style={{
                    padding: '6px 14px',
                    fontSize: '12px',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                  }}
                >
                  Show All Cases
                </button>
              </div>
            ) : (
              <MainPanel
                currentCase={currentCase}
                decision={selectedId ? decisions[selectedId] : undefined}
                onApprove={handleApprove}
                onOpenEdit={() => setShowEditModal(true)}
                onOpenReject={() => setShowRejectModal(true)}
                onNext={handleNext}
                onPrev={handlePrev}
                hasNext={hasNext}
                hasPrev={hasPrev}
                onUpdateReply={handleUpdateReply}
                customReplies={customReplies}
              />
            )}
          </>
        )}
      </div>

      {/* Floating Undo Toast */}
      <UndoToast decision={undoItem} onUndo={handleUndo} onDismiss={() => setUndoItem(null)} />

      {/* Modals & Drawers */}
      {currentCase && (
        <>
          <EditModal
            currentCase={currentCase}
            isOpen={showEditModal}
            onClose={() => setShowEditModal(false)}
            onSaveAndApprove={handleSaveEditAndApprove}
            initialReplies={customReplies}
          />

          <RejectModal
            currentCase={currentCase}
            isOpen={showRejectModal}
            onClose={() => setShowRejectModal(false)}
            onConfirmReject={handleConfirmReject}
          />
        </>
      )}

      <AuditDrawer
        isOpen={showAuditDrawer}
        onClose={() => setShowAuditDrawer(false)}
        auditLog={auditLog}
        reviewerName={reviewerName}
        onEditReviewer={() => setShowReviewerModal(true)}
        onClearAudit={handleClearAudit}
      />

      <ShortcutsModal isOpen={showShortcutsModal} onClose={() => setShowShortcutsModal(false)} />

      <ReviewerModal
        isOpen={showReviewerModal}
        currentName={reviewerName}
        onSave={handleSaveReviewer}
        onClose={() => setShowReviewerModal(false)}
      />
    </div>
  );
}
