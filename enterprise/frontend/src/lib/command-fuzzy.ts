/**
 * Tiny, dependency-free fuzzy matcher used by the command palette.
 * Subsequence scoring with boosts for exact substring, word-start, and contiguous runs,
 * plus a length penalty — good enough to feel like Linear/VS Code on our dataset sizes.
 */

/** Returns a score (higher = better) or -1 when `query` is not a subsequence of `text`. */
export function fuzzyScore(query: string, text: string): number {
  if (!query) return 0;
  const q = query.toLowerCase().trim();
  const t = text.toLowerCase();
  if (!q) return 0;

  let score = 0;
  const sub = t.indexOf(q);
  if (sub >= 0) score += 60 - Math.min(sub, 30); // exact substring, earlier is better

  let qi = 0;
  let lastMatch = -2;
  let streak = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      score += 1;
      if (lastMatch === ti - 1) {
        streak += 1;
        score += streak * 2; // reward contiguous runs
      } else {
        streak = 0;
      }
      if (ti === 0 || t[ti - 1] === " " || t[ti - 1] === "-" || t[ti - 1] === "/") {
        score += 5; // word-start boost
      }
      lastMatch = ti;
      qi += 1;
    }
  }
  if (qi < q.length) return -1; // not all query chars consumed → no match
  score -= (t.length - q.length) * 0.1; // prefer shorter, tighter matches
  return score;
}

/**
 * Best score across several independent fields (label, each keyword, …). Scoring fields
 * separately prevents a query from matching as a subsequence that *spans* fields
 * (e.g. "demo" should not match across "dark mode" + "theme").
 */
export function bestFuzzyScore(query: string, fields: string[]): number {
  let best = -1;
  for (const f of fields) {
    const s = fuzzyScore(query, f);
    if (s > best) best = s;
  }
  return best;
}

export interface Segment {
  text: string;
  hit: boolean;
}

/** Split `label` into highlighted/plain segments by the subsequence matched from `query`. */
export function highlightSegments(query: string, label: string): Segment[] {
  const q = query.toLowerCase().trim();
  if (!q) return [{ text: label, hit: false }];

  const segs: Segment[] = [];
  let qi = 0;
  let buf = "";
  let bufHit = false;
  for (let i = 0; i < label.length; i++) {
    const isHit = qi < q.length && label[i].toLowerCase() === q[qi];
    if (isHit) qi += 1;
    if (i === 0) {
      buf = label[i];
      bufHit = isHit;
    } else if (isHit === bufHit) {
      buf += label[i];
    } else {
      segs.push({ text: buf, hit: bufHit });
      buf = label[i];
      bufHit = isHit;
    }
  }
  if (buf) segs.push({ text: buf, hit: bufHit });
  return segs;
}
