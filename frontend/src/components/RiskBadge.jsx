import { useState, useEffect, useCallback } from 'react';

export default function RiskBadge({ score }) {
  const getConfig = useCallback((s) => {
    if (s <= 35) return { label: 'LOW', color: '#10B981', bg: 'rgba(16, 185, 129, 0.15)', border: 'rgba(16, 185, 129, 0.3)' };
    if (s <= 70) return { label: 'MEDIUM', color: '#F59E0B', bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.3)' };
    return { label: 'HIGH', color: '#EF4444', bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.3)' };
  }, []);

  const config = getConfig(score);

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide"
      style={{
        backgroundColor: config.bg,
        border: `1px solid ${config.border}`,
        color: config.color,
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: config.color }}
      />
      {config.label}
      <span className="font-mono text-[10px] opacity-80">({score})</span>
    </span>
  );
}
