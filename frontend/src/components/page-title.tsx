"use client";

import { useEffect } from "react";

const SUFFIX = " — Auxilab EM";

/**
 * Per-page override for DYNAMIC/contextual titles only (e.g. a specific expense or person):
 *   <PageTitle title={sheet?.title ?? "Expense Details"} />
 * Static page titles use the Next.js Metadata API (segment `layout.tsx` / `metadata`),
 * which is authoritative and avoids racing with the framework's title pipeline.
 */
export function PageTitle({ title }: { title: string }) {
  useEffect(() => {
    if (title) document.title = `${title}${SUFFIX}`;
  }, [title]);
  return null;
}
