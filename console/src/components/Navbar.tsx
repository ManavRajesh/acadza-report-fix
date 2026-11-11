import React from 'react';

interface NavbarProps {
  engineTimestamp?: string;
  totalCases: number;
  reviewedCount: number;
  activeFilter: 'needs_review' | 'auto_apply' | 'no_change' | 'all';
  filterCounts: {
    needs_review: number;
    auto_apply: number;
    no_change: number;
    all: number;
  };
  onFilterChange: (filter: 'needs_review' | 'auto_apply' | 'no_change' | 'all') => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  reviewerName: string;
  onEditReviewer: () => void;
  onOpenAuditDrawer: () => void;
  auditCount: number;
  onOpenShortcuts: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  engineTimestamp,
  totalCases,
  reviewedCount,
  activeFilter,
  filterCounts,
  onFilterChange,
  searchQuery,
  onSearchChange,
  theme,
  onToggleTheme,
  reviewerName,
  onEditReviewer,
  onOpenAuditDrawer,
  auditCount,
  onOpenShortcuts,
}) => {
  const leftCount = Math.max(0, totalCases - reviewedCount);
  const percentReviewed = totalCases > 0 ? Math.round((reviewedCount / totalCases) * 100) : 0;

  const tabs = [
    { id: 'needs_review', label: 'Needs review', count: filterCounts.needs_review },
    { id: 'auto_apply', label: 'Auto-applied', count: filterCounts.auto_apply },
    { id: 'no_change', label: 'No change', count: filterCounts.no_change },
    { id: 'all', label: 'All', count: filterCounts.all },
  ] as const;

  return (
    <header
      style={{
        height: '52px',
        backgroundColor: 'var(--bg)',
        borderBottom: '1px solid var(--border)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        fontSize: '13.5px',
      }}
    >
      {/* 2px Progress line under the whole bar */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          height: '2px',
          width: `${percentReviewed}%`,
          backgroundColor: 'var(--accent)',
          transition: 'width 0.25s ease',
        }}
      />

      {/* Left: Brand & Engine run */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.2px' }}>
          Acadza
        </span>
        <span style={{ color: 'var(--muted)', fontSize: '12.5px' }}>
          Showing precomputed AI results{engineTimestamp ? ` (engine run ${engineTimestamp.slice(0, 16).replace('T', ' ')})` : ''}
        </span>
      </div>

      {/* Center: Filter tabs as plain text with active underline */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', height: '100%' }}>
        {tabs.map((tab) => {
          const isSelected = activeFilter === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onFilterChange(tab.id)}
              style={{
                background: 'none',
                border: 'none',
                height: '100%',
                padding: '0 2px',
                fontSize: '13.5px',
                fontWeight: isSelected ? 500 : 400,
                color: isSelected ? 'var(--text)' : 'var(--muted)',
                cursor: 'pointer',
                borderBottom: isSelected ? '2px solid var(--accent)' : '2px solid transparent',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'color 0.15s ease',
              }}
            >
              <span>{tab.label}</span>
              <span style={{ color: isSelected ? 'var(--text)' : 'var(--faint)', fontSize: '12.5px' }}>
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Right: Search, Progress, Reviewer, Audit Log, Theme Toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Search */}
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            placeholder="Search stem, ID, topic..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            style={{
              width: '200px',
              padding: '5px 8px',
              fontSize: '12.5px',
              backgroundColor: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              color: 'var(--text)',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              style={{
                position: 'absolute',
                right: '6px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                color: 'var(--muted)',
                cursor: 'pointer',
                fontSize: '11px',
              }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Thin progress text */}
        <span style={{ fontSize: '12.5px', color: 'var(--muted)' }}>
          {leftCount} left · {percentReviewed}% done
        </span>

        {/* Reviewer name text link */}
        <button
          onClick={onEditReviewer}
          title="Change reviewer name"
          style={{
            background: 'none',
            border: 'none',
            fontSize: '13px',
            color: 'var(--muted)',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          Reviewer: {reviewerName}
        </button>

        {/* Audit log text link */}
        <button
          onClick={onOpenAuditDrawer}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '13px',
            color: 'var(--muted)',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          Audit log{auditCount > 0 ? ` (${auditCount})` : ''}
        </button>

        {/* Shortcuts ? link */}
        <button
          onClick={onOpenShortcuts}
          title="Keyboard shortcuts (?)"
          style={{
            background: 'none',
            border: 'none',
            fontSize: '13px',
            color: 'var(--faint)',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          ?
        </button>

        {/* Theme toggle text link */}
        <button
          onClick={onToggleTheme}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '13px',
            color: 'var(--muted)',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          {theme === 'dark' ? 'Light' : 'Dark'}
        </button>
      </div>
    </header>
  );
};
