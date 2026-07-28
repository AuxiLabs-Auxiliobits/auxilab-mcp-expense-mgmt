"use client";

import { useEffect, useRef, useState } from "react";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";

/**
 * App-wide request indicator: a thin animated bar pinned to the top of the viewport
 * whenever ANY React Query request (fetch or mutation) is in flight. Because every
 * data call in the app goes through React Query, this gives visual feedback for 100%
 * of API interactions automatically — including background refetches that don't have
 * their own skeleton.
 *
 * Anti-flicker: only shows after a short delay so instant cache hits don't flash, and
 * stays up briefly so it never strobes between back-to-back requests.
 */
const SHOW_DELAY_MS = 150;
const MIN_VISIBLE_MS = 400;

export function GlobalProgress() {
  const active = useIsFetching() + useIsMutating();
  const [visible, setVisible] = useState(false);
  const shownAt = useRef<number>(0);

  useEffect(() => {
    let showTimer: ReturnType<typeof setTimeout> | undefined;
    let hideTimer: ReturnType<typeof setTimeout> | undefined;
    if (active > 0) {
      showTimer = setTimeout(() => {
        shownAt.current = Date.now();
        setVisible(true);
      }, SHOW_DELAY_MS);
    } else {
      const elapsed = Date.now() - shownAt.current;
      const wait = Math.max(0, MIN_VISIBLE_MS - elapsed);
      hideTimer = setTimeout(() => setVisible(false), wait);
    }
    return () => {
      if (showTimer) clearTimeout(showTimer);
      if (hideTimer) clearTimeout(hideTimer);
    };
  }, [active]);

  if (!visible) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Loading"
      className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-0.5 overflow-hidden bg-secondary/20"
    >
      <div className="global-progress-bar h-full w-1/3 bg-secondary" />
    </div>
  );
}
