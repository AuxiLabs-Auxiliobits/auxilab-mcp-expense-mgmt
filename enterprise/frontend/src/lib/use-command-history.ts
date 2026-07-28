/**
 * Lightweight "smart suggestions" backing store (Phase 6): tracks how often and how
 * recently each command is run, in localStorage, to surface a Recent list and prioritize
 * frequently-used commands. Per-browser, no PII, fails silently when storage is unavailable.
 */

const KEY = "auxilab.command.history.v1";

interface Entry {
  count: number;
  last: number;
}
type History = Record<string, Entry>;

export function loadHistory(): History {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}") as History;
  } catch {
    return {};
  }
}

export function recordCommand(id: string): void {
  try {
    const h = loadHistory();
    h[id] = { count: (h[id]?.count ?? 0) + 1, last: Date.now() };
    localStorage.setItem(KEY, JSON.stringify(h));
  } catch {
    /* storage unavailable (private mode) — suggestions just won't persist */
  }
}

/**
 * Rank command ids by a recency + frequency score. Returns the top `limit` ids that still
 * exist in `validIds` (so stale/role-removed commands are dropped).
 */
export function rankRecent(validIds: Set<string>, limit = 5): string[] {
  const h = loadHistory();
  const now = Date.now();
  return Object.entries(h)
    .filter(([id]) => validIds.has(id))
    .map(([id, e]) => {
      const ageDays = (now - e.last) / 86_400_000;
      const recency = Math.max(0, 14 - ageDays); // decays over ~2 weeks
      return { id, score: e.count * 2 + recency };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((x) => x.id);
}
